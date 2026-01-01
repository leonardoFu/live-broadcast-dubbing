"""
Unit tests for voice selection functionality.

Tests for voice/model selection, voice cloning activation, and config loading.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 80% minimum.
"""

import contextlib
import os
import tempfile

import pytest
import yaml
from sts_service.tts.models import VoiceProfile
from sts_service.tts.voice_selection import (
    VoiceConfigError,
    load_voice_config,
    select_model,
    select_voice,
    validate_voice_sample,
)


@pytest.fixture
def sample_config():
    """Provide sample voice configuration."""
    return {
        "defaults": {
            "output_sample_rate_hz": 16000,
            "output_channels": 1,
            "device": "cpu",
        },
        "languages": {
            "en": {
                "model": "tts_models/multilingual/multi-dataset/xtts_v2",
                "fast_model": "tts_models/en/vctk/vits",
                "default_speaker": "p225",
                "sample_rate_hz": 24000,
            },
            "es": {
                "model": "tts_models/multilingual/multi-dataset/xtts_v2",
                "fast_model": "tts_models/es/css10/vits",
                "default_speaker": None,
                "sample_rate_hz": 24000,
            },
        },
    }


@pytest.fixture
def temp_config_file(sample_config):
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        yield f.name
    os.unlink(f.name)


class TestLoadVoiceConfig:
    """Tests for voice configuration loading."""

    def test_load_config_from_file(self, temp_config_file):
        """Test load_voice_config parses YAML correctly."""
        config = load_voice_config(temp_config_file)
        assert "languages" in config
        assert "en" in config["languages"]
        assert "es" in config["languages"]

    def test_load_config_env_override(self, temp_config_file, monkeypatch):
        """Test TTS_VOICES_CONFIG env var override."""
        monkeypatch.setenv("TTS_VOICES_CONFIG", temp_config_file)
        config = load_voice_config()  # No path provided
        assert "languages" in config

    def test_load_config_validates_required_fields(self, temp_config_file):
        """Test config validation (required fields present)."""
        config = load_voice_config(temp_config_file)
        # Should have required structure
        assert "languages" in config

    def test_load_config_file_not_found(self):
        """Test error handling for missing config file."""
        with pytest.raises(VoiceConfigError):
            load_voice_config("/nonexistent/path/config.yaml")


class TestSelectModel:
    """Tests for model selection logic."""

    def test_fast_mode_selects_fast_model(self, sample_config):
        """Test fast_mode=True selects VITS model from config."""
        profile = VoiceProfile(language="en", fast_mode=True)
        model = select_model(profile, sample_config)
        assert "vits" in model.lower()

    def test_quality_mode_selects_xtts(self, sample_config):
        """Test fast_mode=False selects XTTS-v2 model from config."""
        profile = VoiceProfile(language="en", fast_mode=False)
        model = select_model(profile, sample_config)
        assert "xtts" in model.lower()

    def test_fallback_when_fast_model_unavailable(self, sample_config):
        """Test fallback to standard model when fast_model unavailable."""
        # Modify config to remove fast_model for French
        config = sample_config.copy()
        config["languages"]["fr"] = {
            "model": "tts_models/multilingual/multi-dataset/xtts_v2",
            "fast_model": None,  # No fast model
            "default_speaker": None,
        }

        profile = VoiceProfile(language="fr", fast_mode=True)
        model = select_model(profile, config)
        # Should fallback to standard model
        assert "xtts" in model.lower()

    def test_explicit_model_override(self, sample_config):
        """Test explicit model_name override in VoiceProfile."""
        custom_model = "tts_models/custom/test_model"
        profile = VoiceProfile(
            language="en", fast_mode=False, model_name=custom_model
        )
        model = select_model(profile, sample_config)
        assert model == custom_model


class TestSelectVoice:
    """Tests for voice selection (cloning vs speaker)."""

    @pytest.fixture
    def valid_voice_sample(self):
        """Create a temporary valid voice sample file (5 seconds, 16kHz, mono)."""
        duration_seconds = 5  # Must be 3-30 seconds for validation
        sample_rate = 16000
        data_size = sample_rate * 2 * duration_seconds  # 16-bit = 2 bytes per sample
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Write WAV header + data
            f.write(b"RIFF")
            f.write((36 + data_size).to_bytes(4, 'little'))  # File size
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write((16).to_bytes(4, 'little'))  # Chunk size
            f.write((1).to_bytes(2, 'little'))   # Audio format (PCM)
            f.write((1).to_bytes(2, 'little'))   # Channels (mono)
            f.write((sample_rate).to_bytes(4, 'little'))  # Sample rate
            f.write((sample_rate * 2).to_bytes(4, 'little'))  # Byte rate
            f.write((2).to_bytes(2, 'little'))   # Block align
            f.write((16).to_bytes(2, 'little'))  # Bits per sample
            f.write(b"data")
            f.write((data_size).to_bytes(4, 'little'))  # Data size
            # Write 5 seconds of silence (16kHz, 16-bit)
            f.write(b'\x00' * data_size)
            yield f.name
        os.unlink(f.name)

    def test_voice_cloning_activated_with_valid_sample(self, sample_config, valid_voice_sample):
        """Test use_voice_cloning=True with valid voice_sample_path activates cloning."""
        profile = VoiceProfile(
            language="en",
            use_voice_cloning=True,
            voice_sample_path=valid_voice_sample,
        )
        voice_info = select_voice(profile, sample_config)
        assert voice_info["use_cloning"] is True
        assert voice_info["voice_sample_path"] == valid_voice_sample

    def test_voice_cloning_fallback_invalid_sample(self, sample_config):
        """Test use_voice_cloning=True with invalid voice_sample_path falls back to speaker."""
        profile = VoiceProfile(
            language="en",
            use_voice_cloning=True,
            voice_sample_path="/nonexistent/sample.wav",
        )
        voice_info = select_voice(profile, sample_config)
        # Should fallback to speaker mode
        assert voice_info["use_cloning"] is False

    def test_voice_cloning_disabled_in_fast_mode(self, sample_config, valid_voice_sample):
        """Test voice cloning disabled in fast mode (VITS does not support cloning)."""
        profile = VoiceProfile(
            language="en",
            fast_mode=True,  # Fast mode
            use_voice_cloning=True,
            voice_sample_path=valid_voice_sample,
        )
        voice_info = select_voice(profile, sample_config)
        # Fast mode (VITS) doesn't support cloning
        assert voice_info["use_cloning"] is False

    def test_speaker_name_used_for_multi_speaker(self, sample_config):
        """Test speaker_name from VoiceProfile is used for multi-speaker models."""
        profile = VoiceProfile(
            language="en",
            speaker_name="p227",  # Different from default
        )
        voice_info = select_voice(profile, sample_config)
        assert voice_info["speaker_name"] == "p227"

    def test_default_speaker_from_config(self, sample_config):
        """Test fallback to default_speaker from config when speaker_name not set."""
        profile = VoiceProfile(language="en")  # No speaker_name
        voice_info = select_voice(profile, sample_config)
        assert voice_info["speaker_name"] == "p225"  # Default from config


