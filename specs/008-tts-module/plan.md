# Implementation Plan: TTS Audio Synthesis Module

**Branch**: `008-tts-module` | **Date**: 2025-12-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-tts-module/spec.md`

## Summary

Implement a TTS (Text-to-Speech) component for the STS service that converts translated text into synthesized speech audio with duration matching for live stream synchronization. The component follows the established ASR/Translation module pattern with interface/factory architecture, supports quality vs fast synthesis modes, voice cloning capabilities, and provides comprehensive error classification for pipeline-level retry decisions.

**Key Capabilities**:
- Multilingual synthesis using Coqui TTS (XTTS-v2 for quality, VITS for fast mode)
- Duration matching via rubberband time-stretch to maintain A/V sync
- Voice cloning when audio samples provided (quality mode only)
- Text preprocessing for improved synthesis quality
- Asset lineage tracking from TextAsset → AudioAsset
- Structured error classification for retry/fallback orchestration

## Technical Context

**Language/Version**: Python 3.10.x (per constitution and existing monorepo setup)
**Primary Dependencies**: TTS (Coqui TTS library), pydub (audio processing), rubberband (time-stretch), pydantic>=2.0 (data models), numpy (audio manipulation)
**Storage**: In-memory model cache + optional debug artifacts to local filesystem (when debug_artifacts=True)
**Testing**: pytest>=7.0, pytest-asyncio, pytest-mock (mock patterns following ASR/Translation precedent)
**Target Platform**: RunPod GPU service (sts-service container on CPU per constitution principle)
**Project Type**: Single service module within apps/sts-service monorepo
**Performance Goals**:
- First model load <5 seconds
- Subsequent synthesis requests <2 seconds (cached model)
- Fast mode: 40% latency reduction vs quality mode
- Duration matching: 95% of fragments within 50ms tolerance
**Constraints**:
- CPU-only execution (avoid GPU compatibility issues per reference implementation)
- Duration matching clamping: 0.5x to 2.0x speed factor range (configurable)
- Voice samples must be pre-validated (mono, correct sample rate, sufficient duration)
- Text preprocessing must be deterministic (same input → same output)
**Scale/Scope**:
- Supports all languages in coqui-voices.yaml configuration
- Handles fragments from 500ms to 6 seconds (typical live stream chunk size)
- Model caching for single worker lifetime (per-stream isolation per constitution)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I - Real-Time First**: ✅ PASS
- Component processes fragments asynchronously without blocking
- Model caching reduces latency for subsequent requests
- Fast mode option for low-latency scenarios
- Duration matching ensures A/V sync without buffering entire stream

**Principle II - Testability Through Isolation**: ✅ PASS
- Mock implementations planned: MockTTSFixedTone, MockTTSFromFixture, MockTTSFailOnce
- Tests use deterministic fixtures, no external TTS API dependencies
- Component interface allows full swap for testing
- Asset lineage enables verification without executing real synthesis

**Principle III - Spec-Driven Development**: ✅ PASS
- Component contract defined in specs/007-tts-audio-synthesis.md
- Data model aligned with specs/004-sts-pipeline-design.md asset patterns
- This plan generated before implementation begins
- Reference implementation analyzed in specs/sources/TTS.md

**Principle IV - Observability & Debuggability**: ✅ PASS
- Structured logging with stream_id, sequence_number per fragment
- TTSMetrics asset tracks durations, speed factors, clamping decisions
- Optional debug_artifacts persists preprocessed text, baseline/aligned audio
- Asset lineage from TextAsset → AudioAsset enables debugging

**Principle V - Graceful Degradation**: ✅ PASS
- Errors classified as retryable/non-retryable for orchestrator decisions
- Fast mode fallback to standard model if fast_model unavailable
- Voice cloning falls back to named speaker when sample invalid
- Speed factor clamping prevents extreme artifacts that break pipeline

**Principle VI - A/V Sync Discipline**: ✅ PASS
- Duration matching preserves target timing from stream timeline
- Speed factor and clamping metadata tracked for debugging drift
- Sample rate/channel alignment ensures GStreamer compatibility
- Time-stretch preserves pitch (rubberband with pitch-stable mode)

**Principle VII - Incremental Delivery**: ✅ PASS
- Milestone 1: Basic synthesis (quality mode, no voice cloning)
- Milestone 2: Duration matching and sample rate alignment
- Milestone 3: Voice selection (fast mode, voice cloning, fallbacks)
- Milestone 4: Text preprocessing and error classification

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**: ✅ PASS
- Test strategy defined for all 5 user stories
- Mock patterns documented: MockTTSFixedTone, MockTTSFromFixture, MockTTSFailOnce
- Coverage targets: 80% minimum, 95% for duration matching (critical path)
- Test infrastructure: pytest, pytest-mock, deterministic audio fixtures
- Test organization: apps/sts-service/tests/unit/tts/, apps/sts-service/tests/contract/tts/

## Project Structure

### Documentation (this feature)

```text
specs/008-tts-module/
├── plan.md              # This file (speckit.plan command output)
├── spec.md              # Feature specification (speckit.specify command output)
├── research.md          # Phase 0 output (technical decisions documented below)
├── data-model.md        # Phase 1 output (entity relationships and validation rules)
├── quickstart.md        # Phase 1 output (setup and usage guide)
└── contracts/           # Phase 1 output (API contracts and schemas)
    ├── tts-component.yaml       # TTSComponent interface contract
    ├── audio-asset-schema.json  # AudioAsset output schema
    └── tts-config-schema.json   # TTSConfig schema
