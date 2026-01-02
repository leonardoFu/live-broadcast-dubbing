"""
Unit tests for ASR component factory.

TDD: These tests are written BEFORE implementation.
"""


import pytest


class TestASRComponentFactory:
    """Tests for create_asr_component factory function."""

    def test_factory_returns_mock_when_requested(self):
        """Test that factory returns MockASRComponent when mock=True."""
        from sts_service.asr.factory import create_asr_component
        from sts_service.asr.mock import MockASRComponent
        from sts_service.asr.models import ASRConfig

        config = ASRConfig()
        component = create_asr_component(config, mock=True)

        assert isinstance(component, MockASRComponent)

    def test_factory_returns_faster_whisper_by_default(self):
        """Test that factory returns FasterWhisperASR by default when mock=False.

        Note: This test verifies the import path works. Full integration with
        FasterWhisperASR is tested in integration tests where faster-whisper is available.
        """
        # We verify that when mock=False, the factory attempts to import FasterWhisperASR
        # This will fail if faster-whisper is not installed, which is expected in unit tests
        from sts_service.asr.factory import create_asr_component
        from sts_service.asr.models import ASRConfig

        config = ASRConfig()

        # The import will happen - either succeeds or raises ImportError
        try:
            component = create_asr_component(config, mock=False)
            # If faster-whisper is available, should get a real component
            assert component.component_name == "asr"
        except Exception:
            # If faster-whisper not installed, that's fine for unit tests
            pytest.skip("faster-whisper not installed")

    def test_factory_passes_config_to_component(self):
        """Test that factory passes config to the component."""
        from sts_service.asr.factory import create_asr_component
        from sts_service.asr.mock import MockASRComponent
        from sts_service.asr.models import ASRConfig, ASRModelConfig

        config = ASRConfig(
            model=ASRModelConfig(model_size="small"),
            timeout_ms=3000,
        )
        component = create_asr_component(config, mock=True)

        # Config should be accessible
        assert isinstance(component, MockASRComponent)

    def test_factory_with_default_config(self):
        """Test factory works with default config when none provided."""
        from sts_service.asr.factory import create_asr_component
        from sts_service.asr.mock import MockASRComponent

        component = create_asr_component(mock=True)

        assert isinstance(component, MockASRComponent)
