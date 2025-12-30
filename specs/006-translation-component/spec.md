# Translation Component Specification

## Overview

This specification defines the Translation component for the STS (Speech-to-Speech) service, conforming to the pipeline design in `specs/004-sts-pipeline-design.md` Section 6.3. The component translates per-fragment transcript text from source language to target language with deterministic text preprocessing for improved translation quality and real-time stability.

**Feature ID**: 006-translation-component
**Status**: Implementation Ready
**Component Location**: `apps/sts-service/src/sts_service/translation/`
**Dependencies**:
- ASR module (`apps/sts-service/src/sts_service/asr/`)
- STS Pipeline Design (`specs/004-sts-pipeline-design.md`)
- DeepL Python SDK (`deepl>=1.0.0`)

## Goals

1. Provide a Translation component that integrates seamlessly with the ASR module output
2. Implement lightweight, deterministic text normalization to reduce translation variance
3. Support real-time fragment processing with proper asset lineage tracking
4. Follow the established ASR module patterns (Protocol + BaseClass, factory, errors)
5. Enable easy testing with deterministic stub implementations
6. Use DeepL API as the primary translation provider for production workloads

## Non-Goals

- Defining streaming ingest/egress pipelines
- Performing heavy NLP post-editing (summarization, semantic rewriting)
- Named entity disambiguation or context-aware semantic rewriting
- Supporting multiple translation providers simultaneously (single provider per deployment)

## Integration Points

### Input: TranscriptAsset from ASR

The Translation component receives `TranscriptAsset` objects from the ASR module with:

```python
# From apps/sts-service/src/sts_service/asr/models.py
class TranscriptAsset(AssetIdentifiers):
    component: str = "asr"
    component_instance: str  # e.g., "faster-whisper-base"

    # Key fields for translation
    language: str  # Source language (e.g., "en")
    segments: list[TranscriptSegment]

    # Convenience property
    @property
    def total_text(self) -> str:
        return " ".join(seg.text for seg in self.segments)

    # Asset lineage (inherited from AssetIdentifiers)
    stream_id: str
    sequence_number: int
    asset_id: str
    parent_asset_ids: list[str]
    created_at: datetime
```

### Output: TextAsset per STS Pipeline

The Translation component produces `TextAsset` objects conforming to `specs/004-sts-pipeline-design.md` Section 6.3:

```python
# New model in apps/sts-service/src/sts_service/translation/models.py
class TextAsset(AssetIdentifiers):
    component: str = "translate"
    component_instance: str  # e.g., "mock-identity-v1"

    # Language metadata
    source_language: str
    target_language: str

    # Text content
    translated_text: str
    normalized_source_text: str | None  # Preprocessing applied before translation

    # Speaker handling (optional)
    speaker_id: str = "default"

    # Status and errors
    status: TranslationStatus
    errors: list[TranslationError]

    # Processing metadata
    processing_time_ms: int | None
    model_info: str | None

    # Warnings (non-fatal issues)
    warnings: list[str] = []
```

## Component Architecture

Following the ASR module pattern, the Translation component consists of:

### 1. Protocol + Base Class (`interface.py`)

```python
from typing import Protocol, runtime_checkable
from abc import ABC, abstractmethod

@runtime_checkable
class TranslationComponent(Protocol):
    """Protocol defining the Translation component contract."""

    @property
    def component_name(self) -> str:
        """Return the component name (always 'translate')."""
        ...

    @property
    def component_instance(self) -> str:
        """Return the provider identifier."""
        ...

    @property
    def is_ready(self) -> bool:
        """Check if the component is ready to process requests."""
        ...

    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        """Translate text from source to target language."""
        ...

    def shutdown(self) -> None:
        """Release resources."""
        ...


class BaseTranslationComponent(ABC):
    """Abstract base class for Translation component implementations."""

    _component_name: str = "translate"

    @property
    def component_name(self) -> str:
        return self._component_name

    @property
    @abstractmethod
    def component_instance(self) -> str:
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        pass

    def shutdown(self) -> None:
        return  # Default: no cleanup needed
```

