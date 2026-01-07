"""
ElevenLabs TTS Provider Implementation.

Implements the TTSComponent interface using the ElevenLabs API.
Provides cloud-based high-quality text-to-speech synthesis.

Features:
- Multiple language support with language-specific default voices
- ElevenLabs Flash v2.5 model for low latency (default)
- Voice settings customization (stability, similarity_boost)
- Duration matching with rubberband time-stretch
- Automatic audio format conversion (MP3 -> PCM F32LE)
- Error classification for retry logic

Based on specs/022-elevenlabs-tts-provider/spec.md.
"""

import io
import logging
import os
import struct
from datetime import datetime

from pydub import AudioSegment

from sts_service.translation.models import TextAsset

from .duration_matching import align_audio_to_duration
from .errors import TTSError, TTSErrorType, classify_error
from .interface import BaseTTSComponent
from .models import (
    AudioAsset,
    AudioFormat,
    AudioStatus,
    TTSConfig,
    VoiceProfile,
)

logger = logging.getLogger(__name__)

# ElevenLabs API client - imported lazily to handle missing package
try:
    from elevenlabs import VoiceSettings
    from elevenlabs.client import ElevenLabs

    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None
    VoiceSettings = None

# ============================================================================
# Constants
# ============================================================================

# Default ElevenLabs model (Flash v2.5 for low latency)
DEFAULT_MODEL_ID = "eleven_flash_v2_5"

# Default voice mappings by language (FR-008)
# Voice IDs are from ElevenLabs voice library
DEFAULT_VOICES: dict[str, str] = {
    "en": "21m00Tcm4TlvDq8ikWAM",  # Rachel (English)
    "es": "ThT5KcBeYPX3keUQqHPh",  # Diego (Spanish)
    "fr": "N2lVS1w4EtoT3dr4eOWO",  # Thomas (French)
    "de": "pFZP5JQG7iQjIQuC4Bku",  # Sarah (German)
    "it": "onwK4e9ZLuTAKqWW03F9",  # Giovanni (Italian)
    "pt": "cjVigY5qzO86Huf0OWal",  # Domi (Portuguese)
    "ja": "EXAVITQu4vr4xnSDxMaL",  # Hiro (Japanese)
    "zh": "iP95p4xoKVk53GoZ742B",  # Chinese - multilingual
}

# Fallback voice when language not in mapping
FALLBACK_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel (English)


