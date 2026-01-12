"""Unit tests for Full STS Service Pydantic models.

Tests T015-T021: Validate Pydantic models match JSON schemas.
"""

import pytest
from pydantic import ValidationError
from sts_service.full.models import (
    AckStatus,
    AudioData,
    BackpressureAction,
    BackpressurePayload,
    BackpressureSeverity,
    ErrorResponse,
    FragmentAckPayload,
    FragmentDataPayload,
    FragmentMetadata,
    FragmentProcessedPayload,
    PipelineStage,
    ProcessingError,
    ProcessingStatus,
    StageTiming,
    StreamConfig,
    StreamSession,
    StreamState,
    StreamStatistics,
)


class TestAudioData:
    """Test AudioData model."""

    def test_valid_audio_data(self) -> None:
        """Test valid audio data creation."""
        audio = AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=1,
            duration_ms=6000,
            data_base64="AQIDBAU=",
        )
        assert audio.format == "m4a"
        assert audio.sample_rate_hz == 48000
        assert audio.channels == 1
        assert audio.duration_ms == 6000

    def test_invalid_sample_rate(self) -> None:
        """Test validation of sample rate range."""
        with pytest.raises(ValidationError):
            AudioData(
                format="m4a",
                sample_rate_hz=1000,  # Below 8000 minimum
                channels=1,
                duration_ms=6000,
                data_base64="AQIDBAU=",
            )

    def test_invalid_channels(self) -> None:
        """Test validation of channels range."""
        with pytest.raises(ValidationError):
            AudioData(
                format="m4a",
                sample_rate_hz=48000,
                channels=3,  # Above 2 maximum
                duration_ms=6000,
                data_base64="AQIDBAU=",
            )


class TestFragmentDataPayload:
    """Test FragmentDataPayload model."""

    def test_valid_fragment_data(self) -> None:
        """Test valid fragment data creation."""
        fragment = FragmentDataPayload(
            fragment_id="550e8400-e29b-41d4-a716-446655440000",
            stream_id="stream-abc-123",
            sequence_number=0,
            timestamp=1704067200000,
            audio=AudioData(
                format="m4a",
                sample_rate_hz=48000,
                channels=1,
                duration_ms=6000,
                data_base64="AQIDBAU=",
            ),
        )
        assert fragment.fragment_id == "550e8400-e29b-41d4-a716-446655440000"
        assert fragment.stream_id == "stream-abc-123"
        assert fragment.sequence_number == 0

    def test_with_optional_metadata(self) -> None:
        """Test fragment with optional metadata."""
        fragment = FragmentDataPayload(
            fragment_id="test-id",
            stream_id="stream-id",
            sequence_number=1,
            timestamp=1704067200000,
            audio=AudioData(
                format="m4a",
                sample_rate_hz=48000,
                channels=1,
                duration_ms=6000,
                data_base64="AQIDBAU=",
            ),
            metadata=FragmentMetadata(pts_ns=123456789),
        )
        assert fragment.metadata is not None
        assert fragment.metadata.pts_ns == 123456789

    def test_missing_required_fields(self) -> None:
        """Test that missing required fields raise error."""
        with pytest.raises(ValidationError):
            FragmentDataPayload(
                fragment_id="test-id",
                # Missing stream_id, sequence_number, timestamp, audio
            )


class TestFragmentAckPayload:
    """Test FragmentAckPayload model."""

    def test_valid_ack_payload(self) -> None:
        """Test valid acknowledgment payload."""
        ack = FragmentAckPayload(
            fragment_id="550e8400-e29b-41d4-a716-446655440000",
            status=AckStatus.QUEUED,
            timestamp=1704067200000,
        )
        assert ack.fragment_id == "550e8400-e29b-41d4-a716-446655440000"
        assert ack.status == AckStatus.QUEUED

    def test_with_queue_position(self) -> None:
        """Test ack with optional queue position."""
        ack = FragmentAckPayload(
            fragment_id="test-id",
            status=AckStatus.QUEUED,
            timestamp=1704067200000,
            queue_position=3,
            estimated_completion_ms=5000,
        )
        assert ack.queue_position == 3
        assert ack.estimated_completion_ms == 5000


