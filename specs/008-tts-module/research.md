# Research: TTS Audio Synthesis Module

**Feature**: TTS Audio Synthesis Module
**Branch**: `008-tts-module`
**Date**: 2025-12-30

This document consolidates technical research findings for the TTS component implementation. All research decisions are documented inline in `plan.md` Phase 0, but this file provides a condensed reference.

## Research Summary

### 1. TTS Library Selection

**Decision**: Coqui TTS with XTTS-v2 (quality) and VITS (fast)

**Evaluated Alternatives**:
- **pyttsx3**: Too basic, no voice cloning
- **gTTS**: External API (violates testability)
- **Bark**: Too slow for real-time
- **Tortoise TTS**: Excellent quality but 5-10s latency (unacceptable)

**Chosen**: Coqui TTS
- Rationale: Reference implementation proven, supports CPU-only, multilingual, voice cloning
- Trade-offs: 2GB model size, 2-5s first load
- Implementation: Install via `pip install TTS`

---

### 2. Duration Matching Tool

**Decision**: Rubberband CLI for time-stretch

**Evaluated Alternatives**:
- **librosa**: Pure Python but slower, lower quality
- **SoundTouch**: Good but less flexible
- **ffmpeg atempo**: Limited to 0.5-2.0x range
- **pydub**: Changes pitch (unacceptable)

**Chosen**: Rubberband
- Rationale: Industry standard, pitch-preserving, configurable clamping
- Trade-offs: External system dependency
- Implementation: `rubberband -T {factor} input.wav output.wav`

---

### 3. Text Preprocessing

**Decision**: Deterministic preprocessing rules before synthesis

**Rules** (from reference implementation):
1. Normalize smart quotes → ASCII
2. Expand abbreviations ("NBA" → "N B A")
3. Rewrite scores ("15-12" → "15 to 12")
4. Normalize repeated punctuation
5. Strip excessive whitespace

**Rationale**: Improves TTS quality, reduces failures, enables caching (deterministic)

---

### 4. Voice Configuration

**Decision**: YAML configuration with per-language model/voice mappings

**Structure**:
```yaml
languages:
  en:
    model: "xtts_v2"
    fast_model: "vits"
    default_speaker: "p225"
```

**Rationale**: Runtime flexibility, env var override, matches project conventions

---

### 5. Error Classification

**Decision**: Structured error types with retryable flag

**Error Types**:
- `MODEL_LOAD_FAILED` (retryable=True)
- `SYNTHESIS_FAILED` (retryable=False)
- `INVALID_INPUT` (retryable=False)
- `VOICE_SAMPLE_INVALID` (retryable=False)
- `ALIGNMENT_FAILED` (retryable=True)
- `TIMEOUT` (retryable=True)
- `UNKNOWN` (retryable=True, safe default)

**Rationale**: Separation of concerns (TTS classifies, orchestrator retries), mirrors ASR/Translation pattern

---

### 6. Model Caching

**Decision**: In-memory cache per worker, keyed by `{model}_{language}`

**Strategy**:
- Cache lifetime: Worker process lifetime
- No eviction (models stay loaded)
- No cross-worker coordination needed
- Thread safety: Not required (single-threaded workers)

**Performance Targets**:
- First request: <5s (includes model load)
- Subsequent: <2s (cached)
- Fast mode: 40% latency reduction

---

## Implementation Dependencies

### Python Libraries
- `TTS>=0.15.0` - Coqui TTS synthesis engine
- `pydub>=0.25.1` - Audio format conversion
- `numpy>=1.24.0` - Audio data manipulation
- `pydantic>=2.0` - Data models and validation
- `PyYAML>=6.0` - Config file parsing

### System Dependencies
- `rubberband-cli` - Time-stretch tool (macOS: brew, Ubuntu: apt-get)

### Model Files
- XTTS-v2: ~2GB, multilingual with voice cloning
- VITS (per language): ~100MB each, single-speaker fast synthesis

---

## Best Practices Identified

### 1. Asset Lineage (from reference ASR/Translation)
- Track parent_asset_ids: TextAsset → AudioAsset
- Record preprocessed text as asset for debugging
- Emit TTSMetrics with every synthesis

### 2. Interface Design (from ASR/Translation pattern)
- Protocol + BaseClass structure
- Factory pattern for component creation
- Mock implementations for testing

### 3. Configuration Management
- YAML for voice/model mappings
- Env var override for deployment flexibility
- Validate config at component initialization (is_ready)

### 4. Error Handling
- Classify errors immediately
- Return structured errors in AudioAsset
- Orchestrator decides retry/fallback

---

## Performance Considerations

### Model Loading
- XTTS-v2: 2-5 seconds first load
- VITS: <1 second first load
- Mitigation: Pre-warm on startup, model caching

### Synthesis Latency
- XTTS-v2: 1.5-3 seconds per fragment
- VITS: 0.5-1.5 seconds per fragment (40% faster)
- Target: <2 seconds for subsequent requests (cached model)

### Duration Matching
- Rubberband subprocess: 50-200ms overhead
- Clamping prevents extreme artifacts
- Default range: [0.5x, 2.0x] speed factor

### Memory Usage
- XTTS-v2: ~3GB total (2GB model + 1GB working)
- VITS: ~600MB total (100MB model + 500MB working)
- Per-worker isolation (no shared state)

---

## Testing Strategy

### Mock Implementations
1. **MockTTSFixedTone**: 440Hz tone, exact duration, instant
2. **MockTTSFromFixture**: Pre-recorded audio from test files
3. **MockTTSFailOnce**: Fails first call, succeeds on retry

### Test Fixtures
- Deterministic PCM WAV files (mono, 16kHz, PCM_S16LE)
- Metadata JSON for expected duration/language
- Location: `tests/fixtures/tts/`

### Coverage Targets
- Unit tests: 80% minimum
- Critical paths (duration matching): 95%
- Contract tests: 100% of schemas

---

## Unresolved Questions

None - all research questions addressed in plan.md Phase 0.

---

## References

- **Coqui TTS**: https://github.com/coqui-ai/TTS
- **Rubberband**: https://breakfastquay.com/rubberband/
- **Reference Implementation**: specs/sources/TTS.md
- **Component Contract**: specs/007-tts-audio-synthesis.md
- **ASR Pattern Reference**: apps/sts-service/src/sts_service/asr/
- **Translation Pattern Reference**: apps/sts-service/src/sts_service/translation/

---

**Status**: Research complete, ready for implementation (Milestone 1)
