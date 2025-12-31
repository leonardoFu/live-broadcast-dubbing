# Tasks: TTS Audio Synthesis Module

**Input**: Design documents from `/specs/008-tts-module/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This project follows the Python monorepo structure:
- **TTS Module**: `apps/sts-service/src/sts_service/tts/`
- **Tests**: `apps/sts-service/tests/unit/tts/`, `apps/sts-service/tests/contract/tts/`
- **Config**: `apps/sts-service/configs/coqui-voices.yaml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic TTS module structure

- [ ] T001 Create TTS module directory structure at apps/sts-service/src/sts_service/tts/
- [ ] T002 [P] Create empty __init__.py files in apps/sts-service/src/sts_service/tts/ and test directories
- [ ] T003 [P] Create test directory structure apps/sts-service/tests/unit/tts/ and apps/sts-service/tests/contract/tts/
- [ ] T004 [P] Add TTS library dependency (TTS>=0.22.0) to apps/sts-service/requirements.txt
- [ ] T005 [P] Add rubberband-cli system dependency documentation to apps/sts-service/README.md
- [ ] T006 [P] Create voice configuration file apps/sts-service/configs/coqui-voices.yaml with English and Spanish defaults

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core interfaces and models that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Create TTSComponent protocol in apps/sts-service/src/sts_service/tts/interface.py
- [ ] T008 [P] Create AudioAsset model in apps/sts-service/src/sts_service/tts/models.py
- [ ] T009 [P] Create TTSConfig model in apps/sts-service/src/sts_service/tts/models.py
- [ ] T010 [P] Create VoiceProfile model in apps/sts-service/src/sts_service/tts/models.py
- [ ] T011 [P] Create AudioFormat and AudioStatus enums in apps/sts-service/src/sts_service/tts/models.py
- [ ] T012 [P] Create TTSErrorType enum and TTSError model in apps/sts-service/src/sts_service/tts/errors.py
- [ ] T013 Create factory function create_tts_component() skeleton in apps/sts-service/src/sts_service/tts/factory.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Basic Text-to-Speech Conversion (Priority: P1) 🎯 MVP

**Goal**: Core TTS capability - convert translated text into synthesized speech audio

**Independent Test**: Test TTS component in isolation with mock text inputs
- Unit test validates text input produces valid audio output
- Contract test validates AudioAsset output structure
- Integration test validates TTS receives TextAsset and produces AudioAsset

### Tests for User Story 1 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US1**: 80% minimum (95% for synthesis critical path)

- [ ] T014 [P] [US1] **Unit test** for TTSComponent interface contract in apps/sts-service/tests/unit/tts/test_interface.py
  - Test protocol compliance for synthesize() method
  - Test is_ready() method returns bool
  - Test component_name and component_instance properties
- [ ] T015 [P] [US1] **Unit test** for AudioAsset model validation in apps/sts-service/tests/unit/tts/test_models.py
  - Test valid AudioAsset creation with required fields
  - Test sample_rate_hz validation (must be in allowed list)
  - Test channels validation (must be 1 or 2)
  - Test duration_ms validation (must be > 0)
  - Test payload_ref format validation
- [ ] T016 [P] [US1] **Contract test** for AudioAsset schema in apps/sts-service/tests/contract/tts/test_audio_asset_schema.py
  - Test AudioAsset JSON serialization matches schema
  - Test parent_asset_ids linkage to TextAsset
  - Test asset lineage tracking (component, component_instance)
- [ ] T017 [P] [US1] **Unit test** for MockTTSFixedTone in apps/sts-service/tests/unit/tts/test_mock.py
  - Test mock produces deterministic 440Hz tone
  - Test mock respects target_duration_ms parameter
  - Test mock returns valid AudioAsset structure
- [ ] T018 [P] [US1] **Integration test** for basic synthesis workflow in apps/sts-service/tests/unit/tts/test_coqui_provider.py
  - Test CoquiTTSComponent receives TextAsset and produces AudioAsset
  - Test synthesis with English text produces valid audio
  - Test synthesis with Spanish text produces valid audio
- [ ] T018b [US1] **Integration test** for Translation → TTS handoff in apps/sts-service/tests/integration/test_translation_tts.py
  - Test TTS component receives TextAsset from Translation module
  - Test AudioAsset.parent_asset_ids contains TextAsset.asset_id
  - Test language metadata flows correctly from TextAsset to AudioAsset
  - Test stream_id and sequence_number consistency between TextAsset and AudioAsset

