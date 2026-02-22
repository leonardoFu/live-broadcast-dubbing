# Implementation Plan: ElevenLabs TTS Provider

**Feature ID**: 022-elevenlabs-tts-provider
**Created**: 2026-01-03
**Status**: Draft

## Overview

This plan implements ElevenLabs API integration as an alternative TTS provider for the STS service. The implementation adds a new provider class that conforms to the existing `TTSComponent` interface, enabling operators to choose between local Coqui TTS (low latency) and cloud-based ElevenLabs TTS (high quality).

**Key Design Decision**: No automatic fallback to Coqui. Errors propagate to the pipeline orchestrator for centralized retry/fallback logic.

## Prerequisites

**Required Artifacts**:
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/specs/022-elevenlabs-tts-provider/spec.md` - Feature specification
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/interface.py` - TTS component contract
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/coqui_provider.py` - Reference implementation
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/factory.py` - Provider factory
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/models.py` - Data models
- `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/errors.py` - Error types

**Dependencies**:
- ElevenLabs Python client library: `elevenlabs>=0.2.0`
- Existing TTS module architecture (specs/008-tts-module)
- Rubberband for duration matching (already present in Coqui provider)
- Pydub for audio format conversion (already present in Coqui provider)

**Validation**:
- All prerequisite files exist and are accessible
- TTS component interface is stable (no breaking changes planned)
- Error classification types support retryability flags

## Phase 0: Research & Design

### Technology Selection

**ElevenLabs API Client**:
- Library: `elevenlabs` Python package (official client)
- Version: `>=0.2.0` (latest stable)
- Authentication: API key via `ELEVENLABS_API_KEY` environment variable
- Endpoint: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
- Rate Limiting: Handled by client library (429 responses)

**Default Model**:
- Model ID: `eleven_flash_v2_5` (ElevenLabs Flash v2.5)
- Rationale: Fast inference suitable for real-time dubbing
- Alternative: `eleven_multilingual_v2` (higher quality, slower)

**Voice Mapping Strategy**:
```python
DEFAULT_VOICES = {
    "en": "21m00Tcm4TlvDq8ikWAM",  # Rachel (American female)
    "es": "ThT5KcBeYPX3keUQqHPh",  # Diego (Spanish male)
    "fr": "N2lVS1w4EtoT3dr4eOWO",  # Thomas (French male)
    "de": "pFZP5JQG7iQjIQuC4Bku",  # Sarah (German female)
    "it": "onwK4e9ZLuTAKqWW03F9",  # Giovanni (Italian male)
    "pt": "cjVigY5qzO86Huf0OWal",  # Domi (Portuguese female)
    "ja": "EXAVITQu4vr4xnSDxMaL",  # Hiro (Japanese male)
}
FALLBACK_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel (English) for unsupported languages
```

**Audio Format Handling**:
- ElevenLabs API returns: MP3 by default
- Conversion required: MP3 → PCM F32LE (same as Coqui)
- Conversion tool: Pydub with ffmpeg backend
- Resampling: Use pydub to match `output_sample_rate_hz`
- Channel conversion: Mono → Stereo if `output_channels=2`

**Error Mapping**:
| ElevenLabs Error | TTSErrorType | Retryable | Rationale |
|-----------------|--------------|-----------|-----------|
| 401/403 (auth) | INVALID_INPUT | False | Bad API key (permanent) |
| 429 (rate limit) | TIMEOUT | True | Transient quota issue |
| 400 (bad request) | INVALID_INPUT | False | Malformed input (permanent) |
| 500/502/503 (server) | UNKNOWN | True | API downtime (transient) |
| Network timeout | TIMEOUT | True | Connectivity issue (transient) |
| Invalid voice_id | INVALID_INPUT | False | Bad configuration (permanent) |

### Architecture Decisions

**No Automatic Fallback**:
- **Decision**: ElevenLabs provider does NOT fallback to Coqui on failure
- **Rationale**: Centralized retry/fallback logic at orchestrator level prevents duplicate logic and enables A/B testing
- **Impact**: Errors propagate as `TTSError` with `retryable` flag; orchestrator decides retry strategy

**Synchronous API Only**:
- **Decision**: Use standard text-to-speech endpoint (not streaming)
- **Rationale**: Simpler implementation; latency acceptable for 6s fragments
- **Future**: Streaming API can be added as optimization without interface changes

**Configuration Extension**:
- **Approach**: Extend `VoiceProfile` model with optional ElevenLabs fields
- **Fields Added**: `model_id`, `voice_id`, `stability`, `similarity_boost`
- **Backward Compatibility**: All fields optional; Coqui provider ignores them

## Phase 1: Data Model Updates

**Goal**: Extend TTS data models to support ElevenLabs-specific configuration.

### Task 1.1: Update VoiceProfile Model

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/models.py`

