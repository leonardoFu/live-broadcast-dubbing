# Translation Component - Implementation Tasks

**Feature**: 006-translation-component
**Status**: Ready for Implementation
**Dependencies**: ASR module (completed)
**TDD**: Tests MUST be written before implementation

## Overview

This task list follows strict TDD principles (Constitution Principle VIII). Each task includes:
- Test implementation BEFORE production code
- Clear acceptance criteria
- Explicit dependencies
- Verification steps

## Task Dependency Graph

```
Phase 1 (Setup)
T001 → T002 → T003

Phase 2 (Core Models)
T003 → T004 → T005 → T006

Phase 3 (Text Processing - Parallelizable)
T006 → [T007, T008, T009] (can run in parallel)

Phase 3.5 (DeepL Provider)
T009 → T009.1 → T009.2 → T009.3

Phase 4 (Mock Implementations)
[T007, T008, T009] → T010 → T011

Phase 5 (Factory & Integration)
T011, T009.3 → T012 → T013

Phase 6 (Configuration)
T013 → T014 → T015

Phase 7 (Documentation)
T015 → T016
```

---

## Phase 1: Setup (3 tasks)

### T001: Create translation module directory structure
**Priority**: P1 (Critical Path)
**Type**: Setup
**Dependencies**: None
**TDD**: N/A (infrastructure)

**Description**: Create the basic directory structure for the translation module following the ASR module pattern.

**Steps**:
1. Create `apps/sts-service/src/sts_service/translation/` directory
2. Create `apps/sts-service/tests/unit/translation/` directory
3. Create `__init__.py` files in both directories
4. Verify directory structure matches plan.md Phase 1

**Acceptance Criteria**:
- [x] Directory structure exists
- [x] `__init__.py` files created
- [x] Structure matches ASR module pattern

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/__init__.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/__init__.py`

**Verification**:
```bash
ls -la apps/sts-service/src/sts_service/translation/
ls -la apps/sts-service/tests/unit/translation/
```

---

### T002: Create spec documentation structure
**Priority**: P1 (Critical Path)
**Type**: Setup
**Dependencies**: T001
**TDD**: N/A (documentation)

**Description**: Create documentation structure for the Translation component feature.

**Steps**:
1. Create `specs/006-translation-component/contracts/` directory
2. Verify spec.md, plan.md, data-model.md already exist (from previous agents)
3. Create placeholder for quickstart.md (to be filled in Phase 5)

**Acceptance Criteria**:
- [x] Contracts directory exists
- [x] Required spec files present
- [x] Structure ready for contract documentation

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/contracts/` (directory)

**Verification**:
```bash
ls -la specs/006-translation-component/
ls -la specs/006-translation-component/contracts/
```

---

### T003: Create test fixture file
**Priority**: P1 (Critical Path)
**Type**: Setup
**Dependencies**: T002
**TDD**: N/A (test infrastructure)

**Description**: Create shared test fixtures for translation module tests following plan.md test strategy.

**Steps**:
1. Create `apps/sts-service/tests/unit/translation/conftest.py`
2. Add sports domain fixtures (per plan.md)
3. Add conversation fixtures with speaker labels
4. Add punctuation-heavy fixtures
5. Add helper for creating mock TranscriptAsset objects

