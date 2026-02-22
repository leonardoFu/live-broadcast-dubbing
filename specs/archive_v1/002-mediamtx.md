# MediaMTX Integration Spec (RTMP Ingest → Worker Trigger → Republish)

This spec defines how to integrate **MediaMTX** as the ingress/egress “media router” for the pipeline described in `specs/001-spec.md`, with a focus on:
- RTMP ingest as the *entry point* that triggers downstream workers
- observability + troubleshooting
- operable local dev workflow (fast restart, easy testing)
- persisting intermediate media artifacts (recordings) for lookup

---

## 1. Goal

Operate a MediaMTX instance that:
- Accepts inbound **RTMP publish** to an ingest path (entry point)
- Emits **deterministic events** when a stream becomes ready/unavailable (to start/stop workers)
- Exposes **Control API** + **Prometheus metrics** for observability
- Optionally exposes **Playback HTTP server** to download recorded segments for debugging
- Optionally records streams to disk with clear retention controls (**v0 decision: recording disabled**)

---

## 2. Non-Goals

- Implementing the unified worker runtime (see `specs/003-gstreamer-stream-worker.md`)
- Choosing a production deployment platform (K8s/ECS/etc.) beyond configuration requirements
- Designing end-user playback UX (only the MediaMTX playback endpoint)

---

## 3. Interfaces (Ports, URLs, Paths)

### 3.1 External publish (entry point)

- **RTMP publish URL (ingest):** `rtmp://<mediamtx-host>:1935/live/<streamId>/in`

This is the entry point that triggers downstream workers (via hooks).

### 3.2 Internal read/pull (worker input)

Stream worker pulls via RTSP (recommended in `specs/001-spec.md`).

GStreamer note:
- Prefer **RTSP over TCP** for stability (`rtspsrc protocols=tcp`), especially in Docker/CI environments where UDP loss/jitter is common.
- **RTSP read URL:** `rtsp://mediamtx:8554/live/<streamId>/in`

### 3.3 Internal publish (worker output)

Stream worker publishes processed output back to MediaMTX:
- **RTMP publish URL (processed):** `rtmp://mediamtx:1935/live/<streamId>/out`

### 3.4 Observability / control

- **Control API:** `http://mediamtx:9997` (endpoints like `/v3/paths/list`)
- **Prometheus metrics:** `http://mediamtx:9998/metrics`
- **Playback (recordings):** `http://mediamtx:9996` (endpoints like `/list` and `/get`)
- **pprof (optional):** `http://mediamtx:9999/debug/pprof/`

---

## 4. Triggering Workers From RTMP Ingest (Hooks)

MediaMTX supports hooks that run external commands when a stream becomes ready/unavailable.

### 4.1 Hook events to use

For ingest paths `live/<streamId>/in`:
- `runOnReady`: trigger worker start / ensure worker is running
- `runOnNotReady`: trigger worker stop / cleanup

Optional:
- `runOnRead` / `runOnUnread`: track downstream consumers (debugging)
- `runOnRecordSegmentComplete`: notify when a recording segment is finalized (indexing / lookup)

### 4.2 Required “hook receiver” service

Do **not** embed orchestration logic inside the MediaMTX container. Instead, implement a small internal HTTP service named **`stream-orchestration`** that:
- listens on an internal port (example: `http://stream-orchestration:8080`)
- receives hook events from MediaMTX
- starts/stops workers (or enqueues jobs) based on stream identity and policy

**Contract (confirmed):**

`POST /v1/mediamtx/events/ready`
```json
{
  "path": "live/abc/in",
  "query": "lang=es",
  "sourceType": "rtmp",
  "sourceId": "1"
}
```

`POST /v1/mediamtx/events/not-ready`
```json
{
  "path": "live/abc/in",
  "query": "lang=es",
  "sourceType": "rtmp",
  "sourceId": "1"
}
```

Notes:
- MediaMTX provides hook inputs via environment variables (e.g. `MTX_PATH`, `MTX_QUERY`, `MTX_SOURCE_TYPE`, `MTX_SOURCE_ID`).
- Since `MTX_QUERY` can contain characters that are painful to quote safely, the hook command should call a **small wrapper binary/script** (checked into the repo) that:
  - reads env vars
  - constructs JSON safely
  - sends the HTTP request
  - exits non-zero on failure (so failures show up in MediaMTX logs)

