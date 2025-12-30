# Implementation Plan: Translation Component

**Branch**: `006-translation-component` | **Date**: 2025-12-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-translation-component/spec.md`

## Summary

This plan implements the Translation component as a pluggable module in the STS (Speech-to-Speech) service pipeline. The component translates per-fragment transcript text from source to target language with deterministic text preprocessing for improved translation quality and real-time stability. It follows the established ASR module patterns (Protocol + BaseClass, factory, errors) and integrates seamlessly with the ASR module output.

**Core Features**:
- Receive `TranscriptAsset` from ASR module
- Apply deterministic normalization (time phrases, hyphens, abbreviations, symbols)
- Optional speaker label detection and removal
- Translate text (mock implementations: identity, dictionary)
- Optional TTS-oriented cleanup (smart punctuation, score rewriting)
- Produce `TextAsset` with proper lineage tracking
- Comprehensive error handling with retryable classification

## Technical Context

**Language/Version**: Python 3.10.x (per constitution and monorepo setup)
**Primary Dependencies**:
- Pydantic >=2.0 (data models)
- pytest >=7.0 (testing)
- deepl >=1.0.0 (DeepL API client for production translation)

**Storage**: N/A (stateless, in-memory component)
**Testing**: pytest, pytest-mock, pytest-cov (80% minimum coverage, 95% for critical paths)
**Target Platform**: Linux server (RunPod GPU service, CPU-compatible)
**Project Type**: Service module (apps/sts-service/src/sts_service/translation/)
**Performance Goals**:
- <50ms normalization latency per fragment
- Deterministic output for identical inputs
- Zero translation variance for mock implementations

**Constraints**:
- Stateless processing (no cross-fragment context)
- Asset lineage must track parent_asset_ids
- Compatible with per-fragment pipeline processing

**Scale/Scope**:
- Module: ~9 Python files (~1500 LOC)
- Tests: ~7 test files (~1000 LOC)
- Test fixtures: 3 domain-specific fixture sets
- Configuration: .env.example for environment variable documentation

## Constitution Check

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all components (normalization, speaker detection, postprocessing, component contract)
- [x] Mock patterns documented (MockIdentityTranslation, MockDictionaryTranslation)
- [x] Coverage targets specified (80% minimum, 95% for normalization/processing logic)
- [x] Test infrastructure matches constitution requirements (pytest, coverage enforcement)
- [x] Test organization follows standard structure (apps/sts-service/tests/unit/translation/, tests/integration/)

**Principle II - Simplicity First**:
- [x] Single production provider (DeepL API) with mock fallbacks
- [x] Deterministic rules-based normalization (no ML models)
- [x] Minimal preprocessing (speaker detection, normalization only)
- [x] Environment variable configuration (no complex config files)

**Principle V - Explicit Contracts**:
- [x] Protocol-based interface (TranslationComponent)
- [x] Pydantic models for all data structures
- [x] Clear error taxonomy with retryable flags

**Principle X - Modular Architecture**:
- [x] Clear separation: preprocessing, normalization, postprocessing, interface, models, errors
- [x] Factory pattern for component instantiation
- [x] Protocol-based abstraction for future providers

## Project Structure

### Documentation (this feature)

```text
specs/006-translation-component/
├── spec.md              # Feature specification (DONE - from speckit-specify)
├── plan.md              # This file (DONE - speckit-plan output)
├── data-model.md        # Data models and schemas (CREATED by this plan)
├── contracts/           # Interface contracts (CREATED by this plan)
│   ├── TranslationComponent.md
│   └── directory-structure.json
└── quickstart.md        # Developer quick start (CREATED by this plan)
```

### Source Code (repository root)

```text
apps/sts-service/src/sts_service/translation/
├── __init__.py                # Public API exports
├── interface.py               # Protocol + BaseClass (TranslationComponent, BaseTranslationComponent)
├── models.py                  # Pydantic models (TextAsset, policies, errors)
├── errors.py                  # Error classification and handling (DeepL-aware)
├── factory.py                 # Component factory (create_translation_component)
├── mock.py                    # Mock implementations (identity, dictionary)
├── deepl_provider.py          # DeepL API implementation
├── preprocessing.py           # Speaker label detection (SpeakerLabelDetector)
├── normalization.py           # Translation-oriented normalization (TranslationNormalizer)
└── postprocessing.py          # TTS-oriented cleanup (TTSCleanup)

