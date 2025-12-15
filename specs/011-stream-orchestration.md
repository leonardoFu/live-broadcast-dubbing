# Stream Orchestration Spec (MediaMTX Hooks → Worker + Egress Lifecycle)

This spec defines the **stream orchestration** component referenced by:
- `specs/001-spec.md` (high-level architecture)
- `specs/002-mediamtx.md` (MediaMTX hooks + contract)
- `specs/003-gstreamer-stream-worker.md` (worker runtime expectations)

The orchestrator is responsible for turning **MediaMTX “stream ready/unready” events** into a reliable lifecycle for:
1) a per-stream **stream worker** that produces `live/<streamId>/out`, and
2) an optional per-stream **egress forwarder** that pushes to a 3rd-party RTMP destination.

---

## 1. Goal

Provide a deterministic, observable, and safe way to:
- Start/stop exactly one worker per ingest stream (`live/<streamId>/in`)
- Optionally start/stop an egress forwarder for the processed stream (`live/<streamId>/out`)
- Handle duplicate/out-of-order events without creating multiple workers or flapping
- Keep failures isolated per stream and recover automatically where possible

---

## 2. Non-Goals

- Implementing media processing (belongs to the worker; see `specs/003-gstreamer-stream-worker.md`)
- Designing the STS pipeline (see `specs/004-sts-pipeline-design.md`)
- Choosing a production platform for process/container management (Kubernetes/ECS/systemd/etc.)
- Managing end-user entitlements/billing (this spec focuses on internal orchestration)

---

## 3. Concepts & Key Entities

- **StreamId**: Logical identifier extracted from MediaMTX path `live/<streamId>/in`.
- **Stream Session (runId)**: Unique identifier for one “live session” of a stream from first ready → final stop.
- **Desired State**: What the system should be doing for a stream (e.g., worker running, forwarding enabled).
- **Actual State**: What is currently running (worker process/container status, forwarder status).
- **Worker Lease**: A mechanism ensuring “at most one” active worker per `streamId` at a time.
- **Egress Target**: A configured RTMP destination (or disabled).

---

## 4. External Interactions (Component Contracts)

### 4.1 MediaMTX → Orchestrator (hook events)

The orchestrator receives two event types for ingest paths `live/<streamId>/in`:
- **Ready**: a publisher has started sending media
- **NotReady**: the publisher has stopped (or MediaMTX considers the stream unavailable)

Event delivery characteristics (assumptions aligned with typical hook systems):
- At-least-once delivery (duplicates possible)
- Out-of-order delivery possible during restarts/network issues
- Bursty delivery during churn (connect/disconnect loops)

Required orchestrator behavior:
- Idempotent handling of duplicates
- Safe handling of “NotReady after Ready” and “Ready after NotReady” races
- Fast response (do not block MediaMTX hooks on long operations)

### 4.2 Orchestrator → Stream Worker (start/stop)

The orchestrator starts a per-stream worker with a minimal, explicit configuration:
- `streamId`
- input read URL (pull from MediaMTX ingest path)
- output publish URL (push to MediaMTX processed path)
- stream-session identifiers and logging correlation (e.g., `runId`)

Worker expectations:
- If the worker exits non-zero, orchestration treats it as a failure and may restart subject to backoff.
- The worker is responsible for producing `live/<streamId>/out` when healthy.

### 4.3 Orchestrator → Egress Forwarder (start/stop; optional)

If enabled, the orchestrator starts an egress forwarder per stream with:
- input read URL for processed output (`live/<streamId>/out`)
- one configured destination RTMP URL (or a small list of destinations)
- stream-session identifiers for correlation

Forwarder expectations:
- If destination is unavailable, the forwarder retries with backoff and exposes status via logs/metrics.
- Orchestration can stop the forwarder independently of the worker.

---

## 5. Orchestrator API (Internal)

This spec uses the internal HTTP-style contract described in `specs/002-mediamtx.md`.

### 5.1 Receive “ready”

`POST /v1/mediamtx/events/ready`

Example payload:
```json
{
  "path": "live/abc/in",
  "query": "lang=es",
  "sourceType": "rtmp",
  "sourceId": "1"
}
```

### 5.2 Receive “not-ready”

`POST /v1/mediamtx/events/not-ready`

Example payload:
```json
{
  "path": "live/abc/in",
  "query": "lang=es",
  "sourceType": "rtmp",
  "sourceId": "1"
}
```

### 5.3 Response behavior (hook safety)

For both endpoints:
- Respond successfully if the event is accepted for processing (even if the worker/forwarder start happens asynchronously).
- Include a correlation identifier in the response and logs to track event handling.
- If the request is invalid (e.g., path not under `live/*/in`), respond with a clear client error and log a structured reason.

---

## 6. Stream Lifecycle (State Machine)

### 6.1 Derived identifiers

From the incoming event:
- `streamId` is extracted from `path` when it matches `live/<streamId>/in`.
- `runId` is created the first time a stream transitions into a “running” session.

### 6.2 Desired-state model

The orchestrator maintains (conceptually) these desired flags per stream:
- `wantWorker`: true when the ingest is considered live
- `wantForwarder`: true when a destination is configured and forwarding is enabled for this session