### 2. Data Models (`models.py`)

All models extend `AssetIdentifiers` base from ASR module:

```python
from sts_service.asr.models import AssetIdentifiers
from pydantic import BaseModel, Field
from enum import Enum

class TranslationStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

class TranslationErrorType(str, Enum):
    EMPTY_INPUT = "empty_input"
    UNSUPPORTED_LANGUAGE_PAIR = "unsupported_language_pair"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    NORMALIZATION_ERROR = "normalization_error"
    UNKNOWN = "unknown"

class TranslationError(BaseModel):
    error_type: TranslationErrorType
    message: str
    retryable: bool
    details: dict[str, Any] | None = None

class SpeakerPolicy(BaseModel):
    detect_and_remove: bool = False
    allowed_patterns: list[str] = ["^[A-Z][a-z]+: ", "^>> [A-Z][a-z]+: "]

class NormalizationPolicy(BaseModel):
    enabled: bool = True
    normalize_time_phrases: bool = True
    expand_abbreviations: bool = True
    normalize_hyphens: bool = True
    normalize_symbols: bool = True
    tts_cleanup: bool = False  # Post-translation TTS-oriented cleanup

class TextAsset(AssetIdentifiers):
    component: str = Field(default="translate")
    component_instance: str

    source_language: str
    target_language: str

    translated_text: str
    normalized_source_text: str | None = None
    speaker_id: str = "default"

    status: TranslationStatus
    errors: list[TranslationError] = []
    warnings: list[str] = []

    processing_time_ms: int | None = None
    model_info: str | None = None

    @property
    def is_retryable(self) -> bool:
        return self.status == TranslationStatus.FAILED and any(
            e.retryable for e in self.errors
        )
```

### 3. Error Handling (`errors.py`)

Following ASR pattern with retryable classification, including DeepL-specific errors:

```python
from .models import TranslationError, TranslationErrorType
import deepl

_RETRYABLE_ERRORS = {
    TranslationErrorType.TIMEOUT,
    TranslationErrorType.PROVIDER_ERROR,
}

def classify_error(exception: Exception) -> TranslationErrorType:
    """Classify a Python exception to TranslationErrorType."""
    # DeepL-specific errors
    if isinstance(exception, deepl.DeepLException):
        if isinstance(exception, deepl.AuthorizationException):
            return TranslationErrorType.PROVIDER_ERROR  # Non-retryable auth issue
        elif isinstance(exception, deepl.QuotaExceededException):
            return TranslationErrorType.PROVIDER_ERROR  # Non-retryable quota issue
        elif isinstance(exception, deepl.TooManyRequestsException):
            return TranslationErrorType.TIMEOUT  # Retryable rate limit
        elif isinstance(exception, deepl.ConnectionException):
            return TranslationErrorType.PROVIDER_ERROR  # Retryable network issue
        else:
            return TranslationErrorType.PROVIDER_ERROR

    # Generic errors
    if isinstance(exception, TimeoutError):
        return TranslationErrorType.TIMEOUT
    elif isinstance(exception, ValueError):
        return TranslationErrorType.EMPTY_INPUT
    else:
        return TranslationErrorType.UNKNOWN

def is_retryable(error_type: TranslationErrorType, exception: Exception | None = None) -> bool:
    """Determine if an error type is worth retrying.

    Args:
        error_type: Classified error type
        exception: Original exception (for context-specific retry logic)

    Returns:
        True if error is transient and worth retrying
    """
    # Rate limiting and connection issues are retryable
    if exception and isinstance(exception, (
        deepl.TooManyRequestsException,
        deepl.ConnectionException,
    )):
        return True

    # Auth and quota errors are not retryable
    if exception and isinstance(exception, (
        deepl.AuthorizationException,
        deepl.QuotaExceededException,
    )):
        return False

    return error_type in _RETRYABLE_ERRORS

def create_translation_error(exception: Exception) -> TranslationError:
    """Create a TranslationError from a Python exception."""
    error_type = classify_error(exception)
    message = str(exception) if str(exception) else f"{type(exception).__name__}"

    return TranslationError(
        error_type=error_type,
        message=message,
        retryable=is_retryable(error_type, exception),
        details={"exception_type": type(exception).__name__},
    )
```

