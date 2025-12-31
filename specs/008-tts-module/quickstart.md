# TTS Module Quickstart Guide

**Feature**: TTS Audio Synthesis Module
**Branch**: `008-tts-module`
**Date**: 2025-12-30

This guide provides quick setup and usage instructions for the TTS (Text-to-Speech) component in the STS service.

## Prerequisites

- Python 3.10.x (required per constitution)
- rubberband CLI tool (for duration matching)
- At least 4GB available RAM (for model loading)
- Access to apps/sts-service directory

## Installation

### 1. Install Python Dependencies

```bash
cd apps/sts-service

# Install TTS component with dependencies
pip install -r requirements.txt

# requirements.txt should include:
# TTS>=0.15.0          # Coqui TTS library
# pydub>=0.25.1        # Audio processing
# numpy>=1.24.0        # Audio data manipulation
# pydantic>=2.0        # Data models
# PyYAML>=6.0          # Config parsing
```

### 2. Install System Dependencies

**macOS**:
```bash
brew install rubberband
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install rubberband-cli
```

**Verification**:
```bash
rubberband --version
# Should output: Rubberband 3.x.x or similar
```

### 3. Download TTS Models (First-Time Setup)

The TTS component will download models automatically on first use. To pre-download:

```bash
# Python interactive shell
python3 -c "
from TTS.utils.manage import ModelManager
manager = ModelManager()

# Download XTTS-v2 (quality mode, ~2GB)
manager.download_model('tts_models/multilingual/multi-dataset/xtts_v2')

# Download VITS models for fast mode (smaller, ~100MB each)
manager.download_model('tts_models/en/vctk/vits')
manager.download_model('tts_models/es/css10/vits')
"
```

**Note**: Models are cached in `~/.local/share/tts/` by default.

### 4. Configure Voice Models (Optional)

Create or edit `apps/sts-service/configs/coqui-voices.yaml`:

```yaml
languages:
  en:
    model: "tts_models/multilingual/multi-dataset/xtts_v2"
    fast_model: "tts_models/en/vctk/vits"
    default_speaker: "p225"
  es:
    model: "tts_models/multilingual/multi-dataset/xtts_v2"
    fast_model: "tts_models/es/css10/vits"
    default_speaker: null
  fr:
    model: "tts_models/multilingual/multi-dataset/xtts_v2"
    fast_model: null  # No fast model for French
    default_speaker: null
```

Set environment variable to override default path:

```bash
export TTS_VOICES_CONFIG=/path/to/custom/coqui-voices.yaml
```

## Basic Usage

### Quick Test (Python REPL)

```python
from sts_service.tts.factory import create_tts_component
from sts_service.translation.models import TextAsset

# Create TTS component (quality mode)
tts = create_tts_component(provider="coqui", fast_mode=False)

# Verify readiness (will load models on first check)
print(f"TTS ready: {tts.is_ready}")  # May take 3-5 seconds first time

# Create sample TextAsset
text_asset = TextAsset(
    asset_id="text-uuid-123",
    stream_id="test-stream",
    sequence_number=1,
    text="Hello world! This is a test of the text-to-speech system.",
    language="en",
    component="translation",
    component_instance="mock"
)

# Synthesize audio
audio_asset = tts.synthesize(
    text_asset=text_asset,
    target_duration_ms=3000,  # Request 3 seconds duration
    output_sample_rate_hz=16000,
    output_channels=1,
    voice_profile={
        "language": "en",
        "fast_mode": False,
        "use_voice_cloning": False,
    }
)

# Check result
print(f"Status: {audio_asset.status}")
print(f"Duration: {audio_asset.duration_ms}ms")
print(f"Sample rate: {audio_asset.sample_rate_hz}Hz")
print(f"Channels: {audio_asset.channels}")
print(f"Processing time: {audio_asset.processing_time_ms}ms")
print(f"Preprocessed text: {audio_asset.preprocessed_text}")

# Access audio data
from sts_service.common.audio_payload_store import get_payload_store
store = get_payload_store()
audio_bytes = store.get(audio_asset.payload_ref)
print(f"Audio size: {len(audio_bytes)} bytes")
```

