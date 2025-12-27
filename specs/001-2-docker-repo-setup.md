# Docker Repo Setup (macOS + EC2 + RunPod)

## 1. Goal

Provide a **Docker-first** setup that runs the end-to-end workflow described in:
- `specs/001-spec.md` (live ingest → distributed STS → republish)
- `specs/009-end-to-end-workflow.md` (milestones A→E)
- `specs/015-deployment-architecture.md` (EC2 + RunPod split architecture)

The setup must work for:
- **Local development on macOS** (CPU-only, deterministic, easy to iterate, single-host mode)
- **Production deployment on EC2** (stream infrastructure without GPU)
- **Production deployment on RunPod.io** (GPU-accelerated STS processing)

This spec is derived from the dependency baseline in `specs/008-libraries-and-dependencies.md` and the deployment architecture in `specs/015-deployment-architecture.md`.

---

## 2. Non-Goals

- Picking a final production orchestration platform (Kubernetes/ECS/etc.).
- Hardening and SRE-grade operations (alerts, autoscaling, canaries).
- Solving model licensing / distribution policies (only define runtime mechanics).

---

## 3. Design Principles (Good Practice)

- **One-command local start**: `docker compose up` brings up the baseline services required to test ingest/egress.
- **Parity by default**: prefer Linux containers as the “source of truth” runtime (both macOS dev and AWS run the same images).
- **Explicit native deps**: system packages needed by the media pipeline are installed in images (GStreamer, FFmpeg, rubberband) per `specs/008-libraries-and-dependencies.md`.
- **Reproducible caches**: model and artifact caches are mounted as volumes (no repeated multi-GB downloads).
- **No secrets in images**: RTMP keys, endpoints, and tokens come from env/secret injection (with a `.env.example` when implementation lands).

---

## 4. Repo Layout (Docker-Related)

The repository is split into **two deployment projects** (see `specs/015-deployment-architecture.md`):

### 4.1 Stream Infrastructure Project (EC2)

Canonical Docker runtime assets live under `deploy/media-service/`:

- `deploy/media-service/docker-compose.yml`: local baseline stack for MediaMTX + orchestration
- `deploy/media-service/mediamtx/`: MediaMTX container build + config + hooks
- `deploy/media-service/orchestrator/`: hook receiver that starts/stops workers
- `deploy/media-service/recordings/`: local recordings volume (optional)

Application code:

- `apps/media-service/`: stream worker (GStreamer-based, lightweight, CPU-only)
  - Audio/video demux and remux
  - Audio chunking and background separation
  - STS client (HTTP calls to RunPod or local mock)
  - Audio remixing

### 4.2 GPU Processing Project (RunPod)

Canonical Docker runtime assets live under `deploy/sts-service/`:

- `deploy/sts-service/Dockerfile`: CUDA-enabled image for RunPod
- `deploy/sts-service/runpod-template.json`: RunPod pod configuration template
- `deploy/sts-service/docker-compose.yml`: optional local testing (CPU fallback mode)

Application code:

- `apps/sts-service/`: STS service API (HTTP server)
  - ASR module (Whisper, GPU-accelerated)
  - Translation module (MT, GPU-accelerated)
  - TTS module (Coqui or alternative, GPU-accelerated)
  - Time-stretching utilities

---

## 5. Docker Compose Roles

### 5.1 Stream Infrastructure Compose Stack (EC2 / Local Dev)

**File**: `deploy/media-service/docker-compose.yml`

Required services:

- **MediaMTX** (`mediamtx`)
  - Ingest RTMP (`live/<streamId>/in`)
  - Expose RTSP pull endpoint for worker
  - Publish processed stream (`live/<streamId>/out`)
  - Emit hooks (`runOnReady` / `runOnNotReady`) to orchestrator

- **Stream Orchestrator** (`stream-orchestration`)
  - Receive hook events
  - Start/stop exactly one worker per stream id

- **Stream Worker** (`stream-worker`)
  - Pull RTSP from `mediamtx`
  - Run GStreamer demux/remux + chunking + background separation (CPU)
  - Call STS service API (local or RunPod)
  - Remix and remux audio/video
  - Push RTMP back to `mediamtx` (`live/<streamId>/out`)

- **STS Service Mock** (`sts-service-mock`) — **Local dev only**
  - Provides mock STS API for local testing without GPU
  - Returns deterministic pass-through or tone audio

### 5.2 GPU Processing Compose Stack (RunPod / Optional Local)

**File**: `deploy/sts-service/docker-compose.yml`

Optional services (for local GPU testing):

- **STS Service** (`sts-service`)
  - HTTP/gRPC API server
  - GPU-accelerated ASR, MT, TTS
  - Requires NVIDIA Container Toolkit and GPU

This stack is primarily for local validation; production runs as RunPod pod.