### 4. Mock Implementation (`mock.py`)

Deterministic stub implementations for testing:

```python
class MockIdentityTranslation(BaseTranslationComponent):
    """Returns input text unchanged (identity function)."""

    @property
    def component_instance(self) -> str:
        return "mock-identity-v1"

    @property
    def is_ready(self) -> bool:
        return True

    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        # Apply normalization if enabled
        normalized = self._apply_normalization(source_text, normalization_policy)

        return TextAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            parent_asset_ids=parent_asset_ids,
            component_instance=self.component_instance,
            source_language=source_language,
            target_language=target_language,
            translated_text=normalized,  # Identity: output = normalized input
            normalized_source_text=normalized,
            status=TranslationStatus.SUCCESS,
        )


class MockDictionaryTranslation(BaseTranslationComponent):
    """Uses a fixed dictionary for deterministic phrase mapping."""

    def __init__(self, dictionary: dict[str, str]):
        self.dictionary = dictionary

    @property
    def component_instance(self) -> str:
        return "mock-dictionary-v1"

    @property
    def is_ready(self) -> bool:
        return True

    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        normalized = self._apply_normalization(source_text, normalization_policy)
        translated = self.dictionary.get(normalized, normalized)

        return TextAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            parent_asset_ids=parent_asset_ids,
            component_instance=self.component_instance,
            source_language=source_language,
            target_language=target_language,
            translated_text=translated,
            normalized_source_text=normalized,
            status=TranslationStatus.SUCCESS,
        )
```

### 5. DeepL Provider Implementation (`deepl_provider.py`)

Production translation provider using DeepL API:

