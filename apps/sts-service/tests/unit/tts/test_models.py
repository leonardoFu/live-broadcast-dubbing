"""
Unit tests for TTS data models.

Tests for AudioAsset, TTSConfig, VoiceProfile, and TTSMetrics model validation.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 80% minimum.
"""


import pytest
from pydantic import ValidationError
from sts_service.tts.errors import TTSError, TTSErrorType
from sts_service.tts.models import (
    ALLOWED_SAMPLE_RATES,
    AudioAsset,
    AudioFormat,
    AudioStatus,
    TTSConfig,
    TTSMetrics,
    VoiceProfile,
)


class TestAudioFormat:
    """Tests for AudioFormat enum."""

    def test_pcm_f32le_value(self):
        """Test PCM_F32LE has correct value."""
        assert AudioFormat.PCM_F32LE.value == "pcm_f32le"

    def test_pcm_s16le_value(self):
        """Test PCM_S16LE has correct value."""
        assert AudioFormat.PCM_S16LE.value == "pcm_s16le"


class TestAudioStatus:
    """Tests for AudioStatus enum."""

    def test_success_value(self):
        """Test SUCCESS status value."""
        assert AudioStatus.SUCCESS.value == "success"

    def test_partial_value(self):
        """Test PARTIAL status value."""
        assert AudioStatus.PARTIAL.value == "partial"

    def test_failed_value(self):
        """Test FAILED status value."""
        assert AudioStatus.FAILED.value == "failed"