**Acceptance Criteria**:
- [x] conftest.py created with all fixture sets
- [x] Fixtures match plan.md Section "Test Fixtures"
- [x] Helper functions for asset creation

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/conftest.py`

**Verification**:
```bash
pytest apps/sts-service/tests/unit/translation/conftest.py --collect-only
```

---

## Phase 2: Core Models and Contracts (3 tasks)

### T004: Test and implement error classification (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T003
**TDD**: MANDATORY - Write tests first

**Description**: Implement error classification and handling following ASR module pattern.

**Steps**:
1. **TESTS FIRST**: Create `test_errors.py` with test cases:
   - Test exception to TranslationErrorType mapping
   - Test retryable error detection
   - Test create_translation_error factory
   - Test all error types (TIMEOUT, EMPTY_INPUT, PROVIDER_ERROR, etc.)
2. Run tests - verify they FAIL
3. Implement `errors.py`:
   - classify_error() function
   - is_retryable() function
   - create_translation_error() factory
   - _RETRYABLE_ERRORS set
4. Run tests - verify they PASS
5. Check coverage: 95% minimum for error classification

**Acceptance Criteria**:
- [x] test_errors.py written BEFORE implementation
- [x] All tests initially fail
- [x] errors.py implementation passes all tests
- [x] Coverage >= 95% for errors.py
- [x] Retryable classification matches spec (TIMEOUT, PROVIDER_ERROR = retryable)

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_errors.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/errors.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_errors.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_errors.py -v

# Step 5 (coverage check)
pytest apps/sts-service/tests/unit/translation/test_errors.py --cov=sts_service.translation.errors --cov-report=term-missing
```

---

### T005: Test and implement data models (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T004
**TDD**: MANDATORY - Write tests first

**Description**: Implement Pydantic models for Translation component following data-model.md.

**Steps**:
1. **TESTS FIRST**: Create test cases in `test_errors.py` (extend existing):
   - Test TranslationStatus enum values
   - Test TranslationError Pydantic validation
   - Test SpeakerPolicy default values
   - Test NormalizationPolicy default values
   - Test TextAsset extends AssetIdentifiers
   - Test TextAsset.is_retryable property
2. Run tests - verify they FAIL
3. Implement `models.py`:
   - Import AssetIdentifiers from asr.models
   - Define all enums (TranslationStatus, TranslationErrorType)
   - Define all models (TranslationError, SpeakerPolicy, NormalizationPolicy, TextAsset)
4. Run tests - verify they PASS
5. Check Pydantic validation edge cases

**Acceptance Criteria**:
- [x] Test cases written BEFORE models.py
- [x] All tests initially fail
- [x] models.py implementation passes all tests
- [x] TextAsset correctly extends AssetIdentifiers
- [x] All Pydantic constraints validated
- [x] is_retryable property works correctly

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/models.py`

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_errors.py` (add model validation tests)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_errors.py::TestModels -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_errors.py::TestModels -v

# Pydantic validation check
python -c "from sts_service.translation.models import TextAsset; print(TextAsset.model_json_schema())"
```

---

### T006: Test and implement component interface (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T005
**TDD**: MANDATORY - Write tests first

**Description**: Implement Protocol + BaseClass for Translation component following ASR module pattern.

**Steps**:
1. **TESTS FIRST**: Create `test_interface.py`:
   - Test TranslationComponent protocol structure
   - Test runtime_checkable works
   - Test BaseTranslationComponent abstract methods
   - Test component_name property returns "translate"
2. Run tests - verify they FAIL
3. Implement `interface.py`:
   - Define TranslationComponent Protocol
   - Define BaseTranslationComponent ABC
   - Add helper method _apply_normalization stub (to be implemented in Phase 3)
4. Run tests - verify they PASS

**Acceptance Criteria**:
- [x] test_interface.py written BEFORE interface.py
- [x] All tests initially fail
- [x] interface.py matches spec.md Section "Component Architecture"
- [x] Protocol is runtime_checkable
- [x] BaseTranslationComponent has correct abstract methods
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_interface.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/interface.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_interface.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_interface.py -v

# Check runtime_checkable
python -c "from sts_service.translation.interface import TranslationComponent; print(isinstance(TranslationComponent, type))"
```

---

## Phase 3: Text Processing Utilities (3 tasks - Parallelizable)

### T007: Test and implement speaker detection (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T006
**TDD**: MANDATORY - Write tests first

**Description**: Implement SpeakerLabelDetector for pre-translation speaker label removal.

**Steps**:
1. **TESTS FIRST**: Create `test_speaker_detection.py`:
   - Test pattern matching: "Alice: text" → ("Alice", "text")
   - Test no match: "Hello world" → ("default", "Hello world")
   - Test false positive avoidance: "Time: 1:54" should NOT match
   - Test multiple patterns: ">> Bob: text" → ("Bob", "text")
   - Test empty string handling
   - Test determinism: same input 100 times → same output