---

## 5. Recording “Intermediate Results” (Artifacts)

MediaMTX can record streams to disk in **fMP4** or **MPEG-TS** and expose them via the Playback server.

### 5.1 What to record

Options (choose explicitly):

0) Record **nothing** (default; **chosen for v0**).
1) Record **ingest only** (`live/<streamId>/in`) for “what came in” debugging.
2) Record **processed only** (`live/<streamId>/out`) for “what we produced” validation.
3) Record **both** (higher disk usage; best for investigations).

### 5.2 Recording configuration (template)

```yml
pathDefaults:
  record: yes
  recordPath: ./recordings/%path/%Y-%m-%d_%H-%M-%S-%f
  recordFormat: fmp4
  recordPartDuration: 1s
  recordMaxPartSize: 50M
  recordSegmentDuration: 1h
  recordDeleteAfter: 1d
```

### 5.3 Segment indexing / lookup

Use `runOnRecordSegmentComplete` to notify an indexing service so segments are discoverable without scanning the filesystem.

Inputs available to the hook:
- `MTX_PATH`
- `MTX_SEGMENT_PATH`
- `MTX_SEGMENT_DURATION`

---

## 6. Observability & Troubleshooting

### 6.1 Logs

Configuration:
- `logDestinations: [stdout]` for containerized environments
- `logLevel: info` by default; switch to `debug` when troubleshooting

Operational expectations:
- Hook failures must log clearly (non-zero exit from wrapper command)
- Include correlation fields in hook receiver logs:
  - `path`, derived `streamId` (from path or query), `sourceId`, and a request id

### 6.2 Control API (debugging)

Enable `api: yes` and use these endpoints:

```sh
curl http://mediamtx:9997/v3/paths/list
curl http://mediamtx:9997/v3/rtmpconns/list
```

If you need a single path:

```sh
# name must be URL-encoded when it contains slashes
curl "http://mediamtx:9997/v3/paths/get/live%2Fin"
```

### 6.3 Metrics (Prometheus)

Enable `metrics: yes` and scrape:

```sh
curl http://mediamtx:9998/metrics
curl "http://mediamtx:9998/metrics?type=paths&path=live/<streamId>/in"
```

Baseline alerts (examples; finalize later):
- ingest path not ready while expected to be live
- high bytes received but 0 readers (possible worker outage)
- repeated connect/disconnect churn

### 6.4 Performance profiling (optional)

Enable `pprof: yes` and use `go tool pprof` against `:9999` when CPU/RAM issues occur.

---

## 7. MediaMTX Configuration (Minimal, Operable)

This is a *template* that must be finalized once Open Questions are answered.

For a working local-dev example based on this template, see:
- `deploy/mediamtx/mediamtx.yml`
- `deploy/docker-compose.yml`

```yml
logLevel: info
logDestinations: [stdout]

rtmp: yes
rtmpAddress: :1935

rtsp: yes
# keep TCP enabled for GStreamer (default includes tcp already)
# optionally restrict to TCP-only in NAT/firewall environments:
# rtspTransports: [tcp]
rtspAddress: :8554

api: yes
apiAddress: :9997

metrics: yes
metricsAddress: :9998

playback: yes
playbackAddress: :9996

# pprof: yes
# pprofAddress: :9999

pathDefaults:
  # v0 decision: treat all paths as publisher paths; orchestrator decides what
  # to do based on suffix (`.../in` vs `.../out`).
  source: publisher
  runOnReady: /hooks/mtx-hook ready
  runOnNotReady: /hooks/mtx-hook not-ready

  # recording defaults (override per-path if needed)
  record: no
  recordPath: ./recordings/%path/%Y-%m-%d_%H-%M-%S-%f
  recordFormat: fmp4
  recordPartDuration: 1s
  recordMaxPartSize: 50M
  recordSegmentDuration: 1h
  recordDeleteAfter: 1d

# Using path naming, we treat these as conventions (not an allowlist):
# - Ingest:    live/<streamId>/in
# - Processed: live/<streamId>/out
#
# If you want to restrict allowed paths, explicitly enumerate them here.
paths: {}
```

