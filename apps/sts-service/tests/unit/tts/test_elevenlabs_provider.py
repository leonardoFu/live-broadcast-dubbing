"""
Unit tests for ElevenLabs TTS Provider.

Following TDD: These tests are written FIRST and MUST FAIL before implementation.
Tests use mocked ElevenLabs API to avoid external dependencies.

Coverage Target: 95% (critical path for cloud TTS integration).
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from sts_service.translation.models import TextAsset, TranslationStatus
from sts_service.tts.errors import TTSErrorType
from sts_service.tts.models import AudioAsset, AudioFormat, AudioStatus, TTSConfig, VoiceProfile

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_elevenlabs_api():
    """Mock the ElevenLabs API client (v2 API)."""
    # We need to patch both the ElevenLabs class AND the ELEVENLABS_AVAILABLE flag
    with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
        with patch("sts_service.tts.elevenlabs_provider.ElevenLabs") as mock_client_class:
            # Create mock client instance
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Return fake MP3 bytes (minimal valid MP3 header + silence)
            # This is a simplified mock - real MP3 is more complex
            fake_mp3 = b"\xff\xfb\x90\x00" + b"\x00" * 1000

            # Mock text_to_speech.convert to return a generator
            mock_client.text_to_speech.convert.return_value = iter([fake_mp3])

            # Also mock VoiceSettings
            with patch("sts_service.tts.elevenlabs_provider.VoiceSettings") as mock_voice_settings:
                mock_voice_settings.return_value = MagicMock(stability=0.5, similarity_boost=0.75)
                yield mock_client


@pytest.fixture
def mock_audio_segment():
    """Mock pydub AudioSegment for audio conversion."""
    with patch("sts_service.tts.elevenlabs_provider.AudioSegment") as mock_segment_class:
        mock_audio = MagicMock()
        mock_audio.frame_rate = 22050  # ElevenLabs default
        mock_audio.channels = 1
        mock_audio.sample_width = 2  # 16-bit
        mock_audio.duration_seconds = 1.0
        # Mock raw_data as PCM bytes (1 second of silence at 22050 Hz mono)
        mock_audio.raw_data = b"\x00" * (22050 * 4)  # 4 bytes per sample (float32)
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_sample_width.return_value = mock_audio
        mock_segment_class.from_mp3.return_value = mock_audio
        mock_segment_class.from_file.return_value = mock_audio
        yield mock_segment_class


@pytest.fixture
def sample_text_asset():
    """Create a sample TextAsset for testing."""
    return TextAsset(
        stream_id="test-stream-123",
        sequence_number=42,
        asset_id="text-uuid-456",
        parent_asset_ids=["audio-uuid-123"],
        component_instance="mock-translation-v1",
        status=TranslationStatus.SUCCESS,
        source_language="en",
        target_language="ja",
        translated_text="こんにちは世界、これはテストです。",
    )


@pytest.fixture
def default_tts_config():
    """Create a default TTSConfig."""
    return TTSConfig(
        output_sample_rate_hz=16000,
        output_channels=1,
        timeout_ms=5000,
    )


@pytest.fixture
def elevenlabs_voice_profile():
    """Create a VoiceProfile with ElevenLabs settings."""
    return VoiceProfile(
        language="ja",
        voice_id="EXAVITQu4vr4xnSDxMaL",  # Hiro (Japanese)
        elevenlabs_model_id="eleven_flash_v2_5",
        stability=0.5,
        similarity_boost=0.75,
    )


# ============================================================================
# T004: Basic Synthesis Tests
# ============================================================================


class TestElevenLabsBasicSynthesis:
    """Tests for basic ElevenLabs synthesis functionality."""

    def test_elevenlabs_basic_synthesis(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test that basic synthesis returns a valid AudioAsset via mocked API."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                output_sample_rate_hz=16000,
                output_channels=1,
            )

        # Verify AudioAsset is returned with correct structure
        assert isinstance(result, AudioAsset)
        assert result.stream_id == sample_text_asset.stream_id
        assert result.sequence_number == sample_text_asset.sequence_number
        assert result.parent_asset_ids == [sample_text_asset.asset_id]
        assert result.language == sample_text_asset.target_language
        assert result.status == AudioStatus.SUCCESS
        assert result.audio_format == AudioFormat.PCM_F32LE
        assert result.sample_rate_hz == 16000
        assert result.channels == 1
        assert result.duration_ms > 0
        assert len(result.audio_bytes) > 0

    def test_elevenlabs_component_instance(self, default_tts_config):
        """Test that component_instance is formatted as 'elevenlabs-{model_id}'."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            # Default model is eleven_flash_v2_5
            assert component.component_instance == "elevenlabs-eleven_flash_v2_5"

    def test_elevenlabs_is_ready_with_api_key(self, default_tts_config):
        """Test that is_ready=True when API key is valid."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key-valid"}):
                component = ElevenLabsTTSComponent(config=default_tts_config)
                assert component.is_ready is True

    def test_elevenlabs_is_ready_without_api_key(self, default_tts_config):
        """Test that is_ready=False when API key is missing."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        # Ensure ELEVENLABS_API_KEY is not set
        env = os.environ.copy()
        env.pop("ELEVENLABS_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            assert component.is_ready is False

    def test_elevenlabs_audio_format_conversion(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test MP3 to PCM F32LE conversion."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                output_sample_rate_hz=16000,
                output_channels=1,
            )

        # Verify output format is PCM F32LE
        assert result.audio_format == AudioFormat.PCM_F32LE
        # Verify audio bytes are present
        assert len(result.audio_bytes) > 0

    def test_elevenlabs_sample_rate_conversion(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test resampling to target sample rate."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                output_sample_rate_hz=48000,  # Different from ElevenLabs default
                output_channels=1,
            )

        # Verify sample rate in result
        assert result.sample_rate_hz == 48000

    def test_elevenlabs_mono_to_stereo_conversion(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test channel conversion when output_channels=2."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                output_sample_rate_hz=16000,
                output_channels=2,  # Request stereo
            )

        # Verify channels in result
        assert result.channels == 2


# ============================================================================
# T005: Voice Selection Tests
# ============================================================================


class TestElevenLabsVoiceSelection:
    """Tests for voice ID selection logic."""

    def test_elevenlabs_voice_id_explicit(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test that explicit voice_id overrides language default."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        explicit_voice_profile = VoiceProfile(
            language="en",  # English language
            voice_id="ThT5KcBeYPX3keUQqHPh",  # But use Diego (Spanish voice)
        )

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                voice_profile=explicit_voice_profile,
            )

        # Verify API was called with explicit voice_id
        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("voice_id") == "ThT5KcBeYPX3keUQqHPh"

    def test_elevenlabs_voice_id_language_default_english(
        self, mock_elevenlabs_api, mock_audio_segment, default_tts_config
    ):
        """Test English default voice (Adam)."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        text_asset = TextAsset(
            stream_id="test",
            sequence_number=0,
            asset_id="text-123",
            parent_asset_ids=[],
            component_instance="mock-translation-v1",
            status=TranslationStatus.SUCCESS,
            source_language="en",
            target_language="en",
            translated_text="Hello",
        )
        voice_profile = VoiceProfile(language="en")

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(text_asset=text_asset, voice_profile=voice_profile)

        # Adam voice ID
        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("voice_id") == "QIhD5ivPGEoYZQDocuHI"

    def test_elevenlabs_voice_id_language_default_spanish(
        self, mock_elevenlabs_api, mock_audio_segment, default_tts_config
    ):
        """Test Spanish default voice (Diego)."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        text_asset = TextAsset(
            stream_id="test",
            sequence_number=0,
            asset_id="text-123",
            parent_asset_ids=[],
            component_instance="mock-translation-v1",
            status=TranslationStatus.SUCCESS,
            source_language="en",
            target_language="es",
            translated_text="Hola",
        )
        voice_profile = VoiceProfile(language="es")

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(text_asset=text_asset, voice_profile=voice_profile)

        # Diego voice ID
        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("voice_id") == "ThT5KcBeYPX3keUQqHPh"

    def test_elevenlabs_voice_id_language_default_japanese(
        self, mock_elevenlabs_api, mock_audio_segment, default_tts_config
    ):
        """Test Japanese default voice (Hiro)."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        text_asset = TextAsset(
            stream_id="test",
            sequence_number=0,
            asset_id="text-123",
            parent_asset_ids=[],
            component_instance="mock-translation-v1",
            status=TranslationStatus.SUCCESS,
            source_language="en",
            target_language="ja",
            translated_text="こんにちは",
        )
        voice_profile = VoiceProfile(language="ja")

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(text_asset=text_asset, voice_profile=voice_profile)

        # Hiro voice ID
        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("voice_id") == "EXAVITQu4vr4xnSDxMaL"

    def test_elevenlabs_voice_id_chinese_uses_lily(
        self, mock_elevenlabs_api, mock_audio_segment, default_tts_config
    ):
        """Test Chinese language uses Lily voice."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        text_asset = TextAsset(
            stream_id="test",
            sequence_number=0,
            asset_id="text-123",
            parent_asset_ids=[],
            component_instance="mock-translation-v1",
            status=TranslationStatus.SUCCESS,
            source_language="en",
            target_language="zh",
            translated_text="你好",
        )
        voice_profile = VoiceProfile(language="zh")

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(text_asset=text_asset, voice_profile=voice_profile)

        # Should use Lily (Chinese) voice
        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("voice_id") == "Xb7hH8MSUJpSbSDYk0k2"

    def test_elevenlabs_voice_id_unsupported_language_fallback(
        self, mock_elevenlabs_api, mock_audio_segment, default_tts_config
    ):
        """Test unsupported language falls back to English (Adam) with warning."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        text_asset = TextAsset(
            stream_id="test",
            sequence_number=0,
            asset_id="text-123",
            parent_asset_ids=[],
            component_instance="mock-translation-v1",
            status=TranslationStatus.SUCCESS,
            source_language="en",
            target_language="ko",  # Korean - not in default mapping
            translated_text="안녕하세요",
        )
        voice_profile = VoiceProfile(language="ko")

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)

            with patch("sts_service.tts.elevenlabs_provider.logger") as mock_logger:
                component.synthesize(text_asset=text_asset, voice_profile=voice_profile)
                # Should log a warning about fallback
                mock_logger.warning.assert_called()

        # Should fallback to Adam (English)
        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("voice_id") == "QIhD5ivPGEoYZQDocuHI"

    def test_elevenlabs_model_id_default(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test default model is eleven_flash_v2_5."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(text_asset=sample_text_asset)

        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("model_id") == "eleven_flash_v2_5"

    def test_elevenlabs_model_id_custom(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test custom model_id is used when specified."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        voice_profile = VoiceProfile(
            language="en",
            elevenlabs_model_id="eleven_multilingual_v2",
        )

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(text_asset=sample_text_asset, voice_profile=voice_profile)

        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        assert call_args.kwargs.get("model_id") == "eleven_multilingual_v2"

    def test_elevenlabs_voice_settings_applied(
        self,
        mock_elevenlabs_api,
        mock_audio_segment,
        sample_text_asset,
        default_tts_config,
        elevenlabs_voice_profile,
    ):
        """Test stability and similarity_boost are passed to API."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.synthesize(
                text_asset=sample_text_asset, voice_profile=elevenlabs_voice_profile
            )

        mock_elevenlabs_api.text_to_speech.convert.assert_called_once()
        call_args = mock_elevenlabs_api.text_to_speech.convert.call_args
        # Voice settings should be passed
        voice_settings = call_args.kwargs.get("voice_settings")
        assert voice_settings is not None


