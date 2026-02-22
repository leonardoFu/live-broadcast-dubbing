# Task List: ElevenLabs TTS Provider

**Feature ID**: 022-elevenlabs-tts-provider
**Generated**: 2026-01-03
**Status**: Ready for Implementation

---

## Task Summary

This task list follows **Test-Driven Development (TDD)** methodology - tests MUST be written BEFORE implementation.

**Total Tasks**: 19
**Phases**: 6 (Setup → Data Models → Provider Core → Duration Matching → Manual Testing → Integration)

**Key Changes from Original Spec**:
- Default TTS provider: ElevenLabs (not Coqui)
- Default target language: Japanese (ja) instead of Spanish (es)
- Provider selection via TTS_PROVIDER env var (default: "elevenlabs")

---

## Phase 1: Setup & Dependencies

### T001: Add ElevenLabs Dependency to Project

**Priority**: P1 (Critical - Foundation)
**Depends on**: None
**Type**: Configuration

**Description**:
Add `elevenlabs>=0.2.0` Python package dependency to sts-service project configuration files.

**Actions**:
1. Add `elevenlabs>=0.2.0` to `apps/sts-service/requirements.txt`
2. Add `elevenlabs>=0.2.0` to `apps/sts-service/pyproject.toml` dependencies array
3. Run `pip install -r apps/sts-service/requirements.txt` to verify installability
4. Verify ElevenLabs client can be imported: `python -c "from elevenlabs import generate"`

**Success Criteria**:
- [ ] `elevenlabs` package added to requirements.txt
- [ ] `elevenlabs` package added to pyproject.toml
- [ ] Package installs without errors
- [ ] Import test passes

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/requirements.txt`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/pyproject.toml`

**Test Command**:
```bash
cd /Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service
pip install -r requirements.txt
python -c "from elevenlabs import generate; print('ElevenLabs client import successful')"
```

**Estimated Time**: 10 minutes

---

### T001a: Update StreamConfig Default Target Language to Japanese

**Priority**: P1 (Critical - Configuration)
**Depends on**: None
**Type**: Configuration

**Description**:
Change the default target_language in StreamConfig from "es" (Spanish) to "ja" (Japanese) for the whole STS service.

**Actions**:
1. Open `apps/sts-service/src/sts_service/full/models/stream.py`
2. Update StreamConfig.target_language default value:
   - Change `default="es"` to `default="ja"`
3. Update the json_schema_extra example to use "ja" instead of "es"
4. Run existing tests to ensure no regressions
5. Update any test fixtures that depend on default "es" target language

**Success Criteria**:
- [ ] StreamConfig.target_language default is "ja"
- [ ] Existing tests pass (update fixtures as needed)
- [ ] json_schema_extra example updated

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/full/models/stream.py`

**Test Command**:
```bash
make sts-test-unit -k "stream"
# Expected: All stream model tests PASS
```

**Estimated Time**: 15 minutes

---

## Phase 2: Data Model Updates (TDD)

### T002: Write Tests for VoiceProfile ElevenLabs Fields

**Priority**: P1 (Critical - TDD)
**Depends on**: T001
**Type**: Test

**Description**:
Write unit tests for new ElevenLabs-specific fields in VoiceProfile model BEFORE adding the fields. Tests should fail initially.

**Actions**:
1. Create test file: `apps/sts-service/tests/unit/tts/test_voice_profile_elevenlabs.py`
2. Write test: `test_voice_profile_elevenlabs_fields_optional()` - Verify new fields are optional
3. Write test: `test_voice_profile_stability_range_validation()` - Verify 0.0-1.0 range constraint
4. Write test: `test_voice_profile_similarity_boost_range_validation()` - Verify 0.0-1.0 range constraint
5. Write test: `test_voice_profile_backward_compatible()` - Ensure existing Coqui fields work unchanged
6. Run tests - VERIFY THEY FAIL (fields don't exist yet)

**Success Criteria**:
- [ ] Test file created with 4 test functions
- [ ] All tests fail with expected errors (field not found)
- [ ] Test coverage plan documented for new fields

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_voice_profile_elevenlabs.py`