apps/sts-service/tests/unit/translation/
├── __init__.py
├── test_speaker_detection.py       # Speaker label pattern matching
├── test_normalization.py           # Normalization rules determinism
├── test_postprocessing.py          # TTS cleanup rules
├── test_translation_component.py   # Component contract, mocks, lineage
├── test_deepl_provider.py          # DeepL API integration tests (mocked)
└── test_errors.py                  # Error classification (DeepL-aware)

apps/sts-service/tests/integration/
├── __init__.py
└── test_asr_translation.py         # ASR → Translation integration
```

**Structure Decision**: Single service module structure following ASR module pattern. All translation logic lives in `apps/sts-service/src/sts_service/translation/` with unit tests in `apps/sts-service/tests/unit/translation/` and integration tests in `apps/sts-service/tests/integration/`.

**Configuration Files**:
```text
apps/sts-service/
├── .env.example            # Environment variable documentation (DEEPL_AUTH_KEY, etc.)
├── requirements.txt        # Production dependencies (includes deepl>=1.0.0)
└── requirements-dev.txt    # Development dependencies
```

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- Target: All normalization rules, speaker detection patterns, TTS cleanup, error handling
- Tools: pytest, pytest-mock
- Coverage: 80% minimum (95% for preprocessing/normalization/postprocessing)
- Mocking: No external dependencies (pure functions)
- Location: `apps/sts-service/tests/unit/translation/`

**Contract Tests** (mandatory):
- Target: TranslationComponent protocol compliance, TextAsset schema validation
- Tools: pytest with Pydantic validation
- Coverage: 100% of protocol methods, all error types
- Mocking: MockIdentityTranslation, MockDictionaryTranslation
- Location: `apps/sts-service/tests/unit/translation/test_translation_component.py`

**Integration Tests** (required):
- Target: ASR → Translation pipeline, asset lineage tracking
- Tools: pytest with MockASRComponent
- Coverage: Happy path + error propagation
- Mocking: Use MockASRComponent to generate TranscriptAsset
- Location: `apps/sts-service/tests/integration/test_asr_translation.py`

### Mock Patterns

**Translation Mocks**:
- `MockIdentityTranslation`: Returns normalized input as output (identity function)
- `MockDictionaryTranslation`: Uses fixed dictionary for deterministic phrase mapping
- Both implement full `TranslationComponent` protocol

**Test Fixtures** (no audio required):
- Sports domain: `["1:54 REMAINING IN THE FOURTH QUARTER", "TOUCHDOWN CHIEFS!", "NFL PLAYOFFS: CHIEFS VS BILLS", "15-12 FINAL SCORE"]`
- Conversation: `["Alice: How are you today?", ">> Bob: I'm doing great, thanks!", "Charlie: That's wonderful to hear."]`
- Punctuation-heavy: `["Wait... what did you say?", "The score is 21-14—an exciting game!", "She said, \"I'll be there soon.\""]`

### Coverage Enforcement

**Pre-commit**: Run `pytest --cov=sts_service.translation --cov-fail-under=80`
**CI**: Run `pytest --cov=sts_service.translation --cov-fail-under=80` - block merge if fails
**Critical paths**: Normalization, speaker detection, error classification → 95% minimum

### Test Naming Conventions

- `test_<function>_happy_path()` - Normal operation
- `test_<function>_error_<condition>()` - Error handling
- `test_<function>_edge_<case>()` - Boundary conditions
- `test_<function>_determinism()` - Determinism verification
- `test_<function>_integration_<workflow>()` - Integration scenarios

## Implementation Phases

### Phase 0: Setup and Research ✓

**Status**: Complete (spec already defines all patterns)

**Research Findings**:
- ASR module patterns fully documented (interface.py, models.py, errors.py, factory.py, mock.py)
- Pydantic models with AssetIdentifiers base class
- Protocol + BaseClass pattern for component contract
- Error classification with retryable flags
- Factory pattern for component instantiation

**No unknowns remain** - spec provides complete implementation guidance.

### Phase 1: Core Models and Contracts

**Objective**: Define data models, error types, and interface contracts.

**Deliverables**:
1. `models.py`: TextAsset, TranslationStatus, TranslationError, SpeakerPolicy, NormalizationPolicy
2. `errors.py`: Error classification, retryable detection, error factory
3. `interface.py`: TranslationComponent protocol, BaseTranslationComponent
4. `data-model.md`: Schema documentation
5. `contracts/TranslationComponent.md`: Interface contract documentation

**Files to Create**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/__init__.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/models.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/errors.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/interface.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/data-model.md`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/contracts/TranslationComponent.md`

**Tests** (TDD - write first):
- `tests/unit/translation/test_errors.py`: Error classification, retryable detection
- Test fixtures: Python exceptions → TranslationError mapping

**Success Criteria**:
- All models validate with Pydantic
- Error classification handles all exception types
- Retryable errors correctly identified
- TextAsset extends AssetIdentifiers properly

### Phase 2: Text Processing Utilities

**Objective**: Implement deterministic text preprocessing, normalization, and postprocessing.

**Deliverables**:
1. `preprocessing.py`: SpeakerLabelDetector with regex pattern matching
2. `normalization.py`: TranslationNormalizer with policy-driven rules
3. `postprocessing.py`: TTSCleanup for pronounceable text

**Files to Create**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/preprocessing.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/normalization.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/postprocessing.py`

