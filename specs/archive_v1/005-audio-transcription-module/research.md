# Research: Audio Transcription Module (ASR Component)

**Feature**: 005-audio-transcription-module
**Date**: 2025-12-28
**Status**: Complete

## 1. ASR Library Selection

### Decision: faster-whisper

**Rationale**:
- CTranslate2-based reimplementation offers 4x faster transcription than original Whisper
- CPU-friendly with int8 quantization support (critical for cost-effective deployment)
- Word-level timestamps with probability scores
- Built-in VAD (Voice Activity Detection) using Silero VAD v6
- Proven in existing archive codebase (`.sts-service-archive/utils/transcription.py`)

**Alternatives Considered**:
| Library | Rejected Because |
|---------|------------------|
| openai/whisper | Slower inference, higher memory usage |
| whisper.cpp | Requires C++ bindings, less Python-native |
| WhisperX | Adds diarization complexity not needed for single-speaker dubbing |

## 2. Audio Preprocessing Strategy

### Decision: scipy + numpy (no librosa dependency)

**Rationale**:
- `librosa` adds significant dependencies (soundfile, audioread, etc.)
- All required operations achievable with `scipy.signal` and `numpy`:
  - High-pass filtering: `scipy.signal.butter` + `sosfilt`
  - Normalization: `numpy` operations
  - Pre-emphasis: Simple FIR filter with numpy
- Reduces container image size and startup time

**Implementation**:
```python
# High-pass filter (~80 Hz) - replace librosa
nyquist = sample_rate // 2
sos = scipy.signal.butter(4, 80 / nyquist, btype='high', output='sos')
audio = scipy.signal.sosfilt(sos, audio)

# Normalization - replace librosa.util.normalize
max_val = np.abs(audio).max()
audio = audio / max_val if max_val > 0 else audio

# Pre-emphasis - replace librosa.effects.preemphasis
audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])
```

## 3. faster-whisper Configuration

### Decision: Optimized for streaming live commentary

**VAD Parameters**:
```python
vad_parameters = {
    "threshold": 0.5,           # Speech probability threshold
    "min_silence_duration_ms": 300,  # More sensitive (default 2000ms)
    "min_speech_duration_ms": 250,   # Discard very short utterances
    "speech_pad_ms": 400,       # Padding around speech segments
}
```

**Transcription Parameters**:
```python
transcribe_params = {
    "language": "en",           # Fixed English for v0
    "word_timestamps": True,    # Required for segment alignment
    "vad_filter": True,
    "beam_size": 8,             # Quality vs speed tradeoff
    "best_of": 8,
    "temperature": [0.0, 0.2, 0.4],  # Temperature ensemble
    "compression_ratio_threshold": 2.4,
    "log_prob_threshold": -1.0,
    "no_speech_threshold": 0.6,
    "condition_on_previous_text": True,
}
```

**Model Selection**:
- Default: `base` model for CPU deployment (fast, reasonable quality)
- Optional: `large-v3` for GPU deployment (higher accuracy)
- Compute type: `int8` for CPU, `float16` for CUDA

## 4. Confidence Score Mapping

### Decision: Linear mapping from avg_logprob

**Formula**:
```python
confidence = clamp((segment.avg_logprob + 1.0) / 1.0, 0.0, 1.0)
```

**Rationale**:
- `avg_logprob` typically ranges from -1.0 (low confidence) to 0.0 (high confidence)
- Simple linear mapping provides relative ranking (not calibrated probability)
- Matches existing archive implementation

## 5. Utterance Shaping Strategy

### Decision: Two-phase boundary improvement

**Phase 1 - Merge Short Segments**:
- Merge segments < 1.0s into previous if previous lacks terminal punctuation (`. ! ?`)
- Preserves sentence completeness for translation/TTS

**Phase 2 - Split Long Segments**:
- Max duration: 6.0 seconds (configurable)
- Split priority:
  1. Sentence boundaries (`. `)
  2. Punctuation/conjunctions (`, ; and but so`)
  3. Midpoint near whitespace (fallback)

## 6. Domain Priming Strategy

### Decision: Initial prompt injection

**Rationale**:
- faster-whisper supports `initial_prompt` parameter
- Domain-specific prompts bias vocabulary recognition
- No additional model or training required

**Supported Domains**:
| Domain | Prompt Focus |
|--------|--------------|
| sports | Team names, player names, scores, play-by-play |
| football | Yard lines, penalties, touchdowns, positions |
| basketball | Fouls, timeouts, scores, strategy |
| news | Proper names, locations, dates |
| interview | Conversational speech, Q&A patterns |
| general | Default - proper names, natural conversation |

## 7. Error Classification

### Decision: Structured error types with retryable flag

**Error Types**:
| Error Type | Retryable | Example |
|------------|-----------|---------|
| `NO_SPEECH` | No | Silent/noise-only fragment |
| `MODEL_LOAD_ERROR` | Yes | Model file not found (temporary) |
| `MEMORY_ERROR` | Yes | OOM during transcription |
| `INVALID_AUDIO` | No | Corrupt audio data |
| `TIMEOUT` | Yes | Transcription exceeded deadline |
| `UNKNOWN` | No | Unclassified failure |

## 8. Mock Implementation Strategy

### Decision: Deterministic stub with configurable responses

**MockASR Features**:
- Returns configured text regardless of audio content
- Supports deterministic timestamps based on `sequence_number`
- Supports configurable confidence values
- Supports failure injection for error testing

**Test Fixture Integration**:
- `1-min-nfl.m4a`: Real transcription validation with sports domain
- `1-min-nfl.mp4`: Audio extraction + transcription end-to-end
- `big-buck-bunny.mp4`: Silence/no-speech detection validation

## 9. Model Lifecycle Management

### Decision: Global cache with configuration key

**Cache Strategy**:
```python
_model_cache: Dict[str, WhisperModel] = {}

def get_model(model_size: str, device: str) -> WhisperModel:
    cache_key = f"{model_size}_{device}"
    if cache_key not in _model_cache:
        _model_cache[cache_key] = WhisperModel(...)
    return _model_cache[cache_key]
```

**Rationale**:
- Model loading is expensive (~1-5s depending on size)
- Fragments processed sequentially per stream (no concurrent access issues)
- Cache cleared only on worker shutdown

## 10. Test Strategy Alignment

### Unit Tests (mocked faster-whisper):
- Audio preprocessing functions
- Confidence score calculation
- Utterance shaping (merge/split)
- Domain prompt generation
- Error classification

### Integration Tests (real faster-whisper with fixtures):
- Real transcription with `1-min-nfl.m4a` (sports content)
- Timestamp alignment verification
- No-speech detection with `big-buck-bunny.mp4`
- Domain priming effectiveness

### Contract Tests:
- Input/output schema validation
- Error response format
- Asset lineage tracking

## References

- faster-whisper documentation: https://github.com/SYSTRAN/faster-whisper
- Silero VAD: https://github.com/snakers4/silero-vad
- Archive implementation: `.sts-service-archive/utils/transcription.py`
- Feature spec: `specs/005-audio-transcription-module.md`
- Pipeline design: `specs/004-sts-pipeline-design.md`