class TestStageTiming:
    """Test StageTiming model."""

    def test_stage_timing_creation(self) -> None:
        """Test stage timing creation."""
        timing = StageTiming(asr_ms=1200, translation_ms=150, tts_ms=3100)
        assert timing.asr_ms == 1200
        assert timing.translation_ms == 150
        assert timing.tts_ms == 3100

    def test_total_ms_property(self) -> None:
        """Test total_ms calculated property."""
        timing = StageTiming(asr_ms=1200, translation_ms=150, tts_ms=3100)
        assert timing.total_ms == 4450

    def test_default_values(self) -> None:
        """Test default values are zero."""
        timing = StageTiming()
        assert timing.asr_ms == 0
        assert timing.translation_ms == 0
        assert timing.tts_ms == 0
        assert timing.total_ms == 0


class TestProcessingError:
    """Test ProcessingError model."""

    def test_processing_error_creation(self) -> None:
        """Test processing error creation."""
        error = ProcessingError(
            stage=PipelineStage.ASR,
            code="TIMEOUT",
            message="ASR processing timed out after 5000ms",
            retryable=True,
        )
        assert error.stage == PipelineStage.ASR
        assert error.code == "TIMEOUT"
        assert error.retryable is True

    def test_error_stage_enum(self) -> None:
        """Test all pipeline stages can be used."""
        for stage in PipelineStage:
            error = ProcessingError(
                stage=stage,
                code="TEST",
                message="Test error",
                retryable=False,
            )
            assert error.stage == stage


class TestFragmentProcessedPayload:
    """Test FragmentProcessedPayload model."""

    def test_success_payload(self) -> None:
        """Test successful processing payload."""
        payload = FragmentProcessedPayload(
            fragment_id="test-id",
            stream_id="stream-id",
            sequence_number=0,
            status=ProcessingStatus.SUCCESS,
            processing_time_ms=4500,
            dubbed_audio=AudioData(
                format="pcm_s16le",
                sample_rate_hz=48000,
                channels=1,
                duration_ms=6050,
                data_base64="AQIDBAU=",
            ),
            transcript="Hello world",
            translated_text="Hola mundo",
        )
        assert payload.status == ProcessingStatus.SUCCESS
        assert payload.dubbed_audio is not None
        assert payload.dubbed_audio.format == "pcm_s16le"

    def test_failed_payload_with_error(self) -> None:
        """Test failed processing payload with error."""
        payload = FragmentProcessedPayload(
            fragment_id="test-id",
            stream_id="stream-id",
            sequence_number=0,
            status=ProcessingStatus.FAILED,
            processing_time_ms=5100,
            error=ProcessingError(
                stage=PipelineStage.ASR,
                code="TIMEOUT",
                message="ASR processing timed out",
                retryable=True,
            ),
        )
        assert payload.status == ProcessingStatus.FAILED
        assert payload.dubbed_audio is None
        assert payload.error is not None
        assert payload.error.code == "TIMEOUT"

    def test_partial_payload_with_warning(self) -> None:
        """Test partial processing payload."""
        payload = FragmentProcessedPayload(
            fragment_id="test-id",
            stream_id="stream-id",
            sequence_number=0,
            status=ProcessingStatus.PARTIAL,
            processing_time_ms=4500,
            dubbed_audio=AudioData(
                format="pcm_s16le",
                sample_rate_hz=48000,
                channels=1,
                duration_ms=12000,  # Exceeded target
                data_base64="AQIDBAU=",
            ),
            error=ProcessingError(
                stage=PipelineStage.TTS,
                code="DURATION_MISMATCH_EXCEEDED",
                message="Duration variance exceeded 10%",
                retryable=False,
            ),
        )
        assert payload.status == ProcessingStatus.PARTIAL
        assert payload.dubbed_audio is not None
        assert payload.error is not None


