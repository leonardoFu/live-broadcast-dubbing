# TranslationComponent Interface Contract

**Feature**: 006-translation-component
**Last Updated**: 2025-12-30

## Overview

This document defines the `TranslationComponent` protocol contract that all Translation implementations must satisfy. It follows the ASR module pattern of Protocol + BaseClass for interface enforcement.

## Protocol Definition

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TranslationComponent(Protocol):
    """Protocol defining the Translation component contract.

    All Translation implementations (real and mock) must implement this interface.
    This follows the component contract from specs/004-sts-pipeline-design.md Section 6.3.
    """

    @property
    def component_name(self) -> str:
        """Return the component name (always 'translate')."""
        ...

    @property
    def component_instance(self) -> str:
        """Return the provider identifier (e.g., 'mock-identity-v1')."""
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
        """Translate text from source to target language.

        Args:
            source_text: Text to translate
            stream_id: Logical stream/session identifier
            sequence_number: Fragment index within stream
            source_language: ISO 639-1 source language code (e.g., "en")
            target_language: ISO 639-1 target language code (e.g., "es")
            parent_asset_ids: References to upstream assets (TranscriptAsset)
            speaker_policy: Speaker detection configuration (optional)
            normalization_policy: Text normalization configuration (optional)

        Returns:
            TextAsset with translation result

        The component MUST:
        - Return SUCCESS status with translated_text for successful translation
        - Return FAILED status with retryable=True for transient errors
        - Return FAILED status with retryable=False for permanent errors
        - Apply speaker detection if speaker_policy.detect_and_remove=True
        - Apply normalization if normalization_policy.enabled=True
        - Track parent_asset_ids for lineage
        - Generate unique asset_id for each call
        """
        ...

    def shutdown(self) -> None:
        """Release resources (model cache, network connections, etc.)."""
        ...
```

## Base Class Definition

```python
from abc import ABC, abstractmethod

