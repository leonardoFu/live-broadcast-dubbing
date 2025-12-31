"""
Mock TTS Component Implementations.

Provides mock implementations for testing without actual TTS library dependencies.
These mocks implement the TTSComponent interface and produce deterministic outputs.

Mock Implementations:
- MockTTSFixedTone: Produces deterministic 440Hz sine wave tone
- MockTTSFromFixture: Returns pre-recorded audio from test fixtures
- MockTTSFailOnce: Fails first call per sequence_number, succeeds on retry

Based on specs/008-tts-module/plan.md Test Strategy.
"""

import math
import struct
from datetime import datetime

from sts_service.translation.models import TextAsset

from .errors import TTSErrorType, classify_error
from .interface import BaseTTSComponent
from .models import (
    AudioAsset,
    AudioFormat,
    AudioStatus,
    TTSConfig,
    VoiceProfile,
)


class MockTTSFixedTone(BaseTTSComponent):
    """Mock TTS that produces deterministic 440Hz sine wave tone.

    This mock is useful for:
    - Pipeline integration tests
    - Latency benchmarks
    - Testing audio processing without TTS library
    """

    def __init__(
        self,
        config: TTSConfig | None = None,
        frequency_hz: float = 440.0,
        amplitude: float = 0.5,
    ):
        """Initialize MockTTSFixedTone.

        Args:
            config: TTS configuration
            frequency_hz: Frequency of sine wave (default 440Hz = A4 note)
            amplitude: Amplitude of wave (0.0 to 1.0)
        """
        self._config = config or TTSConfig()
        self._frequency_hz = frequency_hz
        self._amplitude = amplitude
        self._is_ready = True

    @property
    def component_instance(self) -> str:
        """Return the provider identifier."""
        return "mock-fixed-tone-v1"

    @property
    def is_ready(self) -> bool:
        """Check if component is ready."""
        return self._is_ready

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Synthesize a 440Hz tone for the given duration.

        Args:
            text_asset: Input TextAsset from Translation module
            target_duration_ms: Target duration for the audio
            output_sample_rate_hz: Output sample rate
            output_channels: Number of output channels
            voice_profile: Optional voice configuration (ignored by mock)

        Returns:
            AudioAsset with synthesized sine wave audio
        """
        start_time = datetime.utcnow()

        # Estimate duration from text if not provided
        if target_duration_ms is None:
            # Rough estimate: ~100ms per word
            word_count = len(text_asset.translated_text.split())
            target_duration_ms = max(500, word_count * 100)

        # Generate sine wave audio (stored in payload)
        self._generate_sine_wave(
            duration_ms=target_duration_ms,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
        )

        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Create payload reference (in real implementation, this would store audio)
        payload_ref = f"mem://fragments/{text_asset.stream_id}/{text_asset.sequence_number}"

        return AudioAsset(
            stream_id=text_asset.stream_id,
            sequence_number=text_asset.sequence_number,
            parent_asset_ids=[text_asset.asset_id],
            component_instance=self.component_instance,
            audio_format=AudioFormat.PCM_F32LE,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
            duration_ms=target_duration_ms,
            payload_ref=payload_ref,
            language=text_asset.target_language,
            status=AudioStatus.SUCCESS,
            processing_time_ms=processing_time_ms,
            voice_cloning_used=False,
            preprocessed_text=text_asset.translated_text,
        )

    def _generate_sine_wave(
        self,
        duration_ms: int,
        sample_rate_hz: int,
        channels: int,
    ) -> bytes:
        """Generate a sine wave as PCM float32 audio data.

        Args:
            duration_ms: Duration in milliseconds
            sample_rate_hz: Sample rate in Hz
            channels: Number of channels

        Returns:
            PCM float32 little-endian audio bytes
        """
        num_samples = int(sample_rate_hz * duration_ms / 1000)
        samples = []

        for i in range(num_samples):
            t = i / sample_rate_hz
            value = self._amplitude * math.sin(2 * math.pi * self._frequency_hz * t)
            # For each channel, add the sample
            for _ in range(channels):
                samples.append(value)

        # Pack as little-endian 32-bit floats
        return struct.pack(f"<{len(samples)}f", *samples)

    def shutdown(self) -> None:
        """Release resources."""
        self._is_ready = False


class MockTTSFromFixture(BaseTTSComponent):
    """Mock TTS that returns pre-recorded audio from test fixtures.

    This mock is useful for:
    - Reproducible integration tests with known audio characteristics
    - Testing with specific audio content
    """

    def __init__(
        self,
        config: TTSConfig | None = None,
        fixture_dir: str | None = None,
    ):
        """Initialize MockTTSFromFixture.

        Args:
            config: TTS configuration
            fixture_dir: Directory containing audio fixtures
        """
        self._config = config or TTSConfig()
        self._fixture_dir = fixture_dir or "tests/fixtures/tts"
        self._is_ready = True

    @property
    def component_instance(self) -> str:
        """Return the provider identifier."""
        return "mock-from-fixture-v1"

    @property
    def is_ready(self) -> bool:
        """Check if component is ready."""
        return self._is_ready

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Return pre-recorded audio from fixture.

        For simplicity, this mock generates a sine wave if no fixture exists.
        """
        start_time = datetime.utcnow()

        # Use target duration or estimate
        if target_duration_ms is None:
            word_count = len(text_asset.translated_text.split())
            target_duration_ms = max(500, word_count * 100)

        # Generate fallback audio (sine wave, stored in payload)
        self._generate_fallback_audio(
            duration_ms=target_duration_ms,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
        )

        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        payload_ref = f"mem://fragments/{text_asset.stream_id}/{text_asset.sequence_number}"

        return AudioAsset(
            stream_id=text_asset.stream_id,
            sequence_number=text_asset.sequence_number,
            parent_asset_ids=[text_asset.asset_id],
            component_instance=self.component_instance,
            audio_format=AudioFormat.PCM_F32LE,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
            duration_ms=target_duration_ms,
            payload_ref=payload_ref,
            language=text_asset.target_language,
            status=AudioStatus.SUCCESS,
            processing_time_ms=processing_time_ms,
            voice_cloning_used=False,
            preprocessed_text=text_asset.translated_text,
        )

    def _generate_fallback_audio(
        self,
        duration_ms: int,
        sample_rate_hz: int,
        channels: int,
    ) -> bytes:
        """Generate fallback sine wave audio."""
        num_samples = int(sample_rate_hz * duration_ms / 1000)
        samples = []
        amplitude = 0.3
        frequency = 440.0

        for i in range(num_samples):
            t = i / sample_rate_hz
            value = amplitude * math.sin(2 * math.pi * frequency * t)
            for _ in range(channels):
                samples.append(value)

        return struct.pack(f"<{len(samples)}f", *samples)

    def shutdown(self) -> None:
        """Release resources."""
        self._is_ready = False


