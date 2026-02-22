"""
ASR Component Interface Contract

This module defines the abstract interface that all ASR implementations must follow.
Both the real faster-whisper implementation and mock implementations conform to this contract.

Location: apps/sts-service/src/sts_service/asr/interface.py
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

# Note: In actual implementation, import from the data models module
# from .models import AudioFragment, TranscriptAsset, ASRConfig


@runtime_checkable
class ASRComponent(Protocol):
    """Protocol defining the ASR component contract.

    All ASR implementations (real and mock) must implement this interface.
    This follows the component contract from specs/004-sts-pipeline-design.md Section 6.2.
    """

    @property
    def component_name(self) -> str:
        """Return the component name (always 'asr')."""
        ...

    @property
    def component_instance(self) -> str:
        """Return the provider identifier (e.g., 'faster-whisper-base')."""
        ...

    @property
    def is_ready(self) -> bool:
        """Check if the component is ready to process requests."""
        ...

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
    ) -> "TranscriptAsset":
        """Transcribe an audio fragment.

        Args:
            audio_data: Raw PCM audio bytes (float32 little-endian)
            stream_id: Logical stream/session identifier
            sequence_number: Fragment index within stream
            start_time_ms: Fragment start in stream timeline
            end_time_ms: Fragment end in stream timeline
            sample_rate_hz: Audio sample rate (default 16kHz)
            domain: Domain hint for vocabulary priming
            language: Expected language code

        Returns:
            TranscriptAsset with transcription results

        The component MUST:
        - Return SUCCESS status with empty segments for silence/no-speech
        - Return FAILED status with retryable=True for transient errors
        - Return FAILED status with retryable=False for permanent errors
        - Produce segment timestamps that are absolute (stream timeline)
        """
        ...

    def shutdown(self) -> None:
        """Release resources (model cache, etc.)."""
        ...


class BaseASRComponent(ABC):
    """Abstract base class for ASR component implementations.

    Provides common functionality and enforces the ASR contract.
    """

    _component_name: str = "asr"

    @property
    def component_name(self) -> str:
        return self._component_name

    @property
    @abstractmethod
    def component_instance(self) -> str:
        """Subclasses must provide their instance identifier."""
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Subclasses must indicate readiness."""
        pass

    @abstractmethod
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
    ) -> "TranscriptAsset":
        """Subclasses must implement transcription logic."""
        pass

    def shutdown(self) -> None:
        """Default implementation does nothing. Override if cleanup needed."""
        pass


# Type alias for the audio payload reference system
AudioPayloadRef = str  # e.g., "mem://fragments/stream-abc/42" or "file:///tmp/audio.raw"


class AudioPayloadStore(Protocol):
    """Protocol for audio payload storage and retrieval.

    The ASR component needs a way to retrieve audio bytes from payload references.
    This protocol defines that interface without coupling to a specific storage backend.
    """

    def get(self, payload_ref: str) -> bytes | None:
        """Retrieve audio bytes by reference.

        Args:
            payload_ref: Reference string (e.g., "mem://fragments/stream-abc/42")

        Returns:
            Raw audio bytes or None if not found
        """
        ...

    def put(self, payload_ref: str, audio_data: bytes) -> None:
        """Store audio bytes with a reference.

        Args:
            payload_ref: Reference string to use
            audio_data: Raw audio bytes to store
        """
        ...

    def delete(self, payload_ref: str) -> bool:
        """Delete audio bytes by reference.

        Args:
            payload_ref: Reference string

        Returns:
            True if deleted, False if not found
        """
        ...


# -----------------------------------------------------------------------------
# Mock Implementation Specification
# -----------------------------------------------------------------------------


class MockASRConfig:
    """Configuration for MockASRComponent behavior.

    Used for deterministic testing without real transcription.
    """

    def __init__(
        self,
        default_text: str = "Mock transcription output.",
        default_confidence: float = 0.95,
        words_per_second: float = 3.0,
        simulate_latency_ms: int = 0,
        failure_rate: float = 0.0,
        failure_type: str | None = None,  # "timeout", "memory_error", etc.
    ):
        self.default_text = default_text
        self.default_confidence = default_confidence
        self.words_per_second = words_per_second
        self.simulate_latency_ms = simulate_latency_ms
        self.failure_rate = failure_rate
        self.failure_type = failure_type


# Example usage in tests:
#
# from sts_service.asr import MockASRComponent, MockASRConfig
#
# mock_config = MockASRConfig(
#     default_text="Touchdown Chiefs! Great play by Mahomes.",
#     default_confidence=0.92,
# )
# mock_asr = MockASRComponent(config=mock_config)
#
# result = mock_asr.transcribe(
#     audio_data=b"...",  # ignored
#     stream_id="test-stream",
#     sequence_number=1,
#     start_time_ms=0,
#     end_time_ms=2000,
# )
#
# assert result.status == TranscriptStatus.SUCCESS
# assert "Touchdown" in result.segments[0].text
