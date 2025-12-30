# Tasks: Audio Transcription Module (ASR Component)

**Feature**: 005-audio-transcription-module
**Generated**: 2025-12-28
**Branch**: `feature2`
**Plan Reference**: `specs/005-audio-transcription-module/plan.md`

---

## Task Summary

| Phase | Task Count | Parallelizable |
|-------|------------|----------------|
| Phase 0: Setup | 3 | 2 |
| Phase 1: Foundation (Models + Interface) | 4 | 2 |
| Phase 2: Preprocessing + Postprocessing | 8 | 4 |
| Phase 3: Mock Implementation | 2 | 0 |
| Phase 4: Real Implementation | 6 | 2 |
| Phase 5: Integration with Fixtures | 4 | 2 |
| Phase 6: Public API + Documentation | 2 | 0 |
| **Total** | **29** | **12** |

---

## Phase 0: Setup

### T001: Create ASR package directory structure
- [ ] **Task**: Create the ASR subpackage directory structure under sts-service
- **Dependencies**: None
- **Test Requirements**: N/A (infrastructure)
- **Files**:
  - `apps/sts-service/src/sts_service/asr/__init__.py`
  - `apps/sts-service/tests/unit/asr/__init__.py`
  - `apps/sts-service/tests/integration/asr/__init__.py`
- **Acceptance Criteria**:
  - All directories exist with `__init__.py` files
  - Package importable as `from sts_service import asr`

### T002: Update sts-service pyproject.toml with ASR dependencies
- [ ] **Task**: Add faster-whisper and audio processing dependencies
- **Dependencies**: T001
- **Test Requirements**: N/A (configuration)
- **Files**:
  - `apps/sts-service/pyproject.toml`
  - `apps/sts-service/requirements.txt`
  - `apps/sts-service/requirements-dev.txt`
- **Dependencies to Add**:
  ```
  faster-whisper>=1.0.0
  numpy<2.0
  scipy>=1.10.0
  soundfile>=0.12.0
  pydantic>=2.0.0
  ```
- **Acceptance Criteria**:
  - `pip install -e apps/sts-service` succeeds
  - All dependencies resolvable

### T003: Create shared test fixtures conftest.py
- [ ] **Task**: Create pytest conftest with audio fixture loaders
- **Dependencies**: T001
- **Test Requirements**: N/A (test infrastructure)
- **Files**:
  - `apps/sts-service/tests/integration/asr/conftest.py`
- **Fixtures to Provide**:
  - `nfl_audio_path` -> Path to `tests/fixtures/test-streams/1-min-nfl.m4a`
  - `nfl_video_path` -> Path to `tests/fixtures/test-streams/1-min-nfl.mp4`
  - `bunny_video_path` -> Path to `tests/fixtures/test-streams/big-buck-bunny.mp4`
  - `load_audio_fragment(path, start_ms, duration_ms)` -> bytes
- **Acceptance Criteria**:
  - Fixtures accessible in integration tests
  - Audio loading returns valid PCM float32 bytes

---

## Phase 1: Foundation (Models + Interface)