**Changes**:
```python
class VoiceProfile(BaseModel):
    """Voice configuration for TTS synthesis."""

    # Existing fields (Coqui-specific)
    language: str
    model_name: str | None = None
    fast_mode: bool = False
    voice_sample_path: str | None = None
    speaker_name: str | None = None
    use_voice_cloning: bool = False
    speed_clamp_min: float = 0.5
    speed_clamp_max: float = 2.0
    only_speed_up: bool = True

    # NEW: ElevenLabs-specific fields
    voice_id: str | None = Field(
        default=None,
        description="ElevenLabs voice ID (overrides language-based default)"
    )
    elevenlabs_model_id: str | None = Field(
        default=None,
        description="ElevenLabs model ID (e.g., eleven_flash_v2_5, eleven_multilingual_v2)"
    )
    stability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="ElevenLabs voice stability setting (0.0-1.0)"
    )
    similarity_boost: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="ElevenLabs similarity boost setting (0.0-1.0)"
    )
```

**Validation**:
- All new fields are optional (default `None`)
- Stability and similarity_boost have range constraints (0.0-1.0)
- Existing Coqui fields remain unchanged
- Pydantic validation ensures type safety

**Testing Strategy** (TDD - write tests BEFORE implementation):
- Unit test: `test_voice_profile_elevenlabs_fields_optional()` - Validate new fields are optional
- Unit test: `test_voice_profile_stability_range_validation()` - Validate 0.0-1.0 range
- Unit test: `test_voice_profile_similarity_boost_range_validation()` - Validate 0.0-1.0 range
- Unit test: `test_voice_profile_backward_compatible()` - Ensure existing Coqui code works unchanged

---

## Phase 2: ElevenLabs Provider Implementation

**Goal**: Implement `ElevenLabsTTSComponent` class conforming to `TTSComponent` protocol.

### Task 2.1: Create ElevenLabsTTSComponent Class

