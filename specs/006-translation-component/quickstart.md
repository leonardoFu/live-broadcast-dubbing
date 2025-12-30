# Translation Component Quick Start Guide

**Feature**: 006-translation-component
**Last Updated**: 2025-12-30

## Overview

This guide shows you how to use the Translation component in the STS pipeline. It covers basic usage, configuration, and common patterns.

## Installation

No external dependencies required - uses mock implementations only.

```bash
# From repository root
cd apps/sts-service
pip install -e .
```

## Basic Usage

### 1. Create a Translation Component

```python
from sts_service.translation import create_translation_component

# Create mock identity translation (returns normalized input)
component = create_translation_component(mock=True, mock_type="identity")

# Create mock dictionary translation
dictionary = {
    "Hello": "Hola",
    "Goodbye": "Adiós",
    "Thank you": "Gracias",
}
component = create_translation_component(
    mock=True,
    mock_type="dictionary",
    mock_dictionary=dictionary,
)
```

### 2. Translate Text Directly

```python
from sts_service.translation import (
    create_translation_component,
    NormalizationPolicy,
)

component = create_translation_component(mock=True)

result = component.translate(
    source_text="1:54 REMAINING IN THE FOURTH QUARTER",
    stream_id="stream-123",
    sequence_number=42,
    source_language="en",
    target_language="es",
    parent_asset_ids=["audio-fragment-uuid"],
    normalization_policy=NormalizationPolicy(
        normalize_time_phrases=True,
        expand_abbreviations=True,
    ),
)

print(result.translated_text)  # "1:54 remaining in the fourth quarter"
print(result.status)  # TranslationStatus.SUCCESS
print(result.asset_id)  # "unique-uuid-here"
```

### 3. Integrate with ASR Output

```python
from sts_service.asr import create_asr_component, MockASRConfig
from sts_service.translation import create_translation_component

# Generate mock transcript
asr = create_asr_component(mock=True)
transcript = asr.transcribe(
    audio_data=b"\x00" * 32000,  # 1 second of silence
    stream_id="stream-123",
    sequence_number=42,
    start_time_ms=84000,
    end_time_ms=86000,
)

# Translate transcript
translation = create_translation_component(mock=True)
text_asset = translation.translate(
    source_text=transcript.total_text,
    stream_id=transcript.stream_id,
    sequence_number=transcript.sequence_number,
    source_language=transcript.language,
    target_language="es",
    parent_asset_ids=[transcript.asset_id],
)

print(text_asset.parent_asset_ids)  # [transcript.asset_id]
print(text_asset.source_language)  # "en"
print(text_asset.target_language)  # "es"
```

## Configuration

### Translation Config

```python
from sts_service.translation import (
    TranslationConfig,
    SpeakerPolicy,
    NormalizationPolicy,
    create_translation_component,
)

config = TranslationConfig(
    # Whitelist supported language pairs (empty = all allowed)
    supported_language_pairs=[("en", "es"), ("en", "fr"), ("es", "en")],

    # Default policies
    default_speaker_policy=SpeakerPolicy(
        detect_and_remove=True,
        allowed_patterns=["^[A-Z][a-z]+: ", "^>> [A-Z][a-z]+: "],
    ),
    default_normalization_policy=NormalizationPolicy(
        enabled=True,
        normalize_time_phrases=True,
        expand_abbreviations=True,
        normalize_hyphens=True,
        normalize_symbols=True,
    ),

    # Fallback behavior
    fallback_to_source_on_error=True,

    # Timeout
    timeout_ms=3000,
)

component = create_translation_component(config=config, mock=True)
```

### Speaker Detection

```python
from sts_service.translation import SpeakerPolicy

policy = SpeakerPolicy(
    detect_and_remove=True,
    allowed_patterns=["^[A-Z][a-z]+: "],  # Match "Alice: text"
)

result = component.translate(
    source_text="Alice: How are you today?",
    stream_id="stream-123",
    sequence_number=0,
    source_language="en",
    target_language="es",
    parent_asset_ids=[],
    speaker_policy=policy,
)

print(result.speaker_id)  # "Alice"
print(result.translated_text)  # "How are you today?" (speaker label removed)
```