### T004: Write tests for Pydantic models
- [ ] **Task**: Write comprehensive unit tests for all Pydantic models FIRST (TDD)
- **Dependencies**: T001
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_models.py`
- **Test Cases**:
  - `test_audio_fragment_valid_creation()`
  - `test_audio_fragment_duration_property()`
  - `test_audio_fragment_sample_rate_bounds()`
  - `test_audio_fragment_invalid_times_rejected()`
  - `test_word_timing_valid_creation()`
  - `test_word_timing_confidence_bounds()`
  - `test_transcript_segment_valid_creation()`
  - `test_transcript_segment_duration_property()`
  - `test_transcript_segment_with_words()`
  - `test_asr_error_types_enum()`
  - `test_asr_error_retryable_flag()`
  - `test_transcript_asset_valid_creation()`
  - `test_transcript_asset_total_text_property()`
  - `test_transcript_asset_average_confidence_empty()`
  - `test_transcript_asset_average_confidence_multiple()`
  - `test_transcript_asset_is_retryable_logic()`
  - `test_transcript_status_success_conditions()`
  - `test_transcript_status_partial_conditions()`
  - `test_transcript_status_failed_conditions()`
  - `test_asr_config_defaults()`
  - `test_asr_model_config_pattern_validation()`
  - `test_vad_config_bounds()`
  - `test_transcription_config_defaults()`
  - `test_asr_metrics_required_fields()`
- **Acceptance Criteria**:
  - All tests written and FAILING (no implementation yet)
  - 100% coverage of model fields and constraints

### T005: Implement Pydantic data models
- [ ] **Task**: Implement all Pydantic models from data-model.md
- **Dependencies**: T004 (tests written first)
- **Test Requirements**: All T004 tests must PASS after implementation
- **Files**:
  - `apps/sts-service/src/sts_service/asr/models.py`
- **Models to Implement**:
  - `AudioFormat` (Enum)
  - `AudioFragment` (Input model)
  - `WordTiming` (Word-level timing)
  - `TranscriptSegment` (Output segment)
  - `ASRErrorType` (Enum)
  - `ASRError` (Error model)
  - `TranscriptStatus` (Enum)
  - `AssetIdentifiers` (Base identifiers)
  - `TranscriptAsset` (Complete output)
  - `ASRModelConfig`, `VADConfig`, `TranscriptionConfig`
  - `UtteranceShapingConfig`, `ASRConfig`
  - `ASRMetrics` (Observability)
- **Acceptance Criteria**:
  - All T004 tests pass
  - Models match data-model.md specification exactly
  - JSON schema export works

### T006: Write tests for ASR interface
- [ ] **Task**: Write tests for interface protocol compliance (TDD)
- **Dependencies**: T005
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_interface.py`
- **Test Cases**:
  - `test_asr_component_protocol_has_required_methods()`
  - `test_asr_component_protocol_is_runtime_checkable()`
  - `test_base_asr_component_is_abstract()`
  - `test_base_asr_component_default_shutdown()`
- **Acceptance Criteria**:
  - Tests define protocol contract
  - Tests FAIL initially (no implementation)

### T007: Implement ASR interface
- [ ] **Task**: Implement ASRComponent protocol and BaseASRComponent
- **Dependencies**: T005, T006
- **Test Requirements**: All T006 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/interface.py`
- **Components**:
  - `ASRComponent` Protocol (runtime_checkable)
  - `BaseASRComponent` Abstract base class
  - `AudioPayloadRef` type alias
  - `AudioPayloadStore` Protocol
- **Acceptance Criteria**:
  - All T006 tests pass
  - Interface matches contracts/asr-interface.py specification

---

## Phase 2: Preprocessing + Postprocessing

### T008: Write tests for audio preprocessing
- [ ] **Task**: Write comprehensive tests for preprocessing functions (TDD)
- **Dependencies**: T005
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_preprocessing.py`
- **Test Cases**:
  - `test_preprocess_audio_returns_numpy_array()`
  - `test_preprocess_audio_normalizes_amplitude()`
  - `test_preprocess_audio_applies_highpass_filter()`
  - `test_preprocess_audio_applies_preemphasis()`
  - `test_preprocess_audio_resamples_to_16khz()`
  - `test_preprocess_audio_handles_stereo_to_mono()`
  - `test_preprocess_audio_preserves_duration()`
  - `test_preprocess_audio_invalid_sample_rate_error()`
  - `test_highpass_filter_removes_low_frequencies()`
  - `test_preemphasis_coefficient_default()`
  - `test_normalize_audio_peak_scaling()`
  - `test_bytes_to_float32_array()`
  - `test_float32_array_to_bytes()`
- **Acceptance Criteria**:
  - All tests written and FAILING
  - Tests use synthetic audio (sine waves, noise)

