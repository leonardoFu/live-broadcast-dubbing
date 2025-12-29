"""Unit tests for Pydantic models in Echo STS Service.

Tests model validation and schema compliance with spec 016.
"""

import base64

import pytest
from pydantic import ValidationError
from sts_service.echo.models.error import (
    ErrorPayload,
    ErrorSimulationConfig,
    ErrorSimulationRule,
)
from sts_service.echo.models.fragment import (
    AudioData,
    BackpressurePayload,
    FragmentAckPayload,
    FragmentDataPayload,
    FragmentMetadata,
    FragmentProcessedPayload,
    StageTimings,
)
from sts_service.echo.models.stream import (
    ServerCapabilities,
    StreamCompletePayload,
    StreamConfigPayload,
    StreamInitPayload,
    StreamReadyPayload,
    StreamStatistics,
)


class TestStreamInitPayload:
    """Tests for StreamInitPayload model."""

    def test_stream_init_payload_schema(self):
        """Validates stream:init structure matches spec 016."""
        payload = StreamInitPayload(
            stream_id="stream-123",
            worker_id="worker-456",
            config=StreamConfigPayload(
                source_language="en",
                target_language="es",
                voice_profile="default",
                chunk_duration_ms=1000,
                sample_rate_hz=48000,
                channels=1,
                format="m4a",
            ),
            max_inflight=3,
            timeout_ms=8000,
        )

        assert payload.stream_id == "stream-123"
        assert payload.worker_id == "worker-456"
        assert payload.config.source_language == "en"
        assert payload.max_inflight == 3
        assert payload.timeout_ms == 8000

    def test_stream_config_validation(self):
        """Validates config field constraints."""
        # Valid config
        config = StreamConfigPayload(
            chunk_duration_ms=1000,
            sample_rate_hz=48000,
            channels=1,
        )
        assert config.chunk_duration_ms == 1000

        # Invalid chunk_duration_ms (too low)
        with pytest.raises(ValidationError):
            StreamConfigPayload(chunk_duration_ms=50)

        # Invalid chunk_duration_ms (too high)
        with pytest.raises(ValidationError):
            StreamConfigPayload(chunk_duration_ms=6000)

        # Invalid channels
        with pytest.raises(ValidationError):
            StreamConfigPayload(channels=3)

    def test_stream_init_max_inflight_validation(self):
        """max_inflight must be between 1 and 10."""
        with pytest.raises(ValidationError):
            StreamInitPayload(
                stream_id="s",
                worker_id="w",
                config=StreamConfigPayload(),
                max_inflight=0,
            )

        with pytest.raises(ValidationError):
            StreamInitPayload(
                stream_id="s",
                worker_id="w",
                config=StreamConfigPayload(),
                max_inflight=11,
            )

    def test_stream_init_timeout_validation(self):
        """timeout_ms must be between 1000 and 30000."""
        with pytest.raises(ValidationError):
            StreamInitPayload(
                stream_id="s",
                worker_id="w",
                config=StreamConfigPayload(),
                timeout_ms=500,
            )


class TestStreamReadyPayload:
    """Tests for StreamReadyPayload model."""

    def test_stream_ready_payload_schema(self):
        """Validates stream:ready response structure."""
        payload = StreamReadyPayload(
            stream_id="stream-123",
            session_id="session-uuid",
            max_inflight=3,
            capabilities=ServerCapabilities(
                batch_processing=False,
                async_delivery=True,
            ),
        )

        assert payload.stream_id == "stream-123"
        assert payload.session_id == "session-uuid"
        assert payload.max_inflight == 3
        assert payload.capabilities.batch_processing is False
        assert payload.capabilities.async_delivery is True

    def test_stream_ready_default_capabilities(self):
        """Default capabilities should be set correctly."""
        payload = StreamReadyPayload(
            stream_id="s",
            session_id="ss",
            max_inflight=3,
        )

        assert payload.capabilities.batch_processing is False
        assert payload.capabilities.async_delivery is True


class TestFragmentDataPayload:
    """Tests for FragmentDataPayload model."""

    def test_fragment_data_payload_schema(self):
        """Validates fragment:data matches spec 016."""
        audio_data = base64.b64encode(b"\x00" * 1000).decode("ascii")

        payload = FragmentDataPayload(
            fragment_id="frag-uuid",
            stream_id="stream-123",
            sequence_number=0,
            timestamp=1703750400000,
            audio=AudioData(
                format="m4a",
                sample_rate_hz=48000,
                channels=1,
                duration_ms=1000,
                data_base64=audio_data,
            ),
            metadata=FragmentMetadata(pts_ns=0, source_pts_ns=0),
        )

        assert payload.fragment_id == "frag-uuid"
        assert payload.sequence_number == 0
        assert payload.audio.sample_rate_hz == 48000

    def test_audio_data_base64_validation(self):
        """Validates audio data constraints."""
        # Valid small audio
        small_audio = base64.b64encode(b"\x00" * 100).decode("ascii")
        audio = AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=1,
            duration_ms=10,
            data_base64=small_audio,
        )
        assert audio.data_base64 == small_audio

    def test_fragment_sequence_number_non_negative(self):
        """sequence_number must be non-negative."""
        with pytest.raises(ValidationError):
            FragmentDataPayload(
                fragment_id="f",
                stream_id="s",
                sequence_number=-1,
                timestamp=0,
                audio=AudioData(
                    format="m4a",
                    sample_rate_hz=48000,
                    channels=1,
                    duration_ms=1000,
                    data_base64="dGVzdA==",
                ),
            )


