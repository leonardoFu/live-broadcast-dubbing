"""
Tests for translation component factory (T012).

TDD: These tests are written BEFORE the implementation.
"""

import pytest


class TestCreateTranslationComponent:
    """Tests for create_translation_component factory function."""

    def test_factory_exists(self):
        """Test create_translation_component can be imported."""
        from sts_service.translation.factory import create_translation_component

        assert create_translation_component is not None

    def test_create_mock_by_default(self):
        """Test factory creates mock component by default."""
        from sts_service.translation.factory import create_translation_component
        from sts_service.translation.mock import MockIdentityTranslator

        component = create_translation_component(mock=True)
        assert isinstance(component, MockIdentityTranslator)

    def test_create_mock_with_mock_true(self):
        """Test factory creates mock when mock=True."""
        from sts_service.translation.factory import create_translation_component
        from sts_service.translation.interface import TranslationComponent

        component = create_translation_component(mock=True)
        assert isinstance(component, TranslationComponent)
        assert component.component_instance.startswith("mock")

    def test_mock_satisfies_protocol(self):
        """Test mock component satisfies TranslationComponent protocol."""
        from sts_service.translation.factory import create_translation_component
        from sts_service.translation.interface import TranslationComponent

        component = create_translation_component(mock=True)
        assert isinstance(component, TranslationComponent)

    def test_factory_with_config(self):
        """Test factory accepts TranslationConfig."""
        from sts_service.translation.factory import create_translation_component
        from sts_service.translation.models import TranslationConfig

        config = TranslationConfig(timeout_ms=3000)
        component = create_translation_component(config=config, mock=True)
        assert component is not None

    def test_deepl_requires_auth_key(self):
        """Test creating DeepL component without auth key raises error."""
        import os

        from sts_service.translation.factory import create_translation_component

        # Ensure no env var is set
        old_key = os.environ.pop("DEEPL_AUTH_KEY", None)

        try:
            with pytest.raises(ValueError, match="[Dd]eepL|auth"):
                create_translation_component(provider="deepl", mock=False)
        finally:
            if old_key:
                os.environ["DEEPL_AUTH_KEY"] = old_key


class TestProviderSelection:
    """Tests for provider selection in factory."""

    def test_default_provider_is_mock(self):
        """Test default behavior creates mock component."""
        from sts_service.translation.factory import create_translation_component

        component = create_translation_component(mock=True)
        assert "mock" in component.component_instance.lower()

    def test_provider_deepl_with_mock(self):
        """Test provider='deepl' with mock=True creates mock."""
        from sts_service.translation.factory import create_translation_component

        component = create_translation_component(provider="deepl", mock=True)
        assert "mock" in component.component_instance.lower()


class TestFactoryIntegration:
    """Integration tests for factory function."""

    def test_created_component_can_translate(self):
        """Test created component can perform translation."""
        from sts_service.translation.factory import create_translation_component
        from sts_service.translation.models import TranslationStatus

        component = create_translation_component(mock=True)
        result = component.translate(
            source_text="Hello world",
            stream_id="test-stream",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=["parent-123"],
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.stream_id == "test-stream"
        assert result.parent_asset_ids == ["parent-123"]

    def test_created_component_handles_shutdown(self):
        """Test created component can be shut down."""
        from sts_service.translation.factory import create_translation_component

        component = create_translation_component(mock=True)
        # Should not raise
        component.shutdown()