### T009: Implement audio preprocessing
- [ ] **Task**: Implement preprocessing functions using scipy/numpy
- **Dependencies**: T008
- **Test Requirements**: All T008 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/preprocessing.py`
- **Functions to Implement**:
  - `preprocess_audio(audio_data: bytes, sample_rate: int) -> np.ndarray`
  - `apply_highpass_filter(audio: np.ndarray, sample_rate: int, cutoff_hz: int = 80)`
  - `apply_preemphasis(audio: np.ndarray, coefficient: float = 0.97)`
  - `normalize_audio(audio: np.ndarray) -> np.ndarray`
  - `resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int = 16000)`
  - `bytes_to_float32_array(audio_bytes: bytes) -> np.ndarray`
  - `float32_array_to_bytes(audio: np.ndarray) -> bytes`
- **Acceptance Criteria**:
  - All T008 tests pass
  - No librosa dependency (scipy/numpy only)
  - 95%+ coverage (critical path)

### T010: Write tests for postprocessing (utterance shaping)
- [ ] **Task**: Write tests for segment merge/split logic (TDD)
- **Dependencies**: T005
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_postprocessing.py`
- **Test Cases**:
  - `test_improve_sentence_boundaries_merges_short_segments()`
  - `test_improve_sentence_boundaries_preserves_long_segments()`
  - `test_improve_sentence_boundaries_handles_empty_list()`
  - `test_improve_sentence_boundaries_single_segment()`
  - `test_improve_sentence_boundaries_updates_timestamps()`
  - `test_improve_sentence_boundaries_recalculates_confidence()`
  - `test_split_long_segments_at_sentence_boundary()`
  - `test_split_long_segments_at_word_boundary()`
  - `test_split_long_segments_preserves_short_segments()`
  - `test_split_long_segments_handles_no_words()`
  - `test_split_long_segments_max_duration_respected()`
  - `test_shape_utterances_pipeline()`
- **Acceptance Criteria**:
  - All tests written and FAILING
  - Tests cover edge cases (empty, single, many segments)

### T011: Implement postprocessing (utterance shaping)
- [ ] **Task**: Implement segment merge/split functions
- **Dependencies**: T010
- **Test Requirements**: All T010 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/postprocessing.py`
- **Functions to Implement**:
  - `improve_sentence_boundaries(segments: list[TranscriptSegment], merge_threshold_seconds: float = 1.0) -> list[TranscriptSegment]`
  - `split_long_segments(segments: list[TranscriptSegment], max_duration_seconds: float = 6.0) -> list[TranscriptSegment]`
  - `shape_utterances(segments: list[TranscriptSegment], config: UtteranceShapingConfig) -> list[TranscriptSegment]`
- **Acceptance Criteria**:
  - All T010 tests pass
  - 95%+ coverage (critical path)

### T012: Write tests for domain prompts
- [ ] **Task**: Write tests for domain prompt generation (TDD)
- **Dependencies**: T001
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_domain_prompts.py`
- **Test Cases**:
  - `test_get_domain_prompt_sports()`
  - `test_get_domain_prompt_football()`
  - `test_get_domain_prompt_basketball()`
  - `test_get_domain_prompt_news()`
  - `test_get_domain_prompt_interview()`
  - `test_get_domain_prompt_general()`
  - `test_get_domain_prompt_unknown_returns_general()`
  - `test_domain_prompts_contain_vocabulary()`
  - `test_domain_prompts_reasonable_length()`
- **Acceptance Criteria**:
  - All tests written and FAILING
  - Tests verify prompt content includes domain vocabulary

### T013: Implement domain prompts
- [ ] **Task**: Implement domain-specific prompt generation
- **Dependencies**: T012
- **Test Requirements**: All T012 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/domain_prompts.py`
- **Functions to Implement**:
  - `get_domain_prompt(domain: str) -> str`
  - `DOMAIN_PROMPTS: dict[str, str]` (constant)
- **Domain Prompts**:
  - `sports`: General sports terminology
  - `football`: NFL-specific vocabulary (Mahomes, Chiefs, touchdown, etc.)
  - `basketball`: NBA-specific vocabulary
  - `news`: News anchor vocabulary
  - `interview`: Conversational vocabulary
  - `general`: Empty/minimal prompt
- **Acceptance Criteria**:
  - All T012 tests pass
  - Prompts contain domain-relevant vocabulary

### T014: Write tests for confidence mapping
- [ ] **Task**: Write tests for confidence score calculation (TDD)
- **Dependencies**: T001
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_confidence.py`
- **Test Cases**:
  - `test_calculate_confidence_high_logprob()`
  - `test_calculate_confidence_low_logprob()`
  - `test_calculate_confidence_zero_logprob()`
  - `test_calculate_confidence_negative_one_logprob()`
  - `test_calculate_confidence_clamps_to_zero()`
  - `test_calculate_confidence_clamps_to_one()`
  - `test_calculate_confidence_linear_mapping()`