**New File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`

**Class Structure**:
```python
class ElevenLabsTTSComponent(BaseTTSComponent):
    """ElevenLabs TTS provider implementation.

    Uses ElevenLabs API for high-quality cloud-based TTS synthesis.
    Conforms to TTSComponent protocol for drop-in compatibility with Coqui provider.

    Features:
    - Multilingual synthesis via ElevenLabs pre-trained voices
    - Configurable quality settings (model, stability, similarity_boost)
    - Error classification with retryability flags
    - Duration matching via rubberband (same as Coqui)
    - Audio format conversion (MP3 → PCM F32LE)

    Requirements:
    - ELEVENLABS_API_KEY environment variable
    - elevenlabs>=0.2.0 Python package
    - ffmpeg (for audio conversion via pydub)
    - rubberband (for duration matching)
    """

    def __init__(
        self,
        config: TTSConfig | None = None,
        api_key: str | None = None,
    ):
        """Initialize ElevenLabs TTS component."""

    @property
    def component_instance(self) -> str:
        """Return provider identifier (e.g., 'elevenlabs-eleven_flash_v2_5')."""

    @property
    def is_ready(self) -> bool:
        """Check if API key is valid and API is reachable."""

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Synthesize speech using ElevenLabs API."""

    def _get_voice_id(self, language: str, voice_profile: VoiceProfile | None) -> str:
        """Get voice ID from profile or language-based default."""

    def _call_elevenlabs_api(
        self,
        text: str,
        voice_id: str,
        model_id: str,
        voice_settings: dict | None,
    ) -> bytes:
        """Call ElevenLabs API and return MP3 audio bytes."""

    def _convert_audio_format(
        self,
        mp3_bytes: bytes,
        target_sample_rate_hz: int,
        target_channels: int,
    ) -> bytes:
        """Convert MP3 to PCM F32LE with target sample rate and channels."""

    def _classify_api_error(self, error: Exception) -> TTSError:
        """Map ElevenLabs API errors to TTSError types."""

    def shutdown(self) -> None:
        """Release resources (no-op for stateless API client)."""
```

**Implementation Details**:

**Voice Selection Logic**:
```python
def _get_voice_id(self, language: str, voice_profile: VoiceProfile | None) -> str:
    """Get voice ID from profile or language-based default.

    Priority:
    1. Explicit voice_id from VoiceProfile (if provided)
    2. Language-based default from DEFAULT_VOICES mapping
    3. Fallback to English (Rachel) if language not supported
    """
    if voice_profile and voice_profile.voice_id:
        return voice_profile.voice_id

    voice_id = DEFAULT_VOICES.get(language, FALLBACK_VOICE)
    if voice_id == FALLBACK_VOICE and language not in DEFAULT_VOICES:
        logger.warning(
            f"Language '{language}' not in ElevenLabs voice mapping. "
            f"Falling back to English voice (Rachel)."
        )

    return voice_id
```

**API Call with Error Handling**:
```python
def _call_elevenlabs_api(
    self,
    text: str,
    voice_id: str,
    model_id: str,
    voice_settings: dict | None,
) -> bytes:
    """Call ElevenLabs API with timeout and error handling."""
    from elevenlabs import generate, VoiceSettings

    try:
        # Prepare voice settings
        settings = None
        if voice_settings:
            settings = VoiceSettings(
                stability=voice_settings.get("stability", 0.5),
                similarity_boost=voice_settings.get("similarity_boost", 0.75),
            )

        # Call API (synchronous)
        audio_bytes = generate(
            text=text,
            voice=voice_id,
            model=model_id,
            api_key=self._api_key,
            voice_settings=settings,
        )

        return audio_bytes  # MP3 format

    except Exception as e:
        raise self._classify_api_error(e)
```

**Audio Format Conversion**:
```python
def _convert_audio_format(
    self,
    mp3_bytes: bytes,
    target_sample_rate_hz: int,
    target_channels: int,
) -> bytes:
    """Convert MP3 to PCM F32LE."""
    from pydub import AudioSegment
    import struct

    # Load MP3 from bytes
    audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))

    # Resample to target sample rate
    if audio.frame_rate != target_sample_rate_hz:
        audio = audio.set_frame_rate(target_sample_rate_hz)

    # Convert mono to stereo if needed
    if target_channels == 2 and audio.channels == 1:
        audio = audio.set_channels(2)

    # Convert to PCM F32LE
    samples = audio.get_array_of_samples()
    max_val = float(2**(audio.sample_width * 8 - 1))
    normalized = [s / max_val for s in samples]

    return struct.pack(f"<{len(normalized)}f", *normalized)
```

**Error Classification**:
```python
def _classify_api_error(self, error: Exception) -> TTSError:
    """Map ElevenLabs exceptions to TTSError types."""
    from elevenlabs import APIError, RateLimitError, AuthenticationError

    if isinstance(error, RateLimitError):
        return classify_error(
            TTSErrorType.TIMEOUT,
            "ElevenLabs rate limit exceeded",
            retryable_override=True,
            details={"status_code": 429}
        )

    if isinstance(error, AuthenticationError):
        return classify_error(
            TTSErrorType.INVALID_INPUT,
            "ElevenLabs API authentication failed (invalid API key)",
            retryable_override=False,
            details={"status_code": 401}
        )

    if isinstance(error, APIError):
        status_code = getattr(error, "status_code", 500)

        if status_code == 400:
            return classify_error(
                TTSErrorType.INVALID_INPUT,
                f"ElevenLabs API bad request: {str(error)}",
                retryable_override=False,
                details={"status_code": 400}
            )

        if status_code >= 500:
            return classify_error(
                TTSErrorType.UNKNOWN,
                f"ElevenLabs API server error: {str(error)}",
                retryable_override=True,
                details={"status_code": status_code}
            )

    # Network/timeout errors
    if isinstance(error, (TimeoutError, ConnectionError)):
        return classify_error(
            TTSErrorType.TIMEOUT,
            f"ElevenLabs API connection error: {str(error)}",
            retryable_override=True,
        )

    # Unknown error - default to retryable
    return classify_error(
        TTSErrorType.UNKNOWN,
        f"ElevenLabs synthesis failed: {str(error)}",
        retryable_override=True,
    )
```

**Testing Strategy** (TDD - write tests BEFORE implementation):

**Unit Tests** (mocked API):
- `test_elevenlabs_basic_synthesis()` - Verify text input produces AudioAsset with mocked API
- `test_elevenlabs_voice_id_explicit()` - Explicit voice_id overrides language default
- `test_elevenlabs_voice_id_language_default()` - Language-based default voice selection
- `test_elevenlabs_voice_id_unsupported_language_fallback()` - Unsupported language falls back to English
- `test_elevenlabs_model_id_default()` - Default model is `eleven_flash_v2_5`
- `test_elevenlabs_model_id_custom()` - Custom model_id is used when specified
- `test_elevenlabs_voice_settings_applied()` - Stability and similarity_boost passed to API
- `test_elevenlabs_error_401_non_retryable()` - 401 errors map to INVALID_INPUT with retryable=False
- `test_elevenlabs_error_429_retryable()` - 429 errors map to TIMEOUT with retryable=True
- `test_elevenlabs_error_500_retryable()` - 500 errors map to UNKNOWN with retryable=True
- `test_elevenlabs_error_400_non_retryable()` - 400 errors map to INVALID_INPUT with retryable=False
- `test_elevenlabs_error_network_timeout_retryable()` - Network errors map to TIMEOUT with retryable=True
- `test_elevenlabs_audio_format_conversion()` - MP3 → PCM F32LE conversion works
- `test_elevenlabs_sample_rate_conversion()` - Resampling to target sample rate
- `test_elevenlabs_mono_to_stereo_conversion()` - Channel conversion when output_channels=2
- `test_elevenlabs_component_instance()` - component_instance format is "elevenlabs-{model_id}"
- `test_elevenlabs_is_ready_with_api_key()` - is_ready=True when API key valid
- `test_elevenlabs_is_ready_without_api_key()` - is_ready=False when API key missing

**Contract Tests** (schema validation):
- `test_elevenlabs_audio_asset_schema()` - AudioAsset output matches TTS contract
- `test_elevenlabs_metadata_lineage()` - parent_asset_ids correctly track text_asset

**Integration Tests** (real API, requires API key, marked `@elevenlabs_live`):
- `test_elevenlabs_real_api_english_synthesis()` - Real API call produces valid audio (English)
- `test_elevenlabs_real_api_spanish_synthesis()` - Real API call produces valid audio (Spanish)
- `test_elevenlabs_real_api_duration_matching()` - Duration matching works with real audio
- `test_elevenlabs_real_api_quality_modes()` - Different models produce valid output

---

### Task 2.2: Update Factory to Support ElevenLabs

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/factory.py`

**Changes**:
```python
ProviderType = Literal[
    "coqui",
    "elevenlabs",  # NEW
    "mock",
    "mock_fixed_tone",
    "mock_from_fixture",
    "mock_fail_once"
]

def create_tts_component(
    provider: ProviderType = "coqui",
    config: TTSConfig | None = None,
    **kwargs: Any,
) -> TTSComponent:
    """Create TTS component instance."""

    if config is None:
        config = TTSConfig()

    if provider == "coqui":
        from .coqui_provider import CoquiTTSComponent
        return CoquiTTSComponent(config=config, **kwargs)

    elif provider == "elevenlabs":  # NEW
        from .elevenlabs_provider import ElevenLabsTTSComponent
        return ElevenLabsTTSComponent(config=config, **kwargs)

    # ... existing mock providers ...

    else:
        raise ValueError(
            f"Unknown TTS provider: {provider}. "
            f"Supported: coqui, elevenlabs, mock, mock_fixed_tone, ..."
        )
```

**Testing Strategy** (TDD):
- Unit test: `test_factory_creates_elevenlabs_provider()` - Verify factory creates ElevenLabsTTSComponent
- Unit test: `test_factory_elevenlabs_with_config()` - Config passed through correctly
- Unit test: `test_factory_elevenlabs_with_kwargs()` - Kwargs (api_key) passed through

---

## Phase 3: Duration Matching Integration

**Goal**: Integrate rubberband duration matching for ElevenLabs audio (same logic as Coqui).

### Task 3.1: Extract Duration Matching to Shared Utility

**Rationale**: Both Coqui and ElevenLabs use identical rubberband logic. Extract to avoid duplication.

**New File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/duration_matching.py`

**Function**:
```python
def apply_duration_matching(
    audio_bytes: bytes,
    sample_rate_hz: int,
    channels: int,
    baseline_duration_ms: int,
    target_duration_ms: int,
    speed_clamp_min: float = 0.5,
    speed_clamp_max: float = 2.0,
    only_speed_up: bool = True,
) -> tuple[bytes, float, bool]:
    """Apply rubberband time-stretching to match target duration.

    Args:
        audio_bytes: PCM F32LE audio data
        sample_rate_hz: Sample rate
        channels: Number of channels
        baseline_duration_ms: Current audio duration
        target_duration_ms: Target duration
        speed_clamp_min: Minimum speed factor
        speed_clamp_max: Maximum speed factor
        only_speed_up: Only speed up (never slow down)

    Returns:
        Tuple of (stretched_audio_bytes, speed_factor_applied, was_clamped)
    """
    # Calculate required speed factor
    speed_factor = baseline_duration_ms / target_duration_ms

    # Apply clamping
    clamped = False
    if only_speed_up and speed_factor < 1.0:
        speed_factor = 1.0
        clamped = True
    elif speed_factor < speed_clamp_min:
        speed_factor = speed_clamp_min
        clamped = True
    elif speed_factor > speed_clamp_max:
        speed_factor = speed_clamp_max
        clamped = True

    # Call rubberband (same logic as Coqui)
    # ... implementation details ...

    return stretched_audio, speed_factor, clamped
```

**Refactor Existing Coqui Provider**:
- Update `CoquiTTSComponent.synthesize()` to use `apply_duration_matching()`
- Remove duplicate rubberband logic from coqui_provider.py
- Ensure backward compatibility (no behavioral changes)

**Testing Strategy** (TDD):
- Unit test: `test_duration_matching_speedup()` - Speed factor > 1.0
- Unit test: `test_duration_matching_slowdown()` - Speed factor < 1.0
- Unit test: `test_duration_matching_clamp_min()` - Clamping to min
- Unit test: `test_duration_matching_clamp_max()` - Clamping to max
- Unit test: `test_duration_matching_only_speed_up()` - Never slow down when flag set
- Integration test: `test_duration_matching_with_real_rubberband()` - Real rubberband call

---

### Task 3.2: Integrate Duration Matching in ElevenLabs Provider

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/src/sts_service/tts/elevenlabs_provider.py`

**Changes**:
```python
def synthesize(
    self,
    text_asset: TextAsset,
    target_duration_ms: int | None = None,
    output_sample_rate_hz: int = 16000,
    output_channels: int = 1,
    voice_profile: VoiceProfile | None = None,
) -> AudioAsset:
    """Synthesize with duration matching."""

    # ... API call and format conversion ...

    # Calculate baseline duration from PCM audio
    baseline_duration_ms = self._calculate_duration_ms(
        audio_bytes=pcm_audio,
        sample_rate_hz=output_sample_rate_hz,
        channels=output_channels,
    )

    # Apply duration matching if requested
    final_audio = pcm_audio
    speed_factor_applied = None
    speed_clamped = False

    if target_duration_ms is not None:
        from .duration_matching import apply_duration_matching

        final_audio, speed_factor_applied, speed_clamped = apply_duration_matching(
            audio_bytes=pcm_audio,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
            baseline_duration_ms=baseline_duration_ms,
            target_duration_ms=target_duration_ms,
            speed_clamp_min=voice_profile.speed_clamp_min,
            speed_clamp_max=voice_profile.speed_clamp_max,
            only_speed_up=voice_profile.only_speed_up,
        )

    # Recalculate final duration
    final_duration_ms = self._calculate_duration_ms(
        audio_bytes=final_audio,
        sample_rate_hz=output_sample_rate_hz,
        channels=output_channels,
    )

    # Determine status
    status = AudioStatus.SUCCESS
    if speed_clamped:
        status = AudioStatus.PARTIAL
        # Add warning to errors list

    return AudioAsset(
        # ... standard fields ...
        duration_ms=final_duration_ms,
        audio_bytes=final_audio,
        status=status,
    )
```

**Testing Strategy** (TDD):
- Unit test: `test_elevenlabs_duration_matching_applied()` - Duration matching works with mocked audio
- Unit test: `test_elevenlabs_duration_matching_clamped_partial_status()` - Clamped speed results in PARTIAL status
- Integration test: `test_elevenlabs_duration_matching_real_audio()` - Duration matching with real API audio

---

## Phase 4: Manual Test Client Integration

**Goal**: Add ElevenLabs provider support to manual test client for operator testing.

### Task 4.1: Update Manual Test Client

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/manual_test_client.py`

**Changes**:
```python
# Add command-line argument
parser.add_argument(
    "--tts-provider",
    type=str,
    choices=["coqui", "elevenlabs"],
    default="coqui",
    help="TTS provider to use (coqui or elevenlabs)"
)

# Initialize TTS component based on flag
if args.tts_provider == "elevenlabs":
    from sts_service.tts.factory import create_tts_component
    tts = create_tts_component(provider="elevenlabs")
    logger.info("Using ElevenLabs TTS provider")
else:
    from sts_service.tts.factory import create_tts_component
    tts = create_tts_component(provider="coqui", fast_mode=True)
    logger.info("Using Coqui TTS provider (fast mode)")
```

**Testing Strategy**:
- Manual test: Run `manual_test_client.py --tts-provider elevenlabs` with valid API key
- Manual test: Run with `--tts-provider coqui` to verify backward compatibility
- Manual test: Run with invalid API key to verify error handling

---

## Phase 5: Integration Testing

**Goal**: Validate ElevenLabs provider with real API calls (optional, requires API key).

### Task 5.1: Create Integration Test Suite

**New File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/tests/integration/tts/test_elevenlabs_live.py`

**Test Structure**:
```python
"""
Integration tests: Live ElevenLabs API synthesis.

