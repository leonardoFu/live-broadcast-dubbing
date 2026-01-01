# Data Model: TTS Audio Synthesis Module

**Feature**: TTS Audio Synthesis Module
**Branch**: `008-tts-module`
**Date**: 2025-12-30

This document defines the entities, relationships, and validation rules for the TTS component. The data model follows the asset-based design pattern from `specs/004-sts-pipeline-design.md` and mirrors the structure established in ASR (`specs/005-audio-transcription-module/data-model.md`) and Translation modules.

## Entity Overview

```
┌─────────────────┐
│   TextAsset     │  (Input from Translation module)
│  - text         │
│  - language     │
│  - speaker_id   │
└────────┬────────┘
         │
         │ parent_asset_ids
         ▼
┌─────────────────┐
│  AudioAsset     │  (Primary output)
│  - audio_format │
│  - sample_rate  │
│  - channels     │
│  - duration_ms  │
│  - payload_ref  │
└────────┬────────┘
         │
         │ has_metadata
         ▼
┌─────────────────┐
│  TTSMetrics     │  (Performance tracking)
│  - preprocess_  │
│    time_ms      │
│  - synthesis_   │
│    time_ms      │
│  - alignment_   │
│    time_ms      │
│  - speed_factor │
│  - clamped      │
└─────────────────┘

┌─────────────────┐
│ VoiceProfile    │  (Configuration)
│  - model_name   │
│  - fast_model   │
│  - voice_sample │
│  - speaker_name │
└─────────────────┘

┌─────────────────┐
│   TTSError      │  (Error classification)
│  - error_type   │
│  - retryable    │
│  - message      │
└─────────────────┘
```

## Core Entities

### 1. AudioAsset (Primary Output)

**Description**: Synthesized speech audio produced by the TTS component. This is the primary output that flows to the mixer/stream worker.