### Normalization Policies

```python
from sts_service.translation import NormalizationPolicy

# Enable all normalization rules
policy = NormalizationPolicy(
    enabled=True,
    normalize_time_phrases=True,
    expand_abbreviations=True,
    normalize_hyphens=True,
    normalize_symbols=True,
    tts_cleanup=False,  # Post-translation TTS cleanup
)

result = component.translate(
    source_text="1:54 REMAINING IN THE NFL GAME & CHIEFS VS BILLS",
    stream_id="stream-123",
    sequence_number=0,
    source_language="en",
    target_language="es",
    parent_asset_ids=[],
    normalization_policy=policy,
)

print(result.normalized_source_text)
# "1:54 remaining IN THE N F L GAME and CHIEFS versus BILLS"
```

## Common Patterns

### Pattern 1: ASR → Translation Integration

```python
def translate_transcript(
    component: TranslationComponent,
    transcript: TranscriptAsset,
    target_language: str,
    speaker_policy: SpeakerPolicy | None = None,
    normalization_policy: NormalizationPolicy | None = None,
) -> TextAsset:
    """Adapter: Translate a TranscriptAsset to target language."""
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

### Pattern 2: Error Handling

```python
from sts_service.translation import TranslationStatus

result = component.translate(...)

if result.status == TranslationStatus.SUCCESS:
    print(f"Translation: {result.translated_text}")
elif result.status == TranslationStatus.FAILED:
    if result.is_retryable:
        # Retry logic
        print(f"Retryable error: {result.errors[0].message}")
    else:
        # Permanent failure
        print(f"Permanent error: {result.errors[0].message}")
```

### Pattern 3: Asset Lineage Tracking

```python
# Track full pipeline lineage
audio_fragment_id = "audio-uuid-123"

# ASR
transcript = asr.transcribe(..., parent_asset_ids=[audio_fragment_id])
# transcript.asset_id = "asr-uuid-456"

# Translation
text = translation.translate(..., parent_asset_ids=[transcript.asset_id])
# text.asset_id = "translate-uuid-789"
# text.parent_asset_ids = ["asr-uuid-456"]

# TTS (future)
audio = tts.synthesize(..., parent_asset_ids=[text.asset_id])
# audio.asset_id = "tts-uuid-abc"
# audio.parent_asset_ids = ["translate-uuid-789"]
```

### Pattern 4: Deterministic Testing

```python
import pytest
from sts_service.translation import create_translation_component

def test_normalization_determinism():
    """Verify identical inputs produce identical outputs."""
    component = create_translation_component(mock=True)

    results = []
    for _ in range(100):
        result = component.translate(
            source_text="1:54 REMAINING IN THE NFL GAME",
            stream_id="stream-123",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
        )
        results.append(result.translated_text)

    # All results should be identical
    assert len(set(results)) == 1
```

### Pattern 5: Batch Processing

```python
from sts_service.translation import create_translation_component

def translate_batch(
    transcripts: list[TranscriptAsset],
    target_language: str,
) -> list[TextAsset]:
    """Translate a batch of transcripts."""
    component = create_translation_component(mock=True)

    results = []
    for transcript in transcripts:
        text_asset = component.translate(
            source_text=transcript.total_text,
            stream_id=transcript.stream_id,
            sequence_number=transcript.sequence_number,
            source_language=transcript.language,
            target_language=target_language,
            parent_asset_ids=[transcript.asset_id],
        )
        results.append(text_asset)

    return results
```

## Testing

### Unit Test Example

```python
import pytest
from sts_service.translation import (
    create_translation_component,
    TranslationStatus,
)

def test_identity_translation_happy_path():
    """Test MockIdentityTranslation returns normalized input."""
    component = create_translation_component(mock=True, mock_type="identity")

    result = component.translate(
        source_text="1:54 REMAINING",
        stream_id="stream-123",
        sequence_number=0,
        source_language="en",
        target_language="es",
        parent_asset_ids=["parent-uuid"],
    )

    assert result.status == TranslationStatus.SUCCESS
    assert result.translated_text == "1:54 remaining"
    assert result.source_language == "en"
    assert result.target_language == "es"
    assert result.parent_asset_ids == ["parent-uuid"]
