# Docker Repo Setup (macOS + Linux, CPU-only)

## 1. Goal

Provide a **Docker-first** setup that runs the end-to-end workflow described in:
- `specs/001-spec.md` (live ingest → Gemini Live dubbing → republish)
- `specs/006-end-to-end-workflow.md` (milestones A→E)

The setup must work for **CPU-only** development on macOS and Linux, focusing on MediaMTX plus the GStreamer worker.

This spec is derived from the dependency baseline in `specs/005-libraries-and-dependencies.md`.

---

## 2. Non-Goals

- Picking a final production orchestration platform (Kubernetes/ECS/etc.).
- Hardening and SRE-grade operations (alerts, autoscaling, canaries).
- Solving model licensing / distribution policies (only define runtime mechanics).

---

## 3. Design Principles (Good Practice)

- **One-command local start**: `docker compose up` brings up the baseline services required to test ingest/egress.
- **Parity by default**: prefer Linux containers as the “source of truth” runtime (both macOS dev and AWS run the same images).
- **Explicit native deps**: system packages needed by the media pipeline are installed in images (GStreamer, FFmpeg, rubberband) per `specs/005-libraries-and-dependencies.md`.
- **Reproducible caches**: model and artifact caches are mounted as volumes (no repeated multi-GB downloads).
- **No secrets in images**: RTMP keys, endpoints, and tokens come from env/secret injection (with a `.env.example` when implementation lands).

---

## 4. Repo Layout (Docker-Related)

Canonical Docker runtime assets live under `deploy/`:

- `deploy/docker-compose.yml`: local “baseline stack” for MediaMTX + orchestration
- `deploy/mediamtx/`: MediaMTX container build + config + hooks
- `deploy/orchestrator/`: hook receiver that starts/stops workers
- `deploy/recordings/`: local recordings volume (optional)

When implementation lands:

- `apps/stream-worker/`: unified worker image (GStreamer + Gemini Live client)
- `apps/sts-service/`: (deprecated) keep only if legacy offline dubbing is needed; Gemini Live is the default provider
- `deploy/stream-worker/` (optional): Dockerfile(s) and runtime configs if not colocated under `apps/`

---

## 5. Docker Compose Roles

### 5.1 Required Services (Baseline)

- **MediaMTX** (`mediamtx`)
  - Ingest RTMP (`live/<streamId>/in`)
  - Expose RTSP pull endpoint for worker
  - Publish processed stream (`live/<streamId>/out`)
  - Emit hooks (`runOnReady` / `runOnNotReady`) to orchestrator

- **Stream orchestrator** (`stream-orchestration`)
  - Receive hook events
  - Start/stop exactly one worker per stream id

### 5.2 Planned Services (Milestones C→E)

- **Stream worker** (`stream-worker`)
  - Pull RTSP from `mediamtx`
  - Run GStreamer demux/remux + chunking + Gemini Live dubbing
  - Push RTMP back to `mediamtx` (`live/<streamId>/out`)

### 5.3 Profiles (CPU)

Compose SHOULD support one execution profile for the worker:

- **`cpu` (default)**: runs everywhere (macOS dev and Linux)

---

## 6. Image Strategy (Good Practice)

### 6.1 Stream Worker Base OS

Use a Debian/Ubuntu base image for the worker so installing GStreamer/FFmpeg/rubberband is predictable via `apt`.

Required native packages (non-exhaustive; final list to match actual pipelines):

- GStreamer core + plugins (`base`, `good`, `bad`, `ugly`, `libav`)
- GI bindings + typelibs for Python (`python3-gi` + GStreamer introspection)
- `ffmpeg` (CLI)
- `rubberband-cli` (CLI)

### 6.2 Python Runtime

Baseline Python runtime for the worker and Gemini Live client:

- Python 3.10.x
- `numpy<2.0` (compatibility with existing DSP helpers)
- Gemini Live SDK or HTTP client dependencies (added when implementation lands)

### 6.3 Image Build (CPU)

Recommended pattern:

- Single Dockerfile targeting CPU (e.g., `python:3.10-slim` + apt deps).
- All Python dependencies from `specs/005-libraries-and-dependencies.md`.

---

## 7. Caches and Volumes (Models + Artifacts)

The stack SHOULD mount persistent volumes for:

- **Separation model cache** (demucs/etc., only if enabled)
- **Recordings** (MediaMTX fMP4 segments; optional, but valuable for debugging)
- **Worker debug artifacts** (optional, behind explicit flags)

Constraints:
- Cache locations must be configurable via environment variables.
- Volumes must be safe to delete (system can rebuild caches from scratch).

---

## 8. Local Development on macOS (Docker Desktop)

### 8.1 Supported “Local Truth”

Local development uses Docker Desktop and runs the stack as Linux containers.

Notes:
- On Apple Silicon, the repo MAY run containers as `linux/amd64` for parity with typical Linux hosts. This trades performance for consistency.
- If arm64 images are supported by the chosen Python/ML wheels, native `linux/arm64` builds are allowed.

### 8.2 Minimal Local Commands (Baseline, CPU)

Start baseline services:

```sh
docker compose -f deploy/docker-compose.yml up --build
```

Validate MediaMTX health (examples; adjust as needed):

```sh
curl http://localhost:9997/v3/paths/list
curl http://localhost:9998/metrics | head
```

### 8.3 Publishing a Test Stream (Local)

For local testing, publish an RTMP stream to:

- `rtmp://localhost:1935/live/<streamId>/in`

Accepted publishers:
- OBS (recommended for manual testing)
- A local FFmpeg command (requires `ffmpeg` installed on the host)

---

## 9. Configuration Inputs (Environment)

The Docker setup MUST support configuration via environment variables for:

- Input/output endpoints:
  - MediaMTX ingest path and worker pull/push URLs
  - Optional final RTMP destination (third-party)
- Dubbing settings (Gemini Live):
  - source/target language
  - voice/profile selection
  - chunk duration and max in-flight fragments
  - Gemini project/region and API key (injected via env/secret, not baked into images)
- Cache locations:
  - Separation model cache dir (if enabled)
- Debug toggles:
  - recordings enablement
  - per-fragment artifact dumps (off by default)

No secrets may be committed; when implementation lands, provide `.env.example`.

---

## 10. Success Criteria

- On macOS, a developer can start the baseline stack with Docker Desktop and validate MediaMTX ingest/RTSP playback using the workflow in `specs/006-end-to-end-workflow.md` (Milestones A and B).
- On Linux, the worker runs and can process at least one live stream end-to-end (Milestones C→E), with persistent caches for any optional separation models across container restarts.
- The Docker setup makes all native dependencies from `specs/005-libraries-and-dependencies.md` explicit and discoverable (no “it works on my machine” packages).

---

## 11. References

- `specs/001-spec.md`
- `specs/002-mediamtx.md`
- `specs/003-gstreamer-stream-worker.md`
- `specs/005-libraries-and-dependencies.md`
- `specs/006-end-to-end-workflow.md`
- `.sts-service-archive/SETUP.md` (historical guidance for FFmpeg/rubberband and Coqui compatibility)