### 5.3 Deployment Modes

Three deployment modes are supported:

1. **Local Development (Single Host, CPU)**:
   - Run `deploy/media-service/docker-compose.yml` with `sts-service-mock`
   - No GPU required
   - Stream worker calls local mock API

2. **Local Development (Single Host, GPU)**:
   - Run both compose stacks on same machine
   - Stream worker calls local STS service on `http://localhost:8000`
   - Requires NVIDIA Container Toolkit

3. **Production (EC2 + RunPod)**:
   - EC2: Run `deploy/media-service/docker-compose.yml` without mock service
   - RunPod: Deploy `apps/sts-service/` as pod
   - Stream worker calls RunPod URL via `STS_SERVICE_URL` env var

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

Baseline Python runtime for STS components:

- Python 3.10.x
- `numpy<2.0` and `coqui-tts==0.27.2` (compatibility baseline from `.sts-service-archive/`)

### 6.3 CPU vs GPU Builds

Recommended pattern:

- One Dockerfile with a build arg (e.g., `TARGET=cpu|gpu`) or two Dockerfiles:
  - CPU image based on `python:3.10-slim` (plus apt deps)
  - GPU image based on a CUDA runtime image (plus Python + apt deps)

Both images must install the same **logical** Python dependencies from `specs/008-libraries-and-dependencies.md`; only the torch build/runtime differs.

---

## 7. Caches and Volumes (Models + Artifacts)

The stack SHOULD mount persistent volumes for:

- **HuggingFace cache** (Translation models)
- **TTS cache** (Coqui models + generated artifacts where appropriate)
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
- On Apple Silicon, the repo MAY run containers as `linux/amd64` for parity with AWS GPU (x86_64). This trades performance for consistency.
- If arm64 images are supported by the chosen Python/ML wheels, native `linux/arm64` builds are allowed, but parity with AWS must remain testable.

### 8.2 Minimal Local Commands (Baseline)

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

## 9. AWS GPU Runtime (Recommended EC2 Setup)

### 9.1 Recommended Instance Type

Recommended baseline: **`g5.xlarge`** (NVIDIA A10G, good price/perf for real-time ML inference).

Acceptable alternatives (cost/perf tradeoffs):
- `g4dn.xlarge` (NVIDIA T4; cheaper, lower throughput)
- Larger `g5.*` sizes when running multiple streams per host

### 9.2 Host OS and GPU Runtime

Recommended host OS: Ubuntu 22.04 LTS (or newer LTS).

Host must have:
- NVIDIA driver compatible with the chosen CUDA runtime in the container
- Docker Engine
- NVIDIA Container Toolkit (so containers can access GPUs)

### 9.3 Disk/Volume Guidance (Good Practice)

Attach a dedicated EBS volume (gp3) for:
- Docker image layers
- model caches (HuggingFace / TTS)
- recordings and debug artifacts

Rationale: avoids re-downloading models on instance replacement and reduces root-volume pressure.

### 9.4 Network/Security Group Guidance

Expose only what you need:
- `1935/tcp` RTMP ingest (if publishing from outside the VPC)
- `9997/tcp` API and `9998/tcp` metrics SHOULD be restricted (VPN / SG allowlist)

Internal worker↔MediaMTX traffic stays on the Docker network.

---

## 10. Configuration Inputs (Environment)

The Docker setup MUST support configuration via environment variables for:

- Input/output endpoints:
  - MediaMTX ingest path and worker pull/push URLs
  - Optional final RTMP destination (third-party)
- STS settings:
  - source/target language
  - voice profile
  - chunk duration and max in-flight fragments
  - CPU/GPU selection (profile-driven)
- Cache locations:
  - HuggingFace cache dir
  - Coqui/TTS cache dirs
- Debug toggles:
  - recordings enablement
  - per-fragment artifact dumps (off by default)

No secrets may be committed; when implementation lands, provide `.env.example`.

---

## 11. Success Criteria

- On macOS, a developer can start the baseline stack with Docker Desktop and validate MediaMTX ingest/RTSP playback using the workflow in `specs/009-end-to-end-workflow.md` (Milestones A and B).
- On AWS (GPU), the worker runs under a GPU-enabled profile and can process at least one live stream end-to-end (Milestones C→E), with persistent model caches across container restarts.
- The Docker setup makes all native dependencies from `specs/008-libraries-and-dependencies.md` explicit and discoverable (no “it works on my machine” packages).

---

## 12. References

- `specs/001-spec.md`
- `specs/002-mediamtx.md`
- `specs/003-gstreamer-stream-worker.md`
- `specs/008-libraries-and-dependencies.md`
- `specs/009-end-to-end-workflow.md`
- `.sts-service-archive/SETUP.md` (historical guidance for FFmpeg/rubberband and Coqui compatibility)
