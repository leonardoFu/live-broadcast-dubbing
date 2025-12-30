"""
Unit tests for STS data models.

Tests T015 and T016 from tasks.md - validating STS models.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from unittest.mock import MagicMock

from media_service.sts.models import (
    AudioData,
    BackpressurePayload,
    FragmentDataPayload,
    FragmentMetadata,
    FragmentProcessedPayload,
    InFlightFragment,
    ProcessingError,
    StageTimings,
    StreamConfig,
)


class TestStreamConfig:
    """Tests for StreamConfig data model (T015)."""

    def test_default_values(self) -> None:
        """Test StreamConfig default values."""
        config = StreamConfig()

        assert config.source_language == "en"
        assert config.target_language == "es"
        assert config.voice_profile == "default"
        assert config.format == "m4a"
        assert config.sample_rate_hz == 48000
        assert config.channels == 2
        assert config.chunk_duration_ms == 6000

    def test_custom_values(self) -> None:
        """Test StreamConfig with custom values."""
        config = StreamConfig(
            source_language="en-US",
            target_language="es-ES",
            voice_profile="female_1",
            format="m4a",
            sample_rate_hz=44100,
            channels=1,
            chunk_duration_ms=3000,
        )

        assert config.source_language == "en-US"
        assert config.target_language == "es-ES"
        assert config.voice_profile == "female_1"
        assert config.sample_rate_hz == 44100
        assert config.channels == 1
        assert config.chunk_duration_ms == 3000

    def test_to_dict(self) -> None:
        """Test StreamConfig serialization to dict."""
        config = StreamConfig(
            source_language="en",
            target_language="fr",
        )

        result = config.to_dict()

        assert result["source_language"] == "en"
        assert result["target_language"] == "fr"
        assert result["format"] == "m4a"
        assert result["sample_rate_hz"] == 48000
        assert result["channels"] == 2


class TestInFlightFragment:
    """Tests for InFlightFragment data model (T016)."""

    def test_create_inflight_fragment(self) -> None:
        """Test creating InFlightFragment."""
        mock_segment = MagicMock()
        mock_segment.fragment_id = "frag-001"

        sent_time = time.monotonic()
        inflight = InFlightFragment(
            fragment_id="frag-001",
            segment=mock_segment,
            sent_time=sent_time,
            sequence_number=0,
        )

        assert inflight.fragment_id == "frag-001"
        assert inflight.segment == mock_segment
        assert inflight.sent_time == sent_time
        assert inflight.sequence_number == 0
        assert inflight.timeout_task is None

    def test_elapsed_ms_property(self) -> None:
        """Test elapsed_ms calculation."""
        mock_segment = MagicMock()

        # Set sent_time to 500ms ago
        sent_time = time.monotonic() - 0.5
        inflight = InFlightFragment(
            fragment_id="frag-001",
            segment=mock_segment,
            sent_time=sent_time,
            sequence_number=0,
        )

        # Elapsed should be approximately 500ms (with some tolerance)
        elapsed = inflight.elapsed_ms
        assert 450 <= elapsed <= 600  # Allow for timing variance

    def test_with_timeout_task(self) -> None:
        """Test InFlightFragment with timeout task."""
        mock_segment = MagicMock()
        mock_task = MagicMock()

        inflight = InFlightFragment(
            fragment_id="frag-001",
            segment=mock_segment,
            sent_time=time.monotonic(),
            sequence_number=5,
            timeout_task=mock_task,
        )

        assert inflight.timeout_task == mock_task


class TestAudioData:
    """Tests for AudioData model."""

    def test_from_bytes(self) -> None:
        """Test creating AudioData from bytes."""
        data = b"test audio data"

        audio = AudioData.from_bytes(
            data=data,
            duration_ms=6000,
            sample_rate_hz=48000,
            channels=2,
        )

        assert audio.format == "m4a"
        assert audio.sample_rate_hz == 48000
        assert audio.channels == 2
        assert audio.duration_ms == 6000
        assert audio.data_base64 == base64.b64encode(data).decode()

    def test_from_m4a_file(self, tmp_path: Path) -> None:
        """Test creating AudioData from M4A file."""
        file_path = tmp_path / "test.m4a"
        test_data = b"m4a file content"
        file_path.write_bytes(test_data)

        audio = AudioData.from_m4a_file(file_path, duration_ms=6000)

        assert audio.format == "m4a"
        assert audio.duration_ms == 6000
        assert audio.decode_audio() == test_data

    def test_decode_audio(self) -> None:
        """Test decoding base64 audio data."""
        original_data = b"original audio bytes"
        audio = AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=2,
            duration_ms=6000,
            data_base64=base64.b64encode(original_data).decode(),
        )

        decoded = audio.decode_audio()
        assert decoded == original_data

    def test_to_dict(self) -> None:
        """Test AudioData serialization to dict."""
        audio = AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=2,
            duration_ms=6000,
            data_base64="dGVzdA==",
        )

        result = audio.to_dict()

        assert result["format"] == "m4a"
        assert result["sample_rate_hz"] == 48000
        assert result["channels"] == 2
        assert result["duration_ms"] == 6000
        assert result["data_base64"] == "dGVzdA=="


class TestFragmentDataPayload:
    """Tests for FragmentDataPayload model."""

    def test_to_dict(self) -> None:
        """Test FragmentDataPayload serialization."""
        audio = AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=2,
            duration_ms=6000,
            data_base64="dGVzdA==",
        )
        metadata = FragmentMetadata(pts_ns=1_000_000_000)

        payload = FragmentDataPayload(
            fragment_id="frag-001",
            stream_id="test-stream",
            sequence_number=0,
            timestamp=1234567890,
            audio=audio,
            metadata=metadata,
        )

        result = payload.to_dict()

        assert result["fragment_id"] == "frag-001"
        assert result["stream_id"] == "test-stream"
        assert result["sequence_number"] == 0
        assert result["timestamp"] == 1234567890
        assert result["audio"]["format"] == "m4a"
        assert result["metadata"]["pts_ns"] == 1_000_000_000

    def test_to_dict_without_metadata(self) -> None:
        """Test FragmentDataPayload without metadata."""
        audio = AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=2,
            duration_ms=6000,
            data_base64="dGVzdA==",
        )

        payload = FragmentDataPayload(
            fragment_id="frag-001",
            stream_id="test-stream",
            sequence_number=0,
            timestamp=1234567890,
            audio=audio,
        )

        result = payload.to_dict()

        assert "metadata" not in result


class TestFragmentProcessedPayload:
    """Tests for FragmentProcessedPayload model."""

    def test_from_dict_success(self) -> None:
        """Test creating FragmentProcessedPayload from success response."""
        data = {
            "fragment_id": "frag-001",
            "stream_id": "test-stream",
            "sequence_number": 0,
            "status": "success",
            "dubbed_audio": {
                "format": "m4a",
                "sample_rate_hz": 48000,
                "channels": 2,
                "duration_ms": 6000,
                "data_base64": "dGVzdA==",
            },
            "transcript": "Hello world",
            "translated_text": "Hola mundo",
            "processing_time_ms": 1500,
            "stage_timings": {
                "asr_ms": 500,
                "translation_ms": 200,
                "tts_ms": 800,
            },
        }

        payload = FragmentProcessedPayload.from_dict(data)

        assert payload.fragment_id == "frag-001"
        assert payload.status == "success"
        assert payload.is_success is True
        assert payload.is_failed is False
        assert payload.dubbed_audio is not None
        assert payload.dubbed_audio.format == "m4a"
        assert payload.transcript == "Hello world"
        assert payload.translated_text == "Hola mundo"
        assert payload.processing_time_ms == 1500
        assert payload.stage_timings is not None
        assert payload.stage_timings.asr_ms == 500

    def test_from_dict_failed(self) -> None:
        """Test creating FragmentProcessedPayload from failed response."""
        data = {
            "fragment_id": "frag-001",
            "stream_id": "test-stream",
            "sequence_number": 0,
            "status": "failed",
            "error": {
                "code": "TIMEOUT",
                "message": "Processing timed out",
                "retryable": True,
            },
        }

        payload = FragmentProcessedPayload.from_dict(data)

        assert payload.status == "failed"
        assert payload.is_success is False
        assert payload.is_failed is True
        assert payload.dubbed_audio is None
        assert payload.error is not None
        assert payload.error.code == "TIMEOUT"
        assert payload.error.retryable is True

    def test_from_dict_partial(self) -> None:
        """Test creating FragmentProcessedPayload from partial response."""
        data = {
            "fragment_id": "frag-001",
            "stream_id": "test-stream",
            "sequence_number": 0,
            "status": "partial",
            "dubbed_audio": {
                "format": "m4a",
                "sample_rate_hz": 48000,
                "channels": 2,
                "duration_ms": 3000,  # Only partial audio
                "data_base64": "dGVzdA==",
            },
        }

        payload = FragmentProcessedPayload.from_dict(data)

        assert payload.status == "partial"
        assert payload.is_partial is True
        assert payload.dubbed_audio is not None


class TestBackpressurePayload:
    """Tests for BackpressurePayload model."""

    def test_from_dict_slow_down(self) -> None:
        """Test creating BackpressurePayload for slow_down action."""
        data = {
            "stream_id": "test-stream",
            "severity": "medium",
            "current_inflight": 3,
            "queue_depth": 10,
            "action": "slow_down",
            "recommended_delay_ms": 500,
        }

        payload = BackpressurePayload.from_dict(data)

        assert payload.stream_id == "test-stream"
        assert payload.severity == "medium"
        assert payload.action == "slow_down"
        assert payload.recommended_delay_ms == 500

    def test_from_dict_pause(self) -> None:
        """Test creating BackpressurePayload for pause action."""
        data = {
            "stream_id": "test-stream",
            "severity": "high",
            "current_inflight": 5,
            "queue_depth": 20,
            "action": "pause",
        }

        payload = BackpressurePayload.from_dict(data)

        assert payload.action == "pause"
        assert payload.severity == "high"
        assert payload.recommended_delay_ms == 0  # Default

    def test_from_dict_none(self) -> None:
        """Test creating BackpressurePayload for none action (resume)."""
        data = {
            "stream_id": "test-stream",
            "severity": "low",
            "current_inflight": 1,
            "queue_depth": 0,
            "action": "none",
        }

        payload = BackpressurePayload.from_dict(data)

        assert payload.action == "none"


class TestFragmentMetadata:
    """Tests for FragmentMetadata model."""

    def test_to_dict_basic(self) -> None:
        """Test FragmentMetadata with only pts_ns."""
        metadata = FragmentMetadata(pts_ns=1_000_000_000)

        result = metadata.to_dict()

        assert result["pts_ns"] == 1_000_000_000
        assert "source_pts_ns" not in result

    def test_to_dict_with_source_pts(self) -> None:
        """Test FragmentMetadata with source_pts_ns."""
        metadata = FragmentMetadata(
            pts_ns=1_000_000_000,
            source_pts_ns=900_000_000,
        )

        result = metadata.to_dict()

        assert result["pts_ns"] == 1_000_000_000
        assert result["source_pts_ns"] == 900_000_000


class TestStageTimings:
    """Tests for StageTimings model."""

    def test_from_dict(self) -> None:
        """Test creating StageTimings from dict."""
        data = {
            "asr_ms": 500,
            "translation_ms": 200,
            "tts_ms": 800,
        }

        timings = StageTimings.from_dict(data)

        assert timings.asr_ms == 500
        assert timings.translation_ms == 200
        assert timings.tts_ms == 800

    def test_from_dict_partial(self) -> None:
        """Test creating StageTimings with missing fields."""
        data = {"asr_ms": 500}

        timings = StageTimings.from_dict(data)

        assert timings.asr_ms == 500
        assert timings.translation_ms == 0
        assert timings.tts_ms == 0


class TestProcessingError:
    """Tests for ProcessingError model."""

    def test_from_dict(self) -> None:
        """Test creating ProcessingError from dict."""
        data = {
            "code": "TIMEOUT",
            "message": "Processing timed out",
            "retryable": True,
        }

        error = ProcessingError.from_dict(data)

        assert error.code == "TIMEOUT"
        assert error.message == "Processing timed out"
        assert error.retryable is True

    def test_from_dict_non_retryable(self) -> None:
        """Test creating non-retryable ProcessingError."""
        data = {
            "code": "INVALID_CONFIG",
            "message": "Invalid configuration",
            "retryable": False,
        }

        error = ProcessingError.from_dict(data)

        assert error.code == "INVALID_CONFIG"
        assert error.retryable is False

    def test_from_dict_defaults(self) -> None:
        """Test ProcessingError with missing fields uses defaults."""
        data = {}

        error = ProcessingError.from_dict(data)

        assert error.code == "UNKNOWN"
        assert error.message == "Unknown error"
        assert error.retryable is False