- **Acceptance Criteria**:
  - Tests define confidence mapping: `clamp((avg_logprob + 1.0) / 1.0, 0, 1)`
  - All tests written and FAILING

### T015: Implement confidence mapping
- [ ] **Task**: Implement confidence score calculation
- **Dependencies**: T014
- **Test Requirements**: All T014 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/confidence.py`
- **Functions to Implement**:
  - `calculate_confidence(avg_logprob: float) -> float`
- **Acceptance Criteria**:
  - All T014 tests pass
  - Linear mapping from avg_logprob to 0-1 range

---

## Phase 3: Mock Implementation

### T016: Write tests for MockASRComponent
- [ ] **Task**: Write tests for deterministic mock behavior (TDD)
- **Dependencies**: T005, T007
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_mock.py`
- **Test Cases**:
  - `test_mock_asr_returns_configured_text()`
  - `test_mock_asr_returns_configured_confidence()`
  - `test_mock_asr_ignores_audio_content()`
  - `test_mock_asr_generates_timestamps_from_words()`
  - `test_mock_asr_respects_start_end_times()`
  - `test_mock_asr_implements_protocol()`
  - `test_mock_asr_is_ready_always_true()`
  - `test_mock_asr_component_instance_name()`
  - `test_mock_asr_failure_injection()`
  - `test_mock_asr_failure_rate_probability()`
  - `test_mock_asr_simulated_latency()`
  - `test_mock_asr_empty_text_returns_empty_segments()`
  - `test_mock_config_defaults()`
- **Acceptance Criteria**:
  - Tests define deterministic mock behavior
  - All tests written and FAILING

### T017: Implement MockASRComponent
- [ ] **Task**: Implement deterministic mock for testing
- **Dependencies**: T016, T005, T007
- **Test Requirements**: All T016 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/mock.py`
- **Components to Implement**:
  - `MockASRConfig` dataclass
  - `MockASRComponent(BaseASRComponent)` class
- **Behavior**:
  - Ignores audio content completely
  - Returns configured text with calculated timestamps
  - Supports failure injection via config
  - Implements `ASRComponent` protocol
- **Acceptance Criteria**:
  - All T016 tests pass
  - `isinstance(mock, ASRComponent)` returns True
  - Deterministic output for same inputs

---

## Phase 4: Real Implementation

### T018: Write tests for error classification
- [ ] **Task**: Write tests for error type mapping (TDD)
- **Dependencies**: T005
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_errors.py`
- **Test Cases**:
  - `test_classify_error_memory_error()`
  - `test_classify_error_timeout_error()`
  - `test_classify_error_file_not_found()`
  - `test_classify_error_value_error()`
  - `test_classify_error_runtime_error()`
  - `test_classify_error_unknown()`
  - `test_create_asr_error_from_exception()`
  - `test_asr_error_retryable_for_timeout()`
  - `test_asr_error_not_retryable_for_invalid_audio()`
  - `test_asr_error_retryable_for_memory()`
- **Acceptance Criteria**:
  - Tests define exception-to-ASRErrorType mapping
  - All tests written and FAILING