**Test Command**:
```bash
make sts-test-unit -k "test_voice_profile_elevenlabs"
# Expected: 4 tests FAIL (fields don't exist yet)
```

**Estimated Time**: 30 minutes

---

### T003: Implement VoiceProfile ElevenLabs Fields

**Priority**: P1 (Critical - Implementation)
**Depends on**: T002
**Type**: Implementation

**Description**:
Add ElevenLabs-specific optional fields to VoiceProfile data model: `voice_id`, `elevenlabs_model_id`, `stability`, `similarity_boost`.

**Actions**:
1. Open `apps/sts-service/src/sts_service/tts/models.py`
2. Add optional fields to VoiceProfile class:
   - `voice_id: str | None = Field(default=None, description="ElevenLabs voice ID")`
   - `elevenlabs_model_id: str | None = Field(default=None, description="ElevenLabs model ID")`
   - `stability: float | None = Field(default=None, ge=0.0, le=1.0, description="Voice stability (0.0-1.0)")`
   - `similarity_boost: float | None = Field(default=None, ge=0.0, le=1.0, description="Similarity boost (0.0-1.0)")`
3. Update docstring to document ElevenLabs fields
4. Run tests from T002 - VERIFY THEY PASS

**Success Criteria**:
- [ ] All 4 new fields added with correct types and constraints
- [ ] All tests from T002 now PASS
- [ ] Existing Coqui-related tests still pass (backward compatibility)
- [ ] Pydantic validation enforces 0.0-1.0 range for stability/similarity_boost

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/models.py`

**Test Command**:
```bash
make sts-test-unit -k "test_voice_profile"
# Expected: All VoiceProfile tests PASS
```

**Estimated Time**: 20 minutes

---

## Phase 3: ElevenLabs Provider Core (TDD)

### T004: Write Tests for ElevenLabs Provider Basic Synthesis

**Priority**: P1 (Critical - TDD)
**Depends on**: T003
**Type**: Test

**Description**:
Write comprehensive unit tests for ElevenLabsTTSComponent BEFORE implementing the class. Use mocks for API calls.

**Actions**:
1. Create test file: `apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`
2. Write test: `test_elevenlabs_basic_synthesis()` - Mocked API returns AudioAsset
3. Write test: `test_elevenlabs_component_instance()` - Format is "elevenlabs-{model_id}"
4. Write test: `test_elevenlabs_is_ready_with_api_key()` - is_ready=True when API key valid
5. Write test: `test_elevenlabs_is_ready_without_api_key()` - is_ready=False when missing
6. Write test: `test_elevenlabs_audio_format_conversion()` - MP3 → PCM F32LE conversion
7. Write test: `test_elevenlabs_sample_rate_conversion()` - Resampling to target rate
8. Write test: `test_elevenlabs_mono_to_stereo_conversion()` - Channel conversion when output_channels=2
9. Set up pytest fixtures for mocked ElevenLabs API client
10. Run tests - VERIFY THEY FAIL (class doesn't exist yet)

**Success Criteria**:
- [ ] Test file created with 8+ test functions
- [ ] Mocked API client fixtures ready
- [ ] All tests fail with expected error (module not found)

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_basic"
# Expected: Tests FAIL (ElevenLabsTTSComponent doesn't exist)
```

**Estimated Time**: 60 minutes

---

### T005: Write Tests for ElevenLabs Voice Selection Logic

**Priority**: P2 (High - TDD)
**Depends on**: T004
**Type**: Test

**Description**:
Write unit tests for voice ID selection logic (explicit voice_id, language defaults, fallback).

**Actions**:
1. Add to test file: `apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`
2. Write test: `test_elevenlabs_voice_id_explicit()` - Explicit voice_id overrides language
3. Write test: `test_elevenlabs_voice_id_language_default()` - Language-based default for "en", "es", "fr"
4. Write test: `test_elevenlabs_voice_id_unsupported_language_fallback()` - Unsupported language → English fallback with warning
5. Write test: `test_elevenlabs_model_id_default()` - Default model is "eleven_flash_v2_5"
6. Write test: `test_elevenlabs_model_id_custom()` - Custom model_id used when specified
7. Write test: `test_elevenlabs_voice_settings_applied()` - Stability and similarity_boost passed to API
8. Run tests - VERIFY THEY FAIL