class TestValidateVoiceSample:
    """Tests for voice sample validation."""

    @pytest.fixture
    def create_wav_file(self):
        """Factory fixture to create WAV files with specific properties."""
        created_files = []

        def _create(
            sample_rate: int = 22050,
            channels: int = 1,
            duration_seconds: float = 5.0,
        ) -> str:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                # Calculate sizes
                bits_per_sample = 16
                byte_rate = sample_rate * channels * bits_per_sample // 8
                data_size = int(sample_rate * channels * duration_seconds * bits_per_sample // 8)

                # Write WAV header
                f.write(b"RIFF")
                f.write((36 + data_size).to_bytes(4, 'little'))
                f.write(b"WAVE")
                f.write(b"fmt ")
                f.write((16).to_bytes(4, 'little'))
                f.write((1).to_bytes(2, 'little'))   # PCM
                f.write((channels).to_bytes(2, 'little'))
                f.write((sample_rate).to_bytes(4, 'little'))
                f.write((byte_rate).to_bytes(4, 'little'))
                f.write((channels * bits_per_sample // 8).to_bytes(2, 'little'))
                f.write((bits_per_sample).to_bytes(2, 'little'))
                f.write(b"data")
                f.write((data_size).to_bytes(4, 'little'))
                # Write silence
                f.write(b'\x00' * data_size)
                created_files.append(f.name)
                return f.name

        yield _create

        # Cleanup
        for path in created_files:
            with contextlib.suppress(Exception):
                os.unlink(path)

    def test_validate_format_wav_only(self, create_wav_file):
        """Test WAV format is accepted."""
        wav_path = create_wav_file()
        result = validate_voice_sample(wav_path)
        assert result.is_valid

    def test_validate_format_mp3_rejected(self):
        """Test MP3 format is rejected."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake mp3 data")
            mp3_path = f.name

        try:
            result = validate_voice_sample(mp3_path)
            assert not result.is_valid
            assert "format" in result.error_message.lower()
        finally:
            os.unlink(mp3_path)

    def test_validate_channels_mono_required(self, create_wav_file):
        """Test mono (1 channel) is required."""
        mono_path = create_wav_file(channels=1)
        result = validate_voice_sample(mono_path)
        assert result.is_valid

    def test_validate_channels_stereo_rejected(self, create_wav_file):
        """Test stereo (2 channels) is rejected."""
        stereo_path = create_wav_file(channels=2)
        result = validate_voice_sample(stereo_path)
        assert not result.is_valid
        assert "channel" in result.error_message.lower()

    def test_validate_sample_rate_minimum(self, create_wav_file):
        """Test minimum 16kHz sample rate."""
        # Valid: 16kHz
        valid_path = create_wav_file(sample_rate=16000)
        result = validate_voice_sample(valid_path)
        assert result.is_valid

        # Invalid: 8kHz
        invalid_path = create_wav_file(sample_rate=8000)
        result = validate_voice_sample(invalid_path)
        assert not result.is_valid
        assert "sample rate" in result.error_message.lower()

    def test_validate_duration_minimum(self, create_wav_file):
        """Test minimum 3 seconds duration."""
        # Valid: 5 seconds
        valid_path = create_wav_file(duration_seconds=5.0)
        result = validate_voice_sample(valid_path)
        assert result.is_valid

        # Invalid: 2 seconds
        short_path = create_wav_file(duration_seconds=2.0)
        result = validate_voice_sample(short_path)
        assert not result.is_valid
        assert "duration" in result.error_message.lower()

    def test_validate_duration_maximum(self, create_wav_file):
        """Test maximum 30 seconds duration."""
        # Invalid: 35 seconds
        long_path = create_wav_file(duration_seconds=35.0)
        result = validate_voice_sample(long_path)
        assert not result.is_valid
        assert "duration" in result.error_message.lower()
