# 012 — Egress Forwarder (Per-Stream Process)

## Summary

The **egress forwarder** is a separate per-stream process managed by `stream-orchestration`. It **pulls** a stream from MediaMTX via RTSP (`/live/<streamId>/out`) and (optionally) **pushes** it to a third-party RTMP destination using **codec copy** (no re-encode).

Forwarding failures are isolated by design: the forwarder has no coupling to the worker pipeline beyond reading from MediaMTX, and it must never stall or crash the worker.

## Goals

- Forward a single stream (`<streamId>`) from MediaMTX RTSP to one third-party RTMP destination.
- Use codec copy for audio/video to minimize latency and compute.
- Be managed as a per-stream process by `stream-orchestration` (start/stop, restarts, limits).
- Fail safely: forwarding issues must not impact ingest, worker processing, or publication to `/out`.
- Provide operational visibility via structured logs and lightweight metrics (no frame-by-frame logging).

## Non-goals (v0)

- Multiple RTMP destinations per stream (allow-list / fanout comes later).
- Transcoding, watermarking, overlays, audio mixing, loudness normalization.
- Automatic destination discovery or UI-driven destination management.
- Auth hardening (dev is unauthenticated; ops/security is deferred).
- Recording (MediaMTX recording remains disabled in v0).

## Stream Identity & Naming

- Stream identity is path-based:
  - Input published by worker: `live/<streamId>/out`
  - (For context) ingest: `live/<streamId>/in`

`streamId` is opaque to the forwarder (treated as a string), and is only used for URL construction and log/metric tags.

## Architecture & Process Model

- **One forwarder process per stream**.
- The forwarder is **stateless** and can be restarted at any time; correctness is “best effort forwarding”.
- The forwarder reads from MediaMTX, which acts as the decoupling buffer between worker and forwarder.

Implementation detail (non-normative): use GStreamer or FFmpeg with stream copy; select one for v0 and keep the other as future option if needed.

## Interfaces

### Input (pull)

- RTSP input URL (fixed pattern):
  - `rtsp://mediamtx:8554/live/<streamId>/out`

Constraints:
- Must be **codec copy**: do not re-encode.
- If the input is not available, the forwarder retries for a bounded grace period before exiting (see Lifecycle).

### Output (push)

- RTMP destination URL (configured per stream):
  - `rtmp://<host>/<app>/<streamKeyOrPath>`

Notes:
- Destination can be disabled (especially in dev) without preventing the forwarder from starting (it should no-op and exit cleanly, or remain idle based on config; see Configuration).
- v0 supports exactly **one** destination per stream.

### Orchestrator Control Plane

`stream-orchestration` is responsible for:
- deciding whether egress is enabled for a stream,
- providing destination config to the forwarder,
- spawning and supervising the per-stream forwarder process.

The forwarder does not receive direct media data from `stream-orchestration`; only configuration and lifecycle commands (start/stop).

## Configuration

All configuration is provided by `stream-orchestration` at process start (env vars or CLI args). v0 uses a single mechanism consistently; avoid split-brain config sources.

### Required

- `STREAM_ID` (string): `<streamId>`
- `MEDIAMTX_RTSP_BASE` (string): default `rtsp://mediamtx:8554`
- `DEST_RTMP_URL` (string): destination RTMP URL (required only when enabled)

### Feature flags

- `EGRESS_ENABLED` (bool): default `false` in dev; default `true` in non-dev deployments
  - If `false`: forwarder should exit with code `0` after logging a single “disabled” event (no retries).

### Timing / retry

- `INPUT_NOT_READY_GRACE_SECONDS` (int): default `30`
  - Time budget to wait for RTSP `/out` to become available before exiting as “not ready”.
- `RETRY_BASE_DELAY_MS` (int): default `500`
- `RETRY_MAX_DELAY_MS` (int): default `10_000`
- `RETRY_JITTER_MS` (int): default `250`
- `RETRY_MAX_ATTEMPTS` (int): default `0` (meaning “unbounded while enabled”; bounded by restart limits)

### Restart limits (enforced by orchestrator)

These are applied by `stream-orchestration` (supervisor), not by the forwarder itself:

- `RESTART_MAX_PER_10_MIN` (int): default `6`
- `RESTART_COOLDOWN_SECONDS` (int): default `60` once the limit is exceeded

### Identity

- `RUN_ID` (string): required; stable for a given orchestrated “run” of the stream
- `INSTANCE_ID` (string): required; unique per forwarder process instance (regenerated on each spawn)

### Logging

- `LOG_LEVEL` (string): default `info`
- `LOG_DIR` (string): default `./logs` (dev: persisted to filesystem)
  - Logs are appended/rotated by the runtime environment or a simple file rotation policy (implementation detail).

## Lifecycle

### Start

1. Validate config.
2. If `EGRESS_ENABLED=false`, log `egress.disabled` and exit `0`.
3. Construct input URL: `rtsp://mediamtx:8554/live/<streamId>/out`.
4. Attempt to connect and start forwarding with codec copy.

### Stop

Stop is initiated by `stream-orchestration` via process termination (SIGTERM) or equivalent:

- Forwarder performs a graceful shutdown:
  - stop pushing to destination,
  - stop pulling from RTSP,
  - exit within a short deadline (e.g., 5s) to avoid hanging orchestration.

### Retry / Backoff

The forwarder retries on transient failures:

- RTSP connect/read errors
- RTMP connect/write errors
- Destination resets / disconnects

Backoff policy:
- exponential backoff from `RETRY_BASE_DELAY_MS` up to `RETRY_MAX_DELAY_MS`
- add jitter up to `RETRY_JITTER_MS`