```

### Source Code (repository root)

```text
apps/sts-service/
├── src/
│   └── sts_service/
│       ├── asr/                 # Existing ASR module (reference pattern)
│       ├── translation/         # Existing Translation module (reference pattern)
│       └── tts/                 # NEW: TTS module (this feature)
│           ├── __init__.py      # Public API exports
│           ├── interface.py     # TTSComponent protocol + BaseClass
│           ├── models.py        # AudioAsset, TTSConfig, VoiceSelection, errors
│           ├── errors.py        # Error classification (retryable/non-retryable)
│           ├── factory.py       # create_tts_component() factory
│           ├── mock.py          # MockTTSFixedTone, MockTTSFromFixture, MockTTSFailOnce
│           ├── coqui_provider.py  # CoquiTTSComponent (XTTS-v2 + VITS)
│           ├── preprocessing.py   # preprocess_text_for_tts() deterministic rules
│           ├── duration_matching.py  # time-stretch via rubberband, clamping
│           └── voice_selection.py    # Model/voice selection from configs/coqui-voices.yaml
│
├── configs/
│   └── coqui-voices.yaml        # Voice/model configuration (language mappings)
│
└── tests/
    ├── unit/
    │   └── tts/                 # NEW: Unit tests for TTS module
    │       ├── __init__.py
    │       ├── test_interface.py
    │       ├── test_models.py
    │       ├── test_preprocessing.py
    │       ├── test_duration_matching.py
    │       ├── test_voice_selection.py
    │       ├── test_errors.py
    │       └── test_coqui_provider.py
    │
    └── contract/
        └── tts/                 # NEW: Contract tests for TTS assets
            ├── __init__.py
            ├── test_audio_asset_schema.py
            └── test_tts_component_contract.py