### Fast Mode (Low Latency)

```python
# Create TTS component in fast mode
tts_fast = create_tts_component(provider="coqui", fast_mode=True)

# Synthesize with VITS model (faster, single-speaker)
audio_asset = tts_fast.synthesize(
    text_asset=text_asset,
    target_duration_ms=2000,
    output_sample_rate_hz=16000,
    output_channels=1,
    voice_profile={
        "language": "en",
        "fast_mode": True,  # Use fast model
    }
)

print(f"Fast mode processing time: {audio_asset.processing_time_ms}ms")
# Expected: 40% faster than quality mode
```

### Voice Cloning (Quality Mode Only)

```python
# Prepare voice sample (mono, 16kHz WAV, 3-10 seconds recommended)
voice_sample_path = "/path/to/voice_sample.wav"

# Synthesize with voice cloning
audio_asset = tts.synthesize(
    text_asset=text_asset,
    target_duration_ms=3000,
    output_sample_rate_hz=16000,
    output_channels=1,
    voice_profile={
        "language": "en",
        "fast_mode": False,
        "use_voice_cloning": True,
        "voice_sample_path": voice_sample_path,
    }
)

print(f"Voice cloning used: {audio_asset.voice_cloning_used}")
```

## Testing

### Run Unit Tests

```bash
cd apps/sts-service

# Run all TTS unit tests
pytest tests/unit/tts/ -v

# Run with coverage
pytest tests/unit/tts/ --cov=src/sts_service/tts --cov-report=html

# Run specific test file
pytest tests/unit/tts/test_preprocessing.py -v
```

### Run Contract Tests

```bash
# Validate AudioAsset schema compliance
pytest tests/contract/tts/test_audio_asset_schema.py -v

# Validate TTSComponent interface
pytest tests/contract/tts/test_tts_component_contract.py -v
```

### Run Integration Tests

```bash
# Integration tests require TTS models downloaded
pytest tests/integration/tts/ -v

# Skip slow model loading tests
pytest tests/integration/tts/ -v -m "not slow"
```

## Mock Components (Testing)

For testing without TTS library:

```python
from sts_service.tts.mock import MockTTSFixedTone, MockTTSFromFixture

# MockTTSFixedTone: Returns 440Hz tone of exact duration
mock_tts = MockTTSFixedTone()
audio = mock_tts.synthesize(
    text_asset=text_asset,
    target_duration_ms=2000,
    output_sample_rate_hz=16000,
    output_channels=1,
    voice_profile={"language": "en"}
)
# Result: 2000ms tone, instant processing

# MockTTSFromFixture: Returns pre-recorded audio from fixtures
mock_tts_fixture = MockTTSFromFixture(fixture_dir="tests/fixtures/tts/")
audio = mock_tts_fixture.synthesize(...)
# Result: Audio from tests/fixtures/tts/{sequence_number}.wav
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_VOICES_CONFIG` | `configs/coqui-voices.yaml` | Path to voice config file |
| `TTS_MODEL_CACHE_DIR` | `~/.local/share/tts/` | Model cache directory |
| `TTS_TIMEOUT_MS` | `10000` | Synthesis timeout (10 seconds) |
| `TTS_DEBUG_ARTIFACTS` | `false` | Enable debug artifact persistence |
| `RUBBERBAND_PATH` | `rubberband` | Path to rubberband executable |

### TTSConfig Structure

See `specs/008-tts-module/contracts/tts-config-schema.json` for full schema.

**Example Config**:

```python
from sts_service.tts.models import TTSConfig

config = TTSConfig(
    voices_config_path="configs/coqui-voices.yaml",
    default_sample_rate_hz=16000,
    default_channels=1,
    model_cache_enabled=True,
    timeout_ms=10000,
    debug_artifacts=False,
    duration_matching={
        "enabled": True,
        "rubberband_path": "rubberband",
        "default_clamp_min": 0.5,
        "default_clamp_max": 2.0,
        "only_speed_up_default": True,
    },
    preprocessing={
        "enabled": True,
        "normalize_quotes": True,
        "expand_abbreviations": True,
        "rewrite_scores": True,
        "normalize_whitespace": True,
    }
)
```