**Fields**:

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `asset_id` | `str (UUID)` | Yes | Valid UUID v4 | Globally unique identifier |
| `stream_id` | `str` | Yes | Non-empty | Logical stream identifier |
| `sequence_number` | `int` | Yes | >= 0 | Fragment index in stream |
| `parent_asset_ids` | `list[str]` | Yes | Non-empty | References to TextAsset(s) |
| `created_at` | `datetime` | Yes | UTC timestamp | Asset creation time |
| `component` | `str` | Yes | Literal "tts" | Always "tts" for this asset |
| `component_instance` | `str` | Yes | Non-empty | Provider ID (e.g., "coqui-xtts-v2") |
| `audio_format` | `AudioFormat` | Yes | Enum value | PCM format (PCM_F32LE, PCM_S16LE) |
| `sample_rate_hz` | `int` | Yes | [8000, 16000, 24000, 44100, 48000] | Audio sample rate |
| `channels` | `int` | Yes | [1, 2] | Number of audio channels |
| `duration_ms` | `int` | Yes | > 0 | Actual audio duration |
| `payload_ref` | `str` | Yes | Non-empty | Reference to PCM bytes (mem:// or file://) |
| `language` | `str` | Yes | ISO 639-1 code | Synthesis language (e.g., "en", "es") |
| `status` | `AudioStatus` | Yes | Enum value | SUCCESS, PARTIAL, FAILED |
| `errors` | `list[TTSError]` | No | - | Errors encountered during synthesis |
| `processing_time_ms` | `int` | No | >= 0 | Total processing time |
| `voice_cloning_used` | `bool` | No | - | Whether voice cloning was active |
| `preprocessed_text` | `str` | No | - | Actual text used for synthesis (post-preprocessing) |

**Validation Rules**:
- `parent_asset_ids` MUST contain at least one valid TextAsset UUID
- `duration_ms` MUST be within [100, 30000] (0.1s to 30s reasonable range)
- `sample_rate_hz` MUST match one of the standard rates
- `payload_ref` MUST follow format: `mem://fragments/{stream_id}/{sequence_number}` or `file:///path/to/audio.raw`
- If `status == FAILED`, `errors` list MUST NOT be empty
- If `status == SUCCESS`, `duration_ms` MUST be > 0 and `payload_ref` MUST be valid

**Relationships**:
- **Parent**: TextAsset (1:1) - Input text for synthesis
- **Children**: None (terminal asset in STS pipeline)
- **Metadata**: TTSMetrics (1:1) - Performance and quality metrics

**Computed Properties**:
- `has_errors: bool` - Returns `True` if `len(errors) > 0`
- `is_retryable: bool` - Returns `True` if status == FAILED and any error has `retryable == True`
- `average_speed_factor: float` - Returns speed factor from TTSMetrics if available

---

### 2. TextAsset (Input Dependency)

**Description**: Translated text input from the Translation module. This is an upstream dependency referenced by `parent_asset_ids` in AudioAsset.

**Fields** (subset relevant to TTS):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `asset_id` | `str (UUID)` | Yes | Globally unique identifier |
| `stream_id` | `str` | Yes | Logical stream identifier |
| `sequence_number` | `int` | Yes | Fragment index in stream |
| `text` | `str` | Yes | Translated text to synthesize |
| `language` | `str` | Yes | Target language (ISO 639-1) |
| `speaker_id` | `str` | No | Speaker identifier (for multi-speaker scenarios) |

**Validation Rules**:
- `text` MUST NOT be empty or whitespace-only
- `language` MUST be a valid ISO 639-1 language code
- `text` length SHOULD be within [1, 500] characters (typical fragment size)

**TTS-Specific Usage**:
- TTS component reads `text` field for synthesis input
- TTS component uses `language` to select appropriate voice model
- TTS component uses `speaker_id` for multi-speaker voice selection (if applicable)
- TTS component records TextAsset.asset_id in AudioAsset.parent_asset_ids

---

### 3. VoiceProfile (Configuration Entity)

**Description**: Configuration for voice selection, model choice, and synthesis parameters. This entity is NOT persisted as an asset but used as input configuration.

**Fields**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `language` | `str` | Yes | - | Target language (ISO 639-1) |
| `model_name` | `str` | No | From config | Explicit model override |
| `fast_mode` | `bool` | No | `False` | Use fast model for low latency |
| `voice_sample_path` | `str` | No | `None` | Path to voice cloning sample |
| `speaker_name` | `str` | No | From config | Named speaker fallback |
| `use_voice_cloning` | `bool` | No | `False` | Enable voice cloning (requires voice_sample_path) |
| `speed_clamp_min` | `float` | No | `0.5` | Minimum speed factor for duration matching |
| `speed_clamp_max` | `float` | No | `2.0` | Maximum speed factor for duration matching |
| `only_speed_up` | `bool` | No | `True` | Only speed up (never slow down) for live fragments |

**Validation Rules**:
- If `use_voice_cloning == True`, `voice_sample_path` MUST be provided and valid
- `speed_clamp_min` MUST be > 0 and < `speed_clamp_max`
- `speed_clamp_max` MUST be <= 4.0 (extreme limit to prevent artifacts)
- If `fast_mode == True` and no fast_model configured for language, fallback to standard model

**Voice Sample Validation Criteria** (for `voice_sample_path`):
- **Format**: WAV only (no MP3, FLAC, or other compressed formats)
- **Channels**: Mono (1 channel) - stereo samples MUST be converted or rejected
- **Sample Rate**: Minimum 16kHz (22050Hz or 24000Hz preferred for XTTS-v2)
- **Duration**: Between 3 and 30 seconds (shorter samples reduce cloning quality, longer samples waste memory)
- **Content**: Must contain clear speech (not silence, music, or noise)
- **Bit Depth**: 16-bit or 32-bit float

Validation is performed:
1. At component startup (`is_ready()` check) - validates all configured voice samples
2. Per-request - validates voice sample exists and meets criteria before synthesis
3. On failure: Returns TTSError with `error_type=VOICE_SAMPLE_INVALID`, `retryable=False`

**Voice Selection Logic**:
1. If `model_name` explicitly set → use that model
2. Else if `fast_mode == True` → use `fast_model` from config, fallback to `model` if unavailable
3. Else → use default `model` from config for the language
4. If `use_voice_cloning == True` and `voice_sample_path` valid → enable cloning
5. Else if multi-speaker model → use `speaker_name` or default_speaker from config
6. Else → single-speaker synthesis

---

### 4. TTSMetrics (Performance Metadata)

**Description**: Structured metrics emitted per synthesis request for observability, debugging, and performance tracking.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stream_id` | `str` | Yes | Logical stream identifier |
| `sequence_number` | `int` | Yes | Fragment index |
| `asset_id` | `str` | Yes | AudioAsset.asset_id this metric belongs to |
| `preprocess_time_ms` | `int` | Yes | Time spent preprocessing text |
| `synthesis_time_ms` | `int` | Yes | Time spent synthesizing audio |
| `alignment_time_ms` | `int` | No | Time spent on duration matching (0 if skipped) |
| `total_time_ms` | `int` | Yes | Total processing time (sum of above) |
| `baseline_duration_ms` | `int` | No | Original synthesized audio duration (pre-alignment) |
| `target_duration_ms` | `int` | No | Requested target duration |
| `final_duration_ms` | `int` | Yes | Actual final audio duration |
| `speed_factor_applied` | `float` | No | Speed factor used for time-stretch (1.0 = no change) |
| `speed_factor_clamped` | `bool` | No | Whether speed factor was clamped |
| `model_used` | `str` | Yes | Model identifier (e.g., "xtts_v2", "vits") |
| `voice_cloning_active` | `bool` | Yes | Whether voice cloning was used |
| `fast_mode_active` | `bool` | Yes | Whether fast mode was used |

**Validation Rules**:
- `total_time_ms` MUST equal sum of `preprocess_time_ms + synthesis_time_ms + alignment_time_ms`
- If `speed_factor_applied` is set, `baseline_duration_ms` and `target_duration_ms` MUST also be set
- `speed_factor_clamped` is only meaningful if `speed_factor_applied` is set

**Usage**:
- Emitted alongside AudioAsset for every synthesis request
- Used for debugging latency issues and duration matching accuracy
- Exported to Prometheus for operational monitoring

---

### 5. TTSError (Error Classification)

**Description**: Structured error information for failed or partial synthesis, enabling retry and fallback decisions.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error_type` | `TTSErrorType` | Yes | Error classification (enum) |
| `message` | `str` | Yes | Human-readable error description |
| `retryable` | `bool` | Yes | Whether this error warrants a retry |
| `details` | `dict[str, Any]` | No | Additional context (stack trace, config values) |

**TTSErrorType Enum**:

| Value | Retryable | Description | Example Trigger |
|-------|-----------|-------------|----------------|
| `MODEL_LOAD_FAILED` | `True` | Model file unavailable or corrupt | Model cache miss, disk I/O error |
| `SYNTHESIS_FAILED` | `False` | Synthesis engine crashed or invalid output | Invalid text, TTS library exception |
| `INVALID_INPUT` | `False` | Input validation failed | Empty text, unsupported language |
| `VOICE_SAMPLE_INVALID` | `False` | Voice cloning sample corrupt or wrong format | Invalid WAV file, wrong sample rate |
| `ALIGNMENT_FAILED` | `True` | Time-stretch operation failed (fallback to baseline audio) | Rubberband subprocess crash, returns unaligned audio with status=PARTIAL |
| `TIMEOUT` | `True` | Processing exceeded deadline | Synthesis took longer than timeout_ms |
| `UNKNOWN` | `True` | Unclassified error (safe default) | Unexpected exception |

**Validation Rules**:
- `message` MUST be non-empty and safe for logging (no secrets)
- `details` SHOULD NOT contain sensitive information (API keys, credentials)
- If `error_type == INVALID_INPUT`, `retryable` MUST be `False`
- If `error_type == UNKNOWN`, `retryable` SHOULD default to `True` (safe retry behavior)

**Error Handling Flow**:
```
1. TTS component encounters error
2. Classify error into TTSErrorType
3. Set retryable flag based on error type
4. Append TTSError to AudioAsset.errors list
5. Set AudioAsset.status = FAILED
6. Return AudioAsset to orchestrator
7. Orchestrator checks asset.is_retryable property
8. If True → retry synthesis
9. If False → apply fallback (silence, passthrough, etc.)
```

---

## Enums

### AudioFormat

```python
class AudioFormat(str, Enum):
    """Supported audio formats for synthesis output."""
    PCM_F32LE = "pcm_f32le"  # 32-bit float little-endian (preferred)
    PCM_S16LE = "pcm_s16le"  # 16-bit signed integer little-endian
```

**Usage**:
- `PCM_F32LE`: Default for TTS synthesis (higher precision, compatible with GStreamer)
- `PCM_S16LE`: Fallback for storage efficiency or compatibility requirements

---

### AudioStatus

```python
class AudioStatus(str, Enum):
    """Status of audio synthesis."""
    SUCCESS = "success"  # Synthesis completed successfully
    PARTIAL = "partial"  # Synthesis completed with warnings (e.g., clamped speed factor)
    FAILED = "failed"    # Synthesis failed completely
```

**Status Decision Logic**:
- `SUCCESS`: No errors, duration within tolerance, speed factor not clamped
- `PARTIAL`: Warnings present (e.g., speed factor clamped, fallback voice used) but audio produced
- `FAILED`: No audio produced, errors list non-empty, retryable flag determines retry behavior

---

## State Transitions

### AudioAsset Status Lifecycle

```
┌─────────┐
│ PENDING │ (initial state, not persisted in this design)
└────┬────┘
     │
     │ synthesis_started
     ▼
┌─────────────┐
│ PROCESSING  │ (internal state during synthesis)
└──────┬──────┘
       │
       ├──────────────┐
       │              │
       │ success      │ failure / warnings
       ▼              ▼
  ┌─────────┐   ┌─────────┐   ┌────────┐
  │ SUCCESS │   │ PARTIAL │   │ FAILED │
  └─────────┘   └─────────┘   └────────┘
                                    │
                                    │ if retryable
                                    ▼
                              ┌───────────┐
                              │  RETRY    │ (orchestrator decision)
                              └───────────┘
```

**Transition Rules**:
1. `PROCESSING → SUCCESS`: Synthesis completed, no errors, duration within tolerance
2. `PROCESSING → PARTIAL`: Synthesis completed with warnings (clamped speed, fallback voice)
3. `PROCESSING → FAILED`: Synthesis failed, errors list non-empty
4. `FAILED → RETRY`: Orchestrator retries if any error has `retryable == True`

---

## Validation Rules Summary

### Cross-Entity Validation

1. **AudioAsset ← TextAsset Linkage**:
   - `AudioAsset.parent_asset_ids` MUST contain valid TextAsset.asset_id
   - `AudioAsset.language` SHOULD match `TextAsset.language`
   - `AudioAsset.stream_id` MUST match `TextAsset.stream_id`
   - `AudioAsset.sequence_number` MUST match `TextAsset.sequence_number`

2. **AudioAsset ↔ TTSMetrics Linkage**:
   - `TTSMetrics.asset_id` MUST reference valid `AudioAsset.asset_id`
   - `TTSMetrics.final_duration_ms` MUST match `AudioAsset.duration_ms`
   - `TTSMetrics.stream_id` and `sequence_number` MUST match AudioAsset

3. **VoiceProfile Consistency**:
   - If `voice_cloning_used == True` in AudioAsset, VoiceProfile MUST have had `voice_sample_path` set
   - If `fast_mode_active == True` in TTSMetrics, VoiceProfile MUST have had `fast_mode == True`

### Business Logic Constraints

1. **Duration Matching**:
   - `speed_factor_applied` MUST be within `[speed_clamp_min, speed_clamp_max]`
   - If `only_speed_up == True`, `speed_factor_applied` MUST be >= 1.0
   - If `speed_factor_clamped == True`, warning MUST be included in AudioAsset metadata

2. **Model Selection**:
   - `model_used` in TTSMetrics MUST match resolved model from VoiceProfile
   - If `fast_mode == True` but no fast_model available, `model_used` MUST be standard model

3. **Error Handling**:
   - If `status == FAILED`, `errors` list MUST have at least one TTSError
   - If `retryable == False` for all errors, orchestrator MUST NOT retry

---

## Example Data Instances

### Example 1: Successful Synthesis with Duration Matching

**TextAsset** (input):
```json
{
  "asset_id": "text-uuid-123",
  "stream_id": "stream-abc",
  "sequence_number": 42,
  "text": "Hello world! This is a test.",
  "language": "en",
  "speaker_id": null
}
```

**VoiceProfile** (configuration):
```json
{
  "language": "en",
  "fast_mode": false,
  "use_voice_cloning": false,
  "speaker_name": "p225",
  "speed_clamp_min": 0.5,
  "speed_clamp_max": 2.0,
  "only_speed_up": true
}
```

**AudioAsset** (output):
```json
{
  "asset_id": "audio-uuid-456",
  "stream_id": "stream-abc",
  "sequence_number": 42,
  "parent_asset_ids": ["text-uuid-123"],
  "created_at": "2025-12-30T10:30:00Z",
  "component": "tts",
  "component_instance": "coqui-xtts-v2",
  "audio_format": "pcm_f32le",
  "sample_rate_hz": 16000,
  "channels": 1,
  "duration_ms": 2000,
  "payload_ref": "mem://fragments/stream-abc/42",
  "language": "en",
  "status": "success",
  "errors": [],
  "processing_time_ms": 1850,
  "voice_cloning_used": false,
  "preprocessed_text": "Hello world! This is a test."
}
```

**TTSMetrics**:
```json
{
  "stream_id": "stream-abc",
  "sequence_number": 42,
  "asset_id": "audio-uuid-456",
  "preprocess_time_ms": 5,
  "synthesis_time_ms": 1645,
  "alignment_time_ms": 200,
  "total_time_ms": 1850,
  "baseline_duration_ms": 2500,
  "target_duration_ms": 2000,
  "final_duration_ms": 2000,
  "speed_factor_applied": 1.25,
  "speed_factor_clamped": false,
  "model_used": "xtts_v2",
  "voice_cloning_active": false,
  "fast_mode_active": false
}
```

---

### Example 2: Synthesis Failure with Retryable Error

**TextAsset** (input):
```json
{
  "asset_id": "text-uuid-789",
  "stream_id": "stream-xyz",
  "sequence_number": 10,
  "text": "Synthesize this text.",
  "language": "es"
}
```

**AudioAsset** (output with error):
```json
{
  "asset_id": "audio-uuid-failed",
  "stream_id": "stream-xyz",
  "sequence_number": 10,
  "parent_asset_ids": ["text-uuid-789"],
  "created_at": "2025-12-30T10:35:00Z",
  "component": "tts",
  "component_instance": "coqui-xtts-v2",
  "audio_format": "pcm_f32le",
  "sample_rate_hz": 16000,
  "channels": 1,
  "duration_ms": 0,
  "payload_ref": "",
  "language": "es",
  "status": "failed",
  "errors": [
    {
      "error_type": "model_load_failed",
      "message": "Failed to load XTTS-v2 model for language 'es': File not found",
      "retryable": true,
      "details": {
        "model_path": "/models/xtts_v2_es",
        "exception": "FileNotFoundError"
      }
    }
  ],
  "processing_time_ms": 120,
  "voice_cloning_used": false,
  "preprocessed_text": "Synthesize this text."
}
```

**Orchestrator Action**: Retry synthesis request (error is retryable)

---

### Example 3: Voice Cloning with Fast Mode

**VoiceProfile**:
```json
{
  "language": "en",
  "fast_mode": true,
  "use_voice_cloning": true,
  "voice_sample_path": "/samples/voice_sample_stream_abc.wav",
  "speed_clamp_min": 1.0,
  "speed_clamp_max": 2.0,
  "only_speed_up": true
}
```

**AudioAsset**:
```json
{
  "asset_id": "audio-uuid-cloning",
  "stream_id": "stream-abc",
  "sequence_number": 99,
  "parent_asset_ids": ["text-uuid-cloning"],
  "component": "tts",
  "component_instance": "coqui-vits",
  "audio_format": "pcm_f32le",
  "sample_rate_hz": 16000,
  "channels": 1,
  "duration_ms": 1500,
  "language": "en",
  "status": "partial",
  "errors": [],
  "processing_time_ms": 950,
  "voice_cloning_used": true,
  "preprocessed_text": "Fast mode with cloning."
}
```

**Note**: Status is "partial" because fast mode was requested but voice cloning requires quality mode (XTTS-v2). The component fell back to VITS model without cloning, producing valid audio but with a warning.

---

## Migration & Versioning

**Version**: 1.0.0 (Initial data model)

**Future Considerations**:
1. **Multi-Voice Mixing**: Support multiple speakers in single AudioAsset (requires speaker_segments field)
2. **Streaming Synthesis**: Support partial audio emission before full synthesis completes
3. **Model Versioning**: Track model version in AudioAsset for reproducibility
4. **Caching Keys**: Add deterministic hash of inputs for cache lookup optimization

**Backward Compatibility**:
- AudioAsset follows same base structure as ASR TranscriptAsset and Translation TextAsset
- Adding new optional fields does NOT break existing consumers
- Enum value additions are backward compatible (existing values unchanged)

---

## Summary

This data model provides:
- **Strict validation** for all TTS inputs/outputs
- **Asset lineage** from TextAsset → AudioAsset → TTSMetrics
- **Error classification** for intelligent retry/fallback decisions
- **Performance observability** through structured metrics
- **Configuration flexibility** via VoiceProfile without runtime state pollution

All entities follow Pydantic v2 schema patterns for automatic validation, JSON serialization, and OpenAPI schema generation.