class TestAudioAsset:
    """Tests for AudioAsset model validation."""

    @pytest.fixture
    def valid_audio_asset_data(self):
        """Fixture providing valid AudioAsset data."""
        return {
            "stream_id": "stream-abc",
            "sequence_number": 42,
            "parent_asset_ids": ["text-uuid-123"],
            "component_instance": "coqui-xtts-v2",
            "audio_format": AudioFormat.PCM_F32LE,
            "sample_rate_hz": 16000,
            "channels": 1,
            "duration_ms": 2000,
            "payload_ref": "mem://fragments/stream-abc/42",
            "language": "en",
            "status": AudioStatus.SUCCESS,
        }

    def test_valid_audio_asset_creation(self, valid_audio_asset_data):
        """Test valid AudioAsset creation with required fields."""
        asset = AudioAsset(**valid_audio_asset_data)
        assert asset.stream_id == "stream-abc"
        assert asset.sequence_number == 42
        assert asset.component == "tts"
        assert asset.component_instance == "coqui-xtts-v2"
        assert asset.audio_format == AudioFormat.PCM_F32LE
        assert asset.sample_rate_hz == 16000
        assert asset.channels == 1
        assert asset.duration_ms == 2000
        assert asset.language == "en"
        assert asset.status == AudioStatus.SUCCESS

    def test_sample_rate_validation_valid(self, valid_audio_asset_data):
        """Test sample_rate_hz validation accepts allowed values."""
        for rate in ALLOWED_SAMPLE_RATES:
            data = valid_audio_asset_data.copy()
            data["sample_rate_hz"] = rate
            asset = AudioAsset(**data)
            assert asset.sample_rate_hz == rate

    def test_sample_rate_validation_invalid(self, valid_audio_asset_data):
        """Test sample_rate_hz validation rejects invalid values."""
        data = valid_audio_asset_data.copy()
        data["sample_rate_hz"] = 12345  # Invalid sample rate
        with pytest.raises(ValidationError) as exc_info:
            AudioAsset(**data)
        assert "sample_rate_hz" in str(exc_info.value)

    def test_channels_validation_mono(self, valid_audio_asset_data):
        """Test channels validation accepts mono (1)."""
        data = valid_audio_asset_data.copy()
        data["channels"] = 1
        asset = AudioAsset(**data)
        assert asset.channels == 1

    def test_channels_validation_stereo(self, valid_audio_asset_data):
        """Test channels validation accepts stereo (2)."""
        data = valid_audio_asset_data.copy()
        data["channels"] = 2
        asset = AudioAsset(**data)
        assert asset.channels == 2

    def test_channels_validation_invalid(self, valid_audio_asset_data):
        """Test channels validation rejects invalid values."""
        data = valid_audio_asset_data.copy()
        data["channels"] = 5  # Invalid channel count
        with pytest.raises(ValidationError):
            AudioAsset(**data)

    def test_duration_validation_positive(self, valid_audio_asset_data):
        """Test duration_ms must be >= 0."""
        data = valid_audio_asset_data.copy()
        data["duration_ms"] = 0
        asset = AudioAsset(**data)
        assert asset.duration_ms == 0

    def test_duration_validation_negative(self, valid_audio_asset_data):
        """Test duration_ms rejects negative values."""
        data = valid_audio_asset_data.copy()
        data["duration_ms"] = -100
        with pytest.raises(ValidationError):
            AudioAsset(**data)

    def test_payload_ref_format_mem(self, valid_audio_asset_data):
        """Test payload_ref accepts mem:// format."""
        data = valid_audio_asset_data.copy()
        data["payload_ref"] = "mem://fragments/stream-abc/42"
        asset = AudioAsset(**data)
        assert asset.payload_ref == "mem://fragments/stream-abc/42"

    def test_payload_ref_format_file(self, valid_audio_asset_data):
        """Test payload_ref accepts file:// format."""
        data = valid_audio_asset_data.copy()
        data["payload_ref"] = "file:///tmp/audio.raw"
        asset = AudioAsset(**data)
        assert asset.payload_ref == "file:///tmp/audio.raw"

    def test_parent_asset_ids_linkage(self, valid_audio_asset_data):
        """Test parent_asset_ids linkage to TextAsset."""
        data = valid_audio_asset_data.copy()
        data["parent_asset_ids"] = ["text-uuid-123", "text-uuid-456"]
        asset = AudioAsset(**data)
        assert len(asset.parent_asset_ids) == 2
        assert "text-uuid-123" in asset.parent_asset_ids

    def test_has_errors_property_empty(self, valid_audio_asset_data):
        """Test has_errors returns False when no errors."""
        asset = AudioAsset(**valid_audio_asset_data)
        assert asset.has_errors is False

    def test_has_errors_property_with_errors(self, valid_audio_asset_data):
        """Test has_errors returns True when errors present."""
        data = valid_audio_asset_data.copy()
        data["status"] = AudioStatus.FAILED
        data["errors"] = [
            TTSError(
                error_type=TTSErrorType.SYNTHESIS_FAILED,
                message="Test error",
                retryable=False,
            )
        ]
        asset = AudioAsset(**data)
        assert asset.has_errors is True

    def test_is_retryable_property_failed_retryable(self, valid_audio_asset_data):
        """Test is_retryable returns True for FAILED status with retryable error."""
        data = valid_audio_asset_data.copy()
        data["status"] = AudioStatus.FAILED
        data["errors"] = [
            TTSError(
                error_type=TTSErrorType.MODEL_LOAD_FAILED,
                message="Model not found",
                retryable=True,
            )
        ]
        asset = AudioAsset(**data)
        assert asset.is_retryable is True

    def test_is_retryable_property_failed_not_retryable(self, valid_audio_asset_data):
        """Test is_retryable returns False for FAILED status with non-retryable error."""
        data = valid_audio_asset_data.copy()
        data["status"] = AudioStatus.FAILED
        data["errors"] = [
            TTSError(
                error_type=TTSErrorType.INVALID_INPUT,
                message="Empty text",
                retryable=False,
            )
        ]
        asset = AudioAsset(**data)
        assert asset.is_retryable is False

    def test_is_retryable_property_success(self, valid_audio_asset_data):
        """Test is_retryable returns False for SUCCESS status."""
        asset = AudioAsset(**valid_audio_asset_data)
        assert asset.is_retryable is False

    def test_asset_lineage_tracking(self, valid_audio_asset_data):
        """Test asset lineage tracking with component info."""
        asset = AudioAsset(**valid_audio_asset_data)
        assert asset.component == "tts"
        assert asset.component_instance == "coqui-xtts-v2"
        assert asset.asset_id  # Should have auto-generated UUID
        assert asset.created_at  # Should have auto-generated timestamp


