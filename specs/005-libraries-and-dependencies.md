# Libraries and Dependencies (Repo Baseline)

## 1. Goal

Define a **curated, minimal** set of libraries and native/system dependencies for this repo’s planned runtime components, grounded in:
- The target architecture in `specs/001-spec.md` (MediaMTX ingest → unified Python worker → Gemini Live streaming → republish).
- Proven media-handling choices from `.sts-service-archive/` where relevant (chunking/mixing), while replacing local ASR/MT/TTS with Gemini Live.

This spec is intentionally implementation-oriented: it exists to make dependency selection explicit, reproducible, and reviewable.

---

## 2. In-Scope Components

- **Unified worker (`apps/stream-worker/`)**: Python + GStreamer pipeline to demux/remux, chunk audio, stream to Gemini Live, and republish.
- **Gemini Live client usage**: provider SDK/HTTP client for speech-to-speech streaming.
- **Infra/runtime**: MediaMTX and container/base OS packages required to run the above reliably.

---

## 3. Dependency Principles

- **Prefer curated lists over “pip freeze”**: pin only where needed for compatibility/reproducibility, avoid platform-specific lock artifacts.
- **Separate native vs Python deps**: media pipelines require OS-level packages (GStreamer, FFmpeg, rubberband) that must be explicit.
- **CPU-first baseline**: all components must run end-to-end on CPU; GPU acceleration is optional and additive.
- **Stable contracts**: dependencies should support the contracts in `specs/004-sts-pipeline-design.md` and the worker boundary in `specs/003-gstreamer-stream-worker.md`.

---

## 4. Baseline Runtime Versions (Defaults)

These defaults match known-good behavior in `.sts-service-archive/` and reduce cross-platform surprises:

- **Python**: 3.10.x
- **NumPy**: `< 2.0` (Coqui TTS compatibility; see `.sts-service-archive/environment.yml`)
- **GStreamer**: 1.20+ (prefer 1.22+ where available)
- **FFmpeg**: 5+ (system binary)
- **rubberband**: `rubberband-cli` (system binary; required for duration matching)
- **MediaMTX**: latest stable release compatible with the config in `specs/002-mediamtx.md`

---

## 5. Native/System Dependencies

### 5.1 Required (Worker + Gemini Live)

- **GStreamer runtime**:
  - Core: `gstreamer1.0`
  - Plugins: `base`, `good`, `bad`, `ugly`, `libav`
  - Needed elements include: `rtspsrc`, `rtph264depay`, `h264parse`, `aacparse`, `avdec_aac`, `audioconvert`, `audioresample`, `flvmux`, `rtmpsink`, `voaacenc`
- **Python GStreamer bindings**:
  - `python3-gi` + GStreamer introspection packages (GI typelibs)
- **FFmpeg** (CLI):
  - Used for fragment decode/encode workflows (mirrors `.sts-service-archive/ARCHITECTURE.md`)
- **rubberband** (CLI):
  - High-quality time-stretch for duration matching (mirrors `.sts-service-archive/TTS.md`)

### 5.2 Optional (Quality / Ops)

- **Audio utilities**: `sox` (debug tooling), `libsndfile` (often already present via Python wheels)
- **GPU enablement** (optional):
  - NVIDIA: CUDA runtime matching the chosen PyTorch build

---

## 6. Python Dependencies (Curated)

The lists below are “what we intend to depend on”, not a final lockfile. Keep the set small and aligned with `specs/001-spec.md`.

### 6.1 Shared Core (Worker + Client)

- `numpy<2.0`
- `scipy` (filters, basic DSP utilities)
- `soundfile` (WAV I/O for debug assets and tests)
- `pydantic` (typed contracts/config validation)
- `rich` (dev-friendly logs/CLI output)
- `typer` (CLI entrypoints for local runs and test harnesses)
- `httpx` or equivalent async HTTP client (for provider calls when SDKs are unavailable)
- Optional:
  - `ffmpeg-python` (drive FFmpeg from Python where convenient)
  - `pydub` (simple audio I/O/playback helpers)
  - `sounddevice` (local audio playback; keep out of production images if not needed)

### 6.2 Gemini Live Client

- Official Gemini API client/SDK (use the provider-supported package when available).
- `grpcio` / `websockets` (if the SDK requires them for streaming).
- `python-dotenv` (dev-only for loading env variables locally; do not use in production images).

### 6.3 Optional Offline/Mock Dubbing

- Keep deterministic tone/pass-through generators for tests (can be implemented with `numpy` only).
- If we need offline speech synthesis for regression tests without network:
  - `coqui-tts` (optional; behind a flag; only for non-production fixtures)
  - `torch` (only when the optional path is enabled)
- Avoid shipping these heavy deps in default images; gate them by extras/profiles.

### 6.4 Speech/Background Separation (Worker)

`specs/001-spec.md` expects 2-stem separation (“speech vs background”). Baseline:

- Optional (recommended for v1 quality):
  - `demucs` (PyTorch-based source separation; use “vocals” as a proxy for speech in early iterations)
  - `spleeter` (alternative source separation; heavier footprint due to TensorFlow; keep optional and behind a flag)
- Fallback (no extra ML deps):
  - VAD + simple gating/ducking policies implemented with `numpy/scipy` (lower quality, but operationally simple)

v0 decision:
- Support `demucs` as the default when available; fall back to VAD + gating/ducking if no separation backend is present.

---

## 7. Serving / Interop Dependencies (Optional)

Gemini Live is consumed directly via the provider SDK/HTTP. No local STS server is planned.

Only include additional serving deps if we intentionally keep a legacy demo path:
- `python-socketio` + lightweight web framework (behind a dev-only flag)

---

## 8. Dev/Test Tooling (When Code Lands)

When adding runnable modules under `apps/`, standardize on:

- Formatting/lint: `ruff` (and optionally `black` if preferred)
- Tests: `pytest` (+ `pytest-asyncio` if async code is introduced)
- Types: `mypy` (required; strict typing is a constitution gate)

---

## 9. Acceptance Criteria

- A clean machine can install the documented **native dependencies** (GStreamer, FFmpeg, rubberband) and run a minimal “smoke” pipeline without additional undocumented packages.
- Python dependency lists remain **curated** (no committed `pip freeze`), with version pins only where required for compatibility (e.g., `numpy<2.0`).
- The chosen libraries support the behavior described in `specs/001-spec.md` with Gemini Live as the dubbing provider, and keep heavy optional deps gated.

---

## 10. References (Source Research)

- `specs/001-spec.md`
- `specs/003-gstreamer-stream-worker.md`
- `specs/004-sts-pipeline-design.md`
- Gemini Live API docs (file-stream example)
- `.sts-service-archive/` (historical media/DSP references only)