```

**Structure Decision**: Single service module within existing apps/sts-service monorepo. Follows established ASR/Translation pattern with interface.py (protocol + base class), models.py (Pydantic assets), factory.py (creation logic), and provider-specific implementations (coqui_provider.py). Mock implementations enable testing without TTS library dependencies. Configuration lives in apps/sts-service/configs/ per existing convention.

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- Target: All business logic (preprocessing, duration matching, voice selection, error classification)
- Tools: pytest, pytest-mock
- Coverage: 80% minimum, 95% for duration matching (critical path)
- Mocking: Mock TTS library calls, mock file I/O for voice samples, mock rubberband subprocess
- Location: `apps/sts-service/tests/unit/tts/`
- Key tests:
  - `test_preprocess_text_normalization()` - deterministic preprocessing rules
  - `test_duration_matching_speed_up()` - time-stretch calculations
  - `test_duration_matching_clamping()` - speed factor limits
  - `test_voice_selection_fast_mode()` - model selection logic
  - `test_error_classification_retryable()` - error categorization

**Contract Tests** (mandatory):
- Target: AudioAsset schema, TTSComponent interface contract, TTSConfig validation
- Tools: pytest with JSON schema validation
- Coverage: 100% of all contracts
- Mocking: Use MockTTSFixedTone to produce valid AudioAssets
- Location: `apps/sts-service/tests/contract/tts/`
- Key tests:
  - `test_audio_asset_schema_validation()` - Pydantic model compliance
  - `test_tts_component_interface()` - Protocol implementation verification
  - `test_audio_asset_lineage()` - parent_asset_ids tracking

**Integration Tests** (required for workflows):
- Target: CoquiTTSComponent with real TTS library, end-to-end synthesis pipeline
- Tools: pytest with real TTS models (small/fast models only)
- Coverage: Happy path + critical error scenarios
- Mocking: Mock voice sample files, mock rubberband for time-stretch
- Location: `apps/sts-service/tests/integration/tts/`
- Key tests:
  - `test_coqui_synthesis_basic()` - real synthesis with VITS model
  - `test_model_caching()` - verify models loaded once per worker
  - `test_duration_matching_with_rubberband()` - real time-stretch operation

**E2E Tests** (optional, for validation only):
- Target: Full STS pipeline (ASR → Translation → TTS) with real audio
- Tools: pytest with Docker Compose (sts-service + dependencies)
- Coverage: Critical user journeys only
- When: Run on-demand for release validation
- Location: `tests/e2e/`

### Mock Patterns (Constitution Principle II)

**TTS Component Mocks** (see `apps/sts-service/src/sts_service/tts/mock.py`):
- `MockTTSFixedTone`: Produces deterministic 440Hz tone of exact target_duration_ms
  - Use case: Pipeline integration tests, latency benchmarks
  - Returns: Valid AudioAsset with synthetic audio, correct sample rate/channels
  - No actual synthesis, instant response

- `MockTTSFromFixture`: Returns pre-recorded audio from test fixtures
  - Use case: Reproducible integration tests with known audio characteristics
  - Fixture format: `{sequence_number}.wav` files in test data directory
  - Returns: AudioAsset with fixture audio resampled to match request

- `MockTTSFailOnce`: Fails first call per sequence_number, succeeds on retry
  - Use case: Retry behavior validation, circuit breaker testing
  - First call: Returns FAILED status with retryable error
  - Second call: Returns SUCCESS with valid AudioAsset

**Audio Fixture Patterns**:
- Use deterministic PCM WAV files in `tests/fixtures/tts/`
- Fixtures: `silence.wav`, `speech_en_2s.wav`, `speech_es_3s.wav`
- All fixtures: mono, 16kHz sample rate, PCM_S16LE format
- Metadata included: `{fixture_name}.json` with expected duration, language

### Coverage Enforcement

**Pre-commit**: Run `make sts-test-unit` - fail if coverage < 80%
**CI**: Run `pytest --cov=apps/sts-service/src/sts_service/tts --cov-fail-under=80` - block merge if fails
**Critical paths**: Duration matching, voice selection, error classification → 95% minimum

### Test Naming Conventions

Follow conventions from `tasks-template.md`:
- `test_<function>_happy_path()` - Normal operation (e.g., `test_synthesis_happy_path()`)
- `test_<function>_error_<condition>()` - Error handling (e.g., `test_synthesis_error_model_load()`)
- `test_<function>_edge_<case>()` - Boundary conditions (e.g., `test_duration_matching_edge_extreme_speed()`)
- `test_<function>_integration_<workflow>()` - Integration scenarios (e.g., `test_synthesis_integration_voice_cloning()`)

## Phase 0: Research & Technical Decisions

### Research Questions Resolved

**1. Coqui TTS Library Integration**

**Decision**: Use Coqui TTS library with XTTS-v2 (quality mode) and VITS (fast mode) models

**Rationale**:
- Coqui TTS is the reference implementation from specs/sources/TTS.md
- XTTS-v2 supports multilingual synthesis and voice cloning
- VITS provides fast single-speaker synthesis for low-latency scenarios
- Library supports CPU-only execution (constitution requirement)
- Active community, good documentation, proven in production

**Alternatives Considered**:
- **pyttsx3**: Simpler but limited voice quality, no voice cloning, platform-dependent
- **gTTS (Google TTS API)**: External API dependency violates testability principle
- **Bark**: Newer but slower, higher memory usage, less mature
- **Tortoise TTS**: Better quality but too slow for real-time (5-10s per fragment)

**Implementation Notes**:
- Install via `pip install TTS` in apps/sts-service/requirements.txt
- Model loading: Use `TTS.utils.manage.ModelManager` for model discovery
- Voice cloning: `tts.tts_to_file(text, speaker_wav=voice_sample_path)`
- Fast mode: Separate VITS model initialization for single-speaker synthesis

---

**2. Duration Matching via Time-Stretch**

**Decision**: Use rubberband CLI tool for pitch-preserving time-stretch

**Rationale**:
- Rubberband is industry-standard for high-quality time-stretch
- Preserves pitch while changing duration (critical for natural speech)
- CLI interface simple to integrate via subprocess
- Configurable clamping prevents extreme artifacts
- Used successfully in reference implementation (specs/sources/TTS.md)

**Alternatives Considered**:
- **librosa time_stretch**: Pure Python but lower quality, slower
- **soundstretch (SoundTouch)**: Good quality but less flexible configuration
- **ffmpeg atempo filter**: Limited to 0.5x-2.0x range, less control
- **pydub speedup**: Changes pitch (unacceptable for speech)

**Implementation Notes**:
- Rubberband command: `rubberband -T {speed_factor} input.wav output.wav`
- Speed factor calculation: `speed_factor = baseline_duration / target_duration`
- Clamping: Default [0.5, 2.0], configurable per voice profile
- Error handling: If rubberband fails, return baseline audio with warning

---

**3. Text Preprocessing Strategy**

**Decision**: Deterministic preprocessing rules applied before synthesis

**Rationale**:
- Preprocessing significantly improves TTS quality and reduces failures
- Deterministic rules enable caching and reproducibility
- Reference implementation (specs/sources/TTS.md) provides proven patterns
- Preprocessing is fast (<1ms) and low risk

**Preprocessing Rules** (from reference implementation):
1. Normalize smart quotes → ASCII quotes (`"` → `"`, `'` → `'`)
2. Expand abbreviations: "NBA" → "N B A", "Dr." → "Doctor"
3. Rewrite score patterns: "15-12" → "15 to 12"
4. Normalize repeated punctuation: "!!!" → "!"
5. Strip excessive whitespace and normalize line breaks

**Implementation Notes**:
- Module: `apps/sts-service/src/sts_service/tts/preprocessing.py`
- Function: `preprocess_text_for_tts(text: str) -> str`
- Must be pure function (no side effects, deterministic)
- Record preprocessed text as asset for debugging

---

**4. Voice Configuration and Selection**

**Decision**: YAML configuration file with per-language model/voice mappings

**Rationale**:
- Configuration-driven voice selection enables runtime flexibility
- YAML format matches existing project conventions (MediaMTX config, etc.)
- Reference implementation uses similar voice config structure
- Env var override (TTS_VOICES_CONFIG) enables deployment-specific customization

**Configuration Structure** (`configs/coqui-voices.yaml`):
```yaml
languages:
  en:
    model: "tts_models/multilingual/multi-dataset/xtts_v2"
    fast_model: "tts_models/en/vctk/vits"  # optional
    default_speaker: "p225"  # for multi-speaker models
  es:
    model: "tts_models/multilingual/multi-dataset/xtts_v2"
    fast_model: "tts_models/es/css10/vits"
    default_speaker: null
  # ... additional languages