**Verification**: Run `pytest apps/sts-service/tests/unit/tts/test_interface.py` - ALL tests MUST FAIL with NotImplementedError

### Implementation for User Story 1

- [ ] T019 [P] [US1] Implement BaseTTSComponent abstract class in apps/sts-service/src/sts_service/tts/interface.py
- [ ] T020 [P] [US1] Implement MockTTSFixedTone in apps/sts-service/src/sts_service/tts/mock.py
- [ ] T021 [US1] Implement CoquiTTSComponent skeleton in apps/sts-service/src/sts_service/tts/coqui_provider.py
- [ ] T022 [US1] Implement basic synthesis logic in CoquiTTSComponent.synthesize() using XTTS-v2 model
- [ ] T023 [US1] Implement model loading and caching in CoquiTTSComponent.__init__()
- [ ] T024 [US1] Implement AudioAsset generation with lineage tracking in CoquiTTSComponent.synthesize()
- [ ] T025 [US1] Implement is_ready() method checking model availability in CoquiTTSComponent
- [ ] T026 [US1] Update factory.py to support provider="coqui" and provider="mock"
- [ ] T027 [US1] Export public API in apps/sts-service/src/sts_service/tts/__init__.py

**Checkpoint**: User Story 1 should be fully functional - basic synthesis works with quality mode

---

## Phase 4: User Story 2 - Duration Matching for Live Streams (Priority: P2)

**Goal**: Time-stretch synthesized speech to match original audio fragment duration for A/V sync

**Independent Test**: Test duration alignment with known input/target durations
- Unit test validates audio is sped up when synthesis is longer than target
- Contract test validates duration metadata is correctly recorded
- Integration test validates synthesized audio matches target duration within 50ms

### Tests for User Story 2 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US2**: 95% (duration matching is critical path for A/V sync)

- [ ] T028 [P] [US2] **Unit test** for speed factor calculation in apps/sts-service/tests/unit/tts/test_duration_matching.py
  - Test speed_factor = baseline_duration / target_duration calculation
  - Test clamping to [0.5, 2.0] range (default)
  - Test clamping to custom range from VoiceProfile
  - Test only_speed_up flag (never slow down)
- [ ] T029 [P] [US2] **Unit test** for time-stretch edge cases in apps/sts-service/tests/unit/tts/test_duration_matching.py
  - Test extreme speed (>2x) triggers clamping warning
  - Test target_duration_ms == baseline_duration_ms skips time-stretch
  - Test zero or negative target_duration_ms raises ValueError
- [ ] T030 [P] [US2] **Unit test** for sample rate alignment in apps/sts-service/tests/unit/tts/test_duration_matching.py
  - Test resampling from 24kHz to 16kHz output
  - Test resampling from 16kHz to 48kHz output
  - Test no resampling when rates match
- [ ] T031 [P] [US2] **Unit test** for channel alignment in apps/sts-service/tests/unit/tts/test_duration_matching.py
  - Test mono to stereo conversion
  - Test stereo to mono conversion (average channels)
  - Test no conversion when channels match
- [ ] T032 [P] [US2] **Contract test** for TTSMetrics in apps/sts-service/tests/contract/tts/test_tts_metrics.py
  - Test TTSMetrics includes baseline_duration_ms, target_duration_ms, final_duration_ms
  - Test speed_factor_applied and speed_factor_clamped flags
  - Test alignment_time_ms tracking
- [ ] T033 [US2] **Integration test** for rubberband subprocess in apps/sts-service/tests/unit/tts/test_duration_matching.py
  - Test rubberband command execution with valid audio
  - Test rubberband failure handling (subprocess crash)
  - Test pitch preservation after time-stretch

**Verification**: Run `pytest apps/sts-service/tests/unit/tts/test_duration_matching.py` - ALL tests MUST FAIL before implementation

### Implementation for User Story 2

