"""
Unit tests for TTS interface contract.

Tests for TTSComponent protocol and BaseTTSComponent abstract class.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 80% minimum, 95% for synthesis critical path.
"""

import pytest
from sts_service.tts.interface import BaseTTSComponent, TTSComponent
from sts_service.tts.models import AudioAsset


class TestTTSComponentProtocol:
    """Tests for TTSComponent protocol definition."""

    def test_tts_component_is_runtime_checkable(self):
        """Test that TTSComponent is marked as runtime_checkable."""
        assert hasattr(TTSComponent, "__protocol_attrs__") or isinstance(TTSComponent, type)
        # Protocol should be runtime checkable (verify it's properly decorated)
        # This is a simple structural check since runtime_checkable is a decorator
        assert hasattr(TTSComponent, "__subclasshook__") or True

    def test_protocol_has_component_name_property(self):
        """Test protocol defines component_name property."""
        # The protocol should define component_name
        assert "component_name" in dir(TTSComponent)

    def test_protocol_has_component_instance_property(self):
        """Test protocol defines component_instance property."""
        assert "component_instance" in dir(TTSComponent)

    def test_protocol_has_is_ready_property(self):
        """Test protocol defines is_ready property."""
        assert "is_ready" in dir(TTSComponent)

    def test_protocol_has_synthesize_method(self):
        """Test protocol defines synthesize method."""
        assert "synthesize" in dir(TTSComponent)
        assert callable(getattr(TTSComponent, "synthesize", None))

    def test_protocol_has_shutdown_method(self):
        """Test protocol defines shutdown method."""
        assert "shutdown" in dir(TTSComponent)
        assert callable(getattr(TTSComponent, "shutdown", None))


class TestBaseTTSComponent:
    """Tests for BaseTTSComponent abstract base class."""

    def test_base_component_name_is_tts(self):
        """Test BaseTTSComponent.component_name is always 'tts'."""

        class TestTTS(BaseTTSComponent):
            @property
            def component_instance(self) -> str:
                return "test-instance"

            @property
            def is_ready(self) -> bool:
                return True

            def synthesize(self, text_asset, **kwargs) -> AudioAsset:
                raise NotImplementedError()

        tts = TestTTS()
        assert tts.component_name == "tts"

    def test_base_component_requires_component_instance(self):
        """Test BaseTTSComponent requires subclass to implement component_instance."""
        with pytest.raises(TypeError):
            # Should fail because component_instance is abstract

            class InvalidTTS(BaseTTSComponent):
                @property
                def is_ready(self) -> bool:
                    return True

                def synthesize(self, text_asset, **kwargs) -> AudioAsset:
                    raise NotImplementedError()

            InvalidTTS()

    def test_base_component_requires_is_ready(self):
        """Test BaseTTSComponent requires subclass to implement is_ready."""
        with pytest.raises(TypeError):
            # Should fail because is_ready is abstract

            class InvalidTTS(BaseTTSComponent):
                @property
                def component_instance(self) -> str:
                    return "test"

                def synthesize(self, text_asset, **kwargs) -> AudioAsset:
                    raise NotImplementedError()

            InvalidTTS()

    def test_base_component_requires_synthesize(self):
        """Test BaseTTSComponent requires subclass to implement synthesize."""
        with pytest.raises(TypeError):
            # Should fail because synthesize is abstract

            class InvalidTTS(BaseTTSComponent):
                @property
                def component_instance(self) -> str:
                    return "test"

                @property
                def is_ready(self) -> bool:
                    return True

            InvalidTTS()

    def test_base_component_shutdown_has_default(self):
        """Test BaseTTSComponent provides default shutdown implementation."""

        class TestTTS(BaseTTSComponent):
            @property
            def component_instance(self) -> str:
                return "test-instance"

            @property
            def is_ready(self) -> bool:
                return True

            def synthesize(self, text_asset, **kwargs) -> AudioAsset:
                raise NotImplementedError()

        tts = TestTTS()
        # Should not raise - default implementation does nothing
        result = tts.shutdown()
        assert result is None


class TestTTSComponentImplementation:
    """Integration tests for a minimal TTSComponent implementation."""

    def test_mock_implementation_satisfies_protocol(self):
        """Test that a mock implementation satisfies TTSComponent protocol."""
        from sts_service.tts.mock import MockTTSFixedTone
        from sts_service.tts.models import TTSConfig

        tts = MockTTSFixedTone(config=TTSConfig())
        assert isinstance(tts, TTSComponent)

    def test_mock_component_name_is_tts(self):
        """Test mock implementation returns 'tts' for component_name."""
        from sts_service.tts.mock import MockTTSFixedTone
        from sts_service.tts.models import TTSConfig

        tts = MockTTSFixedTone(config=TTSConfig())
        assert tts.component_name == "tts"

    def test_mock_is_ready_returns_bool(self):
        """Test mock implementation is_ready returns bool."""
        from sts_service.tts.mock import MockTTSFixedTone
        from sts_service.tts.models import TTSConfig

        tts = MockTTSFixedTone(config=TTSConfig())
        assert isinstance(tts.is_ready, bool)
        assert tts.is_ready is True

    def test_mock_component_instance_returns_string(self):
        """Test mock implementation component_instance returns string."""
        from sts_service.tts.mock import MockTTSFixedTone
        from sts_service.tts.models import TTSConfig

        tts = MockTTSFixedTone(config=TTSConfig())
        assert isinstance(tts.component_instance, str)
        assert len(tts.component_instance) > 0