# ============================================================================
# T006: Error Classification Tests
# ============================================================================


class TestElevenLabsErrorClassification:
    """Tests for API error mapping to TTSError types."""

    def test_elevenlabs_error_401_non_retryable(
        self, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test 401 auth errors are mapped to INVALID_INPUT with retryable=False."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        # Mock API to raise authentication error
        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch("sts_service.tts.elevenlabs_provider.ElevenLabs") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.text_to_speech.convert.side_effect = Exception(
                    "Unauthorized: Invalid API key"
                )

                with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "invalid-key-here"}):
                    component = ElevenLabsTTSComponent(config=default_tts_config)
                    result = component.synthesize(text_asset=sample_text_asset)

        assert result.status == AudioStatus.FAILED
        assert len(result.errors) > 0
        error = result.errors[0]
        assert error.error_type == TTSErrorType.INVALID_INPUT
        assert error.retryable is False

    def test_elevenlabs_error_429_retryable(
        self, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test 429 rate limit errors are mapped to TIMEOUT with retryable=True."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        # Mock API to raise rate limit error
        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch("sts_service.tts.elevenlabs_provider.ElevenLabs") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.text_to_speech.convert.side_effect = Exception("Rate limit exceeded")

                with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-valid"}):
                    component = ElevenLabsTTSComponent(config=default_tts_config)
                    result = component.synthesize(text_asset=sample_text_asset)

        assert result.status == AudioStatus.FAILED
        assert len(result.errors) > 0
        error = result.errors[0]
        # Rate limit errors should be retryable
        assert error.retryable is True

    def test_elevenlabs_error_400_non_retryable(
        self, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test 400 bad request errors are mapped to INVALID_INPUT with retryable=False."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        # Mock API to raise bad request error
        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch("sts_service.tts.elevenlabs_provider.ElevenLabs") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.text_to_speech.convert.side_effect = Exception(
                    "Bad Request: Invalid voice_id"
                )

                with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-valid"}):
                    component = ElevenLabsTTSComponent(config=default_tts_config)
                    result = component.synthesize(text_asset=sample_text_asset)

        assert result.status == AudioStatus.FAILED
        assert len(result.errors) > 0
        error = result.errors[0]
        assert error.error_type == TTSErrorType.INVALID_INPUT
        assert error.retryable is False

    def test_elevenlabs_error_500_retryable(
        self, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test 500 server errors are mapped to UNKNOWN with retryable=True."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        # Mock API to raise server error
        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch("sts_service.tts.elevenlabs_provider.ElevenLabs") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.text_to_speech.convert.side_effect = Exception("Internal Server Error")

                with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-valid"}):
                    component = ElevenLabsTTSComponent(config=default_tts_config)
                    result = component.synthesize(text_asset=sample_text_asset)

        assert result.status == AudioStatus.FAILED
        assert len(result.errors) > 0
        error = result.errors[0]
        # Server errors should be retryable
        assert error.retryable is True

    def test_elevenlabs_error_network_timeout_retryable(
        self, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test network timeout errors are mapped to TIMEOUT with retryable=True."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        # Mock API to raise timeout error
        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch("sts_service.tts.elevenlabs_provider.ElevenLabs") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.text_to_speech.convert.side_effect = TimeoutError(
                    "Connection timed out"
                )

                with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-valid"}):
                    component = ElevenLabsTTSComponent(config=default_tts_config)
                    result = component.synthesize(text_asset=sample_text_asset)

        assert result.status == AudioStatus.FAILED
        assert len(result.errors) > 0
        error = result.errors[0]
        assert error.error_type == TTSErrorType.TIMEOUT
        assert error.retryable is True


# ============================================================================
# T015: Duration Matching Tests
# ============================================================================


class TestElevenLabsDurationMatching:
    """Tests for duration matching integration."""

    def test_elevenlabs_duration_matching_applied(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test that duration matching is applied when target_duration_ms is provided."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                target_duration_ms=2000,  # Request specific duration
            )

        assert result.status in (AudioStatus.SUCCESS, AudioStatus.PARTIAL)
        assert result.duration_ms > 0

    def test_elevenlabs_duration_matching_no_target(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test that no duration matching is applied when target_duration_ms is None."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(
                text_asset=sample_text_asset,
                target_duration_ms=None,  # No duration matching
            )

        assert result.status == AudioStatus.SUCCESS
        assert result.duration_ms > 0


# ============================================================================
# Additional Edge Cases
# ============================================================================


class TestElevenLabsEdgeCases:
    """Tests for edge cases and error handling."""

    def test_elevenlabs_empty_text_returns_error(self, default_tts_config):
        """Test that empty text input returns FAILED status with INVALID_INPUT error."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        text_asset = TextAsset(
            stream_id="test",
            sequence_number=0,
            asset_id="text-123",
            parent_asset_ids=[],
            component_instance="mock-translation-v1",
            status=TranslationStatus.SUCCESS,
            source_language="en",
            target_language="ja",
            translated_text="",  # Empty text
        )

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(text_asset=text_asset)

        assert result.status == AudioStatus.FAILED
        assert len(result.errors) > 0
        assert result.errors[0].error_type == TTSErrorType.INVALID_INPUT

    def test_elevenlabs_lineage_tracking(
        self, mock_elevenlabs_api, mock_audio_segment, sample_text_asset, default_tts_config
    ):
        """Test that parent_asset_ids are tracked correctly."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            result = component.synthesize(text_asset=sample_text_asset)

        # Verify lineage
        assert result.parent_asset_ids == [sample_text_asset.asset_id]
        assert result.stream_id == sample_text_asset.stream_id
        assert result.sequence_number == sample_text_asset.sequence_number

    def test_elevenlabs_component_name(self, default_tts_config):
        """Test that component_name is always 'tts'."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            assert component.component_name == "tts"

    def test_elevenlabs_shutdown(self, default_tts_config):
        """Test that shutdown releases resources without error."""
        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key"}):
            component = ElevenLabsTTSComponent(config=default_tts_config)
            component.shutdown()  # Should not raise

        # After shutdown, is_ready should be False
        assert component.is_ready is False