- [ ] T034 [P] [US2] Create TTSMetrics model in apps/sts-service/src/sts_service/tts/models.py
- [ ] T035 [US2] Implement calculate_speed_factor() in apps/sts-service/src/sts_service/tts/duration_matching.py
- [ ] T036 [US2] Implement apply_clamping() in apps/sts-service/src/sts_service/tts/duration_matching.py
- [ ] T037 [US2] Implement time_stretch_audio() using rubberband CLI in apps/sts-service/src/sts_service/tts/duration_matching.py
- [ ] T038 [US2] Implement resample_audio() for sample rate alignment in apps/sts-service/src/sts_service/tts/duration_matching.py
- [ ] T039 [US2] Implement align_channels() for mono/stereo conversion in apps/sts-service/src/sts_service/tts/duration_matching.py
- [ ] T040 [US2] Integrate duration matching into CoquiTTSComponent.synthesize() workflow
- [ ] T041 [US2] Add TTSMetrics emission alongside AudioAsset in CoquiTTSComponent.synthesize()
- [ ] T042 [US2] Add rubberband error handling with fallback strategy:
  - On rubberband subprocess failure: use baseline (unaligned) audio as output
  - Set AudioAsset.status = PARTIAL (audio produced but not aligned)
  - Add TTSError with error_type=ALIGNMENT_FAILED, retryable=True
  - Record original baseline_duration_ms in TTSMetrics (no speed_factor_applied)
  - Log warning for observability, do NOT fail the entire synthesis

**Checkpoint**: User Stories 1 AND 2 should both work - synthesis with duration matching functional

---

## Phase 5: User Story 3 - Voice Selection and Quality Modes (Priority: P3)

**Goal**: Support multiple synthesis modes (quality vs fast) and voice profiles for quality/latency tradeoffs

**Independent Test**: Test voice selection logic and model switching
- Unit test validates fast model is selected when fast_mode enabled
- Unit test validates voice cloning is used when voice sample provided
- Integration test validates models are cached and reused

### Tests for User Story 3 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US3**: 80% minimum

- [ ] T043 [P] [US3] **Unit test** for voice selection logic in apps/sts-service/tests/unit/tts/test_voice_selection.py
  - Test fast_mode=True selects VITS model from config
  - Test fast_mode=False selects XTTS-v2 model from config
  - Test fallback to standard model when fast_model unavailable
  - Test explicit model_name override in VoiceProfile
- [ ] T044 [P] [US3] **Unit test** for voice cloning activation in apps/sts-service/tests/unit/tts/test_voice_selection.py
  - Test use_voice_cloning=True with valid voice_sample_path activates cloning
  - Test use_voice_cloning=True with invalid voice_sample_path falls back to speaker
  - Test voice cloning disabled in fast mode (VITS does not support cloning)
- [ ] T045 [P] [US3] **Unit test** for speaker selection in apps/sts-service/tests/unit/tts/test_voice_selection.py
  - Test speaker_name from VoiceProfile is used for multi-speaker models
  - Test fallback to default_speaker from config when speaker_name not set
  - Test single-speaker models ignore speaker_name
- [ ] T046 [P] [US3] **Unit test** for config loading in apps/sts-service/tests/unit/tts/test_voice_selection.py
  - Test load_voice_config() parses YAML correctly
  - Test TTS_VOICES_CONFIG env var override
  - Test config validation (required fields present)
- [ ] T047 [US3] **Integration test** for model caching in apps/sts-service/tests/unit/tts/test_coqui_provider.py
  - Test first synthesis loads model (slower)
  - Test second synthesis reuses cached model (faster)
  - Test different languages load separate cached models

**Verification**: Run `pytest apps/sts-service/tests/unit/tts/test_voice_selection.py` - ALL tests MUST FAIL before implementation

### Implementation for User Story 3

- [ ] T048 [P] [US3] Implement load_voice_config() in apps/sts-service/src/sts_service/tts/voice_selection.py
- [ ] T049 [P] [US3] Implement select_model() based on fast_mode and language in apps/sts-service/src/sts_service/tts/voice_selection.py
- [ ] T050 [P] [US3] Implement select_voice() for cloning vs speaker selection in apps/sts-service/src/sts_service/tts/voice_selection.py
- [ ] T051 [P] [US3] Implement validate_voice_sample() for voice cloning validation in apps/sts-service/src/sts_service/tts/voice_selection.py
  - Validate format: WAV only (reject MP3, FLAC, etc.)
  - Validate channels: Mono (1 channel) required
  - Validate sample rate: Minimum 16kHz (22050Hz or 24000Hz preferred)
  - Validate duration: Between 3 and 30 seconds
  - Return TTSError with error_type=VOICE_SAMPLE_INVALID on failure (retryable=False)