```

**Voice Selection Logic**:
1. Check `fast_mode` flag → use `fast_model` if available, else fallback to `model`
2. Check `voice_sample_asset_id` → enable voice cloning if valid (quality mode only)
3. Fallback to `default_speaker` if multi-speaker model and no voice sample
4. Validate model availability at component initialization (is_ready check)

---

**5. Error Classification for Retry Orchestration**

**Decision**: Structured error types with retryable flag for pipeline-level decisions

**Rationale**:
- TTS component classifies errors, orchestrator handles retries (separation of concerns)
- Reference ASR/Translation modules use same pattern (ASRError, TranslationError)
- Enables circuit breaker and fallback policies at pipeline level
- Improves debuggability with structured error types

**Error Types** (see `apps/sts-service/src/sts_service/tts/errors.py`):
- `TTSErrorType.MODEL_LOAD_FAILED` (retryable=True) - Model file unavailable or corrupt
- `TTSErrorType.SYNTHESIS_FAILED` (retryable=False) - Invalid text or synthesis crash
- `TTSErrorType.INVALID_INPUT` (retryable=False) - Empty text, invalid language code
- `TTSErrorType.VOICE_SAMPLE_INVALID` (retryable=False) - Voice cloning sample corrupt
- `TTSErrorType.ALIGNMENT_FAILED` (retryable=True) - Rubberband time-stretch failed
- `TTSErrorType.TIMEOUT` (retryable=True) - Processing exceeded deadline
- `TTSErrorType.UNKNOWN` (retryable=True) - Unclassified failure (safe default)

**Implementation Notes**:
- Return `TTSError` in AudioAsset.errors list
- Set AudioAsset.status = FAILED when errors present
- Orchestrator checks `asset.is_retryable` property for retry decision

---

**6. Model Caching and Performance**

**Decision**: In-memory model cache keyed by resolved model identifier, per worker lifetime

**Rationale**:
- Model loading is expensive (2-5 seconds for XTTS-v2)
- Per-stream workers process multiple fragments sequentially (constitution Principle I)
- In-memory cache simple and effective for single-worker scope
- No cross-worker coordination needed (each worker has isolated cache)

**Caching Strategy**:
- Cache key: `{model_name}_{language}` (e.g., "xtts_v2_en")
- Cache lifetime: Worker process lifetime (no eviction, models stay loaded)
- Cache invalidation: None (worker restart loads fresh models)
- Thread safety: Not required (workers are single-threaded per stream)

**Performance Targets** (from success criteria):
- First synthesis request: <5 seconds (includes model load)
- Subsequent requests: <2 seconds (cached model)
- Fast mode: 40% latency reduction vs quality mode

---

## Phase 1: Design & Contracts

### Data Model

See `specs/008-tts-module/data-model.md` for complete entity relationships and validation rules.

**Key Entities**:
- **AudioAsset**: Synthesized speech output with lineage, duration, format metadata
- **TextAsset**: Input text from Translation module (upstream dependency)
- **VoiceProfile**: Voice selection configuration (model, sample, speaker)
- **TTSMetrics**: Processing metrics (durations, speed factors, clamping flags)
- **TTSError**: Structured error classification (type, retryability, details)

### API Contracts

See `specs/008-tts-module/contracts/` directory for OpenAPI/JSON schemas.

**TTSComponent Interface** (contracts/tts-component.yaml):
- `synthesize(text_asset, voice_profile, target_duration_ms, ...) -> AudioAsset`
- `is_ready() -> bool`
- `component_name` property (always "tts")
- `component_instance` property (e.g., "coqui-xtts-v2")
- `shutdown()` method for cleanup

**AudioAsset Schema** (contracts/audio-asset-schema.json):
- Pydantic model with strict validation
- Required fields: asset_id, stream_id, sequence_number, audio_format, sample_rate_hz, channels, duration_ms
- Optional fields: payload_ref, parent_asset_ids, processing_time_ms, errors
- Validation: sample_rate_hz in [8000, 16000, 24000, 44100, 48000], channels in [1, 2]

**TTSConfig Schema** (contracts/tts-config-schema.json):
- Voice configuration structure
- Model paths and fallback rules
- Duration matching parameters (clamping range, only_speed_up flag)
- Debug artifact flags

### Implementation Milestones

**Milestone 1: Basic Synthesis (Quality Mode)**
- Implement TTSComponent interface protocol
- Implement CoquiTTSComponent with XTTS-v2 model
- Basic synthesis without voice cloning or duration matching
- AudioAsset generation with lineage tracking
- Unit tests: interface, models, basic synthesis
- Contract tests: AudioAsset schema validation

**Milestone 2: Duration Matching**
- Implement duration_matching.py module with rubberband integration
- Speed factor calculation and clamping logic
- Sample rate and channel alignment
- TTSMetrics asset generation
- Unit tests: duration calculations, clamping, edge cases
- Integration tests: rubberband subprocess execution

**Milestone 3: Voice Selection**
- Implement voice_selection.py module with YAML config loading
- Fast mode support with VITS model
- Voice cloning with voice sample validation
- Named speaker fallback logic
- Model caching implementation
- Unit tests: voice selection logic, config parsing
- Integration tests: model loading, cache verification

**Milestone 4: Text Preprocessing & Error Handling**
- Implement preprocessing.py with deterministic rules
- Implement errors.py with error classification
- Error handling in CoquiTTSComponent
- Factory pattern with create_tts_component()
- Mock implementations (MockTTSFixedTone, MockTTSFromFixture, MockTTSFailOnce)
- Unit tests: preprocessing rules, error classification
- Contract tests: TTSComponent contract compliance

### Agent Context Update

Run `.specify/scripts/bash/update-agent-context.sh claude` to add TTS-specific technologies to CLAUDE.md:

**Technologies to Add**:
- TTS (Coqui TTS library) - multilingual synthesis with XTTS-v2 and VITS models
- rubberband - pitch-preserving time-stretch for duration matching
- pydub - audio format conversion and channel alignment
- numpy - audio data manipulation (PCM byte arrays)
- YAML configuration - voice/model selection (configs/coqui-voices.yaml)

**Storage to Add**:
- In-memory model cache (per worker lifetime, keyed by model_name + language)
- Optional debug artifacts (local filesystem, controlled by debug_artifacts flag)

## Quickstart

See `specs/008-tts-module/quickstart.md` for detailed setup and usage instructions.

**Quick Setup** (for developers):
```bash
# Install TTS component dependencies
cd apps/sts-service
pip install -r requirements.txt  # includes TTS library