### T019: Implement error classification
- [ ] **Task**: Implement exception to ASRError mapping
- **Dependencies**: T018
- **Test Requirements**: All T018 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/errors.py`
- **Functions to Implement**:
  - `classify_error(exception: Exception) -> ASRErrorType`
  - `create_asr_error(exception: Exception) -> ASRError`
  - `is_retryable(error_type: ASRErrorType) -> bool`
- **Error Mapping**:
  - `MemoryError` -> `MEMORY_ERROR` (retryable)
  - `TimeoutError` -> `TIMEOUT` (retryable)
  - `FileNotFoundError` -> `MODEL_LOAD_ERROR` (not retryable)
  - `ValueError` -> `INVALID_AUDIO` (not retryable)
  - `RuntimeError` -> `UNKNOWN` (not retryable)
- **Acceptance Criteria**:
  - All T018 tests pass

### T020: Write unit tests for FasterWhisperASR (mocked model)
- [ ] **Task**: Write unit tests with mocked WhisperModel (TDD)
- **Dependencies**: T005, T007, T009, T011, T015, T019
- **Test Requirements**: Write BEFORE implementation
- **Files**:
  - `apps/sts-service/tests/unit/asr/test_transcriber.py`
- **Test Cases**:
  - `test_faster_whisper_asr_implements_protocol()`
  - `test_faster_whisper_asr_component_instance()`
  - `test_faster_whisper_asr_is_ready_after_init()`
  - `test_transcribe_returns_transcript_asset()`
  - `test_transcribe_success_status_for_speech()`
  - `test_transcribe_empty_segments_for_silence()`
  - `test_transcribe_applies_preprocessing()`
  - `test_transcribe_applies_postprocessing()`
  - `test_transcribe_uses_domain_prompt()`
  - `test_transcribe_handles_timeout()`
  - `test_transcribe_handles_memory_error()`
  - `test_transcribe_calculates_confidence()`
  - `test_transcribe_converts_relative_to_absolute_timestamps()`
  - `test_transcribe_records_processing_time()`
  - `test_transcribe_sets_model_info()`
  - `test_shutdown_clears_model_cache()`
- **Mocking Strategy**:
  ```python
  @pytest.fixture
  def mock_whisper_model(mocker):
      mock = mocker.Mock()
      mock.transcribe.return_value = (
          [mock_segment(text="Test", start=0.0, end=1.0)],
          mock_info(language="en"),
      )
      return mock
  ```
- **Acceptance Criteria**:
  - All tests use mocked WhisperModel
  - No real model loading in unit tests
  - All tests written and FAILING

### T021: Implement FasterWhisperASR transcriber
- [ ] **Task**: Implement production ASR component
- **Dependencies**: T020, T009, T011, T013, T015, T019
- **Test Requirements**: All T020 tests must PASS
- **Files**:
  - `apps/sts-service/src/sts_service/asr/transcriber.py`
- **Components to Implement**:
  - `_MODEL_CACHE: dict` (module-level cache)
  - `_get_or_load_model(config: ASRModelConfig) -> WhisperModel`
  - `FasterWhisperASR(BaseASRComponent)` class
- **Implementation Details**:
  - Model loading with global cache keyed by (size, device, compute_type)
  - Preprocessing integration via `preprocess_audio()`
  - faster-whisper `model.transcribe()` call
  - Segment extraction and timestamp conversion
  - Postprocessing via `shape_utterances()`
  - Error handling with `classify_error()`
  - Timeout enforcement
- **Acceptance Criteria**:
  - All T020 tests pass
  - Model cache prevents redundant loading
  - 95%+ coverage (critical path)

### T022: Write integration tests for FasterWhisperASR (real model)
- [ ] **Task**: Write integration tests with real faster-whisper model
- **Dependencies**: T021, T003
- **Test Requirements**: Requires faster-whisper model download
- **Files**:
  - `apps/sts-service/tests/integration/asr/test_transcriber.py`
- **Test Cases**:
  - `test_transcribe_synthetic_speech()`
  - `test_transcribe_returns_valid_timestamps()`
  - `test_transcribe_confidence_in_valid_range()`
  - `test_transcribe_processing_time_recorded()`
  - `test_model_cache_reuses_model()`
  - `test_transcribe_with_vad_enabled()`
  - `test_transcribe_with_vad_disabled()`
- **Notes**:
  - Uses `tiny` or `base` model for fast tests
  - May use synthetic audio (sine wave with silence)
- **Acceptance Criteria**:
  - Tests run with real faster-whisper model
  - Tests complete in <30 seconds each

### T023: Create ASR component factory
- [ ] **Task**: Implement factory function for component instantiation
- **Dependencies**: T021, T017
- **Test Requirements**: Test factory returns correct types
- **Files**:
  - `apps/sts-service/src/sts_service/asr/factory.py`
  - `apps/sts-service/tests/unit/asr/test_factory.py`
- **Functions to Implement**:
  - `create_asr_component(config: ASRConfig, mock: bool = False) -> ASRComponent`
- **Test Cases**:
  - `test_factory_returns_faster_whisper_by_default()`
  - `test_factory_returns_mock_when_requested()`
  - `test_factory_passes_config_to_component()`
- **Acceptance Criteria**:
  - Factory creates correct component type
  - All tests pass

---

## Phase 5: Integration with Fixtures

### T024: Write integration tests with NFL audio fixture
- [ ] **Task**: Test transcription with real NFL sports audio
- **Dependencies**: T021, T003
- **Test Requirements**: Uses `tests/fixtures/test-streams/1-min-nfl.m4a`
- **Files**:
  - `apps/sts-service/tests/integration/asr/test_fixtures.py`
- **Test Cases**:
  - `test_nfl_audio_transcription_produces_text()`
  - `test_nfl_audio_timestamps_within_fragment()`
  - `test_nfl_audio_confidence_reasonable()`
  - `test_nfl_audio_processing_time_under_limit()`
- **Fixture Usage**:
  ```python
  def test_nfl_audio_transcription_produces_text(nfl_audio_path, load_audio_fragment):
      audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=0, duration_ms=2000)
      asr = FasterWhisperASR(ASRConfig())
      result = asr.transcribe(
          audio_data=audio_bytes,
          stream_id="test",
          sequence_number=0,
          start_time_ms=0,
          end_time_ms=2000,
          domain="sports",
      )
      assert result.status == TranscriptStatus.SUCCESS
      assert len(result.total_text) > 0
  ```
- **Acceptance Criteria**:
  - Transcription produces non-empty text
  - Timestamps are valid
  - Processing time <500ms per 2s fragment

### T025: Write integration tests for domain priming
- [ ] **Task**: Test that domain prompts improve sports transcription
- **Dependencies**: T024
- **Test Requirements**: Uses NFL audio fixture
- **Files**:
  - `apps/sts-service/tests/integration/asr/test_fixtures.py` (additional tests)
- **Test Cases**:
  - `test_sports_domain_priming_affects_vocabulary()`
  - `test_general_vs_sports_domain_comparison()`
- **Notes**:
  - These tests may be somewhat non-deterministic
  - Focus on verifying domain prompts are applied, not exact output
- **Acceptance Criteria**:
  - Domain prompt is passed to faster-whisper
  - Test demonstrates different behavior with different domains

### T026: Write integration tests for silence detection
- [ ] **Task**: Test no-speech detection with silent audio
- **Dependencies**: T021, T003
- **Test Requirements**: Uses `tests/fixtures/test-streams/big-buck-bunny.mp4`
- **Files**:
  - `apps/sts-service/tests/integration/asr/test_fixtures.py` (additional tests)
- **Test Cases**:
  - `test_silence_returns_empty_segments()`
  - `test_silence_returns_success_status()`
  - `test_silence_no_hallucination()`
- **Notes**:
  - big-buck-bunny contains music but minimal speech
  - Extract audio sections with no dialogue
- **Acceptance Criteria**:
  - Silent fragments return SUCCESS with empty segments
  - No hallucinated text output

### T027: Write timestamp alignment verification tests
- [ ] **Task**: Verify timestamps are correctly converted to absolute stream time
- **Dependencies**: T024
- **Test Requirements**: Uses NFL audio fixture
- **Files**:
  - `apps/sts-service/tests/integration/asr/test_fixtures.py` (additional tests)
- **Test Cases**:
  - `test_segment_timestamps_are_absolute()`
  - `test_segment_timestamps_within_fragment_bounds()`
  - `test_word_timestamps_within_segment_bounds()`
  - `test_segments_ordered_by_start_time()`
- **Acceptance Criteria**:
  - All segment.start_time_ms >= fragment.start_time_ms
  - All segment.end_time_ms <= fragment.end_time_ms
  - Segments are ordered chronologically

---

## Phase 6: Public API + Documentation

### T028: Create public API exports
- [ ] **Task**: Define clean public API in `__init__.py`
- **Dependencies**: T021, T017, T005, T007
- **Test Requirements**: Test all exports are importable
- **Files**:
  - `apps/sts-service/src/sts_service/asr/__init__.py`
- **Exports**:
  ```python
  # Core implementations
  from .transcriber import FasterWhisperASR
  from .mock import MockASRComponent, MockASRConfig
  from .factory import create_asr_component

  # Interface
  from .interface import ASRComponent, BaseASRComponent

  # Models
  from .models import (
      AudioFormat,
      AudioFragment,
      WordTiming,
      TranscriptSegment,
      TranscriptStatus,
      TranscriptAsset,
      ASRError,
      ASRErrorType,
      ASRConfig,
      ASRModelConfig,
      VADConfig,
      TranscriptionConfig,
      UtteranceShapingConfig,
      ASRMetrics,
  )

  __all__ = [
      "FasterWhisperASR",
      "MockASRComponent",
      "MockASRConfig",
      "create_asr_component",
      "ASRComponent",
      "BaseASRComponent",
      # ... all models
  ]
  ```
- **Test**:
  ```python
  def test_public_api_imports():
      from sts_service.asr import (
          FasterWhisperASR,
          MockASRComponent,
          ASRComponent,
          AudioFragment,
          TranscriptAsset,
      )
  ```
- **Acceptance Criteria**:
  - All exports work from `sts_service.asr`
  - No internal modules exposed

### T029: Update quickstart.md with final API examples
- [ ] **Task**: Document usage examples and API reference
- **Dependencies**: T028
- **Test Requirements**: N/A (documentation)
- **Files**:
  - `specs/005-audio-transcription-module/quickstart.md`
- **Content**:
  - Installation instructions
  - Basic usage example
  - Configuration options
  - Mock usage for testing
  - Error handling patterns
  - Performance tuning tips
- **Acceptance Criteria**:
  - Examples are copy-paste runnable
  - All public API documented

---

## Dependency Graph

```
T001 (Setup directories)
  |
  +---> T002 (Dependencies)
  |       |
  +---> T003 (Conftest fixtures)
  |
  +---> T004 (Test models) --> T005 (Implement models)
  |                              |
  |                              +---> T006 (Test interface) --> T007 (Implement interface)
  |                              |
  |                              +---> T008 (Test preprocessing) --> T009 (Implement preprocessing)
  |                              |
  |                              +---> T010 (Test postprocessing) --> T011 (Implement postprocessing)
  |                              |
  |                              +---> T014 (Test confidence) --> T015 (Implement confidence)
  |                              |
  |                              +---> T018 (Test errors) --> T019 (Implement errors)
  |                              |
  |                              +---> T016 (Test mock) --> T017 (Implement mock)
  |
  +---> T012 (Test domain prompts) --> T013 (Implement domain prompts)

