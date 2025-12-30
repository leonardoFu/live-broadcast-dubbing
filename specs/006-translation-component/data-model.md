# Translation Component Data Model

**Feature**: 006-translation-component
**Last Updated**: 2025-12-30

## Overview

This document defines the data models for the Translation component, following the ASR module pattern of extending `AssetIdentifiers` for asset lineage tracking.

## Core Models

### TextAsset

The primary output artifact from the Translation component.

```python
class TextAsset(AssetIdentifiers):
    """Translated text asset with metadata and lineage.

    Extends AssetIdentifiers to track:
    - stream_id: Logical stream/session identifier
    - sequence_number: Fragment index within stream
    - asset_id: Globally unique identifier (UUID)
    - parent_asset_ids: References to upstream assets (TranscriptAsset)
    - created_at: Timestamp of artifact creation
    - component: Always "translate"
    - component_instance: Provider identifier (e.g., "mock-identity-v1")
    """

    # Component identification
    component: str = Field(default="translate")
    component_instance: str

    # Language metadata
    source_language: str
    target_language: str

    # Text content
    translated_text: str
    normalized_source_text: str | None = None
    speaker_id: str = "default"

    # Status and errors
    status: TranslationStatus
    errors: list[TranslationError] = []
    warnings: list[str] = []

    # Processing metadata
    processing_time_ms: int | None = None
    model_info: str | None = None

    @property
    def is_retryable(self) -> bool:
        """Whether this result should be retried."""
        return self.status == TranslationStatus.FAILED and any(
            e.retryable for e in self.errors
        )
```

**Field Descriptions**:
- `source_language`: ISO 639-1 language code (e.g., "en", "es", "fr")
- `target_language`: ISO 639-1 language code
- `translated_text`: Final translated output (after all processing)
- `normalized_source_text`: Preprocessed source text before translation (for debugging)
- `speaker_id`: Speaker identifier extracted from text (default: "default")
- `status`: Overall translation status (SUCCESS, PARTIAL, FAILED)
- `errors`: List of structured errors encountered
- `warnings`: Non-fatal issues (e.g., "empty input after speaker removal")
- `processing_time_ms`: Total processing time including pre/post-processing
- `model_info`: Provider-specific model identifier (e.g., "mock-identity-v1")

**Example**:
```json
{
  "stream_id": "stream-abc-123",
  "sequence_number": 42,
  "asset_id": "translate-asset-uuid-here",
  "parent_asset_ids": ["asr-asset-uuid-123"],
  "created_at": "2025-12-30T10:30:00Z",
  "component": "translate",
  "component_instance": "mock-identity-v1",
  "source_language": "en",
  "target_language": "es",
  "translated_text": "1:54 remaining in the fourth quarter",
  "normalized_source_text": "1:54 remaining IN THE FOURTH QUARTER",
  "speaker_id": "default",
  "status": "success",
  "errors": [],
  "warnings": [],
  "processing_time_ms": 15,
  "model_info": "mock-identity-v1"
}
```

### TranslationStatus

```python
class TranslationStatus(str, Enum):
    SUCCESS = "success"    # Translation completed successfully
    PARTIAL = "partial"    # Some processing completed, but with errors
    FAILED = "failed"      # Translation completely failed
```

### TranslationError

Structured error information with retryable classification.

```python
class TranslationError(BaseModel):
    error_type: TranslationErrorType
    message: str
    retryable: bool
    details: dict[str, Any] | None = None
```

**Example**:
```json
{
  "error_type": "timeout",
  "message": "Translation exceeded 5000ms deadline",
  "retryable": true,
  "details": {
    "elapsed_ms": 5234,
    "deadline_ms": 5000
  }
}
```

### TranslationErrorType

```python
class TranslationErrorType(str, Enum):
    EMPTY_INPUT = "empty_input"                          # Empty source text
    UNSUPPORTED_LANGUAGE_PAIR = "unsupported_language_pair"  # Language pair not supported
    PROVIDER_ERROR = "provider_error"                    # Translation provider failure
    TIMEOUT = "timeout"                                  # Processing exceeded deadline
    NORMALIZATION_ERROR = "normalization_error"          # Preprocessing failure
    UNKNOWN = "unknown"                                  # Unclassified error
```

**Retryable Classification**:
- **Retryable**: TIMEOUT, PROVIDER_ERROR (transient failures)
- **Non-retryable**: EMPTY_INPUT, UNSUPPORTED_LANGUAGE_PAIR, NORMALIZATION_ERROR, UNKNOWN (permanent failures)

## Policy Models

### SpeakerPolicy

Controls speaker label detection and removal.

```python
class SpeakerPolicy(BaseModel):
    detect_and_remove: bool = False
    allowed_patterns: list[str] = [
        "^[A-Z][a-z]+: ",        # "Alice: text"
        "^>> [A-Z][a-z]+: "      # ">> Bob: text"
    ]
```

**Behavior**:
- If `detect_and_remove=True`, scans text for speaker labels matching `allowed_patterns`
- Extracts speaker name (e.g., "Alice") → `TextAsset.speaker_id`
- Removes label from text before translation (e.g., "Alice: Hello" → "Hello")
- If no match found, `speaker_id="default"` and text unchanged

**Example**:
```python
# Input: "Alice: How are you today?"
# Output: speaker_id="Alice", text="How are you today?"

# Input: "Hello world"
# Output: speaker_id="default", text="Hello world"
```

### NormalizationPolicy

