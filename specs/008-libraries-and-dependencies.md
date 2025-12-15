# Libraries and Dependencies (Repo Baseline)

## 1. Goal

Define a **curated, minimal** set of libraries and native/system dependencies for this repo’s planned runtime components, grounded in:
- The target architecture in `specs/001-spec.md` (MediaMTX ingest → unified Python worker → in-process STS → republish).
- Proven, working choices in `.sts-service-archive/` (ASR/MT/TTS pipeline and operational notes).

This spec is intentionally implementation-oriented: it exists to make dependency selection explicit, reproducible, and reviewable.

---

## 2. In-Scope Components

- **Unified worker (`apps/stream-worker/`)**: Python + GStreamer pipeline to demux/remux, chunk audio, run STS in-process, and republish.
- **STS module (`apps/sts-service/`)**: Python modules for ASR → Translation → TTS and supporting DSP utilities, used in-process by the worker.
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

### 5.1 Required (Worker + STS)

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

The lists below are “what we intend to depend on”, not a final lockfile. The goal is to keep the set small and aligned with `specs/001-spec.md`.

### 6.1 Shared Core (STS module and/or Worker)

- `numpy<2.0`
- `scipy` (filters, basic DSP utilities)
- `soundfile` (WAV I/O for debug assets and tests)
- `pyyaml` (voice/model configuration files, matching `.sts-service-archive/coqui-voices.yaml`)
- `pydantic` (typed contracts/config validation)
- `rich` (dev-friendly logs/CLI output)
- `typer` (CLI entrypoints for local runs and test harnesses)
- Optional (local demos/offline workflows, per `.sts-service-archive/`):
  - `ffmpeg-python` (drive FFmpeg from Python where convenient)
  - `pydub` (simple audio I/O/playback helpers)
  - `sounddevice` (local audio playback; keep out of production images if not needed)

### 6.2 ASR (Speech → Text)

Based on `.sts-service-archive/utils/transcription.py` and `specs/sources/ASR.md`:

- `faster-whisper` (Whisper inference via CTranslate2; CPU-friendly)
- `ctranslate2` (transitive dependency; pin only if compatibility issues arise)
- Optional utilities:
  - `librosa` (preprocessing helpers; keep optional if we can replace with `numpy/scipy`)
  - `inflect` / `num2words` (optional text normalization helpers used by some preprocessing policies)

### 6.3 Translation (Text → Text)

Mirrors `.sts-service-archive` usage of M2M100 and `specs/006-translation-component.md` goals:

- `transformers`
- `sentencepiece` (required by M2M100/NLLB-family tokenizers)
- `torch` (model runtime)
- Optional:
  - `accelerate` (optional runtime ergonomics/perf controls; not required for correctness)
  - `langdetect` (**not used in v0**; language is always configured explicitly)

### 6.4 TTS (Text → Speech)

Based on `.sts-service-archive/talk_multi_coqui.py`, `.sts-service-archive/coqui-voices.yaml`, and `specs/007-tts-audio-synthesis.md`:

- `coqui-tts==0.27.2` (XTTS-v2 + VITS “fast” path as used in the archive)
- `torch` and `torchaudio` (TTS model runtime + audio utils)

### 6.5 Speech/Background Separation (Worker)

`specs/001-spec.md` expects 2-stem separation (“speech vs background”). The archive does not include this stage, so we explicitly select a baseline:

- Optional (recommended for v1 quality):
  - `demucs` (PyTorch-based source separation; use “vocals” as a proxy for speech in early iterations)
  - `spleeter` (alternative source separation; heavier footprint due to TensorFlow; keep optional and behind a flag)
- Fallback (no extra ML deps):
  - VAD + simple gating/ducking policies implemented with `numpy/scipy` (lower quality, but operationally simple)

v0 decision:
- Support both `demucs` and `spleeter` as pluggable separation backends (default: `demucs` when available).
- If no separation backend is available, fall back to VAD + gating/ducking.

---

## 7. Serving / Interop Dependencies (Optional)

`specs/001-spec.md` prefers **in-process** STS usage, but `.sts-service-archive/` implements a Socket.IO live protocol. If we need compatibility with that legacy protocol for local demos/integration:

- `python-socketio`
- `flask` (only if we keep a Flask-based server path; otherwise omit)
- `aiohttp` (only if we implement an async Socket.IO server path; otherwise omit)

---

## 8. Dev/Test Tooling (When Code Lands)

When adding runnable modules under `apps/`, standardize on:

- Formatting/lint: `ruff` (and optionally `black` if preferred)
- Tests: `pytest` (+ `pytest-asyncio` if async code is introduced)
- Types (optional): `mypy`

---

## 9. Acceptance Criteria

- A clean machine can install the documented **native dependencies** (GStreamer, FFmpeg, rubberband) and run a minimal “smoke” pipeline without additional undocumented packages.
- Python dependency lists remain **curated** (no committed `pip freeze`), with version pins only where required for compatibility (e.g., `numpy<2.0`, `coqui-tts==0.27.2`).
- The chosen libraries support the behavior described in `specs/001-spec.md` without forcing a worker↔STS network hop.

---

## 10. References (Source Research)

- `specs/001-spec.md`
- `specs/003-gstreamer-stream-worker.md`
- `specs/004-sts-pipeline-design.md`
- `.sts-service-archive/ARCHITECTURE.md`
- `.sts-service-archive/environment.yml`
- `.sts-service-archive/requirements.txt` (historical; not intended as a baseline lockfile)
- `specs/sources/ASR.md`, `specs/sources/TRANSLATION.md`, `specs/sources/TTS.md`