- [ ] T052 [US3] Add model caching logic to CoquiTTSComponent (keyed by model_name + language)
- [ ] T053 [US3] Integrate select_model() into CoquiTTSComponent.synthesize() workflow
- [ ] T054 [US3] Integrate select_voice() into CoquiTTSComponent.synthesize() workflow
- [ ] T055 [US3] Add fast mode support with VITS model initialization in CoquiTTSComponent
- [ ] T056 [US3] Add voice cloning support with speaker_wav parameter in CoquiTTSComponent
- [ ] T057 [US3] Update TTSMetrics to track model_used, voice_cloning_active, fast_mode_active
- [ ] T058 [US3] Update AudioAsset to include voice_cloning_used flag

**Checkpoint**: All synthesis modes working - quality mode, fast mode, voice cloning functional

---

## Phase 6: User Story 4 - Text Preprocessing for TTS Quality (Priority: P4)

**Goal**: Preprocess text before synthesis to normalize punctuation, expand abbreviations, improve quality

**Independent Test**: Test preprocessing rules independently
- Unit test validates smart quotes are normalized to ASCII
- Unit test validates abbreviations expand correctly
- Unit test validates score patterns rewrite correctly

### Tests for User Story 4 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US4**: 80% minimum (deterministic rules, straightforward testing)

- [ ] T059 [P] [US4] **Unit test** for punctuation normalization in apps/sts-service/tests/unit/tts/test_preprocessing.py
  - Test smart quotes "" converted to ASCII ""
  - Test smart apostrophes ' converted to ASCII '
  - Test ellipsis … converted to ...
  - Test em dash — converted to --
- [ ] T060 [P] [US4] **Unit test** for abbreviation expansion in apps/sts-service/tests/unit/tts/test_preprocessing.py
  - Test "NBA" expands to "N B A"
  - Test "Dr." expands to "Doctor"
  - Test "PhD" expands to "P H D"
  - Test custom abbreviations from config
- [ ] T061 [P] [US4] **Unit test** for score pattern rewriting in apps/sts-service/tests/unit/tts/test_preprocessing.py
  - Test "15-12" converts to "15 to 12"
  - Test "3-0" converts to "3 to 0"
  - Test hyphenated words not affected (e.g., "well-known")
- [ ] T062 [P] [US4] **Unit test** for whitespace normalization in apps/sts-service/tests/unit/tts/test_preprocessing.py
  - Test multiple spaces reduced to single space
  - Test leading/trailing whitespace stripped
  - Test newlines normalized to spaces
- [ ] T063 [P] [US4] **Unit test** for determinism in apps/sts-service/tests/unit/tts/test_preprocessing.py
  - Test same input produces same output (100 iterations)
  - Test preprocessing is pure function (no side effects)

**Verification**: Run `pytest apps/sts-service/tests/unit/tts/test_preprocessing.py` - ALL tests MUST FAIL before implementation

### Implementation for User Story 4

- [ ] T064 [P] [US4] Implement normalize_punctuation() in apps/sts-service/src/sts_service/tts/preprocessing.py
- [ ] T065 [P] [US4] Implement expand_abbreviations() in apps/sts-service/src/sts_service/tts/preprocessing.py
- [ ] T066 [P] [US4] Implement rewrite_score_patterns() in apps/sts-service/src/sts_service/tts/preprocessing.py
- [ ] T067 [P] [US4] Implement normalize_whitespace() in apps/sts-service/src/sts_service/tts/preprocessing.py
- [ ] T068 [US4] Implement preprocess_text_for_tts() main function in apps/sts-service/src/sts_service/tts/preprocessing.py
- [ ] T069 [US4] Integrate preprocessing into CoquiTTSComponent.synthesize() before synthesis
- [ ] T070 [US4] Add preprocessed_text field to AudioAsset for debugging
- [ ] T071 [US4] Add preprocess_time_ms to TTSMetrics tracking

**Checkpoint**: Text preprocessing functional - synthesis quality improved

---

## Phase 7: User Story 5 - Error Handling and Fallbacks (Priority: P5)

**Goal**: Handle synthesis failures gracefully with structured error classification for retry/fallback decisions

**Independent Test**: Test error classification and recovery
- Unit test validates model load errors are retryable
- Unit test validates synthesis failures return structured error
- Integration test validates retry logic for retryable errors

### Tests for User Story 5 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US5**: 80% minimum