```python
import deepl
from .interface import BaseTranslationComponent
from .models import TextAsset, TranslationStatus, NormalizationPolicy, SpeakerPolicy
from .errors import create_translation_error, TranslationErrorType
from .preprocessing import SpeakerLabelDetector
from .normalization import TranslationNormalizer
from .postprocessing import TTSCleanup
import time
import os

class DeepLTranslationComponent(BaseTranslationComponent):
    """DeepL API-based translation component."""

    def __init__(
        self,
        auth_key: str | None = None,
        formality: str | None = None,
        model_type: str = "quality_optimized",
    ):
        """Initialize DeepL translation component.

        Args:
            auth_key: DeepL API key (defaults to DEEPL_AUTH_KEY env var)
            formality: Formality preference ("less" or "more", language-dependent)
            model_type: Model selection ("quality_optimized", "latency_optimized",
                       "prefer_quality_optimized")
        """
        self.auth_key = auth_key or os.environ.get("DEEPL_AUTH_KEY")
        if not self.auth_key:
            raise ValueError("DeepL auth key required (DEEPL_AUTH_KEY env var or auth_key param)")

        self.formality = formality
        self.model_type = model_type
        self.client = deepl.Translator(self.auth_key)

        # Text processing helpers
        self.speaker_detector = SpeakerLabelDetector()
        self.normalizer = TranslationNormalizer()
        self.tts_cleanup = TTSCleanup()

    @property
    def component_instance(self) -> str:
        return f"deepl-{self.model_type}"

    @property
    def is_ready(self) -> bool:
        try:
            # Verify API connectivity with usage check
            self.client.get_usage()
            return True
        except Exception:
            return False

    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        """Translate text using DeepL API."""
        start_time = time.perf_counter()
        warnings = []
        errors = []

        # Step 1: Speaker label detection
        speaker_id = "default"
        working_text = source_text

        if speaker_policy and speaker_policy.detect_and_remove:
            speaker_id, working_text = self.speaker_detector.detect_and_remove(source_text)
            if not working_text.strip():
                warnings.append("Empty text after speaker removal, using original")
                working_text = source_text
                speaker_id = "default"

        # Step 2: Pre-translation normalization
        normalized_text = working_text
        if normalization_policy:
            try:
                normalized_text = self.normalizer.normalize(working_text, normalization_policy)
            except Exception as e:
                warnings.append(f"Normalization failed: {str(e)}, using original text")
                normalized_text = working_text

        # Step 3: Translation via DeepL
        translated_text = normalized_text
        status = TranslationStatus.SUCCESS

        try:
            if not normalized_text.strip():
                raise ValueError("Cannot translate empty text")

            # Call DeepL API
            result = self.client.translate_text(
                normalized_text,
                source_lang=source_language.upper(),
                target_lang=target_language.upper(),
                split_sentences="nonewlines",  # Preserve fragment boundaries
                preserve_formatting=True,
                formality=self.formality,
                model_type=self.model_type,
            )
            translated_text = result.text

        except deepl.DeepLException as e:
            errors.append(create_translation_error(e))
            status = TranslationStatus.FAILED
            translated_text = normalized_text  # Fallback to source

        except Exception as e:
            errors.append(create_translation_error(e))
            status = TranslationStatus.FAILED
            translated_text = normalized_text  # Fallback to source

        # Step 4: Optional TTS cleanup
        if normalization_policy and normalization_policy.tts_cleanup:
            try:
                translated_text = self.tts_cleanup.cleanup(translated_text)
            except Exception as e:
                warnings.append(f"TTS cleanup failed: {str(e)}")

        # Calculate processing time
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        return TextAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            parent_asset_ids=parent_asset_ids,
            component_instance=self.component_instance,
            source_language=source_language,
            target_language=target_language,
            translated_text=translated_text,
            normalized_source_text=normalized_text,
            speaker_id=speaker_id,
            status=status,
            errors=errors,
            warnings=warnings,
            processing_time_ms=processing_time_ms,
            model_info=f"DeepL {self.model_type}",
        )

    def shutdown(self) -> None:
        """Release DeepL client resources."""
        # DeepL client cleanup if needed
        self.client = None
```

### 6. Factory (`factory.py`)

Following ASR pattern for component instantiation:

```python
from .interface import TranslationComponent
from .mock import MockIdentityTranslation, MockDictionaryTranslation
from .deepl_provider import DeepLTranslationComponent
import os

def create_translation_component(
    provider: str | None = None,
    mock: bool = False,
    mock_type: str = "identity",
    mock_dictionary: dict[str, str] | None = None,
    **provider_kwargs,
) -> TranslationComponent:
    """Create a Translation component instance.

    Args:
        provider: Provider name ("deepl" or None for env-based selection)
        mock: If True, return mock implementation
        mock_type: Type of mock ("identity" or "dictionary")
        mock_dictionary: Dictionary for mock_type="dictionary"
        **provider_kwargs: Provider-specific configuration

    Environment Variables:
        TRANSLATION_PROVIDER: Provider selection (defaults to "deepl")
        DEEPL_AUTH_KEY: DeepL API authentication key
        STS_SOURCE_LANGUAGE: Default source language (e.g., "EN")
        STS_TARGET_LANGUAGE: Default target language (e.g., "ES")

    Returns:
        TranslationComponent instance
    """
    if mock:
        if mock_type == "dictionary":
            if mock_dictionary is None:
                raise ValueError("mock_dictionary required for dictionary mock")
            return MockDictionaryTranslation(mock_dictionary)
        else:
            return MockIdentityTranslation()

    # Determine provider from parameter or environment
    provider = provider or os.environ.get("TRANSLATION_PROVIDER", "deepl")

    if provider == "deepl":
        return DeepLTranslationComponent(**provider_kwargs)

    raise ValueError(f"Unsupported translation provider: {provider}")
```

## Configuration

### Environment Variables

The translation component requires the following environment variables:

