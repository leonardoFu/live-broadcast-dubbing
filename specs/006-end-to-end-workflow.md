# End-to-End Workflow (Ingest → Process → Republish)

This doc connects `specs/001-spec.md`, `specs/002-mediamtx.md`, and `specs/003-gstreamer-stream-worker.md` into a single, runnable workflow, with a clear path from “MediaMTX only” to “full Gemini Live dubbing”.

---

## 1. One-line flow

1) Publisher pushes RTMP to MediaMTX (`live/<streamId>/in`)  
2) MediaMTX emits `runOnReady` → hook receiver (`stream-orchestration`)  
3) Orchestrator starts a per-stream worker (`stream-worker`)  
4) Worker pulls RTSP from MediaMTX (`live/<streamId>/in`), processes audio, pushes RTMP to MediaMTX (`live/<streamId>/out`)  
5) Orchestrator starts an egress forwarder that pulls `live/<streamId>/out` and pushes to the 3rd-party RTMP destination (optional)

---

## 2. Interfaces (quick reference)

- Ingest (external): `rtmp://<host>:1935/live/<streamId>/in`
- Worker input (internal): `rtsp://mediamtx:8554/live/<streamId>/in` (use RTSP-over-TCP)
- Worker output (internal): `rtmp://mediamtx:1935/live/<streamId>/out`
- Control API: `http://<host>:9997/v3/paths/list`
- Metrics: `http://<host>:9998/metrics`
- Playback (recordings): disabled in v0 (recording is off)

---

## 3. Recommended local dev workflow (milestones)

### Milestone A — MediaMTX baseline (ingest works)

1) Start MediaMTX (see `specs/002-mediamtx.md`; repo-local: `make dev`)
2) Publish a test stream to `rtmp://localhost:1935/live/test-stream/in`
3) Verify you can read it back:

```sh
ffplay rtsp://localhost:8554/live/test-stream/in
```

Success criteria: stable playback; `GET /v3/paths/get/live%2Ftest-stream%2Fin` shows the path ready.

### Milestone B — “Bypass worker” (republish works)

Use the GStreamer bypass pipeline from `specs/002-mediamtx.md` to republish `live/test-stream/in` → `live/test-stream/out` without any audio processing.

Verify:

```sh
ffplay rtmp://localhost:1935/live/test-stream/out
```

Success criteria: `live/test-stream/out` plays; no re-encode assumptions; minimal added latency.

### Milestone C — Real worker, no Gemini (remux + sync)

Run the `apps/stream-worker/` in “bypass mode” as defined in `specs/003-gstreamer-stream-worker.md`:
- pull `rtsp://mediamtx:8554/live/test-stream/in`
- publish `rtmp://mediamtx:1935/live/test-stream/out`

Success criteria: same as Milestone B, but via the worker process, with worker logs/metrics present.

### Milestone D — Worker + mock Gemini Live (deterministic)

Enable the mock Gemini Live backend (tone/pass-through) from `specs/003-gstreamer-stream-worker.md` to validate:
- fragment chunking
- backpressure / max in-flight
- A/V sync correction strategy

Success criteria: audible deterministic tone (or pass-through); bounded `worker_av_sync_delta_ms`.

### Milestone E — Worker + Gemini Live (full pipeline)

Swap the mock backend for the Gemini Live streaming session (see `specs/004-sts-pipeline-design.md`).

Success criteria: dubbed speech is present; background remains; fallbacks behave under induced Gemini latency/failure.

---

## 4. Orchestration workflow (hooks → start/stop workers)

MediaMTX triggers orchestration on `live/<streamId>/in` state changes (see `specs/002-mediamtx.md`):
- `runOnReady` → start (or ensure running) a worker for the stream
- `runOnNotReady` → stop worker (or idle it for a grace period)

Minimum behavior for v1:
- derive `streamId` from the ingest path (`live/<streamId>/in`)
- map `streamId` → exactly one worker instance
- emit logs with: `path`, `streamId`, `sourceId`, and a request id

---

## 5. Forwarding to the final RTMP destination

v0 decision (see `specs/002-mediamtx.md`): forwarding is handled by an **egress forwarder** started by `stream-orchestration`.

- Forwarder input: `rtsp://mediamtx:8554/live/<streamId>/out` (codec copy)
- Forwarder output: configured 3rd-party RTMP URL(s)

Local workflow: keep the destination unset/disabled until the worker pipeline is stable.

---

## 6. Debug loop (when something breaks)

- “Nothing plays”: check MediaMTX `GET /v3/paths/list` and container logs.
- “Worker can’t pull RTSP”: verify worker network can reach `mediamtx:8554`, and force TCP (`protocols=tcp`).
- “A/V drift”: inspect the worker A/V sync gauge and confirm `appsrc` timestamps are monotonic.
- “Dub gaps”: look at `worker_inflight_fragments`, Gemini RTT histogram, and fallback counters.