- [ ] T072 [P] [US5] **Unit test** for error classification in apps/sts-service/tests/unit/tts/test_errors.py
  - Test MODEL_LOAD_FAILED classified as retryable
  - Test SYNTHESIS_FAILED classified as non-retryable
  - Test INVALID_INPUT classified as non-retryable
  - Test VOICE_SAMPLE_INVALID classified as non-retryable
  - Test ALIGNMENT_FAILED classified as retryable
  - Test TIMEOUT classified as retryable
  - Test UNKNOWN classified as retryable (safe default)
- [ ] T073 [P] [US5] **Unit test** for TTSError model in apps/sts-service/tests/unit/tts/test_errors.py
  - Test TTSError creation with error_type, message, retryable
  - Test TTSError includes optional details dict
  - Test message field is non-empty
- [ ] T074 [P] [US5] **Unit test** for AudioAsset error handling in apps/sts-service/tests/unit/tts/test_models.py
  - Test AudioAsset.status = FAILED when errors list non-empty
  - Test AudioAsset.has_errors property returns True when errors present
  - Test AudioAsset.is_retryable property checks error retryability
- [ ] T075 [P] [US5] **Unit test** for MockTTSFailOnce in apps/sts-service/tests/unit/tts/test_mock.py
  - Test first call per sequence_number returns FAILED status with retryable error
  - Test second call per sequence_number returns SUCCESS status with valid audio
- [ ] T076 [US5] **Integration test** for error recovery in apps/sts-service/tests/unit/tts/test_coqui_provider.py
  - Test empty text input raises INVALID_INPUT error
  - Test invalid language code raises SYNTHESIS_FAILED error
  - Test model load failure raises MODEL_LOAD_FAILED error

**Verification**: Run `pytest apps/sts-service/tests/unit/tts/test_errors.py` - ALL tests MUST FAIL before implementation

### Implementation for User Story 5

- [ ] T077 [P] [US5] Implement classify_error() helper in apps/sts-service/src/sts_service/tts/errors.py
- [ ] T078 [P] [US5] Implement MockTTSFailOnce in apps/sts-service/src/sts_service/tts/mock.py
- [ ] T079 [P] [US5] Implement MockTTSFromFixture in apps/sts-service/src/sts_service/tts/mock.py
- [ ] T080 [US5] Add input validation to CoquiTTSComponent.synthesize() (empty text, invalid language)
- [ ] T081 [US5] Add try/except error handling around model loading in CoquiTTSComponent
- [ ] T082 [US5] Add try/except error handling around synthesis call in CoquiTTSComponent
- [ ] T083 [US5] Add try/except error handling around duration matching in CoquiTTSComponent
- [ ] T084 [US5] Add error classification and TTSError creation in exception handlers
- [ ] T085 [US5] Update AudioAsset with errors list and status=FAILED on failure
- [ ] T086 [US5] Implement has_errors and is_retryable computed properties on AudioAsset

**Checkpoint**: All user stories complete - TTS module fully functional with robust error handling

---

## Test Organization Standards

### Directory Structure
```
apps/sts-service/
├── src/
│   └── sts_service/
│       ├── asr/                 # Reference pattern
│       ├── translation/         # Reference pattern
│       └── tts/                 # NEW: This feature
│           ├── __init__.py
│           ├── interface.py
│           ├── models.py
│           ├── errors.py
│           ├── factory.py
│           ├── mock.py
│           ├── coqui_provider.py
│           ├── preprocessing.py
│           ├── duration_matching.py
│           └── voice_selection.py
│
├── configs/
│   └── coqui-voices.yaml        # Voice configuration
│
└── tests/
    ├── conftest.py              # Shared fixtures
    ├── unit/
    │   └── tts/                 # NEW: Unit tests
    │       ├── __init__.py
    │       ├── test_interface.py
    │       ├── test_models.py
    │       ├── test_errors.py
    │       ├── test_preprocessing.py
    │       ├── test_duration_matching.py
    │       ├── test_voice_selection.py
    │       ├── test_mock.py
    │       └── test_coqui_provider.py
    │
    └── contract/
        └── tts/                 # NEW: Contract tests
            ├── __init__.py
            ├── test_audio_asset_schema.py
            └── test_tts_metrics.py
```

### Naming Conventions

**Test Files**:
- `test_<module>.py` - Tests for a specific module

**Test Functions**:
- `test_<function>_happy_path()` - Normal operation
- `test_<function>_error_<condition>()` - Error handling
- `test_<function>_edge_<case>()` - Boundary conditions
- `test_<function>_integration_<workflow>()` - Integration scenarios