T005 + T007 + T009 + T011 + T013 + T015 + T019
  |
  +---> T020 (Test transcriber unit) --> T021 (Implement transcriber)
                                           |
                                           +---> T022 (Integration test transcriber)
                                           |
                                           +---> T023 (Factory)

T021 + T003
  |
  +---> T024 (Test NFL audio)
  +---> T025 (Test domain priming)
  +---> T026 (Test silence detection)
  +---> T027 (Test timestamp alignment)

T021 + T017 + T005 + T007
  |
  +---> T028 (Public API) --> T029 (Documentation)
```

---

## Parallelization Opportunities

**Phase 1 (can run in parallel after T001)**:
- T004 (Test models) || T006 (Test interface)

**Phase 2 (can run in parallel after T005)**:
- T008 (Test preprocessing) || T010 (Test postprocessing) || T012 (Test domain prompts) || T014 (Test confidence)

**Phase 4 (can run in parallel after dependencies met)**:
- T018 (Test errors) || T020 (Test transcriber unit)

**Phase 5 (can run in parallel after T021)**:
- T024 || T025 || T026 || T027 (all fixture tests)

---

## Coverage Targets

| Module | Target | Rationale |
|--------|--------|-----------|
| `models.py` | 100% | Contract definitions |
| `preprocessing.py` | 95% | Critical path |
| `postprocessing.py` | 95% | Critical path |
| `transcriber.py` | 95% | Critical path |
| `confidence.py` | 100% | Simple logic |
| `domain_prompts.py` | 100% | Simple logic |
| `errors.py` | 100% | Error handling |
| `mock.py` | 90% | Testing support |
| `interface.py` | 80% | Protocol definitions |
| `factory.py` | 90% | Factory pattern |
| **Overall** | **80%** | Constitution minimum |

---

## Verification Checklist

Before marking Phase complete:

- [ ] All tests pass: `make media-test-unit`
- [ ] Coverage meets target: `make media-test-coverage`
- [ ] Type check passes: `make typecheck`
- [ ] Linting passes: `make lint`
- [ ] Integration tests pass: `make media-test-integration`