class TestStreamConfig:
    """Test StreamConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = StreamConfig()
        assert config.source_language == "en"
        assert config.target_language == "es"
        assert config.voice_profile == "default"
        assert config.chunk_duration_ms == 6000
        assert config.sample_rate_hz == 48000
        assert config.channels == 1
        assert config.format == "m4a"

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = StreamConfig(
            source_language="en",
            target_language="fr",
            voice_profile="french_female_1",
            chunk_duration_ms=3000,
            sample_rate_hz=24000,
            channels=2,
            domain_hints=["sports", "commentary"],
        )
        assert config.target_language == "fr"
        assert config.domain_hints == ["sports", "commentary"]


class TestStreamSessionUsage:
    """Test StreamSession model for stream lifecycle."""

    def test_valid_stream_session_init(self) -> None:
        """Test valid stream session initialization."""
        session = StreamSession(
            stream_id="stream-abc-123",
            session_id="session-xyz-789",
            worker_id="worker-001",
            socket_id="socket-001",
            config=StreamConfig(
                source_language="en",
                target_language="es",
                voice_profile="spanish_male_1",
            ),
        )
        assert session.stream_id == "stream-abc-123"
        assert session.worker_id == "worker-001"
        assert session.max_inflight == 3  # default
        assert session.timeout_ms == 8000  # default

    def test_custom_inflight_and_timeout(self) -> None:
        """Test custom max_inflight and timeout."""
        session = StreamSession(
            stream_id="stream-id",
            session_id="session-id",
            worker_id="worker-id",
            socket_id="socket-id",
            config=StreamConfig(),
            max_inflight=5,
            timeout_ms=10000,
        )
        assert session.max_inflight == 5
        assert session.timeout_ms == 10000

    def test_stream_state_transitions(self) -> None:
        """Test stream state values."""
        session = StreamSession(
            stream_id="stream-abc-123",
            session_id="session-xyz-789",
            worker_id="worker-001",
            socket_id="socket-001",
            config=StreamConfig(),
            state=StreamState.READY,
        )
        assert session.stream_id == "stream-abc-123"
        assert session.session_id == "session-xyz-789"
        assert session.state == StreamState.READY

    def test_paused_state(self) -> None:
        """Test session in paused state."""
        session = StreamSession(
            stream_id="stream-id",
            session_id="session-id",
            worker_id="worker-id",
            socket_id="socket-id",
            config=StreamConfig(),
            state=StreamState.PAUSED,
        )
        assert session.state == StreamState.PAUSED

    def test_ending_state(self) -> None:
        """Test session in ending state."""
        session = StreamSession(
            stream_id="stream-id",
            session_id="session-id",
            worker_id="worker-id",
            socket_id="socket-id",
            config=StreamConfig(),
            state=StreamState.ENDING,
        )
        assert session.state == StreamState.ENDING


class TestStreamStatistics:
    """Test StreamStatistics model (was StreamCompletePayload)."""

    def test_valid_stream_statistics(self) -> None:
        """Test valid stream statistics."""
        stats = StreamStatistics(
            total_fragments=50,
            success_count=45,
            partial_count=3,
            failed_count=2,
            avg_processing_time_ms=4500.0,
            p95_processing_time_ms=6200.0,
            total_audio_duration_ms=300000,
        )
        assert stats.total_fragments == 50
        assert stats.success_count == 45
        assert stats.failed_count == 2

    def test_success_rate_property(self) -> None:
        """Test success rate calculation."""
        stats = StreamStatistics(
            total_fragments=100,
            success_count=90,
            partial_count=5,
            failed_count=5,
            avg_processing_time_ms=4500.0,
            p95_processing_time_ms=6200.0,
            total_audio_duration_ms=600000,
        )
        assert stats.success_rate == 90.0


class TestBackpressurePayload:
    """Test BackpressurePayload model."""

    def test_low_severity_backpressure(self) -> None:
        """Test low severity backpressure."""
        payload = BackpressurePayload(
            stream_id="stream-id",
            severity=BackpressureSeverity.LOW,
            action=BackpressureAction.NONE,
            current_inflight=2,
            max_inflight=3,
            threshold_exceeded=None,
        )
        assert payload.severity == BackpressureSeverity.LOW
        assert payload.action == BackpressureAction.NONE

    def test_high_severity_backpressure(self) -> None:
        """Test high severity backpressure."""
        payload = BackpressurePayload(
            stream_id="stream-id",
            severity=BackpressureSeverity.HIGH,
            action=BackpressureAction.PAUSE,
            current_inflight=9,
            max_inflight=3,
            threshold_exceeded="high",
            recommended_delay_ms=2000,
        )
        assert payload.severity == BackpressureSeverity.HIGH
        assert payload.action == BackpressureAction.PAUSE
        assert payload.recommended_delay_ms == 2000


class TestErrorResponse:
    """Test ErrorResponse model."""

    def test_basic_error_response(self) -> None:
        """Test basic error response."""
        error = ErrorResponse(
            code="STREAM_NOT_FOUND",
            message="Stream stream-abc-123 not found",
            retryable=False,
        )
        assert error.code == "STREAM_NOT_FOUND"
        assert error.retryable is False
        assert error.stage is None

    def test_error_with_stage(self) -> None:
        """Test error response with pipeline stage."""
        error = ErrorResponse(
            code="TIMEOUT",
            message="ASR processing timed out",
            retryable=True,
            stage=PipelineStage.ASR,
            details={"elapsed_ms": 5234, "deadline_ms": 5000},
        )
        assert error.stage == PipelineStage.ASR
        assert error.details is not None
        assert error.details["elapsed_ms"] == 5234


class TestStreamSession:
    """Test StreamSession model (was SessionInfo)."""

    def test_session_creation(self) -> None:
        """Test session creation."""
        session = StreamSession(
            stream_id="stream-id",
            session_id="session-id",
            worker_id="worker-id",
            socket_id="socket-id",
            config=StreamConfig(),
        )
        assert session.stream_id == "stream-id"
        assert session.state == StreamState.INITIALIZING
        assert session.fragments_received == 0
        assert session.current_inflight == 0

    def test_avg_processing_time(self) -> None:
        """Test average processing time calculation."""
        session = StreamSession(
            stream_id="stream-id",
            session_id="session-id",
            worker_id="worker-id",
            socket_id="socket-id",
            config=StreamConfig(),
            fragments_processed=10,
            total_processing_time_ms=45000,
        )
        assert session.avg_processing_time_ms == 4500.0

    def test_avg_processing_time_zero_fragments(self) -> None:
        """Test average processing time with zero fragments."""
        session = StreamSession(
            stream_id="stream-id",
            session_id="session-id",
            worker_id="worker-id",
            socket_id="socket-id",
            config=StreamConfig(),
        )
        assert session.avg_processing_time_ms == 0.0


class TestEnums:
    """Test enum definitions."""

    def test_pipeline_stages(self) -> None:
        """Test all pipeline stages exist."""
        assert PipelineStage.ASR.value == "asr"
        assert PipelineStage.TRANSLATION.value == "translation"
        assert PipelineStage.TTS.value == "tts"

    def test_processing_status(self) -> None:
        """Test all processing statuses exist."""
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.PARTIAL.value == "partial"
        assert ProcessingStatus.FAILED.value == "failed"

    def test_stream_states(self) -> None:
        """Test all stream states exist."""
        assert StreamState.INITIALIZING.value == "initializing"
        assert StreamState.READY.value == "ready"
        assert StreamState.PAUSED.value == "paused"
        assert StreamState.ENDING.value == "ending"
        assert StreamState.COMPLETED.value == "completed"

    def test_backpressure_severities(self) -> None:
        """Test all backpressure severities exist."""
        assert BackpressureSeverity.LOW.value == "low"
        assert BackpressureSeverity.MEDIUM.value == "medium"
        assert BackpressureSeverity.HIGH.value == "high"

    def test_backpressure_actions(self) -> None:
        """Test all backpressure actions exist."""
        assert BackpressureAction.NONE.value == "none"
        assert BackpressureAction.SLOW_DOWN.value == "slow_down"
        assert BackpressureAction.PAUSE.value == "pause"
