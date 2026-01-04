"""
Unit tests for ElevenLabs-specific VoiceProfile fields.

Following TDD: These tests are written FIRST and MUST FAIL before implementation.
After implementation (T003), all tests MUST PASS.

Tests validate:
- ElevenLabs-specific fields are optional
- Validation constraints for stability and similarity_boost (0.0-1.0 range)
- Backward compatibility with existing Coqui fields
"""

import pytest
from pydantic import ValidationError
from sts_service.tts.models import VoiceProfile


class TestVoiceProfileElevenLabsFields:
    """Tests for new ElevenLabs-specific fields in VoiceProfile."""

    def test_voice_profile_elevenlabs_fields_optional(self):
        """Test that ElevenLabs fields are optional (existing profiles work unchanged).

        VoiceProfile should continue to work without any ElevenLabs fields specified.
        """
        # Create profile with only required field (language)
        profile = VoiceProfile(language="en")

        # ElevenLabs fields should be None by default
        assert profile.voice_id is None
        assert profile.elevenlabs_model_id is None
        assert profile.stability is None
        assert profile.similarity_boost is None

    def test_voice_profile_elevenlabs_fields_set(self):
        """Test that ElevenLabs fields can be set."""
        profile = VoiceProfile(
            language="en",
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
            elevenlabs_model_id="eleven_flash_v2_5",
            stability=0.5,
            similarity_boost=0.75,
        )

        assert profile.voice_id == "21m00Tcm4TlvDq8ikWAM"
        assert profile.elevenlabs_model_id == "eleven_flash_v2_5"
        assert profile.stability == 0.5
        assert profile.similarity_boost == 0.75

    def test_voice_profile_stability_range_validation_min(self):
        """Test that stability must be >= 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            VoiceProfile(
                language="en",
                stability=-0.1,  # Invalid: below 0.0
            )

        # Check error message mentions the constraint
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        assert any("stability" in str(e).lower() for e in errors)

    def test_voice_profile_stability_range_validation_max(self):
        """Test that stability must be <= 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            VoiceProfile(
                language="en",
                stability=1.5,  # Invalid: above 1.0
            )

        # Check error message mentions the constraint
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        assert any("stability" in str(e).lower() for e in errors)

    def test_voice_profile_stability_valid_range(self):
        """Test that stability accepts valid values in range [0.0, 1.0]."""
        # Test boundary values
        profile_min = VoiceProfile(language="en", stability=0.0)
        assert profile_min.stability == 0.0

        profile_max = VoiceProfile(language="en", stability=1.0)
        assert profile_max.stability == 1.0

        profile_mid = VoiceProfile(language="en", stability=0.5)
        assert profile_mid.stability == 0.5

    def test_voice_profile_similarity_boost_range_validation_min(self):
        """Test that similarity_boost must be >= 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            VoiceProfile(
                language="en",
                similarity_boost=-0.1,  # Invalid: below 0.0
            )

        # Check error message mentions the constraint
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        assert any("similarity" in str(e).lower() for e in errors)

    def test_voice_profile_similarity_boost_range_validation_max(self):
        """Test that similarity_boost must be <= 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            VoiceProfile(
                language="en",
                similarity_boost=1.5,  # Invalid: above 1.0
            )

        # Check error message mentions the constraint
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        assert any("similarity" in str(e).lower() for e in errors)

    def test_voice_profile_similarity_boost_valid_range(self):
        """Test that similarity_boost accepts valid values in range [0.0, 1.0]."""
        # Test boundary values
        profile_min = VoiceProfile(language="en", similarity_boost=0.0)
        assert profile_min.similarity_boost == 0.0

        profile_max = VoiceProfile(language="en", similarity_boost=1.0)
        assert profile_max.similarity_boost == 1.0

        profile_mid = VoiceProfile(language="en", similarity_boost=0.5)
        assert profile_mid.similarity_boost == 0.5

    def test_voice_profile_backward_compatible(self):
        """Test that existing Coqui fields still work unchanged."""
        # Create profile with Coqui-specific fields
        profile = VoiceProfile(
            language="es",
            model_name="tts_models/es/css10/vits",
            fast_mode=True,
            voice_sample_path="/path/to/sample.wav",
            speaker_name="p225",
            use_voice_cloning=True,
            speed_clamp_min=0.6,
            speed_clamp_max=1.8,
            only_speed_up=False,
        )

        # All existing fields should work
        assert profile.language == "es"
        assert profile.model_name == "tts_models/es/css10/vits"
        assert profile.fast_mode is True
        assert profile.voice_sample_path == "/path/to/sample.wav"
        assert profile.speaker_name == "p225"
        assert profile.use_voice_cloning is True
        assert profile.speed_clamp_min == 0.6
        assert profile.speed_clamp_max == 1.8
        assert profile.only_speed_up is False

        # ElevenLabs fields should be None (not specified)
        assert profile.voice_id is None
        assert profile.elevenlabs_model_id is None
        assert profile.stability is None
        assert profile.similarity_boost is None

    def test_voice_profile_mixed_coqui_and_elevenlabs_fields(self):
        """Test that both Coqui and ElevenLabs fields can coexist."""
        profile = VoiceProfile(
            language="en",
            # Coqui fields
            speed_clamp_min=0.5,
            speed_clamp_max=2.0,
            only_speed_up=True,
            # ElevenLabs fields
            voice_id="21m00Tcm4TlvDq8ikWAM",
            elevenlabs_model_id="eleven_flash_v2_5",
            stability=0.5,
            similarity_boost=0.75,
        )

        # Both should work
        assert profile.speed_clamp_min == 0.5
        assert profile.speed_clamp_max == 2.0
        assert profile.only_speed_up is True
        assert profile.voice_id == "21m00Tcm4TlvDq8ikWAM"
        assert profile.elevenlabs_model_id == "eleven_flash_v2_5"
        assert profile.stability == 0.5
        assert profile.similarity_boost == 0.75
