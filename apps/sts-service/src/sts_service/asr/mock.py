"""
Mock ASR Component for testing.

Provides deterministic behavior without real transcription.
"""

import random
import time
from dataclasses import dataclass

from .interface import BaseASRComponent
from .models import (
    ASRError,
    ASRErrorType,
    TranscriptAsset,
    TranscriptSegment,
    TranscriptStatus,
    WordTiming,
)


@dataclass
class MockASRConfig:
    """Configuration for MockASRComponent behavior.

    Used for deterministic testing without real transcription.
    """

    default_text: str = "Mock transcription output."
    default_confidence: float = 0.95
    words_per_second: float = 3.0
    simulate_latency_ms: int = 0
    failure_rate: float = 0.0
    failure_type: str | None = None  # "timeout", "memory_error", etc.


class MockASRComponent(BaseASRComponent):
    """Deterministic mock ASR component for testing.

    Ignores actual audio content and returns configured text with
    calculated timestamps. Supports failure injection for testing
    error handling.
    """

    def __init__(self, config: MockASRConfig | None = None):
        """Initialize mock with configuration.

        Args:
            config: Mock behavior configuration
        """
        self._config = config or MockASRConfig()
        self._ready = True

    @property
    def component_instance(self) -> str:
        """Return mock instance identifier."""
        return "mock-asr"

    @property
    def is_ready(self) -> bool:
        """Mock is always ready."""
        return self._ready

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
    ) -> TranscriptAsset:
        """Return mock transcription result.

        Args:
            audio_data: Ignored - audio content not used
            stream_id: Stream identifier for result
            sequence_number: Sequence number for result
            start_time_ms: Fragment start time
            end_time_ms: Fragment end time
            sample_rate_hz: Ignored
            domain: Ignored
            language: Language code for result

        Returns:
            Mock TranscriptAsset with configured text
        """
        # Simulate latency if configured
        if self._config.simulate_latency_ms > 0:
            time.sleep(self._config.simulate_latency_ms / 1000.0)

        # Check for failure injection
        if self._should_fail():
            return self._create_failed_result(
                stream_id=stream_id,
                sequence_number=sequence_number,
                language=language,
            )

        # Generate mock transcript
        return self._create_success_result(
            stream_id=stream_id,
            sequence_number=sequence_number,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            language=language,
        )

    def _should_fail(self) -> bool:
        """Determine if this call should fail based on failure rate."""
        if self._config.failure_rate <= 0:
            return False
        if self._config.failure_rate >= 1:
            return True
        return random.random() < self._config.failure_rate

    def _create_failed_result(
        self,
        stream_id: str,
        sequence_number: int,
        language: str,
    ) -> TranscriptAsset:
        """Create a failed transcription result."""
        error_type = self._get_error_type()
        error = ASRError(
            error_type=error_type,
            message=f"Mock failure: {error_type.value}",
            retryable=error_type in (ASRErrorType.TIMEOUT, ASRErrorType.MEMORY_ERROR),
        )

        return TranscriptAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            component_instance=self.component_instance,
            language=language,
            segments=[],
            status=TranscriptStatus.FAILED,
            errors=[error],
        )

    def _get_error_type(self) -> ASRErrorType:
        """Get error type from configuration."""
        if self._config.failure_type == "timeout":
            return ASRErrorType.TIMEOUT
        elif self._config.failure_type == "memory_error":
            return ASRErrorType.MEMORY_ERROR
        elif self._config.failure_type == "invalid_audio":
            return ASRErrorType.INVALID_AUDIO
        else:
            return ASRErrorType.UNKNOWN

    def _create_success_result(
        self,
        stream_id: str,
        sequence_number: int,
        start_time_ms: int,
        end_time_ms: int,
        language: str,
    ) -> TranscriptAsset:
        """Create a successful transcription result."""
        text = self._config.default_text

        # Handle empty text
        if not text.strip():
            return TranscriptAsset(
                stream_id=stream_id,
                sequence_number=sequence_number,
                component_instance=self.component_instance,
                language=language,
                segments=[],
                status=TranscriptStatus.SUCCESS,
            )

        # Generate word timestamps
        words = self._generate_word_timestamps(
            text=text,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

        segment = TranscriptSegment(
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            text=text,
            confidence=self._config.default_confidence,
            words=words,
        )

        return TranscriptAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            component_instance=self.component_instance,
            language=language,
            segments=[segment],
            status=TranscriptStatus.SUCCESS,
        )

    def _generate_word_timestamps(
        self,
        text: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> list[WordTiming]:
        """Generate word-level timestamps from text.

        Distributes time evenly across words.
        """
        words = text.split()
        if not words:
            return []

        total_duration = end_time_ms - start_time_ms
        word_duration = total_duration // len(words)

        result = []
        current_time = start_time_ms

        for word in words:
            word_end = current_time + word_duration
            # Ensure last word extends to end
            if word == words[-1]:
                word_end = end_time_ms

            result.append(
                WordTiming(
                    start_time_ms=current_time,
                    end_time_ms=word_end,
                    word=word,
                    confidence=self._config.default_confidence,
                )
            )
            current_time = word_end

        return result