# Install rubberband (system dependency)
# macOS: brew install rubberband
# Ubuntu: apt-get install rubberband-cli

# Configure voice models (optional, uses defaults if not set)
export TTS_VOICES_CONFIG=/path/to/configs/coqui-voices.yaml

# Run unit tests
pytest tests/unit/tts/ --cov=apps/sts-service/src/sts_service/tts
```

**Usage Example**:
```python
from sts_service.tts.factory import create_tts_component
from sts_service.translation.models import TextAsset

# Create TTS component (loads models on first use)
tts = create_tts_component(provider="coqui", fast_mode=False)

# Check readiness
assert tts.is_ready

# Synthesize from TextAsset
text_asset = TextAsset(
    stream_id="stream-123",
    sequence_number=42,
    text="Hello world",
    language="en",
    # ... other fields
)

audio_asset = tts.synthesize(
    text_asset=text_asset,
    target_duration_ms=2000,
    output_sample_rate_hz=16000,
    output_channels=1,
    voice_profile={"use_cloning": False},
)

# Check result
assert audio_asset.status == "success"
print(f"Duration: {audio_asset.duration_ms}ms")
print(f"Lineage: {audio_asset.parent_asset_ids}")
```

## Complexity Tracking

**No violations** - This implementation follows all constitution principles without exceptions. The TTS module integrates cleanly into the existing STS service structure using established patterns from ASR and Translation modules.

## Next Steps

1. **Generate Tasks** (`speckit.tasks`): Break this plan into actionable tasks with TDD workflow
2. **Generate Checklist** (`speckit.checklist`): Create feature-specific validation checklist
3. **Implement Milestone 1**: Basic synthesis with TTS component interface and tests
4. **Implement Milestone 2**: Duration matching with rubberband integration
5. **Implement Milestone 3**: Voice selection, fast mode, and model caching
6. **Implement Milestone 4**: Text preprocessing and error classification
