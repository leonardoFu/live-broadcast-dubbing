"""
Unit tests for TTS Factory with TTS_PROVIDER environment variable support.

Following TDD: These tests are written FIRST and MUST FAIL before implementation.
Tests validate:
- New "elevenlabs" provider type
- TTS_PROVIDER environment variable for default provider selection
- Default provider is now "elevenlabs" (not "coqui")
- Backward compatibility with explicit provider parameter
"""

import os
from unittest.mock import patch

import pytest

# ============================================================================
# T011: Factory Provider Tests
# ============================================================================


class TestTTSFactoryElevenLabs:
    """Tests for ElevenLabs provider in factory."""

    def test_factory_creates_elevenlabs_provider(self):
        """Test that factory can create ElevenLabs provider."""
        from sts_service.tts.factory import create_tts_component

        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-api-key-valid"}):
                component = create_tts_component(provider="elevenlabs")

        from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

        assert isinstance(component, ElevenLabsTTSComponent)
        assert component.component_instance == "elevenlabs-eleven_flash_v2_5"

    def test_factory_creates_coqui_provider(self):
        """Test that factory still creates Coqui provider when requested."""
        from sts_service.tts.factory import create_tts_component

        component = create_tts_component(provider="coqui")

        from sts_service.tts.coqui_provider import CoquiTTSComponent

        assert isinstance(component, CoquiTTSComponent)

    def test_factory_creates_mock_provider(self):
        """Test that factory still creates mock provider when requested."""
        from sts_service.tts.factory import create_tts_component

        component = create_tts_component(provider="mock")

        from sts_service.tts.mock import MockTTSFixedTone

        assert isinstance(component, MockTTSFixedTone)


class TestTTSFactoryEnvVar:
    """Tests for TTS_PROVIDER environment variable support."""

    def test_factory_uses_tts_provider_env_var(self):
        """Test that TTS_PROVIDER env var controls default provider."""
        from sts_service.tts.factory import create_tts_component

        # When TTS_PROVIDER=coqui, default should be coqui
        with patch.dict(os.environ, {"TTS_PROVIDER": "coqui"}):
            component = create_tts_component()

            from sts_service.tts.coqui_provider import CoquiTTSComponent

            assert isinstance(component, CoquiTTSComponent)

    def test_factory_env_var_elevenlabs(self):
        """Test that TTS_PROVIDER=elevenlabs creates ElevenLabs provider."""
        from sts_service.tts.factory import create_tts_component

        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch.dict(
                os.environ, {"TTS_PROVIDER": "elevenlabs", "ELEVENLABS_API_KEY": "test-key-valid"}
            ):
                component = create_tts_component()

                from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

                assert isinstance(component, ElevenLabsTTSComponent)

    def test_factory_default_is_elevenlabs(self):
        """Test that default provider (when no env var) is 'elevenlabs'."""
        from sts_service.tts.factory import create_tts_component

        # Clear TTS_PROVIDER env var but set ELEVENLABS_API_KEY
        env = os.environ.copy()
        env.pop("TTS_PROVIDER", None)
        env["ELEVENLABS_API_KEY"] = "test-key-valid"

        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch.dict(os.environ, env, clear=True):
                component = create_tts_component()

                from sts_service.tts.elevenlabs_provider import ElevenLabsTTSComponent

                assert isinstance(component, ElevenLabsTTSComponent)

    def test_factory_explicit_provider_overrides_env_var(self):
        """Test that explicit provider parameter overrides TTS_PROVIDER env var."""
        from sts_service.tts.factory import create_tts_component

        # Even with TTS_PROVIDER=elevenlabs, explicit provider=coqui should work
        with patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs"}):
            component = create_tts_component(provider="coqui")

            from sts_service.tts.coqui_provider import CoquiTTSComponent

            assert isinstance(component, CoquiTTSComponent)

    def test_factory_env_var_invalid_raises(self):
        """Test that invalid TTS_PROVIDER env var raises ValueError."""
        from sts_service.tts.factory import create_tts_component

        with patch.dict(os.environ, {"TTS_PROVIDER": "invalid_provider"}):
            with pytest.raises(ValueError) as exc_info:
                create_tts_component()

        assert "Unknown TTS provider" in str(exc_info.value)


class TestTTSFactoryProviderList:
    """Tests for provider listing in error messages."""

    def test_factory_error_lists_all_providers(self):
        """Test that error message lists all supported providers including elevenlabs."""
        from sts_service.tts.factory import create_tts_component

        with pytest.raises(ValueError) as exc_info:
            create_tts_component(provider="nonexistent")  # type: ignore

        error_message = str(exc_info.value)
        assert "elevenlabs" in error_message
        assert "coqui" in error_message
        assert "mock" in error_message


class TestTTSFactoryConfig:
    """Tests for factory configuration passing."""

    def test_factory_passes_config_to_elevenlabs(self):
        """Test that factory passes config to ElevenLabs provider."""
        from sts_service.tts.factory import create_tts_component
        from sts_service.tts.models import TTSConfig

        config = TTSConfig(
            output_sample_rate_hz=48000,
            output_channels=2,
        )

        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-valid"}):
                component = create_tts_component(provider="elevenlabs", config=config)

        assert component._config.output_sample_rate_hz == 48000
        assert component._config.output_channels == 2

    def test_factory_passes_kwargs_to_elevenlabs(self):
        """Test that factory passes kwargs (like api_key, model_id) to ElevenLabs."""
        from sts_service.tts.factory import create_tts_component

        with patch("sts_service.tts.elevenlabs_provider.ELEVENLABS_AVAILABLE", True):
            component = create_tts_component(
                provider="elevenlabs",
                api_key="custom-api-key-test",
                model_id="eleven_multilingual_v2",
            )

        assert component._api_key == "custom-api-key-test"
        assert component._model_id == "eleven_multilingual_v2"