```bash
# Required: DeepL API authentication
DEEPL_AUTH_KEY=your-deepl-api-key-here

# Optional: Provider selection (defaults to "deepl")
TRANSLATION_PROVIDER=deepl

# Optional: Default language configuration
STS_SOURCE_LANGUAGE=EN
STS_TARGET_LANGUAGE=ES

# Optional: DeepL-specific configuration
DEEPL_FORMALITY=less|more        # Formality level (language-dependent)
DEEPL_MODEL_TYPE=quality_optimized  # quality_optimized|latency_optimized|prefer_quality_optimized
```

### Configuration Precedence

1. **Direct parameters** to `create_translation_component()` or `DeepLTranslationComponent()`
2. **Environment variables** (used if parameters not provided)
3. **Defaults** (quality_optimized model, auto-detect source language)

### Example Usage

```python
# Production usage with environment variables
component = create_translation_component()

# Development/testing with mock
component = create_translation_component(mock=True, mock_type="identity")

# Custom DeepL configuration
component = create_translation_component(
    provider="deepl",
    auth_key="explicit-key",
    formality="more",
    model_type="latency_optimized",
)
```

### Environment Configuration File

A `.env.example` file must be added to `apps/sts-service/` to document required environment variables:

```bash
# .env.example - Copy to .env and fill in actual values

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

**Security Note**: The actual `.env` file containing real API keys must be in `.gitignore` and never committed to version control.

## Text Processing Pipeline

### Speaker Label Handling (Pre-Translation)

Purpose: Prevent translation and TTS from translating/speaking a label present as plain text.

**Implementation** (`preprocessing.py`):

```python
import re

class SpeakerLabelDetector:
    """Detects and removes speaker labels from text."""

    DEFAULT_PATTERNS = [
        r"^([A-Z][a-z]+): ",       # "Name: ..."
        r"^>> ([A-Z][a-z]+): ",    # ">> Name: ..."
    ]

    def __init__(self, patterns: list[str] | None = None):
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.compiled_patterns = [re.compile(p) for p in self.patterns]

    def detect_and_remove(self, text: str) -> tuple[str, str]:
        """Detect and remove speaker label.

        Returns:
            (speaker_id, cleaned_text)
            If no label detected, returns ("default", original_text)
        """
        for pattern in self.compiled_patterns:
            match = pattern.match(text)
            if match:
                speaker_id = match.group(1)
                cleaned = pattern.sub("", text).strip()
                return (speaker_id, cleaned)

        return ("default", text)
```

### Translation-Oriented Normalization (Pre-Translation)

Purpose: Reduce translation errors and cache churn by normalizing common ASR formatting noise.

**Rules**:
1. Time/clock phrases: `"1:54 REMAINING"` → `"1:54 remaining"`
2. Hyphen handling: `"TEN-YARD"` → `"TEN YARD"`
3. Abbreviation expansion: `"NFL"` → `"N F L"`, `"vs."` → `"versus"`
4. Symbol expansion: `"&"` → `"and"`, `"%"` → `"percent"`, `"$"` → `"dollars"`
5. Preserve numerals by default (to avoid unintended rewrites)

**Implementation** (`normalization.py`):

```python
class TranslationNormalizer:
    """Applies deterministic normalization rules for translation."""

    def normalize(self, text: str, policy: NormalizationPolicy) -> str:
        if not policy.enabled:
            return text

        result = text

        if policy.normalize_time_phrases:
            result = self._normalize_time_phrases(result)

        if policy.normalize_hyphens:
            result = self._normalize_hyphens(result)

        if policy.expand_abbreviations:
            result = self._expand_abbreviations(result)

        if policy.normalize_symbols:
            result = self._normalize_symbols(result)

        return result

    def _normalize_time_phrases(self, text: str) -> str:
        # "1:54 REMAINING" → "1:54 remaining"
        pattern = r'(\d+:\d+)\s+([A-Z]+)'
        return re.sub(pattern, lambda m: f"{m.group(1)} {m.group(2).lower()}", text)

    def _normalize_hyphens(self, text: str) -> str:
        # "TEN-YARD" → "TEN YARD"
        # But preserve score patterns like "15-12"
        pattern = r'([A-Z]+)-([A-Z]+)'
        return re.sub(pattern, r'\1 \2', text)

    def _expand_abbreviations(self, text: str) -> str:
        expansions = {
            r'\bNFL\b': 'N F L',
            r'\bvs\.': 'versus',
            r'\bVS\b': 'versus',
        }
        result = text
        for pattern, replacement in expansions.items():
            result = re.sub(pattern, replacement, result)
        return result

    def _normalize_symbols(self, text: str) -> str:
        replacements = {
            '&': ' and ',
            '%': ' percent ',
            '$': ' dollars ',
            '@': ' at ',
        }
        result = text
        for symbol, replacement in replacements.items():
            result = result.replace(symbol, replacement)
        return result