Requirements:
- ElevenLabs API key in ELEVENLABS_API_KEY environment variable
- Tests are marked with @elevenlabs_live
- Skip with: pytest -m "not elevenlabs_live"
"""

import pytest

@pytest.mark.elevenlabs_live
@pytest.mark.skipif(
    not os.getenv("ELEVENLABS_API_KEY"),
    reason="ELEVENLABS_API_KEY not set"
)
class TestElevenLabsLiveAPI:
    """Integration tests with real ElevenLabs API."""

    def test_english_synthesis_produces_audio(self):
        """Test English synthesis with real API."""
        # ... implementation ...

    def test_spanish_synthesis_produces_audio(self):
        """Test Spanish synthesis with real API."""
        # ... implementation ...

    def test_duration_matching_with_real_audio(self):
        """Test duration matching with real ElevenLabs audio."""
        # ... implementation ...

    def test_voice_settings_applied(self):
        """Test custom stability and similarity_boost settings."""
        # ... implementation ...
```

**CI/CD Integration**:
- Mark tests as `@elevenlabs_live` (skipped by default)
- Optional CI job: Run integration tests if `ELEVENLABS_API_KEY` secret is set
- Local testing: Developers can run with own API key

---

## Phase 6: Documentation & Deployment

**Goal**: Document ElevenLabs provider usage and deployment requirements.

### Task 6.1: Update STS Service README

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/README.md`

**Add Section**:
```markdown
## TTS Providers

### Coqui TTS (Default)

Local TTS synthesis using Coqui XTTS-v2 or VITS models.

**Pros**:
- Low latency (no network calls)
- No API costs
- Full offline capability

**Cons**:
- Lower quality than cloud TTS
- Requires GPU for best performance
- Model download required (~2GB)

### ElevenLabs TTS

Cloud-based TTS using ElevenLabs API.

**Pros**:
- High-quality synthesis
- No local GPU required
- Multilingual pre-trained voices

**Cons**:
- Network latency (200-500ms per request)
- API costs (character-based pricing)
- Requires API key

**Setup**:
1. Get API key from https://elevenlabs.io/
2. Set environment variable:
   ```bash
   export ELEVENLABS_API_KEY="your_api_key_here"
   ```
3. Install dependencies:
   ```bash
   pip install elevenlabs>=0.2.0
   ```
4. Use in code:
   ```python
   from sts_service.tts.factory import create_tts_component

   tts = create_tts_component(provider="elevenlabs")
   audio = tts.synthesize(text_asset, target_duration_ms=2000)
   ```

**Configuration**:
```python
voice_profile = VoiceProfile(
    language="en",
    voice_id="21m00Tcm4TlvDq8ikWAM",  # Optional: explicit voice ID
    elevenlabs_model_id="eleven_flash_v2_5",  # Optional: model override
    stability=0.5,  # Optional: 0.0-1.0
    similarity_boost=0.75,  # Optional: 0.0-1.0
)
```
```

---

### Task 6.2: Update Dependencies

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/requirements.txt`

**Add**:
```
elevenlabs>=0.2.0
```

**File**: `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/sts-service/pyproject.toml`

**Add to dependencies**:
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "elevenlabs>=0.2.0",
]

[project.optional-dependencies]
dev = [
    # ... existing dev dependencies ...
]
```

---

## Acceptance Criteria

**User Story 1 - Basic ElevenLabs TTS Synthesis (P1)**:
- [ ] ElevenLabsTTSComponent implements BaseTTSComponent
- [ ] Factory creates ElevenLabs provider when `provider="elevenlabs"`
- [ ] Component reports `is_ready=True` with valid API key
- [ ] Component reports `is_ready=False` with missing/invalid API key
- [ ] English text produces valid AudioAsset via mocked API (unit test)
- [ ] Real API call produces valid audio when API key available (integration test)

**User Story 2 - Voice Selection and Language Support (P2)**:
- [ ] Explicit `voice_id` overrides language-based defaults
- [ ] Language-based defaults work for supported languages (en, es, fr, de, it, pt, ja)
- [ ] Unsupported languages fall back to English (Rachel) with warning
- [ ] Voice selection logic tested with 100% coverage

**User Story 3 - Error Handling and Rate Limiting (P3)**:
- [ ] 429 errors map to TIMEOUT with `retryable=True`
- [ ] 401/403 errors map to INVALID_INPUT with `retryable=False`
- [ ] 500/502/503 errors map to UNKNOWN with `retryable=True`
- [ ] 400 errors map to INVALID_INPUT with `retryable=False`
- [ ] Network timeouts map to TIMEOUT with `retryable=True`

**User Story 4 - Configuration and Provider Selection (P4)**:
- [ ] Factory creates ElevenLabs component when `provider="elevenlabs"`
- [ ] ElevenLabs-specific config (model_id, stability, similarity_boost) passed through
- [ ] manual_test_client.py supports `--tts-provider elevenlabs` flag

**User Story 5 - Quality and Performance Settings (P5)**:
- [ ] Custom `model_id` overrides default `eleven_flash_v2_5`
- [ ] Stability and similarity_boost settings passed to API
- [ ] Different models produce valid audio output

**General Requirements**:
- [ ] All unit tests pass (80% minimum coverage)
- [ ] Contract tests validate AudioAsset schema compatibility
- [ ] Integration tests pass when API key available
- [ ] Duration matching works identically to Coqui provider
- [ ] No automatic fallback to Coqui (errors propagate)
- [ ] Manual test client supports both providers

---

## Dependencies & Risks

### External Dependencies

**ElevenLabs API**:
- **Dependency**: ElevenLabs API availability and stability
- **Risk**: API downtime breaks ElevenLabs provider
- **Mitigation**: Errors propagate as retryable; orchestrator can switch to Coqui

**Python Packages**:
- `elevenlabs>=0.2.0` - Official ElevenLabs client
- `pydub` - Audio format conversion (already present)
- `ffmpeg` - Pydub backend (already present)
- `rubberband` - Duration matching (already present)

**Voice IDs**:
- **Dependency**: ElevenLabs voice IDs remain stable
- **Risk**: Voice ID changes break default mappings
- **Mitigation**: Explicit voice_id configuration overrides defaults

### Technical Risks

**Rate Limiting**:
- **Risk**: API rate limits impact throughput for high-volume streams
- **Mitigation**: Errors marked as retryable; orchestrator implements backoff

**Network Latency**:
- **Risk**: API calls add 200-500ms latency per fragment
- **Impact**: May increase end-to-end dubbing latency by 1-2 seconds
- **Mitigation**: Use fast model (`eleven_flash_v2_5`) by default

**Audio Format Conversion**:
- **Risk**: MP3 → PCM conversion adds processing overhead
- **Mitigation**: Pydub conversion is fast (<50ms for 6s audio)

---

## Constitution Compliance

### Principle I: Real-Time First
- **Compliance**: ✅ Synchronous API calls complete within timeout (5s default)
- **Latency Impact**: Adds 200-500ms API latency + 50ms format conversion
- **Justification**: Acceptable for 6s fragment windows; quality tradeoff

### Principle II: Testability Through Isolation
- **Compliance**: ✅ Unit tests mock ElevenLabs API; no live endpoints required
- **Testing Strategy**: Mock-based unit tests + optional integration tests with real API

### Principle III: Spec-Driven Development
- **Compliance**: ✅ Spec created before implementation (specs/022-elevenlabs-tts-provider/spec.md)
- **Implementation**: Plan follows spec requirements exactly

### Principle IV: Observability & Debuggability
- **Compliance**: ✅ Structured logging for API calls, errors, and duration matching
- **Metrics**: API call duration, model used, voice ID recorded in AudioAsset metadata

### Principle V: Graceful Degradation
- **Compliance**: ✅ Errors propagate with retryability flags; no automatic fallback
- **Orchestrator Responsibility**: Pipeline can switch to Coqui on repeated failures

### Principle VI: A/V Sync Discipline
- **Compliance**: ✅ Duration matching uses same rubberband logic as Coqui
- **Timestamp Preservation**: No timestamp manipulation; duration matching only

### Principle VII: Incremental Delivery
- **Compliance**: ✅ Milestone-based delivery:
  - Milestone 1: Basic synthesis (P1)
  - Milestone 2: Voice selection (P2)
  - Milestone 3: Error handling (P3)
  - Milestone 4: Configuration (P4)
  - Milestone 5: Quality settings (P5)

### Principle VIII: Test-First Development
- **Compliance**: ✅ TDD enforced
- **Test Coverage**: 80% minimum for new code, 95% for critical paths
- **Test Strategy**: Unit tests written BEFORE implementation; mock-based

---

## Complexity Tracking

### New Components Added

**Files Created** (5):
1. `apps/sts-service/src/sts_service/tts/elevenlabs_provider.py` - Main provider implementation (~400 lines)
2. `apps/sts-service/src/sts_service/tts/duration_matching.py` - Shared duration matching utility (~150 lines)
3. `apps/sts-service/tests/unit/tts/test_elevenlabs_provider.py` - Unit tests (~600 lines)
4. `apps/sts-service/tests/contract/tts/test_elevenlabs_schema.py` - Contract tests (~100 lines)
5. `apps/sts-service/tests/integration/tts/test_elevenlabs_live.py` - Integration tests (~300 lines)

**Files Modified** (3):
1. `apps/sts-service/src/sts_service/tts/models.py` - Add ElevenLabs fields to VoiceProfile (~20 lines)
2. `apps/sts-service/src/sts_service/tts/factory.py` - Add ElevenLabs case (~10 lines)
3. `apps/sts-service/manual_test_client.py` - Add --tts-provider flag (~15 lines)

**Total LOC Added**: ~1,595 lines (implementation + tests)
**Complexity Score**: Medium (extends existing pattern, no new architectural components)

### Justification

**Why Add ElevenLabs Provider?**:
- User requirement: High-quality TTS for production streams
- Existing pattern: Follows established TTS provider architecture (same as Coqui, mock providers)
- No duplication: Reuses existing interfaces, error types, duration matching

**Complexity Mitigation**:
- Conforms to `TTSComponent` protocol (no interface changes)
- Shares duration matching logic with Coqui (extracted to utility)
- Factory pattern isolates provider selection logic

---

## Future Considerations

**Streaming API Support**:
- **Current**: Synchronous API (complete audio returned in one response)
- **Future**: ElevenLabs streaming API for lower latency
- **Impact**: Requires async/await pattern; interface remains compatible

**Voice Cloning**:
- **Current**: Pre-trained voices only
- **Future**: ElevenLabs voice cloning via API (upload voice sample, get voice_id)
- **Impact**: Add voice cloning workflow; no interface changes

**Cost Optimization**:
- **Current**: No cost tracking or limits
- **Future**: Character count tracking, cost estimation, per-stream budgets
- **Impact**: Add metrics; orchestrator enforces limits

**Caching**:
- **Current**: No caching (every fragment calls API)
- **Future**: Cache identical text+voice combinations
- **Impact**: Add cache layer; reduces API costs for repeated phrases

---

## Success Metrics

**Functional Metrics**:
- [ ] All P1-P5 user stories pass acceptance tests
- [ ] Unit test coverage ≥ 80% for new code
- [ ] Integration tests pass with real API (when API key available)
- [ ] Manual test client works with both Coqui and ElevenLabs

**Performance Metrics**:
- [ ] ElevenLabs API calls complete within 5s timeout (95th percentile)
- [ ] Audio format conversion adds <100ms overhead
- [ ] Duration matching works identically to Coqui (same rubberband results)

**Quality Metrics**:
- [ ] Error classification correctly identifies retryable vs non-retryable (100% accuracy in tests)
- [ ] No automatic fallback to Coqui (errors propagate to orchestrator)
- [ ] AudioAsset schema matches Coqui provider (contract tests pass)

---

## Rollout Plan

### Phase 1: Development & Testing (Week 1)
- Implement ElevenLabsTTSComponent with mocked API
- Write and pass all unit tests
- Write and pass contract tests
- Extract duration matching to shared utility
- Refactor Coqui provider to use shared utility

### Phase 2: Integration Testing (Week 2)
- Test with real ElevenLabs API (manual testing)
- Run integration test suite with API key
- Validate error handling with intentional failures
- Test manual_test_client.py with both providers

### Phase 3: Documentation & Deployment (Week 3)
- Update README with ElevenLabs setup instructions
- Add API key setup guide
- Document cost considerations
- Merge to main branch

### Phase 4: Production Rollout (Week 4)
- Deploy to staging environment
- Test with real streams (A/B test Coqui vs ElevenLabs)
- Monitor API latency and error rates
- Gradual rollout to production streams

---

## Version History

- **v1.0.0** (2026-01-03): Initial plan created