class ElevenLabsTTSComponent(BaseTTSComponent):
    """ElevenLabs TTS component implementing the TTSComponent interface.

    This implementation uses the ElevenLabs API for cloud-based text-to-speech
    synthesis with high-quality voices and low latency.

    Features:
    - Multilingual synthesis with language-specific default voices
    - ElevenLabs Flash v2.5 model for real-time dubbing
    - Voice settings customization (stability, similarity_boost)
    - Duration matching with rubberband time-stretch
    - MP3 to PCM F32LE format conversion
    - Automatic sample rate and channel conversion
    - Error classification for retry logic

    Environment Variables:
    - ELEVENLABS_API_KEY: Required. API key for ElevenLabs service.
    """

    def __init__(
        self,
        config: TTSConfig | None = None,
        api_key: str | None = None,
        model_id: str | None = None,
    ):
        """Initialize ElevenLabsTTSComponent.

        Args:
            config: TTS configuration
            api_key: Optional API key (defaults to ELEVENLABS_API_KEY env var)
            model_id: Optional model ID (defaults to eleven_flash_v2_5)
        """
        self._config = config or TTSConfig()
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self._model_id = model_id or DEFAULT_MODEL_ID
        self._is_ready = self._validate_api_key()

        if not ELEVENLABS_AVAILABLE:
            logger.warning("ElevenLabs library not available. Install with: pip install elevenlabs")
            self._is_ready = False

    def _validate_api_key(self) -> bool:
        """Validate that API key is present.

        Returns:
            True if API key is valid, False otherwise
        """
        if not self._api_key:
            logger.warning("ELEVENLABS_API_KEY not set. ElevenLabs provider will not be ready.")
            return False

        if len(self._api_key) < 10:
            logger.warning("ELEVENLABS_API_KEY appears invalid (too short).")
            return False

        return True

    @property
    def component_instance(self) -> str:
        """Return the provider identifier."""
        return f"elevenlabs-{self._model_id}"

    @property
    def is_ready(self) -> bool:
        """Check if component is ready."""
        return self._is_ready

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Synthesize speech audio from translated text.

        Args:
            text_asset: Input TextAsset from Translation module
            target_duration_ms: Target duration for duration matching
            output_sample_rate_hz: Output sample rate
            output_channels: Number of output channels
            voice_profile: Voice configuration

        Returns:
            AudioAsset with synthesized speech audio
        """
        start_time = datetime.utcnow()

        # Input validation
        text = text_asset.translated_text.strip()
        if not text:
            error = classify_error(
                TTSErrorType.INVALID_INPUT,
                "Empty text input - cannot synthesize empty text",
            )
            return self._create_failed_asset(
                text_asset, output_sample_rate_hz, output_channels, [error], start_time
            )

        # Use voice profile or create default
        if voice_profile is None:
            voice_profile = VoiceProfile(language=text_asset.target_language)

        # Preprocess text
        preprocessed_text = self._preprocess_text(text)

        try:
            # Get voice ID and model
            voice_id = self._get_voice_id(voice_profile)
            model_id = voice_profile.elevenlabs_model_id or self._model_id

            # Call ElevenLabs API
            mp3_bytes = self._call_elevenlabs_api(
                text=preprocessed_text,
                voice_id=voice_id,
                model_id=model_id,
                voice_profile=voice_profile,
            )

            # Convert MP3 to PCM F32LE
            audio_data, synthesis_sample_rate = self._convert_audio_format(mp3_bytes)

            # Calculate baseline duration
            bytes_per_sample = 4  # 4 bytes per float32
            num_samples = len(audio_data) // bytes_per_sample
            baseline_duration_ms = (
                int(num_samples * 1000 / synthesis_sample_rate) if num_samples > 0 else 0
            )

            # Apply duration matching if target specified
            final_audio_data = audio_data
            final_duration_ms = baseline_duration_ms
            speed_factor_applied = None
            speed_factor_clamped = False
            status = AudioStatus.SUCCESS
            errors: list[TTSError] = []

            if target_duration_ms is not None and baseline_duration_ms > 0:
                try:
                    alignment_result = align_audio_to_duration(
                        audio_data=audio_data,
                        baseline_duration_ms=baseline_duration_ms,
                        target_duration_ms=target_duration_ms,
                        input_sample_rate_hz=synthesis_sample_rate,
                        output_sample_rate_hz=output_sample_rate_hz,
                        input_channels=1,  # ElevenLabs returns mono
                        output_channels=output_channels,
                        clamp_min=voice_profile.speed_clamp_min,
                        clamp_max=voice_profile.speed_clamp_max,
                        only_speed_up=voice_profile.only_speed_up,
                    )
                    final_audio_data = alignment_result.audio_data
                    final_duration_ms = alignment_result.final_duration_ms
                    speed_factor_applied = alignment_result.speed_factor_applied
                    speed_factor_clamped = alignment_result.speed_factor_clamped

                    if speed_factor_clamped:
                        status = AudioStatus.PARTIAL
                        errors.append(
                            classify_error(
                                TTSErrorType.ALIGNMENT_FAILED,
                                f"Speed factor clamped: {speed_factor_applied:.2f}",
                                retryable_override=False,
                            )
                        )
                except Exception as e:
                    logger.warning(f"Duration matching failed: {e}")
                    # Continue with original audio
                    status = AudioStatus.PARTIAL
                    errors.append(
                        classify_error(
                            TTSErrorType.ALIGNMENT_FAILED,
                            f"Duration matching failed: {str(e)}",
                            retryable_override=False,
                        )
                    )
            else:
                # No duration matching - just convert sample rate and channels
                if synthesis_sample_rate != output_sample_rate_hz or output_channels != 1:
                    alignment_result = align_audio_to_duration(
                        audio_data=audio_data,
                        baseline_duration_ms=baseline_duration_ms,
                        target_duration_ms=baseline_duration_ms,  # Same duration
                        input_sample_rate_hz=synthesis_sample_rate,
                        output_sample_rate_hz=output_sample_rate_hz,
                        input_channels=1,
                        output_channels=output_channels,
                        clamp_min=voice_profile.speed_clamp_min,
                        clamp_max=voice_profile.speed_clamp_max,
                        only_speed_up=voice_profile.only_speed_up,
                    )
                    final_audio_data = alignment_result.audio_data
                    final_duration_ms = alignment_result.final_duration_ms

            # Create payload reference
            payload_ref = f"mem://fragments/{text_asset.stream_id}/{text_asset.sequence_number}"

            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            return AudioAsset(
                stream_id=text_asset.stream_id,
                sequence_number=text_asset.sequence_number,
                parent_asset_ids=[text_asset.asset_id],
                component_instance=self.component_instance,
                audio_format=AudioFormat.PCM_F32LE,
                sample_rate_hz=output_sample_rate_hz,
                channels=output_channels,
                duration_ms=final_duration_ms,
                payload_ref=payload_ref,
                audio_bytes=final_audio_data,
                language=text_asset.target_language,
                status=status,
                errors=errors,
                processing_time_ms=processing_time_ms,
                voice_cloning_used=False,
                preprocessed_text=preprocessed_text,
            )

        except Exception as e:
            logger.exception(f"ElevenLabs synthesis failed: {e}")
            error = self._classify_api_error(e)
            return self._create_failed_asset(
                text_asset, output_sample_rate_hz, output_channels, [error], start_time
            )

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for TTS synthesis.

        Same preprocessing as Coqui for consistency.

        Args:
            text: Raw text to preprocess

        Returns:
            Preprocessed text
        """
        return text.strip()

    def _get_voice_id(self, voice_profile: VoiceProfile) -> str:
        """Get the voice ID to use for synthesis.

        Priority:
        1. Explicit voice_id in voice_profile
        2. Language-based default from DEFAULT_VOICES
        3. Fallback to English (Rachel)

        Args:
            voice_profile: Voice configuration

        Returns:
            ElevenLabs voice ID
        """
        # Priority 1: Explicit voice_id
        if voice_profile.voice_id:
            return voice_profile.voice_id

        # Priority 2: Language-based default
        language = voice_profile.language.lower()
        if language in DEFAULT_VOICES:
            return DEFAULT_VOICES[language]

        # Priority 3: Fallback to English with warning
        logger.warning(
            f"No default voice for language '{language}'. Falling back to English (Rachel)."
        )
        return FALLBACK_VOICE

    def _call_elevenlabs_api(
        self,
        text: str,
        voice_id: str,
        model_id: str,
        voice_profile: VoiceProfile,
    ) -> bytes:
        """Call ElevenLabs API to synthesize audio.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            model_id: ElevenLabs model ID
            voice_profile: Voice settings

        Returns:
            MP3 audio bytes

        Raises:
            Exception: If API call fails
        """
        if not ELEVENLABS_AVAILABLE:
            raise RuntimeError("ElevenLabs library not available")

        # Create ElevenLabs client with API key
        client = ElevenLabs(api_key=self._api_key)

        # Build voice settings if specified
        voice_settings = None
        if voice_profile.stability is not None or voice_profile.similarity_boost is not None:
            voice_settings = VoiceSettings(
                stability=voice_profile.stability or 0.5,
                similarity_boost=voice_profile.similarity_boost or 0.75,
            )

        # Call text_to_speech.convert (v2 API)
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )

        # Collect all audio chunks from generator
        audio = b"".join(audio_generator)

        return audio

    def _convert_audio_format(self, mp3_bytes: bytes) -> tuple[bytes, int]:
        """Convert MP3 bytes to PCM F32LE.

        Args:
            mp3_bytes: MP3 audio bytes from ElevenLabs

        Returns:
            Tuple of (PCM F32LE bytes, sample_rate_hz)
        """
        # Load MP3 with pydub
        audio_segment = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))

        # Get sample rate
        sample_rate = audio_segment.frame_rate

        # Convert to mono if stereo
        if audio_segment.channels > 1:
            audio_segment = audio_segment.set_channels(1)

        # Get raw samples as 16-bit PCM
        raw_samples = audio_segment.raw_data

        # Convert 16-bit PCM to 32-bit float
        # Assuming 16-bit signed little-endian
        num_samples = len(raw_samples) // 2
        samples_16bit = struct.unpack(f"<{num_samples}h", raw_samples)

        # Normalize to float [-1.0, 1.0]
        samples_float = [s / 32768.0 for s in samples_16bit]

        # Pack as 32-bit float
        pcm_f32le = struct.pack(f"<{len(samples_float)}f", *samples_float)

        return pcm_f32le, sample_rate

    def _classify_api_error(self, error: Exception) -> TTSError:
        """Classify ElevenLabs API error to TTSError.

        Maps HTTP status codes and error types to appropriate
        TTSErrorType with correct retryability.

        Args:
            error: Exception from API call

        Returns:
            TTSError with proper classification
        """
        error_str = str(error).lower()

        # Network/timeout errors (retryable)
        if isinstance(error, (TimeoutError, ConnectionError)):
            return classify_error(
                TTSErrorType.TIMEOUT,
                f"ElevenLabs API timeout: {str(error)}",
                details={"exception_type": type(error).__name__},
                retryable_override=True,
            )

        # Rate limit (429) - retryable
        if "rate limit" in error_str or "429" in error_str:
            return classify_error(
                TTSErrorType.TIMEOUT,
                f"ElevenLabs rate limit exceeded: {str(error)}",
                details={"exception_type": type(error).__name__},
                retryable_override=True,
            )

        # Authentication errors (401/403) - not retryable
        if (
            "unauthorized" in error_str
            or "invalid api key" in error_str
            or "401" in error_str
            or "403" in error_str
        ):
            return classify_error(
                TTSErrorType.INVALID_INPUT,
                f"ElevenLabs authentication failed: {str(error)}",
                details={"exception_type": type(error).__name__},
                retryable_override=False,
            )

        # Bad request (400) - not retryable
        if "bad request" in error_str or "invalid" in error_str or "400" in error_str:
            return classify_error(
                TTSErrorType.INVALID_INPUT,
                f"ElevenLabs bad request: {str(error)}",
                details={"exception_type": type(error).__name__},
                retryable_override=False,
            )

        # Server errors (5xx) - retryable
        if (
            "internal server error" in error_str
            or "500" in error_str
            or "502" in error_str
            or "503" in error_str
        ):
            return classify_error(
                TTSErrorType.UNKNOWN,
                f"ElevenLabs server error: {str(error)}",
                details={"exception_type": type(error).__name__},
                retryable_override=True,
            )

        # Default: unknown error (retryable for safety)
        return classify_error(
            TTSErrorType.SYNTHESIS_FAILED,
            f"ElevenLabs synthesis failed: {str(error)}",
            details={"exception_type": type(error).__name__},
            retryable_override=True,
        )

    def _create_failed_asset(
        self,
        text_asset: TextAsset,
        sample_rate_hz: int,
        channels: int,
        errors: list[TTSError],
        start_time: datetime,
    ) -> AudioAsset:
        """Create a failed AudioAsset.

        Args:
            text_asset: Input text asset
            sample_rate_hz: Requested sample rate
            channels: Requested channels
            errors: List of errors
            start_time: Processing start time

        Returns:
            AudioAsset with FAILED status
        """
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return AudioAsset(
            stream_id=text_asset.stream_id,
            sequence_number=text_asset.sequence_number,
            parent_asset_ids=[text_asset.asset_id],
            component_instance=self.component_instance,
            audio_format=AudioFormat.PCM_F32LE,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            duration_ms=0,
            payload_ref="",
            language=text_asset.target_language,
            status=AudioStatus.FAILED,
            errors=errors,
            processing_time_ms=processing_time_ms,
            voice_cloning_used=False,
            preprocessed_text=text_asset.translated_text,
        )

    def shutdown(self) -> None:
        """Release resources."""
        self._is_ready = False
        logger.info("ElevenLabsTTSComponent shutdown complete")