```

### Integration Test Example

```python
import pytest
from sts_service.asr import create_asr_component, MockASRConfig
from sts_service.translation import create_translation_component

def test_asr_translation_integration():
    """Test ASR → Translation pipeline."""
    # Setup
    asr = create_asr_component(mock=True)
    translation = create_translation_component(mock=True)

    # ASR
    transcript = asr.transcribe(
        audio_data=b"\x00" * 32000,
        stream_id="stream-123",
        sequence_number=42,
        start_time_ms=0,
        end_time_ms=2000,
    )

    # Translation
    text_asset = translation.translate(
        source_text=transcript.total_text,
        stream_id=transcript.stream_id,
        sequence_number=transcript.sequence_number,
        source_language=transcript.language,
        target_language="es",
        parent_asset_ids=[transcript.asset_id],
    )

    # Verify lineage
    assert text_asset.parent_asset_ids == [transcript.asset_id]
    assert text_asset.stream_id == transcript.stream_id
    assert text_asset.sequence_number == transcript.sequence_number
```

## Performance Tuning

### Disable Expensive Rules

```python
from sts_service.translation import NormalizationPolicy

# Minimal normalization for low-latency scenarios
policy = NormalizationPolicy(
    enabled=True,
    normalize_time_phrases=True,
    expand_abbreviations=False,  # Disable expensive rule
    normalize_hyphens=True,
    normalize_symbols=True,
)
```

### Benchmark Normalization

```python
import time
from sts_service.translation import create_translation_component

component = create_translation_component(mock=True)

text = "1:54 REMAINING IN THE NFL GAME & CHIEFS VS BILLS"

start = time.perf_counter()
for _ in range(1000):
    result = component.translate(
        source_text=text,
        stream_id="stream-123",
        sequence_number=0,
        source_language="en",
        target_language="es",
        parent_asset_ids=[],
    )
elapsed_ms = (time.perf_counter() - start) * 1000

print(f"Average latency: {elapsed_ms / 1000:.2f}ms")
```

## Troubleshooting

### Issue: Normalization not applied

**Symptom**: Output text identical to input (no normalization)

**Solution**: Ensure `normalization_policy.enabled=True`

```python
policy = NormalizationPolicy(enabled=True)
result = component.translate(..., normalization_policy=policy)
```

### Issue: Speaker label not detected

**Symptom**: Speaker label remains in translated text

**Solution**: Ensure pattern matches your text format

```python
# For "Alice: text"
policy = SpeakerPolicy(
    detect_and_remove=True,
    allowed_patterns=["^[A-Z][a-z]+: "],
)

# For ">> Alice: text"
policy = SpeakerPolicy(
    detect_and_remove=True,
    allowed_patterns=["^>> [A-Z][a-z]+: "],
)
```

### Issue: Asset lineage broken

**Symptom**: `parent_asset_ids` empty or incorrect

**Solution**: Always pass `parent_asset_ids` from upstream asset

```python
# Correct
text_asset = translation.translate(
    ...,
    parent_asset_ids=[transcript.asset_id],  # Link to parent
)

# Incorrect
text_asset = translation.translate(
    ...,
    parent_asset_ids=[],  # Missing lineage!
)
```

## Next Steps

- **Add real translation provider**: Implement `BaseTranslationComponent` with actual MT model
- **Integrate with TTS**: Pass `TextAsset.translated_text` to TTS component
- **Tune normalization rules**: Add domain-specific rules for your use case
- **Monitor performance**: Track `processing_time_ms` in production

## References

- Spec: [spec.md](spec.md)
- Data Model: [data-model.md](data-model.md)
- Interface Contract: [contracts/TranslationComponent.md](contracts/TranslationComponent.md)
- ASR Module: `apps/sts-service/src/sts_service/asr/`