**Tests** (TDD - write first):
- `tests/unit/translation/test_speaker_detection.py`:
  - Pattern matching accuracy ("Alice: text" → ("Alice", "text"))
  - False positive avoidance ("Time: 1:54" should not match)
  - Empty string handling
  - Multiple pattern support (">> Bob: text")
- `tests/unit/translation/test_normalization.py`:
  - Time phrase normalization ("1:54 REMAINING" → "1:54 remaining")
  - Hyphen handling ("TEN-YARD" → "TEN YARD", preserve "15-12")
  - Abbreviation expansion ("NFL" → "N F L")
  - Symbol normalization ("&" → "and", "%" → "percent")
  - Determinism: same input → same output (run 100 times)
  - Policy disable (enabled=False should skip all rules)
- `tests/unit/translation/test_postprocessing.py`:
  - Smart punctuation normalization (""" → "\"", "—" → "-")
  - Score rewriting ("15-12" → "15 to 12")
  - Whitespace normalization (multiple spaces → single space)

**Success Criteria**:
- All rules produce deterministic output
- No false positives in speaker detection
- Normalization reduces translation variance (verify with fixture comparisons)
- TTS cleanup produces pronounceable text (manual inspection)

### Phase 3: Mock Implementations

**Objective**: Implement deterministic mock translation components for testing.

**Deliverables**:
1. `mock.py`: MockIdentityTranslation, MockDictionaryTranslation
2. Integration with preprocessing/normalization utilities

**Files to Create**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/mock.py`

**Files to Modify**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/interface.py` (add `_apply_normalization` helper to BaseTranslationComponent)

**Tests** (TDD - write first):
- `tests/unit/translation/test_translation_component.py`:
  - MockIdentityTranslation: normalized input = output
  - MockDictionaryTranslation: phrase mapping determinism
  - Component protocol compliance (component_name, component_instance, is_ready)
  - Asset lineage tracking (parent_asset_ids propagation)
  - Error handling (empty input, unsupported language pair)
  - Speaker policy integration (detect and remove)
  - Normalization policy integration (apply rules)

**Success Criteria**:
- Both mocks implement TranslationComponent protocol
- Identical inputs produce identical outputs (determinism)
- Asset IDs are unique, parent_asset_ids correctly reference inputs
- Errors include proper retryable flags

### Phase 3.5: DeepL Provider Implementation

**Objective**: Implement production-ready DeepL API translation provider.

**Deliverables**:
1. `deepl_provider.py`: DeepLTranslationComponent with DeepL API integration
2. Environment variable configuration (DEEPL_AUTH_KEY, etc.)
3. DeepL-specific error handling (AuthorizationException, QuotaExceededException, etc.)
4. `.env.example` file for documentation

**Files to Create**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/deepl_provider.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/.env.example`

**Files to Modify**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/errors.py` (add DeepL exception handling)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/factory.py` (add DeepL provider support)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/requirements.txt` (add deepl>=1.0.0)

**Tests** (TDD - write first):
- `tests/unit/translation/test_deepl_provider.py`:
  - DeepL client initialization with auth key (from env or parameter)
  - Environment variable configuration (DEEPL_AUTH_KEY)
  - Translation success with proper language codes
  - DeepL-specific error handling:
    - AuthorizationException → PROVIDER_ERROR (non-retryable)
    - QuotaExceededException → PROVIDER_ERROR (non-retryable)
    - TooManyRequestsException → TIMEOUT (retryable)
    - ConnectionException → PROVIDER_ERROR (retryable)
  - Model type selection (quality_optimized, latency_optimized)
  - Formality parameter handling
  - Mock DeepL API responses for deterministic testing
- `tests/unit/translation/test_errors.py` (update):
  - DeepL exception classification
  - Retryable detection for DeepL errors

**Environment Variables** (.env.example):
```bash
# DeepL API Configuration (REQUIRED for production)
DEEPL_AUTH_KEY=your-deepl-api-key-here

# Translation Provider Selection (optional, defaults to deepl)
TRANSLATION_PROVIDER=deepl

# Default Language Configuration (optional)
STS_SOURCE_LANGUAGE=EN
STS_TARGET_LANGUAGE=ES

# DeepL-Specific Options (optional)
DEEPL_FORMALITY=less
DEEPL_MODEL_TYPE=quality_optimized
```

**Success Criteria**:
- DeepLTranslationComponent implements TranslationComponent protocol
- API key loaded from environment or parameter
- All DeepL exceptions properly classified
- Tests run without real API credentials (use mocks)
- is_ready() checks API connectivity
- Formality and model_type parameters work correctly

### Phase 4: Factory and Integration Adapter

**Objective**: Component factory and adapter for TranscriptAsset → translate() integration.

**Deliverables**:
1. `factory.py`: create_translation_component with mock support
2. Integration adapter pattern (documented in quickstart.md)
3. `quickstart.md`: Developer guide with examples

**Files to Create**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/factory.py`
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/quickstart.md`

**Files to Modify**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/__init__.py` (export factory, models, interface)

**Tests** (TDD - write first):
- `tests/integration/test_asr_translation.py`:
  - ASR → Translation pipeline (MockASRComponent → MockIdentityTranslation)
  - Asset lineage (TextAsset.parent_asset_ids contains TranscriptAsset.asset_id)
  - Language metadata propagation (source_language from TranscriptAsset.language)
  - Speaker detection with ASR output ("Alice: text" from transcript)
  - Error propagation (ASR failure → Translation failure)

**Integration Adapter Pattern** (to address clarify gap):
```python
# Adapter: TranscriptAsset → translate()
def translate_transcript(
    component: TranslationComponent,
    transcript: TranscriptAsset,
    target_language: str,
    speaker_policy: SpeakerPolicy | None = None,
    normalization_policy: NormalizationPolicy | None = None,
) -> TextAsset:
    """Translate a TranscriptAsset to target language.

    Extracts source text from transcript.total_text and calls translate().
    """
    return component.translate(
        source_text=transcript.total_text,
        stream_id=transcript.stream_id,
        sequence_number=transcript.sequence_number,
        source_language=transcript.language,
        target_language=target_language,
        parent_asset_ids=[transcript.asset_id],
        speaker_policy=speaker_policy,
        normalization_policy=normalization_policy,
    )
```

**Success Criteria**:
- Factory creates correct mock types (identity, dictionary)
- Adapter correctly extracts fields from TranscriptAsset
- Language metadata flows correctly (TranscriptAsset.language → TextAsset.source_language)
- Parent asset IDs properly linked
- quickstart.md runnable examples work

### Phase 5: Configuration and Validation

**Objective**: Add TranslationConfig model and language pair validation (addresses clarify gaps).

**Deliverables**:
1. `TranslationConfig` model in models.py
2. Language pair validation logic
3. Asset construction pattern documentation

**Files to Modify**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/models.py` (add TranslationConfig)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/apps/sts-service/src/sts_service/translation/factory.py` (accept TranslationConfig)
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/data-model.md` (document TranslationConfig)

**TranslationConfig Model**:
```python
class TranslationConfig(BaseModel):
    """Configuration for Translation component."""

    # Supported language pairs (empty = all pairs allowed)
    supported_language_pairs: list[tuple[str, str]] = []

    # Default policies
    default_speaker_policy: SpeakerPolicy = Field(default_factory=SpeakerPolicy)
    default_normalization_policy: NormalizationPolicy = Field(default_factory=NormalizationPolicy)

    # Fallback behavior
    fallback_to_source_on_error: bool = False

    # Timeout
    timeout_ms: int = Field(default=5000, ge=1000)
```

**Language Pair Validation**:
```python
def validate_language_pair(
    source: str,
    target: str,
    supported_pairs: list[tuple[str, str]]
) -> bool:
    """Validate if language pair is supported.

    Returns True if supported_pairs is empty (all pairs allowed).
    """
    if not supported_pairs:
        return True
    return (source, target) in supported_pairs
```

**Tests**:
- Language pair validation (supported, unsupported, empty list = all allowed)
- Config validation (Pydantic constraints)
- Factory with config parameter

**Success Criteria**:
- Config validates with Pydantic
- Language pair validation correct
- Factory accepts config parameter
- Unsupported language pair returns FAILED status with retryable=False

### Phase 6: Documentation and Directory Structure

**Objective**: Complete documentation artifacts and contracts.

**Deliverables**:
1. `contracts/directory-structure.json`: Module structure
2. Update data-model.md with all models
3. Update quickstart.md with configuration examples

**Files to Create**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/worktree/tts-translation/specs/006-translation-component/contracts/directory-structure.json`

**Directory Structure Contract**:
```json
{
  "module": "apps/sts-service/src/sts_service/translation/",
  "structure": {
    "interface.py": "Protocol + BaseClass",
    "models.py": "Pydantic models (TextAsset, policies, errors, config)",
    "errors.py": "Error classification and handling",
    "factory.py": "Component factory",
    "mock.py": "Mock implementations (identity, dictionary)",
    "preprocessing.py": "Speaker label detection",
    "normalization.py": "Translation-oriented normalization",
    "postprocessing.py": "TTS-oriented cleanup"
  },
  "tests": {
    "unit": "apps/sts-service/tests/unit/translation/",
    "integration": "apps/sts-service/tests/integration/test_asr_translation.py"
  }
}
```

**Success Criteria**:
- All contracts match implementation
- Documentation complete and accurate
- Quickstart examples runnable

## Integration Points

### Input: ASR Module

**Source**: `apps/sts-service/src/sts_service/asr/models.py`
**Contract**: `TranscriptAsset` with segments, language, total_text
**Usage**: Extract `total_text` property for translation input
**Lineage**: `TranscriptAsset.asset_id` → `TextAsset.parent_asset_ids`

### Output: STS Pipeline

**Consumer**: TTS component (future)
**Contract**: `TextAsset` with translated_text, speaker_id, timing metadata
**Usage**: TTS reads `translated_text` for speech synthesis
**Lineage**: `TextAsset.asset_id` → downstream asset parent_asset_ids

### Configuration: Factory Pattern

**Source**: STS service configuration
**Contract**: `TranslationConfig` with policies and language pairs
**Usage**: `create_translation_component(config=config, mock=True/False)`

## Risk Analysis

### Technical Risks

1. **Normalization variance**: Rules may not reduce translation variance
   - Mitigation: Test with representative fixtures, measure variance
   - Contingency: Make normalization opt-in with policy flags

2. **Speaker detection false positives**: Pattern matching may match non-speaker text
   - Mitigation: Strict regex patterns, extensive test cases
   - Contingency: Make speaker detection opt-in with policy flag

3. **Performance overhead**: Text processing adds latency
   - Mitigation: Benchmark all processing steps, target <50ms
   - Contingency: Disable expensive rules via policy

### Integration Risks

1. **Asset lineage tracking**: Parent IDs may be incorrectly propagated
   - Mitigation: Integration tests verify lineage at each step
   - Contingency: Add validation in TranslationComponent protocol

2. **ASR output format changes**: TranscriptAsset structure may change
   - Mitigation: Use adapter pattern to isolate changes
   - Contingency: Version TranscriptAsset schema

## Dependencies

**Required Before Implementation**:
- ASR module complete (DONE - apps/sts-service/src/sts_service/asr/)
- AssetIdentifiers base class (DONE - apps/sts-service/src/sts_service/asr/models.py)
- Python 3.10 environment (DONE - monorepo setup)

**Blocked By**: None

**Blocks**:
- TTS component implementation (needs TextAsset input)
- Full STS pipeline assembly (needs translation component)

## Success Metrics

1. **Determinism**: 100% identical outputs for identical inputs (100 runs)
2. **Coverage**: 80% minimum (95% for processing logic)
3. **Performance**: <50ms normalization latency (95th percentile)
4. **Integration**: ASR → Translation pipeline works end-to-end
5. **Error handling**: All error types classified with correct retryable flags
6. **Lineage**: All assets track parent_asset_ids correctly

## Open Questions

None - all gaps from clarify agent addressed:
- [x] Integration adapter layer documented (Phase 4)
- [x] TranslationConfig model defined (Phase 5)
- [x] _apply_normalization() location clarified (BaseTranslationComponent helper)
- [x] Language pair validation added (Phase 5)
- [x] Asset construction patterns documented (Phase 4, quickstart.md)

## Complexity Tracking

No constitution violations - implementation follows all principles.