Notes:
- `/hooks/mtx-hook` is a repo-provided wrapper (see `deploy/mediamtx/hooks/mtx-hook`) included in the container image or mounted into it.
- When using forwarding with FFmpeg, use `runOnReadyRestart: yes` so forwarding restarts if FFmpeg exits.

---

## 8. Local Dev Workflow (Fast Test + Restart)

### 8.1 Recommended dev setup

Add a `docker compose` service for MediaMTX that:
- mounts `mediamtx.yml` so config edits are a fast restart away
- mounts a writable recordings directory
- exposes ports for RTMP/RTSP/API/metrics/playback

This repo includes a minimal, runnable setup:

```sh
make dev
```

Files:
- Compose: `deploy/docker-compose.yml`
- MediaMTX config: `deploy/mediamtx/mediamtx.yml`
- Hook wrapper: `deploy/mediamtx/hooks/mtx-hook` (sends JSON to the dev hook receiver)
- Dev hook receiver: `deploy/orchestrator/server.py` (logs events; does not start workers yet)

### 8.2 Test publish commands

RTMP publish using FFmpeg test sources:

```sh
ffmpeg -re \
  -f lavfi -i testsrc=size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=440:sample_rate=44100 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac -ar 44100 \
  -f flv rtmp://localhost:1935/live/test-stream/in
```

RTMP publish using GStreamer test sources (H.264 + AAC in FLV, low-latency oriented):

```sh
gst-launch-1.0 -e \
  videotestsrc is-live=true pattern=smpte ! video/x-raw,width=1280,height=720,framerate=30/1 \
    ! x264enc tune=zerolatency speed-preset=veryfast key-int-max=60 \
    ! h264parse config-interval=-1 ! queue ! mux. \
  audiotestsrc is-live=true wave=sine freq=440 ! audio/x-raw,rate=44100,channels=2 \
    ! audioconvert ! audioresample ! voaacenc bitrate=128000 \
    ! aacparse ! queue ! mux. \
  flvmux name=mux streamable=true \
    ! rtmpsink location="rtmp://localhost:1935/live/test-stream/in"
```

Read back (quick sanity):

```sh
ffplay rtmp://localhost:1935/live/test-stream/in
ffplay rtsp://localhost:8554/live/test-stream/in
```

Read back with GStreamer (RTSP over TCP):

```sh
gst-launch-1.0 -v \
  rtspsrc location="rtsp://localhost:8554/live/test-stream/in" protocols=tcp latency=200 name=src \
    src. ! queue ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink \
    src. ! queue ! rtpmp4gdepay ! aacparse ! avdec_aac ! audioconvert ! audioresample ! autoaudiosink
```

Bypass “worker” republish with GStreamer (remux H.264/AAC from RTSP → RTMP `live/<streamId>/out`):

```sh
gst-launch-1.0 -e \
  rtspsrc location="rtsp://localhost:8554/live/test-stream/in" protocols=tcp latency=200 name=src \
    src. ! queue ! rtph264depay ! h264parse ! queue ! mux. \
    src. ! queue ! rtpmp4gdepay ! aacparse ! queue ! mux. \
  flvmux name=mux streamable=true \
    ! rtmpsink location="rtmp://localhost:1935/live/test-stream/out"
```

GStreamer troubleshooting notes:
- If you see frequent underflows/stutter, try increasing `latency=` (e.g. 200 → 500).
- If codec depayload fails, confirm the ingest stream is **H.264 + AAC** (typical for RTMP) or adjust depayloaders accordingly.

### 8.3 Recording lookup

Recording is disabled by default in v0 (`record: no`). If recording is enabled later, use the per-stream path:
- `live/<streamId>/in` (ingest) and/or `live/<streamId>/out` (processed)

List recorded timespans:

```sh
curl "http://localhost:9996/list?path=live/<streamId>/in"
```

Download a timespan (example requires values from `/list`):