Not-ready behavior:
- If RTSP `/out` is unavailable, keep retrying until `INPUT_NOT_READY_GRACE_SECONDS` elapses.
- When grace elapses, exit with a distinct non-zero exit code indicating “input not ready” (see Failure Modes).
- Orchestrator may choose to stop trying entirely or restart later based on stream state.

### Restart Policy (Orchestrator)

`stream-orchestration` supervises the forwarder and applies limits:

- If the forwarder exits unexpectedly, restart it until `RESTART_MAX_PER_10_MIN` is reached.
- After reaching the limit, stop restarting for `RESTART_COOLDOWN_SECONDS`, then allow restarts again if the stream is still configured as enabled.

## Failure Isolation & Modes

### Isolation requirements

- Forwarder failures must not:
  - block the worker pipeline,
  - modify MediaMTX `/out`,
  - cause `stream-orchestration` to crash,
  - cascade to other streams’ forwarders.

### Failure modes

Forwarder exit codes are used by `stream-orchestration` for classification and policy:

- `0`: clean exit (disabled; graceful stop requested)
- `10`: configuration error (missing/invalid `DEST_RTMP_URL` while enabled, invalid URL formats)
- `20`: input not ready (RTSP `/out` not available within grace)
- `30`: destination auth/permission error (e.g., RTMP “publish denied”)
- `40`: transient forwarding failure (network disconnects, timeouts, IO errors)
- `50`: internal error (unexpected exception, pipeline build failure)

Notes:
- “Auth/permission error” is treated as non-transient unless proven otherwise; orchestrator may stop restarts sooner or apply longer cooldown.
- “Transient” errors may be retried aggressively within restart limits.

## Observability

### Logging

Structured logs (JSON preferred) written to filesystem in dev via `LOG_DIR`.

Log events (minimum set), emitted per fragment/connection state change (not per frame):

- `egress.starting`: process boot and config summary (redact destination secrets; log only host/app, not stream key)
- `egress.disabled`: egress disabled for the stream
- `egress.input.connecting`: RTSP connect attempt
- `egress.input.connected`: RTSP connected; include detected codec info
- `egress.output.connecting`: RTMP connect attempt
- `egress.output.connected`: RTMP connected
- `egress.forwarding.started`: forwarding active
- `egress.forwarding.stopped`: forwarding ended; include reason and duration
- `egress.retry.scheduled`: includes error class and next delay
- `egress.exit`: exit code and final reason

Common log fields:

- `ts` (RFC3339)
- `level` (`debug|info|warn|error`)
- `service` = `egress-forwarder`
- `streamId`
- `runId`
- `instanceId`
- `event`
- `attempt` (integer, for retries)
- `inputUrl` (RTSP, safe)
- `destHost` / `destApp` (safe); do not log full `DEST_RTMP_URL` if it contains secrets
- `error.kind` (e.g., `rtsp_connect`, `rtmp_publish_denied`, `io_timeout`)
- `error.message` (truncated)

### Metrics

Expose metrics in a lightweight, pullable form (implementation detail: stdout scrape, sidecar, or embedded HTTP) without requiring network access in dev. If an HTTP endpoint is used, bind to localhost only.

Minimum metrics (names are illustrative):

- `egress_forwarder_up{streamId,runId,instanceId}`: `1` while process is running
- `egress_forwarder_forwarding{streamId,runId,instanceId}`: `1` while actively forwarding
- `egress_forwarder_restarts_total{streamId,runId}`: increments on each new `instanceId`
- `egress_forwarder_retry_total{streamId,runId,error_kind}`: increments per retry scheduling
- `egress_forwarder_connect_latency_ms{streamId,runId,stage=rtsp|rtmp}`: connect durations
- `egress_forwarder_bytes_out_total{streamId,runId}`: bytes successfully written to destination (if available)
- `egress_forwarder_last_error{streamId,runId}`: string/label reference or an error code (avoid high-cardinality messages)

## Example Pipelines (Non-normative)

FFmpeg (codec copy):

```bash
ffmpeg -rtsp_transport tcp \
  -i "rtsp://mediamtx:8554/live/${STREAM_ID}/out" \
  -c copy -f flv "${DEST_RTMP_URL}"
```

GStreamer (codec copy):

```bash
gst-launch-1.0 -e \
  rtspsrc location="rtsp://mediamtx:8554/live/${STREAM_ID}/out" protocols=tcp \
  ! rtspjitterbuffer \
  ! queue \
  ! flvmux streamable=true \
  ! rtmpsink location="${DEST_RTMP_URL}"
```

## Acceptance Criteria

- With `EGRESS_ENABLED=false`, the forwarder exits `0` and emits `egress.disabled` once.
- With `EGRESS_ENABLED=true` and a valid destination, the forwarder pulls from `rtsp://mediamtx:8554/live/<streamId>/out` and pushes to the configured RTMP destination using codec copy.
- If the RTSP `/out` stream is not available, the forwarder retries for up to `INPUT_NOT_READY_GRACE_SECONDS` and then exits with code `20` without impacting the worker.
- If the RTMP destination is unreachable, the forwarder retries with exponential backoff and jitter; repeated failures do not crash `stream-orchestration` and do not stall other streams.
- Restart limits are enforced by `stream-orchestration` (max restarts per 10 minutes and cooldown), and the forwarder’s `instanceId` changes on each restart while `runId` stays stable.
- Logs are persisted to filesystem in dev, are structured, do not include per-frame spam, and include `streamId`, `runId`, and `instanceId` on all events.