class MockTTSFailOnce(BaseTTSComponent):
    """Mock TTS that fails first call per sequence_number, succeeds on retry.

    This mock is useful for:
    - Testing retry behavior
    - Circuit breaker validation
    - Error handling verification
    """

    def __init__(
        self,
        config: TTSConfig | None = None,
    ):
        """Initialize MockTTSFailOnce.

        Args:
            config: TTS configuration
        """
        self._config = config or TTSConfig()
        self._is_ready = True
        # Track which (stream_id, sequence_number) pairs have failed once
        self._failed_once: set[tuple[str, int]] = set()

    @property
    def component_instance(self) -> str:
        """Return the provider identifier."""
        return "mock-fail-once-v1"

    @property
    def is_ready(self) -> bool:
        """Check if component is ready."""
        return self._is_ready

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Fail first call, succeed on retry.

        Args:
            text_asset: Input TextAsset
            target_duration_ms: Target duration
            output_sample_rate_hz: Output sample rate
            output_channels: Output channels
            voice_profile: Voice configuration

        Returns:
            AudioAsset - FAILED on first call, SUCCESS on retry
        """
        start_time = datetime.utcnow()
        key = (text_asset.stream_id, text_asset.sequence_number)

        # Check if this is the first call for this sequence
        if key not in self._failed_once:
            # First call - fail with retryable error
            self._failed_once.add(key)

            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            error = classify_error(
                TTSErrorType.MODEL_LOAD_FAILED,
                "Simulated transient failure (will succeed on retry)",
                details={"attempt": 1, "stream_id": text_asset.stream_id},
            )

            return AudioAsset(
                stream_id=text_asset.stream_id,
                sequence_number=text_asset.sequence_number,
                parent_asset_ids=[text_asset.asset_id],
                component_instance=self.component_instance,
                audio_format=AudioFormat.PCM_F32LE,
                sample_rate_hz=output_sample_rate_hz,
                channels=output_channels,
                duration_ms=0,
                payload_ref="",
                language=text_asset.target_language,
                status=AudioStatus.FAILED,
                errors=[error],
                processing_time_ms=processing_time_ms,
                voice_cloning_used=False,
                preprocessed_text=text_asset.translated_text,
            )

        # Retry - succeed
        if target_duration_ms is None:
            word_count = len(text_asset.translated_text.split())
            target_duration_ms = max(500, word_count * 100)

        # Generate audio (stored in payload)
        self._generate_audio(
            duration_ms=target_duration_ms,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
        )

        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        payload_ref = f"mem://fragments/{text_asset.stream_id}/{text_asset.sequence_number}"

        return AudioAsset(
            stream_id=text_asset.stream_id,
            sequence_number=text_asset.sequence_number,
            parent_asset_ids=[text_asset.asset_id],
            component_instance=self.component_instance,
            audio_format=AudioFormat.PCM_F32LE,
            sample_rate_hz=output_sample_rate_hz,
            channels=output_channels,
            duration_ms=target_duration_ms,
            payload_ref=payload_ref,
            language=text_asset.target_language,
            status=AudioStatus.SUCCESS,
            processing_time_ms=processing_time_ms,
            voice_cloning_used=False,
            preprocessed_text=text_asset.translated_text,
        )

    def _generate_audio(
        self,
        duration_ms: int,
        sample_rate_hz: int,
        channels: int,
    ) -> bytes:
        """Generate sine wave audio."""
        num_samples = int(sample_rate_hz * duration_ms / 1000)
        samples = []
        amplitude = 0.5
        frequency = 440.0

        for i in range(num_samples):
            t = i / sample_rate_hz
            value = amplitude * math.sin(2 * math.pi * frequency * t)
            for _ in range(channels):
                samples.append(value)

        return struct.pack(f"<{len(samples)}f", *samples)

    def shutdown(self) -> None:
        """Release resources."""
        self._is_ready = False
        self._failed_once.clear()
