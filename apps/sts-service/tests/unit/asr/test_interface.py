"""
Unit tests for ASR interface protocol and base class.

TDD: These tests are written BEFORE implementation.
"""

from abc import ABC
from typing import Protocol, runtime_checkable

import pytest


class TestASRComponentProtocol:
    """Tests for ASRComponent protocol definition."""

    def test_asr_component_protocol_has_required_methods(self):
        """Test that ASRComponent protocol defines all required methods."""
        from sts_service.asr.interface import ASRComponent

        # Check protocol has required properties
        assert hasattr(ASRComponent, "component_name")
        assert hasattr(ASRComponent, "component_instance")
        assert hasattr(ASRComponent, "is_ready")

        # Check protocol has required methods
        assert hasattr(ASRComponent, "transcribe")
        assert hasattr(ASRComponent, "shutdown")

    def test_asr_component_protocol_is_runtime_checkable(self):
        """Test that ASRComponent is a runtime_checkable Protocol."""
        from sts_service.asr.interface import ASRComponent

        # Protocol should be runtime_checkable
        assert hasattr(ASRComponent, "__protocol_attrs__") or issubclass(
            type(ASRComponent), type(Protocol)
        )


class TestBaseASRComponent:
    """Tests for BaseASRComponent abstract base class."""

    def test_base_asr_component_is_abstract(self):
        """Test that BaseASRComponent cannot be instantiated directly."""
        from sts_service.asr.interface import BaseASRComponent

        # Should be an ABC
        assert issubclass(BaseASRComponent, ABC)

        # Cannot instantiate directly
        with pytest.raises(TypeError):
            BaseASRComponent()

    def test_base_asr_component_default_shutdown(self):
        """Test that BaseASRComponent provides default shutdown implementation."""
        from sts_service.asr.interface import BaseASRComponent

        # Create a minimal concrete implementation
        class MinimalASR(BaseASRComponent):
            @property
            def component_instance(self) -> str:
                return "test-instance"

            @property
            def is_ready(self) -> bool:
                return True

            def transcribe(
                self,
                audio_data: bytes,
                stream_id: str,
                sequence_number: int,
                start_time_ms: int,
                end_time_ms: int,
                sample_rate_hz: int = 16000,
                domain: str = "general",
                language: str = "en",
            ):
                pass

        instance = MinimalASR()
        # Default shutdown should not raise
        instance.shutdown()

    def test_base_asr_component_component_name_is_asr(self):
        """Test that component_name is always 'asr'."""
        from sts_service.asr.interface import BaseASRComponent

        # Create a minimal concrete implementation
        class MinimalASR(BaseASRComponent):
            @property
            def component_instance(self) -> str:
                return "test"

            @property
            def is_ready(self) -> bool:
                return True

            def transcribe(
                self,
                audio_data: bytes,
                stream_id: str,
                sequence_number: int,
                start_time_ms: int,
                end_time_ms: int,
                sample_rate_hz: int = 16000,
                domain: str = "general",
                language: str = "en",
            ):
                pass

        instance = MinimalASR()
        assert instance.component_name == "asr"


class TestAudioPayloadRef:
    """Tests for AudioPayloadRef type alias."""

    def test_audio_payload_ref_is_string_type(self):
        """Test that AudioPayloadRef is a string type alias."""
        from sts_service.asr.interface import AudioPayloadRef

        # Should be str
        assert AudioPayloadRef == str


class TestAudioPayloadStore:
    """Tests for AudioPayloadStore protocol."""

    def test_audio_payload_store_has_required_methods(self):
        """Test that AudioPayloadStore defines get, put, delete."""
        from sts_service.asr.interface import AudioPayloadStore

        assert hasattr(AudioPayloadStore, "get")
        assert hasattr(AudioPayloadStore, "put")
        assert hasattr(AudioPayloadStore, "delete")