Controls translation-oriented text normalization.

```python
class NormalizationPolicy(BaseModel):
    enabled: bool = True
    normalize_time_phrases: bool = True
    expand_abbreviations: bool = True
    normalize_hyphens: bool = True
    normalize_symbols: bool = True
    tts_cleanup: bool = False  # Post-translation TTS-oriented cleanup
```

**Rules**:
1. **Time phrases**: `"1:54 REMAINING"` → `"1:54 remaining"`
2. **Hyphens**: `"TEN-YARD"` → `"TEN YARD"` (preserve score patterns like "15-12")
3. **Abbreviations**: `"NFL"` → `"N F L"`, `"vs."` → `"versus"`
4. **Symbols**: `"&"` → `"and"`, `"%"` → `"percent"`, `"$"` → `"dollars"`
5. **TTS cleanup** (if enabled):
   - Smart punctuation: `"""` → `"\""`, `"—"` → `"-"`
   - Score rewriting: `"15-12"` → `"15 to 12"`
   - Whitespace normalization

**Example**:
```python
# Input: "1:54 REMAINING IN THE NFL GAME & CHIEFS VS BILLS"
# Output: "1:54 remaining IN THE N F L GAME and CHIEFS versus BILLS"
```

## Configuration Models

### TranslationConfig

Global configuration for Translation component instances.

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

### DeepLConfig

DeepL-specific configuration model.

```python
class DeepLConfig(BaseModel):
    """Configuration for DeepL translation provider."""

    # Authentication
    auth_key: str | None = Field(
        default=None,
        description="DeepL API authentication key (or use DEEPL_AUTH_KEY env var)"
    )

    # Translation options
    formality: str | None = Field(
        default=None,
        description="Formality preference: 'less', 'more', or None (language-dependent)"
    )
    model_type: str = Field(
        default="quality_optimized",
        description="Model selection: quality_optimized, latency_optimized, prefer_quality_optimized"
    )

    # API behavior
    split_sentences: str = Field(
        default="nonewlines",
        description="Sentence splitting mode: nonewlines, 0 (off), 1 (on)"
    )
    preserve_formatting: bool = Field(
        default=True,
        description="Preserve original formatting in translation"
    )

    @property
    def effective_auth_key(self) -> str:
        """Get auth key from config or environment."""
        import os
        key = self.auth_key or os.environ.get("DEEPL_AUTH_KEY")
        if not key:
            raise ValueError("DeepL auth key required (DEEPL_AUTH_KEY env var or auth_key param)")
        return key
```

**Usage Example**:
```python
# Minimal configuration (uses environment variables)
config = DeepLConfig()

# Explicit configuration
config = DeepLConfig(
    auth_key="explicit-key-here",
    formality="more",
    model_type="latency_optimized",
)

# Environment variable precedence
# 1. auth_key parameter (if provided)
# 2. DEEPL_AUTH_KEY environment variable
# 3. ValueError if neither available
```

**Field Descriptions**:
- `supported_language_pairs`: Whitelist of allowed (source, target) pairs. Empty list = all pairs allowed.
- `default_speaker_policy`: Default speaker detection policy (can be overridden per request)
- `default_normalization_policy`: Default normalization policy (can be overridden per request)
- `fallback_to_source_on_error`: If True, return source text as translation on failure
- `timeout_ms`: Maximum processing time per fragment (includes pre/post-processing)

**Example**:
```python
config = TranslationConfig(
    supported_language_pairs=[("en", "es"), ("en", "fr"), ("es", "en")],
    default_normalization_policy=NormalizationPolicy(
        normalize_time_phrases=True,
        expand_abbreviations=True,
    ),
    fallback_to_source_on_error=True,
    timeout_ms=3000,
)
```

## Asset Lineage

All Translation assets extend `AssetIdentifiers` (from ASR module):

```python
class AssetIdentifiers(BaseModel):
    stream_id: str
    sequence_number: int
    asset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_asset_ids: list[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    component: str
    component_instance: str
```

**Lineage Flow**:
```
AudioFragment (media-service)
    ↓
TranscriptAsset (ASR) [parent_asset_ids: [audio_fragment_id]]
    ↓
TextAsset (Translation) [parent_asset_ids: [transcript_asset_id]]
    ↓
AudioAsset (TTS) [parent_asset_ids: [text_asset_id]]
```

**Example Lineage**:
```python
# TranscriptAsset from ASR
transcript = TranscriptAsset(
    stream_id="stream-123",
    sequence_number=42,
    asset_id="asr-uuid-abc",
    parent_asset_ids=["audio-uuid-xyz"],
    component="asr",
    component_instance="faster-whisper-base",
    language="en",
    segments=[...],
)

# TextAsset from Translation
text = TextAsset(
    stream_id="stream-123",
    sequence_number=42,
    asset_id="translate-uuid-def",
    parent_asset_ids=["asr-uuid-abc"],  # References TranscriptAsset
    component="translate",
    component_instance="mock-identity-v1",
    source_language="en",
    target_language="es",
    translated_text="...",
)
```

## Schema Evolution

**Versioning Strategy**:
- Models use Pydantic for validation and schema generation
- Breaking changes require new component_instance version (e.g., "v2")
- Optional fields added with defaults for backward compatibility

**Future Extensions**:
- `context_window`: Cross-fragment context for improved translation
- `glossary_id`: Reference to domain-specific terminology
- `translation_quality_score`: Confidence score from provider
- `alternative_translations`: Multiple translation candidates