## Performance Tuning

### Model Selection

**XTTS-v2 (Quality Mode)**:
- Best quality, supports voice cloning
- Latency: 1.5-3 seconds per fragment (after model load)
- Memory: ~2GB model + ~1GB working memory
- Use for: High-quality recordings, voice cloning scenarios

**VITS (Fast Mode)**:
- Lower quality, single-speaker only
- Latency: 0.5-1.5 seconds per fragment (40% faster)
- Memory: ~100MB model + ~500MB working memory
- Use for: Low-latency live streams, fast turnaround

### Duration Matching

**Speed Factor Clamping**:
- Default range: [0.5x, 2.0x]
- Conservative range: [0.8x, 1.5x] (better quality, less aggressive)
- Aggressive range: [0.5x, 3.0x] (more flexible, potential artifacts)

**Only Speed Up Mode**:
- Enabled by default for live streams
- Prevents slowing down audio (maintains flow)
- Use `only_speed_up=False` for subtitle/VTT alignment

### Model Caching

Models are cached in memory per worker lifetime:
- First synthesis: 3-5 seconds (includes model load)
- Subsequent synthesis: <2 seconds (cached model)
- Cache is never evicted (worker restart reloads)

## Troubleshooting

### "Model not found" Error

**Problem**: TTS model files not downloaded

**Solution**:
```bash
# Download manually
python3 -c "from TTS.utils.manage import ModelManager; ModelManager().download_model('tts_models/multilingual/multi-dataset/xtts_v2')"

# Or let component download on first use (slower first request)
```

### "Rubberband not found" Error

**Problem**: rubberband CLI not installed or not in PATH

**Solution**:
```bash
# Install rubberband (see Installation section)
# Verify installation
which rubberband

# Or set explicit path
export RUBBERBAND_PATH=/usr/local/bin/rubberband
```

### Slow First Synthesis

**Problem**: First synthesis takes 5+ seconds

**Explanation**: Normal behavior - model loading is expensive

**Solutions**:
- Pre-warm component on startup: `tts.is_ready` triggers model load
- Use fast mode for lower latency: `fast_mode=True`
- Pre-download models during deployment (see Installation step 3)

### Duration Mismatch

**Problem**: Synthesized audio duration doesn't match target

**Debug**:
```python
# Check TTSMetrics for speed factor and clamping
metrics = get_tts_metrics(audio_asset.asset_id)
print(f"Baseline duration: {metrics.baseline_duration_ms}ms")
print(f"Target duration: {metrics.target_duration_ms}ms")
print(f"Speed factor: {metrics.speed_factor_applied}x")
print(f"Clamped: {metrics.speed_factor_clamped}")
```

**Solutions**:
- If clamped: Increase `speed_clamp_max` or accept warning
- If alignment failed: Check rubberband installation
- If extreme mismatch: Consider different synthesis speed hint

### Memory Usage High

**Problem**: TTS component using 3-4GB RAM

**Explanation**: Normal for XTTS-v2 model (~2GB) + working memory

**Solutions**:
- Use fast mode (VITS) for lower memory: ~600MB total
- Increase worker memory allocation
- Disable model caching (not recommended, slower)

## Next Steps

1. **Integration**: Integrate TTS component into STS pipeline orchestrator
2. **Voice Samples**: Prepare voice cloning samples (3-10s, mono, 16kHz WAV)
3. **Monitoring**: Set up Prometheus metrics for TTS latency and error rates
4. **Optimization**: Benchmark different models for your use case
5. **Testing**: Run E2E tests with full STS pipeline (ASR → Translation → TTS)

## References

- **Spec**: [specs/008-tts-module/spec.md](./spec.md)
- **Plan**: [specs/008-tts-module/plan.md](./plan.md)
- **Data Model**: [specs/008-tts-module/data-model.md](./data-model.md)
- **Component Contract**: [specs/007-tts-audio-synthesis.md](../007-tts-audio-synthesis.md)
- **Coqui TTS Docs**: https://github.com/coqui-ai/TTS
- **Rubberband Docs**: https://breakfastquay.com/rubberband/