class TestFragmentProcessedPayload:
    """Tests for FragmentProcessedPayload model."""

    def test_fragment_processed_payload_schema(self):
        """Validates fragment:processed matches spec 016."""
        audio_data = base64.b64encode(b"\x00" * 1000).decode("ascii")

        payload = FragmentProcessedPayload(
            fragment_id="frag-uuid",
            stream_id="stream-123",
            sequence_number=0,
            status="success",
            dubbed_audio=AudioData(
                format="m4a",
                sample_rate_hz=48000,
                channels=1,
                duration_ms=1000,
                data_base64=audio_data,
            ),
            transcript="[ECHO] Original audio",
            translated_text="[ECHO] Audio original",
            processing_time_ms=5,
            stage_timings=StageTimings(asr_ms=1, translation_ms=2, tts_ms=2),
        )

        assert payload.status == "success"
        assert payload.dubbed_audio is not None
        assert payload.processing_time_ms == 5

    def test_fragment_processed_failed_status(self):
        """Failed status should allow error field."""
        payload = FragmentProcessedPayload(
            fragment_id="f",
            stream_id="s",
            sequence_number=0,
            status="failed",
            processing_time_ms=0,
        )

        assert payload.status == "failed"
        assert payload.dubbed_audio is None


class TestFragmentAckPayload:
    """Tests for FragmentAckPayload model."""

    def test_fragment_ack_payload_schema(self):
        """Validates fragment:ack structure."""
        # STS -> Worker ack
        payload = FragmentAckPayload(
            fragment_id="frag-uuid",
            status="queued",
            queue_position=0,
            estimated_completion_ms=100,
        )

        assert payload.status == "queued"
        assert payload.queue_position == 0

        # Worker -> STS ack
        payload2 = FragmentAckPayload(
            fragment_id="frag-uuid",
            status="received",
            timestamp=1703750400000,
        )

        assert payload2.status == "received"


class TestBackpressurePayload:
    """Tests for BackpressurePayload model."""

    def test_backpressure_payload_schema(self):
        """Validates backpressure message matches spec 016."""
        payload = BackpressurePayload(
            stream_id="stream-123",
            severity="medium",
            current_inflight=5,
            queue_depth=3,
            action="slow_down",
            recommended_delay_ms=100,
        )

        assert payload.severity == "medium"
        assert payload.action == "slow_down"

    def test_backpressure_severity_levels(self):
        """low, medium, high values accepted."""
        for severity in ["low", "medium", "high"]:
            payload = BackpressurePayload(
                stream_id="s",
                severity=severity,
                current_inflight=1,
                queue_depth=1,
                action="none",
            )
            assert payload.severity == severity

    def test_backpressure_action_values(self):
        """slow_down, pause, none values accepted."""
        for action in ["slow_down", "pause", "none"]:
            payload = BackpressurePayload(
                stream_id="s",
                severity="low",
                current_inflight=1,
                queue_depth=1,
                action=action,
            )
            assert payload.action == action


class TestErrorSimulationConfig:
    """Tests for ErrorSimulationConfig model."""

    def test_error_simulation_config_schema(self):
        """Validates config:error_simulation payload."""
        config = ErrorSimulationConfig(
            enabled=True,
            rules=[
                ErrorSimulationRule(
                    trigger="sequence_number",
                    value=5,
                    error_code="TIMEOUT",
                    error_message="Simulated timeout",
                    retryable=True,
                    stage="asr",
                ),
            ],
        )

        assert config.enabled is True
        assert len(config.rules) == 1
        assert config.rules[0].error_code == "TIMEOUT"

    def test_error_simulation_rule_schema(self):
        """Validates rule structure."""
        rule = ErrorSimulationRule(
            trigger="nth_fragment",
            value=3,
            error_code="MODEL_ERROR",
            error_message="Every 3rd fragment fails",
            retryable=True,
            stage="tts",
        )

        assert rule.trigger == "nth_fragment"
        assert rule.value == 3

    def test_error_codes_valid(self):
        """All 10 error codes from spec 016 accepted."""
        valid_codes = [
            "AUTH_FAILED",
            "STREAM_NOT_FOUND",
            "INVALID_CONFIG",
            "FRAGMENT_TOO_LARGE",
            "TIMEOUT",
            "MODEL_ERROR",
            "GPU_OOM",
            "QUEUE_FULL",
            "INVALID_SEQUENCE",
            "RATE_LIMIT",
        ]

        for code in valid_codes:
            rule = ErrorSimulationRule(
                trigger="sequence_number",
                value=0,
                error_code=code,
            )
            assert rule.error_code == code

    def test_error_event_structure(self):
        """Validates error event payload."""
        error = ErrorPayload(
            error_id="err-123",
            stream_id="stream-123",
            fragment_id="frag-456",
            code="TIMEOUT",
            message="Processing timeout exceeded",
            severity="error",
            retryable=True,
        )

        assert error.code == "TIMEOUT"
        assert error.retryable is True
        assert error.severity == "error"


class TestStreamCompletePayload:
    """Tests for StreamCompletePayload model."""

    def test_stream_complete_payload_structure(self):
        """Validates stream:complete schema."""
        payload = StreamCompletePayload(
            stream_id="stream-123",
            total_fragments=100,
            total_duration_ms=100000,
            statistics=StreamStatistics(
                success_count=95,
                partial_count=3,
                failed_count=2,
                avg_processing_time_ms=50.5,
                p95_processing_time_ms=120.0,
            ),
        )

        assert payload.total_fragments == 100
        assert payload.statistics.success_count == 95
        assert payload.statistics.avg_processing_time_ms == 50.5