**Examples**:
```python
# Unit test
def test_synthesize_happy_path():
    """Test synthesis with valid text input."""
    pass

# Error case
def test_synthesize_error_empty_text():
    """Test synthesis raises INVALID_INPUT error for empty text."""
    pass

# Edge case
def test_duration_matching_edge_extreme_speed():
    """Test duration matching clamps extreme speed factors."""
    pass

# Integration test
def test_coqui_integration_voice_cloning():
    """Test XTTS-v2 model with voice cloning enabled."""
    pass
```

### Fixture Organization

**apps/sts-service/tests/conftest.py** (add TTS fixtures):
```python
"""Module-level test fixtures."""
import pytest

@pytest.fixture
def sample_text_asset():
    """Provide deterministic TextAsset for TTS testing."""
    from sts_service.translation.models import TextAsset
    return TextAsset(
        asset_id="text-uuid-test",
        stream_id="test-stream",
        sequence_number=1,
        text="Hello world, this is a test.",
        language="en",
    )

@pytest.fixture
def sample_voice_profile():
    """Provide default VoiceProfile for testing."""
    return {
        "language": "en",
        "fast_mode": False,
        "use_voice_cloning": False,
        "speed_clamp_min": 0.5,
        "speed_clamp_max": 2.0,
        "only_speed_up": True,
    }

@pytest.fixture
def sample_pcm_audio():
    """Provide deterministic PCM audio (1 second silence at 16kHz, mono)."""
    return b'\x00\x00' * 16000
```

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T087 [P] Update apps/sts-service/README.md with TTS module documentation
- [ ] T088 [P] Add inline documentation (docstrings) to all public APIs in tts/ module
- [ ] T089 [P] Run ruff format and lint on all TTS module files
- [ ] T090 [P] Run mypy type checking on TTS module
- [ ] T091 [P] Validate quickstart.md usage instructions with real synthesis
- [ ] T092 [P] Add performance benchmarks for synthesis latency (optional)
- [ ] T093 Code cleanup and refactoring based on test coverage report
- [ ] T094 Security review - ensure no secrets in error messages or logs

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Integrates with US1 but independently testable
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Integrates with all stories but independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
pytest apps/sts-service/tests/unit/tts/test_interface.py &
pytest apps/sts-service/tests/unit/tts/test_models.py &
pytest apps/sts-service/tests/contract/tts/test_audio_asset_schema.py &

# Launch all models/mocks for User Story 1 together:
# (After tests are written and failing)
# Edit apps/sts-service/src/sts_service/tts/interface.py &
# Edit apps/sts-service/src/sts_service/tts/models.py &
# Edit apps/sts-service/src/sts_service/tts/mock.py &
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Basic synthesis)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP: Basic synthesis works!)
3. Add User Story 2 → Test independently → Deploy/Demo (Duration matching for A/V sync!)
4. Add User Story 3 → Test independently → Deploy/Demo (Voice modes and quality options!)
5. Add User Story 4 → Test independently → Deploy/Demo (Better synthesis quality!)
6. Add User Story 5 → Test independently → Deploy/Demo (Production-ready error handling!)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Basic synthesis)
   - Developer B: User Story 2 (Duration matching)
   - Developer C: User Story 3 (Voice selection)
   - Developer D: User Story 4 (Preprocessing)
   - Developer E: User Story 5 (Error handling)
3. Stories complete and integrate independently

---

## Task Summary

- **Total Tasks**: 95
- **Setup Tasks**: 6
- **Foundational Tasks**: 7
- **User Story 1 Tasks**: 15 (6 tests + 9 implementation) - includes T018b Translation→TTS integration test
- **User Story 2 Tasks**: 15 (6 tests + 9 implementation)
- **User Story 3 Tasks**: 16 (5 tests + 11 implementation)
- **User Story 4 Tasks**: 13 (5 tests + 8 implementation)
- **User Story 5 Tasks**: 15 (5 tests + 10 implementation)
- **Polish Tasks**: 8

**Parallelizable Tasks**: 61 (marked with [P])
**Test Tasks**: 27 (mandatory TDD)
**Implementation Tasks**: 61

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD requirement)
- Commit after each task or logical group
- Checkpoints are informational - run automated tests to validate, then continue automatically
- Reference implementations: apps/sts-service/src/sts_service/asr/ and translation/ modules
- Follow existing patterns for interface.py, models.py, factory.py, mock.py structure