2. Run tests - verify they FAIL
3. Implement `preprocessing.py`:
   - SpeakerLabelDetector class
   - DEFAULT_PATTERNS from spec
   - detect_and_remove() method
4. Run tests - verify they PASS
5. Coverage: 95% minimum

**Acceptance Criteria**:
- [x] test_speaker_detection.py written BEFORE preprocessing.py
- [x] All tests initially fail
- [x] No false positives (manual inspection of edge cases)
- [x] Determinism verified (100 runs same output)
- [x] Coverage >= 95%
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_speaker_detection.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/preprocessing.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_speaker_detection.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_speaker_detection.py -v

# Coverage check
pytest apps/sts-service/tests/unit/translation/test_speaker_detection.py --cov=sts_service.translation.preprocessing --cov-report=term-missing --cov-fail-under=95
```

---

### T008: Test and implement translation normalization (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T006
**TDD**: MANDATORY - Write tests first

**Description**: Implement TranslationNormalizer for deterministic text preprocessing.

**Steps**:
1. **TESTS FIRST**: Create `test_normalization.py`:
   - Test time phrases: "1:54 REMAINING" → "1:54 remaining"
   - Test hyphens: "TEN-YARD" → "TEN YARD" (preserve "15-12")
   - Test abbreviations: "NFL" → "N F L", "vs." → "versus"
   - Test symbols: "&" → "and", "%" → "percent"
   - Test policy disable: enabled=False should return input unchanged
   - Test determinism: same input 100 times → same output
   - Test each policy flag independently
2. Run tests - verify they FAIL
3. Implement `normalization.py`:
   - TranslationNormalizer class
   - normalize() method with policy checks
   - _normalize_time_phrases(), _normalize_hyphens(), _expand_abbreviations(), _normalize_symbols()
4. Run tests - verify they PASS
5. Coverage: 95% minimum

**Acceptance Criteria**:
- [x] test_normalization.py written BEFORE normalization.py
- [x] All tests initially fail
- [x] All rules produce deterministic output (100 runs)
- [x] Policy flags work correctly
- [x] Coverage >= 95%
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_normalization.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/normalization.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_normalization.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_normalization.py -v

# Coverage and determinism
pytest apps/sts-service/tests/unit/translation/test_normalization.py --cov=sts_service.translation.normalization --cov-report=term-missing --cov-fail-under=95
```

---

### T009: Test and implement TTS cleanup (TDD)
**Priority**: P2 (Nice to have)
**Type**: Implementation
**Dependencies**: T006
**TDD**: MANDATORY - Write tests first

**Description**: Implement TTSCleanup for post-translation text optimization.