```sh
curl -L "http://localhost:9996/get?path=live/<streamId>/in&start=<RFC3339>&duration=<seconds>" -o recording.mp4
```

---

## 9. Operational Runbook (Common Failures)

### 9.1 “Publisher connected but worker didn’t start”

Checks:
- MediaMTX logs: did `runOnReady` run? did it exit non-zero?
- Control API: `GET /v3/paths/get/live%2F<streamId>%2Fin` shows state and tracks
- Hook receiver logs: did it receive the `ready` event?

### 9.2 “Worker started but can’t pull input”

Checks:
- `ffplay rtsp://mediamtx:8554/live/<streamId>/in` from inside the worker network namespace
- Confirm path naming matches exactly (`live/<streamId>/in`)
- If using auth, confirm worker credentials (RTSP: `rtsp://user:pass@...`, RTMP: `?user=&pass=`)

### 9.3 “No metrics / API access from other services”

Checks:
- listeners: `apiAddress`, `metricsAddress` bound to an interface reachable from the network
- authentication: if non-local access is required, ensure permissions allow `api` / `metrics`

---

## 10. Security & Access Control (Must Decide)

MediaMTX supports:
- internal auth (credentials in config, optionally hashed)
- external HTTP auth (recommended for service-to-service)
- JWT auth

Current decision (v0):
- **Publish:** everyone (unauthenticated)
- **Read:** everyone (unauthenticated)
- **Control API / metrics / playback / pprof:** everyone (unauthenticated)

This is acceptable for local development only. Before any production exposure, revisit and implement a real access policy (at minimum: network-level restrictions + auth for API/metrics/playback).

---

## 11. Acceptance Criteria

- RTMP publish to `live/<streamId>/in` reliably triggers a `ready` event to the hook receiver
- `not-ready` event is emitted when the ingest ends
- `apps/stream-worker/` can pull via `rtsp://mediamtx:8554/live/<streamId>/in` and publish to `rtmp://mediamtx:1935/live/<streamId>/out`
- A GStreamer-only bypass pipeline can republish `live/<streamId>/in` → `live/<streamId>/out` for debugging without the worker
- Control API and metrics are reachable from other services (per decided auth policy)
- Recording is disabled by default (v0)
- A “single command” dev workflow exists to start/stop MediaMTX and inspect logs/metrics (`make dev`, `make logs`, `make ps`, `make down`)

---

## 12. Open Questions (Answer Before Implementation)

Resolved decisions (v0):

1) **Stream identity:** derive `streamId` from **path naming**.
   - Ingest: `live/<streamId>/in`
   - Processed: `live/<streamId>/out`

2) **Hook receiver:** new service named **`stream-orchestration`** receives hooks over **HTTP**.

3) **Worker lifecycle policy:** **one worker per stream**.
   - Stop policy: stop on `not-ready` after a **grace period** (default: 30s) to allow for transient disconnects.

4) **Forwarding to 3rd-party RTMP (decision + tradeoffs):**
   - Decision: implement forwarding as a small **egress forwarder** process started/stopped by `stream-orchestration` (not inside MediaMTX, not inside the worker).
   - Input: pull `rtsp://mediamtx:8554/live/<streamId>/out` (codec-copy)
   - Output: push to the configured 3rd-party RTMP URL(s)
   - Rationale:
     - isolates flaky outbound RTMP from the worker’s real-time pipeline (forwarder restarts don’t stall processing)
     - keeps 3rd-party credentials and retry logic out of the worker image
     - makes it easy to test locally by swapping destinations without rebuilding the worker

5) **Recording policy:** **no recording** in v0 (keep `record: no`).

6) **Access & security:** **unauthenticated** for dev (everyone can publish/read/API/metrics/playback/pprof).

7) **Observability stack:** logs should be **persisted to the filesystem** in dev (via Docker log capture/volumes); Prometheus metrics remain available at `:9998` but scraping/shipping is not required in v0.

8) **Port requirements:** no port conflicts; expose externally as needed.
   - External (dev): `1935` (RTMP), `9997` (API), `9998` (metrics), `9996` (playback)
   - Internal-only (dev): `8554` (RTSP) unless you explicitly need external RTSP access