class BaseTranslationComponent(ABC):
    """Abstract base class for Translation component implementations.

    Provides common functionality and enforces the Translation contract.
    """

    _component_name: str = "translate"

    @property
    def component_name(self) -> str:
        """Return the component name (always 'translate')."""
        return self._component_name

    @property
    @abstractmethod
    def component_instance(self) -> str:
        """Subclasses must provide their instance identifier."""
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Subclasses must indicate readiness."""
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
        """Subclasses must implement translation logic."""
        pass

    def shutdown(self) -> None:
        """Default implementation does nothing. Override if cleanup needed."""
        return  # noqa: B027 - intentionally empty default implementation

    # Helper methods for preprocessing
    def _apply_normalization(
        self,
        text: str,
        policy: NormalizationPolicy | None,
    ) -> str:
        """Apply normalization rules to text.

        Uses TranslationNormalizer internally.
        """
        if policy is None:
            policy = NormalizationPolicy()

        from .normalization import TranslationNormalizer
        normalizer = TranslationNormalizer()
        return normalizer.normalize(text, policy)

    def _detect_speaker(
        self,
        text: str,
        policy: SpeakerPolicy | None,
    ) -> tuple[str, str]:
        """Detect and remove speaker label from text.

        Returns:
            (speaker_id, cleaned_text)
        """
        if policy is None or not policy.detect_and_remove:
            return ("default", text)

        from .preprocessing import SpeakerLabelDetector
        detector = SpeakerLabelDetector(patterns=policy.allowed_patterns)
        return detector.detect_and_remove(text)
```

## Method Contracts

### translate()

**Preconditions**:
- Component is ready (`is_ready == True`)
- `source_text` is valid UTF-8 string (may be empty)
- `stream_id` is non-empty
- `sequence_number >= 0`
- `source_language` and `target_language` are ISO 639-1 codes
- `parent_asset_ids` is non-empty list

**Postconditions**:
- Returns valid `TextAsset` instance
- `TextAsset.asset_id` is unique (UUID)
- `TextAsset.parent_asset_ids == parent_asset_ids` (input)
- `TextAsset.stream_id == stream_id` (input)
- `TextAsset.sequence_number == sequence_number` (input)
- `TextAsset.source_language == source_language` (input)
- `TextAsset.target_language == target_language` (input)
- `TextAsset.component == "translate"`
- `TextAsset.component_instance` matches implementation
- If status == SUCCESS, `translated_text` is non-empty
- If status == FAILED, `errors` list is non-empty

**Error Handling**:
- Empty input → WARNING + fallback to original text
- Unsupported language pair → FAILED (retryable=False)
- Provider timeout → FAILED (retryable=True)
- Normalization error → WARNING + fallback to original text

### shutdown()

**Preconditions**:
- Component may be in any state (ready or not ready)

**Postconditions**:
- Resources released (model cache, network connections)
- Component may transition to `is_ready == False`
- Safe to call multiple times (idempotent)

## Implementation Requirements

All implementations MUST:

1. **Asset Lineage**:
   - Generate unique `asset_id` for each translation
   - Preserve `parent_asset_ids` from input
   - Include `stream_id` and `sequence_number` from input

2. **Error Classification**:
   - Classify all exceptions to `TranslationErrorType`
   - Set `retryable` flag correctly (timeout=True, unsupported_language=False)
   - Include human-readable error messages

3. **Preprocessing Order**:
   - Speaker detection (if enabled)
   - Text normalization (if enabled)
   - Translation
   - TTS cleanup (if enabled)

4. **Determinism** (for mock implementations):
   - Identical inputs → identical outputs
   - No random behavior unless explicitly seeded

5. **Performance**:
   - Normalization: <50ms (95th percentile)
   - Total processing (mock): <100ms (95th percentile)

6. **Thread Safety**:
   - Implementations should be thread-safe for concurrent requests
   - Stateless processing preferred (no cross-fragment context)

## Mock Implementations

### MockIdentityTranslation

Returns normalized input as output (identity function).

**Contract**:
- `component_instance == "mock-identity-v1"`
- `translated_text == normalized_source_text`
- Always returns SUCCESS status
- No errors

**Use Cases**:
- Testing normalization rules
- Testing asset lineage
- Performance benchmarking

### MockDictionaryTranslation

Uses fixed dictionary for deterministic phrase mapping.

**Contract**:
- `component_instance == "mock-dictionary-v1"`
- `translated_text == dictionary.get(normalized_source_text, normalized_source_text)`
- Always returns SUCCESS status
- No errors

**Use Cases**:
- Deterministic integration testing
- Fixture-based validation
- Pipeline testing without real translation

## Integration Adapter

For integrating with ASR module output:

```python
def translate_transcript(
    component: TranslationComponent,
    transcript: TranscriptAsset,
    target_language: str,
    speaker_policy: SpeakerPolicy | None = None,
    normalization_policy: NormalizationPolicy | None = None,
) -> TextAsset:
    """Translate a TranscriptAsset to target language.

    Extracts source text from transcript.total_text and calls translate().

    Args:
        component: Translation component instance
        transcript: ASR output to translate
        target_language: Target language code
        speaker_policy: Optional speaker detection policy
        normalization_policy: Optional normalization policy

    Returns:
        TextAsset with translation result
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

## Compliance Testing

To verify protocol compliance, implementations must pass:

```python
def test_translation_component_protocol_compliance():
    """Verify implementation satisfies TranslationComponent protocol."""
    component = MockIdentityTranslation()

    # Check protocol compliance
    assert isinstance(component, TranslationComponent)

    # Check required properties
    assert component.component_name == "translate"
    assert isinstance(component.component_instance, str)
    assert isinstance(component.is_ready, bool)

    # Check translate() signature and return type
    result = component.translate(
        source_text="test",
        stream_id="stream-123",
        sequence_number=0,
        source_language="en",
        target_language="es",
        parent_asset_ids=["parent-uuid"],
    )
    assert isinstance(result, TextAsset)
    assert result.component == "translate"
    assert result.stream_id == "stream-123"
    assert result.sequence_number == 0
    assert result.parent_asset_ids == ["parent-uuid"]

    # Check shutdown() is callable
    component.shutdown()
```

## Version History

- **v1.0** (2025-12-30): Initial protocol definition
  - Protocol + BaseClass pattern
  - Mock implementations (identity, dictionary)
  - Integration adapter for TranscriptAsset