class TestVoiceProfile:
    """Tests for VoiceProfile configuration model."""

    def test_valid_voice_profile_defaults(self):
        """Test VoiceProfile with minimal required fields and defaults."""
        profile = VoiceProfile(language="en")
        assert profile.language == "en"
        assert profile.fast_mode is False
        assert profile.use_voice_cloning is False
        assert profile.speed_clamp_min == 0.5
        assert profile.speed_clamp_max == 2.0
        assert profile.only_speed_up is True

    def test_voice_profile_fast_mode(self):
        """Test VoiceProfile with fast_mode enabled."""
        profile = VoiceProfile(language="en", fast_mode=True)
        assert profile.fast_mode is True

    def test_voice_profile_voice_cloning(self):
        """Test VoiceProfile with voice cloning configuration."""
        profile = VoiceProfile(
            language="en",
            use_voice_cloning=True,
            voice_sample_path="/samples/voice.wav",
        )
        assert profile.use_voice_cloning is True
        assert profile.voice_sample_path == "/samples/voice.wav"

    def test_voice_profile_speaker_name(self):
        """Test VoiceProfile with speaker_name for multi-speaker models."""
        profile = VoiceProfile(language="en", speaker_name="p225")
        assert profile.speaker_name == "p225"

    def test_speed_clamp_validation_valid(self):
        """Test speed_clamp_max must be greater than speed_clamp_min."""
        profile = VoiceProfile(
            language="en", speed_clamp_min=0.8, speed_clamp_max=1.5
        )
        assert profile.speed_clamp_min == 0.8
        assert profile.speed_clamp_max == 1.5

    def test_speed_clamp_validation_invalid(self):
        """Test speed_clamp_max <= speed_clamp_min raises ValidationError."""
        with pytest.raises(ValidationError):
            VoiceProfile(language="en", speed_clamp_min=2.0, speed_clamp_max=1.5)

    def test_speed_clamp_max_limit(self):
        """Test speed_clamp_max must be <= 4.0."""
        with pytest.raises(ValidationError):
            VoiceProfile(language="en", speed_clamp_max=5.0)


class TestTTSConfig:
    """Tests for TTSConfig model."""

    def test_valid_config_defaults(self):
        """Test TTSConfig with default values."""
        config = TTSConfig()
        assert config.output_sample_rate_hz == 16000
        assert config.output_channels == 1
        assert config.output_format == AudioFormat.PCM_F32LE
        assert config.timeout_ms == 5000
        assert config.debug_artifacts is False

    def test_config_sample_rate_validation(self):
        """Test sample rate validation in config."""
        config = TTSConfig(output_sample_rate_hz=24000)
        assert config.output_sample_rate_hz == 24000

    def test_config_sample_rate_invalid(self):
        """Test invalid sample rate is rejected."""
        with pytest.raises(ValidationError):
            TTSConfig(output_sample_rate_hz=12345)

    def test_config_channels_validation(self):
        """Test channels validation in config."""
        config = TTSConfig(output_channels=2)
        assert config.output_channels == 2

    def test_config_timeout_minimum(self):
        """Test timeout_ms has minimum of 1000ms."""
        with pytest.raises(ValidationError):
            TTSConfig(timeout_ms=500)


class TestTTSMetrics:
    """Tests for TTSMetrics model."""

    @pytest.fixture
    def valid_metrics_data(self):
        """Fixture providing valid TTSMetrics data."""
        return {
            "stream_id": "stream-abc",
            "sequence_number": 42,
            "asset_id": "audio-uuid-456",
            "preprocess_time_ms": 5,
            "synthesis_time_ms": 1645,
            "alignment_time_ms": 200,
            "total_time_ms": 1850,
            "final_duration_ms": 2000,
            "model_used": "xtts_v2",
            "voice_cloning_active": False,
            "fast_mode_active": False,
        }

    def test_valid_metrics_creation(self, valid_metrics_data):
        """Test valid TTSMetrics creation."""
        metrics = TTSMetrics(**valid_metrics_data)
        assert metrics.stream_id == "stream-abc"
        assert metrics.sequence_number == 42
        assert metrics.total_time_ms == 1850
        assert metrics.model_used == "xtts_v2"

    def test_metrics_includes_duration_info(self, valid_metrics_data):
        """Test TTSMetrics includes duration matching info."""
        data = valid_metrics_data.copy()
        data["baseline_duration_ms"] = 2500
        data["target_duration_ms"] = 2000
        data["speed_factor_applied"] = 1.25
        data["speed_factor_clamped"] = False
        metrics = TTSMetrics(**data)
        assert metrics.baseline_duration_ms == 2500
        assert metrics.target_duration_ms == 2000
        assert metrics.speed_factor_applied == 1.25
        assert metrics.speed_factor_clamped is False

    def test_metrics_alignment_time_tracking(self, valid_metrics_data):
        """Test TTSMetrics tracks alignment_time_ms."""
        metrics = TTSMetrics(**valid_metrics_data)
        assert metrics.alignment_time_ms == 200