**Success Criteria**:
- [ ] 6 new test functions added
- [ ] All tests fail (implementation doesn't exist)
- [ ] Test fixtures include VoiceProfile variations

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_voice"
# Expected: Tests FAIL
```

**Estimated Time**: 45 minutes

---

### T006: Write Tests for ElevenLabs Error Classification

**Priority**: P3 (High - TDD)
**Depends on**: T004
**Type**: Test

**Description**:
Write unit tests for API error mapping to TTSError types with correct retryability flags.

**Actions**:
1. Add to test file: `apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`
2. Write test: `test_elevenlabs_error_401_non_retryable()` - Auth errors → INVALID_INPUT, retryable=False
3. Write test: `test_elevenlabs_error_429_retryable()` - Rate limit → TIMEOUT, retryable=True
4. Write test: `test_elevenlabs_error_400_non_retryable()` - Bad request → INVALID_INPUT, retryable=False
5. Write test: `test_elevenlabs_error_500_retryable()` - Server error → UNKNOWN, retryable=True
6. Write test: `test_elevenlabs_error_network_timeout_retryable()` - Timeout → TIMEOUT, retryable=True
7. Mock ElevenLabs exception types (APIError, RateLimitError, AuthenticationError)
8. Run tests - VERIFY THEY FAIL

**Success Criteria**:
- [ ] 5 error classification tests added
- [ ] All tests fail (error handling not implemented)
- [ ] Mock fixtures for ElevenLabs exceptions ready

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_error"
# Expected: Tests FAIL
```

**Estimated Time**: 45 minutes

---

### T007: Implement ElevenLabsTTSComponent Class Structure

**Priority**: P1 (Critical - Implementation)
**Depends on**: T004, T005, T006
**Type**: Implementation

**Description**:
Create ElevenLabsTTSComponent class with BaseTTSComponent inheritance, basic structure, and initialization logic.

**Actions**:
1. Create file: `apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`
2. Implement class structure:
   - Inherit from BaseTTSComponent
   - Define `__init__` with config and optional api_key parameters
   - Implement `component_instance` property (returns "elevenlabs-{model_id}")
   - Implement `is_ready` property (validates API key)
   - Add placeholder for `synthesize()` method (raise NotImplementedError)
   - Define DEFAULT_VOICES mapping (en→Rachel, es→Diego, fr→Thomas, de→Sarah, it→Giovanni, pt→Domi, ja→Hiro)
   - Define FALLBACK_VOICE constant
3. Add docstring with feature overview
4. Run basic structure tests - VERIFY SOME TESTS PASS

**Success Criteria**:
- [ ] File created with class skeleton
- [ ] `component_instance` and `is_ready` tests PASS
- [ ] Class imports without errors
- [ ] synthesize() not yet implemented

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_is_ready or test_elevenlabs_component_instance"
# Expected: Basic structure tests PASS
```

**Estimated Time**: 40 minutes

---

### T008: Implement Voice Selection and API Call Logic

**Priority**: P2 (High - Implementation)
**Depends on**: T007
**Type**: Implementation

**Description**:
Implement `_get_voice_id()` helper and `_call_elevenlabs_api()` with error handling.

**Actions**:
1. Implement `_get_voice_id(language, voice_profile)` method:
   - Priority: explicit voice_id → language default → fallback to English
   - Add warning log when falling back to English
2. Implement `_call_elevenlabs_api(text, voice_id, model_id, voice_settings)` method:
   - Use `elevenlabs.generate()` synchronous API
   - Apply timeout from TTSConfig
   - Return MP3 bytes
3. Implement `_classify_api_error(error)` method:
   - Map ElevenLabs exceptions to TTSError types
   - Set retryability flags correctly
4. Run voice selection and error tests - VERIFY THEY PASS

**Success Criteria**:
- [ ] Voice selection tests PASS (T005 tests)
- [ ] Error classification tests PASS (T006 tests)
- [ ] API call logic handles timeouts
- [ ] Logging for fallback scenarios works

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_voice or test_elevenlabs_error"
# Expected: Voice selection and error tests PASS
```

**Estimated Time**: 60 minutes

---

### T009: Implement Audio Format Conversion

**Priority**: P1 (Critical - Implementation)
**Depends on**: T007
**Type**: Implementation

**Description**:
Implement `_convert_audio_format()` to transform ElevenLabs MP3 output to PCM F32LE with target sample rate and channels.

**Actions**:
1. Implement `_convert_audio_format(mp3_bytes, target_sample_rate_hz, target_channels)` method:
   - Load MP3 from bytes using pydub.AudioSegment
   - Resample to target sample rate if different
   - Convert mono to stereo if target_channels=2
   - Convert to PCM F32LE (32-bit float little-endian)
   - Return bytes
2. Add helper method: `_calculate_duration_ms(audio_bytes, sample_rate_hz, channels)` - Calculate duration from PCM bytes
3. Run audio format conversion tests - VERIFY THEY PASS

**Success Criteria**:
- [ ] Format conversion tests PASS (T004 tests)
- [ ] MP3 → PCM F32LE conversion works
- [ ] Resampling to different rates works
- [ ] Mono → stereo conversion works

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_audio_format or test_elevenlabs_sample_rate or test_elevenlabs_mono_to_stereo"
# Expected: Audio format tests PASS
```

**Estimated Time**: 50 minutes

---

### T010: Implement Basic Synthesize Method (No Duration Matching)

**Priority**: P1 (Critical - Implementation)
**Depends on**: T008, T009
**Type**: Implementation

**Description**:
Implement `synthesize()` method WITHOUT duration matching - basic text → audio pipeline.

**Actions**:
1. Implement `synthesize(text_asset, target_duration_ms=None, ...)` method:
   - Extract text from text_asset
   - Apply text preprocessing (same as Coqui)
   - Get voice_id using `_get_voice_id()`
   - Call ElevenLabs API using `_call_elevenlabs_api()`
   - Convert MP3 to PCM using `_convert_audio_format()`
   - Calculate duration using `_calculate_duration_ms()`
   - Build AudioAsset with metadata (status=SUCCESS, no duration matching yet)
   - Track lineage: parent_asset_ids from text_asset.asset_id
   - Record component_instance as "elevenlabs-{model_id}"
2. Add error handling: catch exceptions, map to TTSError, return FAILED status
3. Ignore `target_duration_ms` for now (duration matching in next phase)
4. Run basic synthesis test - VERIFY IT PASSES

**Success Criteria**:
- [ ] `test_elevenlabs_basic_synthesis()` PASSES
- [ ] AudioAsset returned with correct schema
- [ ] Lineage tracking works (parent_asset_ids)
- [ ] Errors mapped correctly to AudioStatus.FAILED

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_basic_synthesis"
# Expected: Basic synthesis test PASSES
```

**Estimated Time**: 60 minutes

---

## Phase 4: Factory Integration (TDD)

### T011: Write Tests for Factory ElevenLabs Support and TTS_PROVIDER Env Var

**Priority**: P1 (Critical - TDD)
**Depends on**: T010
**Type**: Test

**Description**:
Write unit tests for factory creating ElevenLabs provider as DEFAULT and TTS_PROVIDER env var support.

**Actions**:
1. Create or update test file: `apps/sts-service/tests/unit/tts/test_factory.py`
2. Write test: `test_factory_creates_elevenlabs_provider()` - Verify factory returns ElevenLabsTTSComponent instance
3. Write test: `test_factory_elevenlabs_with_config()` - Verify TTSConfig passed through
4. Write test: `test_factory_default_is_elevenlabs()` - Verify default provider is ElevenLabs when TTS_PROVIDER not set
5. Write test: `test_factory_tts_provider_env_coqui()` - Verify TTS_PROVIDER=coqui returns CoquiTTSComponent
6. Write test: `test_factory_tts_provider_env_elevenlabs()` - Verify TTS_PROVIDER=elevenlabs returns ElevenLabsTTSComponent
7. Write test: `test_factory_explicit_provider_overrides_env()` - Verify explicit provider param overrides TTS_PROVIDER env
8. Run tests - VERIFY THEY FAIL (factory doesn't support "elevenlabs" yet)

**Success Criteria**:
- [ ] 6 factory tests added
- [ ] All tests fail (factory doesn't create ElevenLabs provider)

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_factory.py`

**Test Command**:
```bash
make sts-test-unit -k "test_factory_elevenlabs"
# Expected: Tests FAIL (factory not updated)
```

**Estimated Time**: 30 minutes

---

### T012: Update Factory with TTS_PROVIDER Env Var and ElevenLabs Default

**Priority**: P1 (Critical - Implementation)
**Depends on**: T011
**Type**: Implementation

**Description**:
Add "elevenlabs" to ProviderType, implement TTS_PROVIDER env var support, and make elevenlabs the DEFAULT provider.

**Actions**:
1. Open `apps/sts-service/src/sts_service/tts/factory.py`
2. Add `import os` at top of file
3. Update ProviderType Literal:
   - Add "elevenlabs" to the list
4. Update `create_tts_component()` function:
   - Change default `provider` parameter to `None` instead of `"coqui"`
   - Add logic to read `TTS_PROVIDER` env var when provider is None
   - Default to "elevenlabs" when TTS_PROVIDER not set
   ```python
   def create_tts_component(
       provider: ProviderType | None = None,  # Changed from "coqui"
       config: TTSConfig | None = None,
       **kwargs: Any,
   ) -> TTSComponent:
       if provider is None:
           provider = os.environ.get("TTS_PROVIDER", "elevenlabs")
       ...
   ```
5. Add elif branch for "elevenlabs":
   ```python
   elif provider == "elevenlabs":
       from .elevenlabs_provider import ElevenLabsTTSComponent
       return ElevenLabsTTSComponent(config=config, **kwargs)
   ```
6. Update ValueError message to include "elevenlabs" in supported list
7. Update docstring to document TTS_PROVIDER env var and ElevenLabs default
8. Run factory tests - VERIFY THEY PASS

**Success Criteria**:
- [ ] ProviderType includes "elevenlabs"
- [ ] Default provider is "elevenlabs" when TTS_PROVIDER not set
- [ ] TTS_PROVIDER=coqui returns CoquiTTSComponent
- [ ] Explicit provider parameter overrides TTS_PROVIDER env var
- [ ] All factory tests PASS (T011 tests)
- [ ] Backward compatibility maintained (Coqui and mock providers still work)

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/factory.py`

**Test Command**:
```bash
make sts-test-unit -k "test_factory"
# Expected: All factory tests PASS
```

**Estimated Time**: 15 minutes

---

## Phase 5: Duration Matching Integration (TDD)

### T013: Write Tests for Shared Duration Matching Utility

**Priority**: P2 (High - TDD)
**Depends on**: T010
**Type**: Test

**Description**:
Write unit tests for extracting rubberband duration matching logic to shared utility BEFORE creating the utility.

**Actions**:
1. Create test file: `apps/sts-service/tests/unit/tts/test_duration_matching.py`
2. Write test: `test_duration_matching_speedup()` - Speed factor > 1.0
3. Write test: `test_duration_matching_slowdown()` - Speed factor < 1.0
4. Write test: `test_duration_matching_clamp_min()` - Clamping to min speed
5. Write test: `test_duration_matching_clamp_max()` - Clamping to max speed
6. Write test: `test_duration_matching_only_speed_up()` - Never slow down when flag set
7. Write test: `test_duration_matching_with_real_rubberband()` - Integration test with real rubberband binary
8. Run tests - VERIFY THEY FAIL (module doesn't exist)

**Success Criteria**:
- [ ] 6+ tests created for duration matching logic
- [ ] All tests fail (utility doesn't exist yet)

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_duration_matching.py`

**Test Command**:
```bash
make sts-test-unit -k "test_duration_matching"
# Expected: Tests FAIL (module not found)
```

**Estimated Time**: 45 minutes

---

### T014: Extract Duration Matching to Shared Utility

**Priority**: P2 (High - Implementation)
**Depends on**: T013
**Type**: Refactoring

**Description**:
Extract rubberband time-stretching logic from Coqui provider to reusable `duration_matching.py` utility module.

**Actions**:
1. Create file: `apps/sts-service/src/sts_service/tts/duration_matching.py`
2. Implement `apply_duration_matching(audio_bytes, sample_rate_hz, channels, baseline_duration_ms, target_duration_ms, speed_clamp_min, speed_clamp_max, only_speed_up)`:
   - Calculate speed factor: `baseline_duration_ms / target_duration_ms`
   - Apply clamping logic (only_speed_up, min/max clamps)
   - Call rubberband binary for time-stretching
   - Return tuple: `(stretched_audio_bytes, speed_factor_applied, was_clamped)`
3. Run tests from T013 - VERIFY THEY PASS

**Success Criteria**:
- [ ] Utility module created with `apply_duration_matching()` function
- [ ] All duration matching tests PASS
- [ ] Function returns correct tuple format

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/duration_matching.py`

**Test Command**:
```bash
make sts-test-unit -k "test_duration_matching"
# Expected: All tests PASS
```

**Estimated Time**: 60 minutes

---

### T015: Integrate Duration Matching in ElevenLabs Provider

**Priority**: P2 (High - Implementation)
**Depends on**: T014
**Type**: Implementation

**Description**:
Update ElevenLabs `synthesize()` to apply duration matching using shared utility when `target_duration_ms` is provided.

**Actions**:
1. Update `synthesize()` method in `elevenlabs_provider.py`:
   - After audio format conversion, calculate baseline_duration_ms
   - If `target_duration_ms` is not None, call `apply_duration_matching()`
   - Update final_duration_ms after time-stretching
   - Set status=PARTIAL if speed was clamped (was_clamped=True)
   - Add warning to errors list if clamped
2. Write test: `test_elevenlabs_duration_matching_applied()` - Duration matching works
3. Write test: `test_elevenlabs_duration_matching_clamped_partial_status()` - Clamped speed results in PARTIAL status
4. Run tests - VERIFY THEY PASS

**Success Criteria**:
- [ ] Duration matching integrated in synthesize() method
- [ ] New tests PASS
- [ ] Status correctly set to PARTIAL when speed clamped
- [ ] Duration matching works identically to Coqui provider

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_duration_matching"
# Expected: Duration matching tests PASS
```

**Estimated Time**: 45 minutes

---

### T016: Refactor Coqui Provider to Use Shared Duration Matching Utility

**Priority**: P5 (Low - Refactoring)
**Depends on**: T014
**Type**: Refactoring

**Description**:
Update Coqui provider to use shared `duration_matching.py` utility instead of duplicate rubberband logic. Ensure backward compatibility.

**Actions**:
1. Open `apps/sts-service/src/sts_service/tts/coqui_provider.py`
2. Replace inline rubberband logic with call to `apply_duration_matching()`
3. Verify same parameters passed (speed_clamp_min, speed_clamp_max, only_speed_up from voice_profile)
4. Run ALL existing Coqui tests - VERIFY THEY STILL PASS (no behavioral change)
5. Run integration tests if available

**Success Criteria**:
- [ ] Coqui provider uses shared utility
- [ ] All existing Coqui tests PASS (100% backward compatible)
- [ ] No duplicate rubberband logic remains
- [ ] Code reduction: ~50-100 lines removed from coqui_provider.py

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/coqui_provider.py`

**Test Command**:
```bash
make sts-test-unit -k "coqui"
# Expected: All Coqui tests PASS (no behavioral change)
```

**Estimated Time**: 30 minutes

---

## Phase 6: Manual Testing & Integration

### T017: Update Manual Test Client to Support ElevenLabs

**Priority**: P4 (Medium - Implementation)
**Depends on**: T012
**Type**: Configuration

**Description**:
Add `--tts-provider` command-line flag to manual_test_client.py to support choosing between Coqui and ElevenLabs.

**Actions**:
1. Open `apps/sts-service/manual_test_client.py`
2. Add argparse argument:
   ```python
   parser.add_argument(
       "--tts-provider",
       type=str,
       choices=["coqui", "elevenlabs"],
       default="coqui",
       help="TTS provider to use (coqui or elevenlabs)"
   )
   ```
3. Update TTS component initialization to use factory with args.tts_provider
4. Add logging to indicate which provider is active
5. Test manually: Run with both `--tts-provider coqui` and `--tts-provider elevenlabs`

**Success Criteria**:
- [ ] Command-line flag added
- [ ] Manual test client works with `--tts-provider elevenlabs`
- [ ] Manual test client works with `--tts-provider coqui` (backward compatible)
- [ ] Logging indicates active provider

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/manual_test_client.py`

**Manual Test Command**:
```bash
# Test with ElevenLabs (requires ELEVENLABS_API_KEY)
export ELEVENLABS_API_KEY="your_key_here"
python apps/sts-service/manual_test_client.py --tts-provider elevenlabs

# Test with Coqui (default)
python apps/sts-service/manual_test_client.py --tts-provider coqui
```

**Estimated Time**: 20 minutes

---

### T018: Create Contract Tests for AudioAsset Schema Compatibility

**Priority**: P3 (High - Test)
**Depends on**: T010
**Type**: Test

**Description**:
Write contract tests to validate that ElevenLabs provider produces AudioAsset output identical in schema to Coqui provider.

**Actions**:
1. Create test file: `apps/sts-service/tests/unit/tts/test_elevenlabs_contract.py`
2. Write test: `test_elevenlabs_audio_asset_schema()` - Validate AudioAsset fields match contract
3. Write test: `test_elevenlabs_metadata_lineage()` - Verify parent_asset_ids tracking
4. Write test: `test_elevenlabs_component_instance_format()` - Verify format "elevenlabs-{model_id}"
5. Write test: `test_elevenlabs_audio_asset_compatible_with_coqui()` - Compare schemas
6. Run tests - VERIFY THEY PASS

**Success Criteria**:
- [ ] Contract tests created
- [ ] All tests PASS
- [ ] AudioAsset schema from ElevenLabs matches Coqui provider
- [ ] Lineage tracking validated

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/unit/tts/test_elevenlabs_contract.py`

**Test Command**:
```bash
make sts-test-unit -k "test_elevenlabs_contract"
# Expected: All contract tests PASS
```

**Estimated Time**: 40 minutes

---

## Phase 7: Optional Integration Testing (Live API)

> **Note**: These tasks are optional and require `ELEVENLABS_API_KEY` environment variable. Skip if API key is not available.

### OPTIONAL-T019: Create Integration Test Suite for Live API

**Priority**: P5 (Optional)
**Depends on**: T015
**Type**: Integration Test

**Description**:
Create integration test suite that validates ElevenLabs provider with real API calls (skipped by default in CI).

**Actions**:
1. Create test file: `apps/sts-service/tests/integration/tts/test_elevenlabs_live.py`
2. Add pytest marker: `@pytest.mark.elevenlabs_live`
3. Add skipif decorator: Skip if `ELEVENLABS_API_KEY` not set
4. Write test: `test_english_synthesis_produces_audio()` - Real API call for English
5. Write test: `test_spanish_synthesis_produces_audio()` - Real API call for Spanish
6. Write test: `test_duration_matching_with_real_audio()` - Duration matching with real ElevenLabs audio
7. Write test: `test_voice_settings_applied()` - Custom stability/similarity_boost settings
8. Run with API key - VERIFY THEY PASS

**Success Criteria**:
- [ ] Integration test file created
- [ ] Tests marked as `@elevenlabs_live`
- [ ] Tests skipped when ELEVENLABS_API_KEY not set
- [ ] Tests PASS when API key provided
- [ ] Real audio validated (duration, format, sample rate)

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/integration/tts/test_elevenlabs_live.py`

**Test Command**:
```bash
# Skip by default (no API key)
make sts-test-unit -m "not elevenlabs_live"

# Run with API key
export ELEVENLABS_API_KEY="your_key"
pytest apps/sts-service/tests/integration/tts/test_elevenlabs_live.py -v
```

**Estimated Time**: 60 minutes

---

## Task Dependency Graph

```
Setup & Dependencies:
T001 (Add Dependencies)
  ↓

Data Models (TDD):
T002 (Write VoiceProfile Tests) → T003 (Implement VoiceProfile Fields)
  ↓

Provider Core (TDD):
T004 (Write Basic Tests) ──┐
T005 (Write Voice Tests) ──┼─→ T007 (Implement Class Structure)
T006 (Write Error Tests) ──┘           ↓
                                        ├─→ T008 (Implement Voice Selection & API)
                                        ├─→ T009 (Implement Audio Conversion)
                                        └─→ T010 (Implement Synthesize - Basic)
                                              ↓
Factory Integration:                          ├─→ T011 (Write Factory Tests) → T012 (Update Factory)
                                              ↓
Duration Matching:                            ├─→ T013 (Write Duration Tests) → T014 (Extract Duration Utility)
                                              │                                      ↓
                                              │                                      ├─→ T015 (Integrate in ElevenLabs)
                                              │                                      └─→ T016 (Refactor Coqui)
                                              ↓
Manual Testing & Contracts:                   ├─→ T017 (Update Manual Client)
                                              └─→ T018 (Contract Tests)
                                                    ↓
Optional Integration:                               └─→ OPTIONAL-T019 (Live API Tests)
```

---

## Parallelizable Tasks

These tasks can be worked on in parallel after their dependencies are met:

**After T003 (VoiceProfile Fields Complete)**:
- T004 (Write Basic Tests)
- T005 (Write Voice Tests)
- T006 (Write Error Tests)

**After T010 (Basic Synthesize Complete)**:
- T011 (Factory Tests)
- T013 (Duration Matching Tests)
- T018 (Contract Tests)

**After T014 (Duration Utility Complete)**:
- T015 (Integrate in ElevenLabs)
- T016 (Refactor Coqui)

---

## Test Coverage Goals

**Unit Test Coverage**: 80% minimum for new code
**Critical Path Coverage**: 95% for:
- Voice selection logic
- Error classification
- Audio format conversion
- Duration matching integration

**Test Distribution**:
- Unit tests (mocked API): ~20 tests
- Contract tests: ~4 tests
- Integration tests (optional, live API): ~4 tests

**Total Test Count**: 24-28 tests

---

## Pre-Commit Checklist

Before considering this feature complete, verify:

- [ ] All unit tests PASS (make sts-test-unit)
- [ ] Test coverage ≥ 80% (make sts-test-coverage)
- [ ] Code formatted (make fmt)
- [ ] Code linted (make lint)
- [ ] Type checking passes (make typecheck)
- [ ] Manual test client works with both providers
- [ ] Contract tests validate AudioAsset schema compatibility
- [ ] Duration matching works identically to Coqui provider
- [ ] No duplicate code (rubberband logic extracted to utility)
- [ ] All task acceptance criteria met
- [ ] Documentation updated (README with ElevenLabs setup instructions)

---

## Next Steps After Task Completion

1. **Merge to main branch**: Create PR with summary of changes
2. **Update STS service README**: Document ElevenLabs setup (API key, usage)
3. **Add to deployment docs**: Document ELEVENLABS_API_KEY environment variable
4. **Consider follow-up features**:
   - Streaming API support (lower latency)
   - Voice cloning integration
   - Cost tracking and limits
   - Response caching for repeated phrases

---

## Estimated Total Time

**Critical Path** (P1-P3 tasks): ~10-12 hours
**Full Implementation** (including P4-P5): ~13-15 hours
**With Optional Integration Tests**: ~14-16 hours

---

## Risk Mitigation

**Risk**: ElevenLabs API changes breaking implementation
- **Mitigation**: Pin `elevenlabs>=0.2.0,<1.0.0` in requirements

**Risk**: Rate limiting during testing
- **Mitigation**: Mark integration tests as optional, use mocks for unit tests

**Risk**: API latency exceeds timeout
- **Mitigation**: Configurable timeout_ms in TTSConfig (default 5000ms)

**Risk**: Rubberband extraction breaks Coqui provider
- **Mitigation**: T016 includes comprehensive backward compatibility testing

---

**Generated by**: speckit.tasks agent
**Constitution Compliance**: ✅ Principle VIII (TDD enforced - tests written BEFORE implementation)