**Steps**:
1. **TESTS FIRST**: Create `test_postprocessing.py`:
   - Test smart punctuation: """ → "\"", "—" → "-"
   - Test score rewriting: "15-12" → "15 to 12"
   - Test whitespace normalization: multiple spaces → single space
   - Test determinism: same input 100 times → same output
2. Run tests - verify they FAIL
3. Implement `postprocessing.py`:
   - TTSCleanup class
   - cleanup() method
   - _normalize_smart_punctuation(), _normalize_scores(), _normalize_whitespace()
4. Run tests - verify they PASS
5. Coverage: 95% minimum

**Acceptance Criteria**:
- [x] test_postprocessing.py written BEFORE postprocessing.py
- [x] All tests initially fail
- [x] Determinism verified (100 runs)
- [x] Coverage >= 95%
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_postprocessing.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/postprocessing.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_postprocessing.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_postprocessing.py -v

# Coverage check
pytest apps/sts-service/tests/unit/translation/test_postprocessing.py --cov=sts_service.translation.postprocessing --cov-report=term-missing --cov-fail-under=95
```

---

## Phase 3.5: DeepL Provider Implementation (3 tasks)

### T009.1: Create .env.example with DeepL documentation
**Priority**: P1 (Critical Path)
**Type**: Documentation
**Dependencies**: T009
**TDD**: N/A (documentation)

**Description**: Create environment variable documentation for DeepL API configuration.

**Steps**:
1. Create `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/.env.example`
2. Document DEEPL_API_KEY variable
3. Document DEEPL_FREE_API variable (boolean)
4. Add comments explaining DeepL API key sources (free vs pro)
5. Add link to DeepL API documentation

**Acceptance Criteria**:
- [ ] .env.example created with clear documentation
- [ ] Both required environment variables documented
- [ ] Comments explain free vs pro API differences
- [ ] Link to DeepL documentation included

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/.env.example`

**Verification**:
```bash
cat apps/sts-service/.env.example
```

---

### T009.2: Update error classification for DeepL exceptions
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T004, T009.1
**TDD**: Extend existing error tests

**Description**: Extend error classification to handle DeepL-specific exceptions.

**Steps**:
1. **TESTS FIRST**: Extend `test_errors.py`:
   - Test DeepLException → PROVIDER_ERROR mapping
   - Test AuthorizationException → PROVIDER_ERROR (retryable=False)
   - Test QuotaExceededException → PROVIDER_ERROR (retryable=False)
   - Test ConnectionException → TIMEOUT (retryable=True)
   - Test classify_error() handles deepl.exceptions.*
2. Run tests - verify they FAIL
3. Modify `errors.py`:
   - Add deepl.exceptions import (conditional on deepl availability)
   - Update classify_error() to handle DeepL exceptions
   - Update _RETRYABLE_ERRORS for DeepL connection errors
4. Run tests - verify they PASS
5. Coverage: 95% minimum

**Acceptance Criteria**:
- [ ] Tests extended BEFORE errors.py modification
- [ ] All tests initially fail
- [ ] DeepL exceptions correctly classified
- [ ] Auth/quota errors marked as non-retryable
- [ ] Connection errors marked as retryable
- [ ] Coverage >= 95%
- [ ] All tests pass

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_errors.py` (extend tests)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/errors.py` (add DeepL handling)

**Verification**:
```bash
# Tests should fail first
pytest apps/sts-service/tests/unit/translation/test_errors.py::TestDeepLExceptions -v

# Tests should pass after implementation
pytest apps/sts-service/tests/unit/translation/test_errors.py::TestDeepLExceptions -v

# Coverage check
pytest apps/sts-service/tests/unit/translation/test_errors.py --cov=sts_service.translation.errors --cov-report=term-missing --cov-fail-under=95
```

---

### T009.3: Test and implement DeepL provider (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T009.2
**TDD**: MANDATORY - Write tests first

**Description**: Implement DeepLTranslationComponent with production-grade error handling.

**Steps**:
1. **TESTS FIRST**: Create `test_deepl_provider.py`:
   - Test DeepLTranslationComponent protocol compliance
   - Test successful translation with mocked deepl.Translator
   - Test API key initialization from env vars
   - Test formality handling (preserve from TranscriptAsset.formality)
   - Test language code mapping (en-US → EN-US for DeepL)
   - Test error handling:
     - AuthorizationException → TextAsset(status=FAILED, retryable=False)
     - QuotaExceededException → TextAsset(status=FAILED, retryable=False)
     - ConnectionException → TextAsset(status=FAILED, retryable=True)
   - Test timeout handling (deepl client timeout)
   - Test component_name = "translate"
   - Test component_instance = "deepl"
   - Test is_ready checks API key presence
   - Test asset lineage preservation
   - Test speaker policy integration
   - Test normalization policy integration
2. Run tests - verify they FAIL
3. Implement `deepl_provider.py`:
   - DeepLTranslationComponent class extends BaseTranslationComponent
   - Initialize deepl.Translator in __init__
   - Implement translate() method with error handling
   - Map language codes for DeepL compatibility
   - Use _apply_normalization helper from base class
   - Set timeout from TranslationConfig
4. Run tests - verify they PASS
5. Coverage: 95% minimum

**Acceptance Criteria**:
- [ ] test_deepl_provider.py written BEFORE deepl_provider.py
- [ ] All tests initially fail
- [ ] DeepLTranslationComponent implements TranslationComponent protocol
- [ ] Error handling covers all DeepL exception types
- [ ] Language code mapping correct (DeepL uses uppercase variants)
- [ ] API key loaded from environment variables
- [ ] is_ready returns False if API key missing
- [ ] Coverage >= 95%
- [ ] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_deepl_provider.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/deepl_provider.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_deepl_provider.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_deepl_provider.py -v

# Coverage check
pytest apps/sts-service/tests/unit/translation/test_deepl_provider.py --cov=sts_service.translation.deepl_provider --cov-report=term-missing --cov-fail-under=95

# Check protocol compliance
python -c "from sts_service.translation.deepl_provider import DeepLTranslationComponent; from sts_service.translation.interface import TranslationComponent; print(isinstance(DeepLTranslationComponent(), TranslationComponent))"
```

---

## Phase 4: Mock Implementations (2 tasks)

### T010: Update BaseTranslationComponent with normalization helper
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T007, T008, T009
**TDD**: Extend existing interface tests

**Description**: Add _apply_normalization helper method to BaseTranslationComponent.

**Steps**:
1. **TESTS FIRST**: Extend `test_interface.py`:
   - Test _apply_normalization calls TranslationNormalizer
   - Test _apply_normalization with policy=None returns original text
   - Test _apply_normalization with policy.enabled=False returns original text
2. Run tests - verify they FAIL
3. Modify `interface.py`:
   - Add _apply_normalization() helper to BaseTranslationComponent
   - Integrate TranslationNormalizer and SpeakerLabelDetector
4. Run tests - verify they PASS

**Acceptance Criteria**:
- [x] Tests extended BEFORE implementation
- [x] All tests initially fail
- [x] Helper method integrates preprocessing utilities
- [x] All tests pass

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_interface.py` (extend tests)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/interface.py` (add helper)

**Verification**:
```bash
pytest apps/sts-service/tests/unit/translation/test_interface.py -v
```

---

### T011: Test and implement mock translation components (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T010
**TDD**: MANDATORY - Write tests first

**Description**: Implement MockIdentityTranslation and MockDictionaryTranslation.

**Steps**:
1. **TESTS FIRST**: Create `test_translation_component.py`:
   - Test MockIdentityTranslation protocol compliance
   - Test identity: normalized input = output
   - Test MockDictionaryTranslation phrase mapping
   - Test component_name = "translate"
   - Test component_instance values
   - Test is_ready = True
   - Test asset lineage (parent_asset_ids propagation)
   - Test speaker policy integration
   - Test normalization policy integration
   - Test error handling (empty input, unsupported language)
   - Test determinism: same inputs → same outputs (100 runs)
2. Run tests - verify they FAIL
3. Implement `mock.py`:
   - MockIdentityTranslation class
   - MockDictionaryTranslation class
   - Both extend BaseTranslationComponent
   - Use _apply_normalization helper
4. Run tests - verify they PASS
5. Coverage: 95% minimum

**Acceptance Criteria**:
- [x] test_translation_component.py written BEFORE mock.py
- [x] All tests initially fail
- [x] Both mocks implement TranslationComponent protocol
- [x] Determinism verified (100 runs)
- [x] Asset IDs unique, parent_asset_ids correct
- [x] Coverage >= 95%
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_translation_component.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/mock.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_translation_component.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_translation_component.py -v

# Coverage check
pytest apps/sts-service/tests/unit/translation/test_translation_component.py --cov=sts_service.translation.mock --cov-report=term-missing --cov-fail-under=95
```

---

## Phase 5: Factory and Integration (2 tasks)

### T012: Test and implement factory (TDD)
**Priority**: P1 (Critical Path)
**Type**: Implementation
**Dependencies**: T011, T009.3
**TDD**: MANDATORY - Write tests first

**Description**: Implement create_translation_component factory following ASR module pattern with DeepL provider support.

**Steps**:
1. **TESTS FIRST**: Create `test_factory.py`:
   - Test mock=True, mock_type="identity" returns MockIdentityTranslation
   - Test mock=True, mock_type="dictionary" returns MockDictionaryTranslation
   - Test mock_type="dictionary" without dictionary raises ValueError
   - Test mock=False, provider="deepl" returns DeepLTranslationComponent
   - Test mock=False, provider="deepl" without API key returns component with is_ready=False
   - Test mock=False with unsupported provider raises ValueError
   - Test factory returns TranslationComponent protocol-compliant objects
2. Run tests - verify they FAIL
3. Implement `factory.py`:
   - create_translation_component() function with provider parameter
   - Mock instantiation logic
   - DeepL provider instantiation logic
   - Config parameter support (for Phase 6)
   - Provider validation
4. Run tests - verify they PASS

**Acceptance Criteria**:
- [x] test_factory.py written BEFORE factory.py
- [x] All tests initially fail
- [x] Factory creates correct mock types
- [x] Factory creates DeepL provider when mock=False, provider="deepl"
- [x] Factory validates provider parameter
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_factory.py` (FIRST)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/factory.py` (SECOND)

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/unit/translation/test_factory.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/unit/translation/test_factory.py -v
```

---

### T013: Test and implement ASR integration (TDD)
**Priority**: P1 (Critical Path)
**Type**: Integration
**Dependencies**: T012
**TDD**: MANDATORY - Write tests first

**Description**: Implement and test ASR → Translation pipeline integration.

**Steps**:
1. **TESTS FIRST**: Create `apps/sts-service/tests/integration/test_asr_translation.py`:
   - Test ASR → Translation pipeline (MockASRComponent → MockIdentityTranslation)
   - Test asset lineage (TextAsset.parent_asset_ids contains TranscriptAsset.asset_id)
   - Test language metadata flow (TranscriptAsset.language → TextAsset.source_language)
   - Test speaker detection with ASR output
   - Test error propagation
   - Test adapter pattern (TranscriptAsset → translate() call)
2. Run tests - verify they FAIL
3. Create integration adapter helper in test file:
   - translate_transcript() function per plan.md Phase 4
4. Run tests - verify they PASS
5. Document adapter pattern in code comments

**Acceptance Criteria**:
- [x] Integration test written BEFORE adapter implementation
- [x] All tests initially fail
- [x] Asset lineage correctly tracked
- [x] Language metadata flows correctly
- [x] Adapter pattern documented
- [x] All tests pass

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/integration/test_asr_translation.py`

**Verification**:
```bash
# Step 2 (should fail)
pytest apps/sts-service/tests/integration/test_asr_translation.py -v

# Step 4 (should pass)
pytest apps/sts-service/tests/integration/test_asr_translation.py -v

# Lineage verification
pytest apps/sts-service/tests/integration/test_asr_translation.py::test_asset_lineage -v
```

---

## Phase 6: Configuration and Validation (2 tasks)

### T014: Test and implement TranslationConfig (TDD)
**Priority**: P2 (Nice to have)
**Type**: Implementation
**Dependencies**: T013
**TDD**: MANDATORY - Write tests first

**Description**: Add TranslationConfig model and language pair validation.

**Steps**:
1. **TESTS FIRST**: Extend `test_errors.py` with config tests:
   - Test TranslationConfig Pydantic validation
   - Test default values
   - Test timeout_ms constraint (ge=1000)
   - Test language pair validation (empty list = all allowed)
   - Test supported_language_pairs matching
2. Run tests - verify they FAIL
3. Modify `models.py`:
   - Add TranslationConfig model per plan.md Phase 5
   - Add validate_language_pair() helper
4. Run tests - verify they PASS

**Acceptance Criteria**:
- [x] Tests written BEFORE models.py modification
- [x] All tests initially fail
- [x] Config validates with Pydantic
- [x] Language pair validation correct
- [x] All tests pass

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_errors.py` (extend with config tests)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/models.py` (add TranslationConfig)

**Verification**:
```bash
pytest apps/sts-service/tests/unit/translation/test_errors.py::TestTranslationConfig -v
```

---

### T015: Update factory with config support
**Priority**: P2 (Nice to have)
**Type**: Implementation
**Dependencies**: T014
**TDD**: Extend existing factory tests

**Description**: Update factory to accept TranslationConfig parameter.

**Steps**:
1. **TESTS FIRST**: Extend `test_factory.py`:
   - Test factory accepts config parameter
   - Test unsupported language pair returns FAILED with retryable=False
   - Test config defaults propagate to components
2. Run tests - verify they FAIL
3. Modify `factory.py`:
   - Accept config: TranslationConfig | None parameter
   - Pass config to component constructors
4. Run tests - verify they PASS

**Acceptance Criteria**:
- [x] Tests extended BEFORE factory.py modification
- [x] All tests initially fail
- [x] Factory accepts config
- [x] Language pair validation integrated
- [x] All tests pass

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/tests/unit/translation/test_factory.py` (extend tests)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/factory.py` (add config)

**Verification**:
```bash
pytest apps/sts-service/tests/unit/translation/test_factory.py -v
```

---

## Phase 7: Documentation (1 task)

### T016: Create documentation artifacts
**Priority**: P2 (Nice to have)
**Type**: Documentation
**Dependencies**: T015
**TDD**: N/A (documentation)

**Description**: Complete documentation for Translation component.

**Steps**:
1. Create `contracts/TranslationComponent.md`:
   - Document TranslationComponent protocol contract
   - Include method signatures and behavior
   - Document error handling contract
2. Create `contracts/directory-structure.json`:
   - Document module structure per plan.md Phase 6
3. Create `quickstart.md`:
   - Developer quick start guide
   - Example usage with ASR integration
   - Configuration examples
4. Update `__init__.py` to export public API:
   - Export factory, models, interface, errors
   - Add module docstring

**Acceptance Criteria**:
- [x] All contract documentation complete
- [x] directory-structure.json matches implementation
- [x] quickstart.md has runnable examples
- [x] Public API properly exported

**Files Created**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/contracts/TranslationComponent.md`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/contracts/directory-structure.json`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/quickstart.md`

**Files Modified**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/__init__.py`

**Verification**:
```bash
# Validate JSON structure
python -c "import json; json.load(open('specs/006-translation-component/contracts/directory-structure.json'))"

# Check public API exports
python -c "from sts_service.translation import create_translation_component, TextAsset, TranslationComponent; print('OK')"
```

---

## Summary

**Total Tasks**: 19
**Critical Path**: T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T009.1 → T009.2 → T009.3 → T010 → T011 → T012 → T013
**Parallelizable Tasks**: T007, T008, T009 (after T006)

**By Phase**:
- Phase 1 (Setup): 3 tasks
- Phase 2 (Core Models): 3 tasks
- Phase 3 (Text Processing): 3 tasks (parallelizable)
- Phase 3.5 (DeepL Provider): 3 tasks
- Phase 4 (Mock Implementations): 2 tasks
- Phase 5 (Factory & Integration): 2 tasks
- Phase 6 (Configuration): 2 tasks
- Phase 7 (Documentation): 1 task

**By Priority**:
- P1 (Critical): 16 tasks
- P2 (Nice to have): 3 tasks

**TDD Requirements**:
- All implementation tasks require tests BEFORE code
- Tests must initially FAIL
- Coverage targets: 80% minimum, 95% for critical paths
- Determinism tests: 100 runs same output

**Estimated Effort**:
- Phase 1-2: ~2 hours (setup + models)
- Phase 3: ~4 hours (text processing + tests)
- Phase 3.5: ~3 hours (DeepL provider + error handling)
- Phase 4-5: ~3 hours (mocks + integration)
- Phase 6-7: ~2 hours (config + docs)
- **Total**: ~14 hours

**Success Criteria**:
- All tests pass
- Coverage >= 80% (95% for preprocessing/normalization/DeepL provider)
- ASR → Translation integration works end-to-end
- DeepL provider fully integrated with factory
- Error handling covers all DeepL exception types
- Asset lineage correctly tracked
- Determinism verified for all processing
- Documentation complete and accurate