```

### TTS-Oriented Cleanup (Post-Translation, Optional)

Purpose: Produce more consistently pronounceable text for speech synthesis.

**Rules**:
1. Normalize smart punctuation: `"` → `"`, `—` → `-`, `…` → `...`
2. Preserve ellipses, compress excessive punctuation
3. Rewrite score-like hyphens: `"15-12"` → `"15 to 12"`
4. Normalize whitespace

**Implementation** (`postprocessing.py`):

```python
class TTSCleanup:
    """Applies TTS-oriented cleanup to translated text."""

    def cleanup(self, text: str) -> str:
        result = self._normalize_smart_punctuation(text)
        result = self._normalize_scores(result)
        result = self._normalize_whitespace(result)
        return result

    def _normalize_smart_punctuation(self, text: str) -> str:
        replacements = {
            '"': '"', '"': '"',  # Smart quotes
            ''': "'", ''': "'",  # Smart apostrophes
            '—': '-', '–': '-',  # Em/en dashes
        }
        result = text
        for smart, simple in replacements.items():
            result = result.replace(smart, simple)
        return result

    def _normalize_scores(self, text: str) -> str:
        # "15-12" → "15 to 12"
        pattern = r'(\d+)-(\d+)'
        return re.sub(pattern, r'\1 to \2', text)

    def _normalize_whitespace(self, text: str) -> str:
        return ' '.join(text.split())