### 6.3 State transitions

Minimum state machine (per stream):

1) **Idle**
- No worker, no forwarder

2) **Starting**
- Worker start initiated (lease acquired or being acquired)
- Optional: forwarder start blocked until output is expected to exist

3) **Running**
- Worker is running (and expected to be publishing `live/<streamId>/out`)
- Forwarder may be running (if enabled)

4) **Stopping**
- Stop initiated due to NotReady, operator action, or policy

5) **Stopped**
- Graceful shutdown completed; transitions back to Idle

Rules:
- Duplicate Ready while in Starting/Running MUST NOT start another worker.
- NotReady while in Idle MUST be a no-op.
- NotReady while in Starting/Running SHOULD stop worker and forwarder after a configurable grace period to tolerate brief disconnects.

---

## 7. Policies (Idempotency, Backoff, and Flap Control)

### 7.1 Idempotency

The orchestrator MUST enforce **at-most-one** worker per `streamId` using a lease/lock concept.

Idempotency requirements:
- Multiple Ready events for the same stream session do not create multiple workers.
- Multiple NotReady events do not cause errors and do not break future Ready handling.
- If the orchestrator crashes and restarts, it can reconcile desired vs actual state without duplicating workers.

### 7.2 Backoff and restart limits

When the worker or forwarder fails repeatedly:
- Apply exponential backoff per stream (not global).
- Cap retries over a time window (to prevent infinite crash loops).
- Emit a clear “degraded” status for the stream session (logs/metrics).

### 7.3 Disconnect grace period

To reduce flapping from brief publisher reconnects:
- On NotReady, delay stop by a short grace period.
- If a new Ready arrives during the grace period, cancel the stop and continue the same session when safe.

---

## 8. Routing & Configuration Model (Per Stream)

Orchestration needs a mapping from `streamId` to operational settings. Minimum configuration:
- Whether forwarding is enabled for this stream
- Destination RTMP URL (when enabled)
- Optional per-stream processing preferences passed to the worker (e.g., target language)

Configuration sources (non-binding options; choose one at implementation time):
- Embedded in the ingest query string (e.g., `?lang=es`)
- Looked up by `streamId` in a configuration store
- Provided by an operator action before the stream starts

Policy requirements:
- Invalid/unsupported configuration must not break ingest; it must fail safely (e.g., forwarding disabled, worker uses defaults).
- Secrets (e.g., stream keys) must be handled as sensitive and must not be logged.

---

## 9. Failure Handling (Operational Expectations)

### 9.1 MediaMTX hook delivery failures

If MediaMTX cannot deliver hook events (e.g., receiver down):
- The system may fail to start workers for new ingests.
- The orchestrator should provide a way to diagnose missed events (e.g., via logs and/or reconciling against MediaMTX control state).

### 9.2 Worker start failures

If worker start fails:
- Retry with backoff.
- If failures persist beyond policy limits, mark the stream session as degraded and stop retrying until a new session starts or an operator intervenes.

### 9.3 Forwarder failures

If destination is invalid/unreachable:
- Continue producing `live/<streamId>/out` (worker can keep running).
- Retry forwarder with backoff and surface status clearly.

### 9.4 Safe fallback principle

Orchestration MUST prioritize:
1) avoiding runaway resource creation (duplicate workers/forwarders),
2) keeping processed output available internally (`live/<streamId>/out`) when possible,
3) failing forwarding independently without taking down the worker unless policy requires it.

---

## 10. Observability (Minimum)

Orchestrator logs MUST include, at minimum:
- `streamId`, `runId`, event type (ready/not-ready), and `sourceId` (when provided)
- State transitions (Idle/Starting/Running/Stopping/Stopped)
- Worker and forwarder lifecycle actions (start/stop/restart) with outcomes
- Backoff decisions and “degraded” status transitions

Recommended metrics (names are illustrative; exact names are non-binding):
- Active streams (workers running)
- Active forwarders
- Start/stop/restart counts per stream
- Failure counts per stream and a “degraded” indicator

---

## 11. Example End-to-End Flow (Nominal)

```text
1) Publisher starts sending RTMP → MediaMTX path live/demo/in
2) MediaMTX sends Ready hook → orchestrator
3) Orchestrator acquires worker lease for streamId=demo, creates runId
4) Orchestrator starts worker (pull live/demo/in, push live/demo/out)
5) If configured, orchestrator starts forwarder (pull live/demo/out, push destination RTMP)
6) Publisher stops → MediaMTX sends NotReady hook
7) Orchestrator waits grace period, then stops forwarder and worker
8) Orchestrator releases lease and closes the run
```

---

## 12. Success Criteria

- A single ingest stream triggers at most one worker instance for its `streamId` during a session, even under duplicate/out-of-order hook events.
- Brief disconnect/reconnect loops do not cause repeated worker churn beyond configured policy limits.
- Operators can identify stream session state and failure reasons using orchestrator logs/metrics without inspecting worker internals.
- Forwarding failures do not prevent internal processed output (`live/<streamId>/out`) from being produced when the worker is healthy.

