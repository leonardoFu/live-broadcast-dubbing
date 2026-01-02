"""
Tests for Translation component interface (Protocol + BaseClass).

TDD: These tests are written BEFORE the implementation.
"""


import pytest


class TestTranslationComponentProtocol:
    """Tests for TranslationComponent Protocol (T006)."""

    def test_protocol_exists(self):
        """Test TranslationComponent protocol can be imported."""
        from sts_service.translation.interface import TranslationComponent

        assert TranslationComponent is not None

    def test_protocol_is_runtime_checkable(self):
        """Test TranslationComponent is runtime_checkable."""
        from sts_service.translation.interface import TranslationComponent

        # Protocol should be decorated with @runtime_checkable
        assert hasattr(TranslationComponent, "__protocol_attrs__") or hasattr(
            TranslationComponent, "_is_runtime_protocol"
        )

    def test_protocol_defines_component_name_property(self):
        """Test protocol defines component_name property."""
        from sts_service.translation.interface import TranslationComponent

        # Check protocol has expected members
        assert "component_name" in dir(TranslationComponent)

    def test_protocol_defines_component_instance_property(self):
        """Test protocol defines component_instance property."""
        from sts_service.translation.interface import TranslationComponent

        assert "component_instance" in dir(TranslationComponent)

    def test_protocol_defines_is_ready_property(self):
        """Test protocol defines is_ready property."""
        from sts_service.translation.interface import TranslationComponent

        assert "is_ready" in dir(TranslationComponent)

    def test_protocol_defines_translate_method(self):
        """Test protocol defines translate method."""
        from sts_service.translation.interface import TranslationComponent

        assert "translate" in dir(TranslationComponent)
        assert callable(getattr(TranslationComponent, "translate", None))

    def test_protocol_defines_shutdown_method(self):
        """Test protocol defines shutdown method."""
        from sts_service.translation.interface import TranslationComponent

        assert "shutdown" in dir(TranslationComponent)


class TestBaseTranslationComponent:
    """Tests for BaseTranslationComponent abstract base class (T006)."""

    def test_base_class_exists(self):
        """Test BaseTranslationComponent can be imported."""
        from sts_service.translation.interface import BaseTranslationComponent

        assert BaseTranslationComponent is not None

    def test_base_class_is_abstract(self):
        """Test BaseTranslationComponent cannot be instantiated directly."""
        from sts_service.translation.interface import BaseTranslationComponent

        with pytest.raises(TypeError):
            # Should fail because abstract methods not implemented
            BaseTranslationComponent()

    def test_component_name_returns_translate(self):
        """Test component_name property returns 'translate'."""
        from sts_service.translation.interface import BaseTranslationComponent
        from sts_service.translation.models import (
            NormalizationPolicy,
            SpeakerPolicy,
            TextAsset,
            TranslationStatus,
        )

        # Create a minimal concrete implementation to test base class
        class TestComponent(BaseTranslationComponent):
            @property
            def component_instance(self) -> str:
                return "test-component"

            @property
            def is_ready(self) -> bool:
                return True

            def translate(
                self,
                source_text: str,
                stream_id: str,
                sequence_number: int,
                source_language: str,
                target_language: str,
                parent_asset_ids: list[str],
                speaker_policy: SpeakerPolicy | None = None,
                normalization_policy: NormalizationPolicy | None = None,
            ) -> TextAsset:
                return TextAsset(
                    stream_id=stream_id,
                    sequence_number=sequence_number,
                    component_instance=self.component_instance,
                    source_language=source_language,
                    target_language=target_language,
                    translated_text=source_text,
                    status=TranslationStatus.SUCCESS,
                )

        component = TestComponent()
        assert component.component_name == "translate"

    def test_component_instance_is_abstract(self):
        """Test component_instance is abstract."""
        from sts_service.translation.interface import BaseTranslationComponent

        # component_instance should be abstract
        assert hasattr(BaseTranslationComponent.component_instance, "fget")

    def test_is_ready_is_abstract(self):
        """Test is_ready is abstract."""
        from sts_service.translation.interface import BaseTranslationComponent

        # is_ready should be abstract
        assert hasattr(BaseTranslationComponent.is_ready, "fget")

    def test_translate_is_abstract(self):
        """Test translate is abstract."""

        from sts_service.translation.interface import BaseTranslationComponent

        # translate should be abstract
        assert getattr(BaseTranslationComponent.translate, "__isabstractmethod__", False)

    def test_shutdown_has_default_implementation(self):
        """Test shutdown has a default (no-op) implementation."""
        from sts_service.translation.interface import BaseTranslationComponent
        from sts_service.translation.models import (
            NormalizationPolicy,
            SpeakerPolicy,
            TextAsset,
            TranslationStatus,
        )

        class TestComponent(BaseTranslationComponent):
            @property
            def component_instance(self) -> str:
                return "test"

            @property
            def is_ready(self) -> bool:
                return True

            def translate(
                self,
                source_text: str,
                stream_id: str,
                sequence_number: int,
                source_language: str,
                target_language: str,
                parent_asset_ids: list[str],
                speaker_policy: SpeakerPolicy | None = None,
                normalization_policy: NormalizationPolicy | None = None,
            ) -> TextAsset:
                return TextAsset(
                    stream_id=stream_id,
                    sequence_number=sequence_number,
                    component_instance="test",
                    source_language=source_language,
                    target_language=target_language,
                    translated_text=source_text,
                    status=TranslationStatus.SUCCESS,
                )

        component = TestComponent()
        # Should not raise - default implementation does nothing
        component.shutdown()


class TestConcreteImplementationCompliance:
    """Test that concrete implementations can satisfy the protocol (T006)."""

    def test_minimal_implementation_satisfies_protocol(self):
        """Test a minimal implementation satisfies TranslationComponent protocol."""
        from sts_service.translation.interface import (
            BaseTranslationComponent,
            TranslationComponent,
        )
        from sts_service.translation.models import (
            NormalizationPolicy,
            SpeakerPolicy,
            TextAsset,
            TranslationStatus,
        )

        class MinimalComponent(BaseTranslationComponent):
            @property
            def component_instance(self) -> str:
                return "minimal-v1"

            @property
            def is_ready(self) -> bool:
                return True

            def translate(
                self,
                source_text: str,
                stream_id: str,
                sequence_number: int,
                source_language: str,
                target_language: str,
                parent_asset_ids: list[str],
                speaker_policy: SpeakerPolicy | None = None,
                normalization_policy: NormalizationPolicy | None = None,
            ) -> TextAsset:
                return TextAsset(
                    stream_id=stream_id,
                    sequence_number=sequence_number,
                    parent_asset_ids=parent_asset_ids,
                    component_instance=self.component_instance,
                    source_language=source_language,
                    target_language=target_language,
                    translated_text=source_text,
                    status=TranslationStatus.SUCCESS,
                )

        component = MinimalComponent()

        # Test protocol compliance via isinstance
        assert isinstance(component, TranslationComponent)

        # Test all required properties
        assert component.component_name == "translate"
        assert component.component_instance == "minimal-v1"
        assert component.is_ready is True

        # Test translate method
        result = component.translate(
            source_text="Hello",
            stream_id="stream-123",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=["parent-abc"],
        )

        assert isinstance(result, TextAsset)
        assert result.translated_text == "Hello"
        assert result.status == TranslationStatus.SUCCESS
        assert result.parent_asset_ids == ["parent-abc"]