```

## Error Handling & Fallbacks

The Translation component follows the STS pipeline error contract (`specs/004-sts-pipeline-design.md` Section 7.2):

1. **Empty input after speaker removal**: Return warning, fall back to unstripped text
2. **Translation provider failure**: Return FAILED status with retryable flag
3. **Normalization errors**: Return warning, fall back to original text
4. **Unsupported language pair**: Return FAILED status with retryable=False

**Fallback policies** (configured at pipeline level):
- If translation fails and fallback enabled, pass through source text as "translated" text
- Record errors and warnings in TextAsset for observability

## Testing Strategy

### Unit Tests

**Normalization rules** (`tests/unit/test_normalization.py`):
- Time phrase normalization
- Hyphen-to-space conversion
- Abbreviation expansion
- Symbol normalization
- Determinism: same input → same output

**Speaker label detection** (`tests/unit/test_speaker_detection.py`):
- Pattern matching accuracy
- False positive avoidance
- Empty string handling

**TTS cleanup** (`tests/unit/test_postprocessing.py`):
- Smart punctuation normalization
- Score rewriting
- Whitespace normalization

### Functional Tests

**Component contract** (`tests/unit/test_translation_component.py`):
- Mock identity translation
- Mock dictionary translation
- Error handling (retryable vs non-retryable)
- Asset lineage tracking (parent_asset_ids)

**DeepL provider tests** (`tests/unit/test_deepl_provider.py`):
- DeepL API client initialization with auth key
- Environment variable configuration (DEEPL_AUTH_KEY)
- Translation success with proper language codes
- Error handling for DeepL-specific exceptions:
  - `AuthorizationException` (non-retryable)
  - `QuotaExceededException` (non-retryable)
  - `TooManyRequestsException` (retryable)
  - `ConnectionException` (retryable)
- Model type selection (quality_optimized, latency_optimized)
- Formality parameter handling
- Mock DeepL API responses for deterministic testing (use `unittest.mock` or `pytest-mock`)

### Integration Tests

**ASR → Translation integration** (`tests/integration/test_asr_translation.py`):
- Use MockASRComponent to generate TranscriptAsset
- Feed to MockIdentityTranslation
- Verify TextAsset has correct parent_asset_ids referencing TranscriptAsset
- Verify language metadata flows correctly

### Test Fixtures

No audio fixtures required. Use deterministic text samples:

**Sports domain**:
```python
SPORTS_FIXTURES = [
    "1:54 REMAINING IN THE FOURTH QUARTER",
    "TOUCHDOWN CHIEFS!",
    "NFL PLAYOFFS: CHIEFS VS BILLS",
    "15-12 FINAL SCORE",
]
```

**Conversation with speaker labels**:
```python
CONVERSATION_FIXTURES = [
    "Alice: How are you today?",
    ">> Bob: I'm doing great, thanks!",
    "Charlie: That's wonderful to hear.",
]
```

**Punctuation-heavy**:
```python
PUNCTUATION_FIXTURES = [
    "Wait... what did you say?",
    "The score is 21-14—an exciting game!",
    "She said, "I'll be there soon."",
]
```

## Success Criteria

1. Translation preprocessing is deterministic for identical inputs and policies
2. For representative fixtures, normalized inputs reduce translation variance
3. Component supports per-fragment processing without violating ordering (orchestrator's responsibility)
4. All intermediate assets include proper lineage tracking (parent_asset_ids)
5. Error classification correctly identifies retryable vs non-retryable failures
6. Mock implementations enable deterministic testing without external dependencies
7. Component follows ASR module patterns for consistency
8. DeepL API integration works correctly with environment variable configuration
9. DeepL-specific errors are properly classified (auth, quota, rate limit, connection)
10. Factory pattern allows seamless switching between mock and DeepL providers
11. All tests pass without requiring real DeepL API credentials (use mocks)
12. `.env.example` file documents all required and optional environment variables

## File Structure

```
apps/sts-service/src/sts_service/translation/
├── __init__.py
├── interface.py          # Protocol + BaseClass
├── models.py             # Pydantic models (TextAsset, policies, errors)
├── errors.py             # Error classification and handling (DeepL-aware)
├── factory.py            # Component factory (DeepL + mock selection)
├── mock.py               # Mock implementations (identity, dictionary)
├── deepl_provider.py     # DeepL API implementation
├── preprocessing.py      # Speaker detection
├── normalization.py      # Translation-oriented normalization
└── postprocessing.py     # TTS-oriented cleanup

apps/sts-service/tests/unit/translation/
├── __init__.py
├── test_speaker_detection.py
├── test_normalization.py
├── test_postprocessing.py
├── test_translation_component.py
├── test_deepl_provider.py    # DeepL-specific tests
└── test_errors.py

apps/sts-service/tests/integration/
├── __init__.py
└── test_asr_translation.py
```

## References

- ASR Module: `apps/sts-service/src/sts_service/asr/`
- STS Pipeline Design: `specs/004-sts-pipeline-design.md`
- Original Translation Spec: `specs/006-translation-component.md`
- ASR Module Spec: `specs/005-audio-transcription-module/`
- DeepL Python SDK: https://github.com/DeepLcom/deepl-python
- DeepL API Documentation: https://developers.deepl.com/docs

## Dependencies

Add the following to `apps/sts-service/requirements.txt`:

```txt
deepl>=1.0.0
```

Language code compatibility:
- DeepL uses uppercase ISO 639-1 codes: `EN`, `ES`, `FR`, `DE`, etc.
- Source language can be omitted for auto-detection
- Target language is always required
