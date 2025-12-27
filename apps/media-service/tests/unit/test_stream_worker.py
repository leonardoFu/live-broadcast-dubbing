"""
Unit tests for Stream Worker.

Tests RTSP URL construction, RTMP publish URL format, and retry logic
for User Story 3: Stream Worker Input/Output via MediaMTX.
"""

from unittest.mock import AsyncMock, patch

import pytest

# Import will fail until implementation exists - this is TDD
# We write tests first, then implement the module


class TestRtspUrlConstruction:
    """Test RTSP URL construction for stream input."""

    def test_rtsp_url_construction_basic(self) -> None:
        """Test basic RTSP URL construction with stream ID."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test-stream",
            mediamtx_host="mediamtx",
        )

        expected = "rtsp://mediamtx:8554/live/test-stream/in"
        assert worker.get_rtsp_input_url() == expected

    def test_rtsp_url_construction_custom_host(self) -> None:
        """Test RTSP URL construction with custom host."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="stream123",
            mediamtx_host="localhost",
        )

        expected = "rtsp://localhost:8554/live/stream123/in"
        assert worker.get_rtsp_input_url() == expected

    def test_rtsp_url_construction_custom_port(self) -> None:
        """Test RTSP URL construction with custom port."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="stream456",
            mediamtx_host="mediamtx",
            rtsp_port=9554,
        )

        expected = "rtsp://mediamtx:9554/live/stream456/in"
        assert worker.get_rtsp_input_url() == expected

    def test_rtsp_url_construction_with_tcp_protocol(self) -> None:
        """Test RTSP URL includes TCP transport option."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
            use_tcp=True,
        )

        # The worker should use TCP transport to avoid UDP packet loss
        assert worker.use_tcp is True
        # URL construction itself doesn't include protocol, but worker config does
        assert worker.get_rtsp_input_url() == "rtsp://mediamtx:8554/live/test/in"

    def test_rtsp_url_construction_special_characters(self) -> None:
        """Test RTSP URL construction with alphanumeric, hyphen, underscore."""
        from media_service.worker.stream_worker import StreamWorker

        # Valid stream IDs per FR-020
        valid_ids = ["stream123", "my-stream", "my_stream", "Stream-123_test"]

        for stream_id in valid_ids:
            worker = StreamWorker(stream_id=stream_id, mediamtx_host="mediamtx")
            url = worker.get_rtsp_input_url()
            assert f"/live/{stream_id}/in" in url

    def test_rtsp_url_construction_invalid_stream_id(self) -> None:
        """Test RTSP URL construction rejects invalid stream IDs."""
        from media_service.worker.stream_worker import InvalidStreamIdError, StreamWorker

        # Invalid stream IDs (special characters not allowed)
        invalid_ids = ["stream/123", "stream with spaces", "stream@123", ""]

        for stream_id in invalid_ids:
            with pytest.raises(InvalidStreamIdError):
                StreamWorker(stream_id=stream_id, mediamtx_host="mediamtx")


class TestRtmpPublishUrlFormat:
    """Test RTMP publish URL construction for stream output."""

    def test_rtmp_publish_url_format_basic(self) -> None:
        """Test basic RTMP publish URL construction."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test-stream",
            mediamtx_host="mediamtx",
        )

        expected = "rtmp://mediamtx:1935/live/test-stream/out"
        assert worker.get_rtmp_output_url() == expected

    def test_rtmp_publish_url_format_custom_host(self) -> None:
        """Test RTMP URL construction with custom host."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="stream789",
            mediamtx_host="192.168.1.100",
        )

        expected = "rtmp://192.168.1.100:1935/live/stream789/out"
        assert worker.get_rtmp_output_url() == expected

    def test_rtmp_publish_url_format_custom_port(self) -> None:
        """Test RTMP URL construction with custom port."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="stream456",
            mediamtx_host="mediamtx",
            rtmp_port=2935,
        )

        expected = "rtmp://mediamtx:2935/live/stream456/out"
        assert worker.get_rtmp_output_url() == expected

    def test_rtmp_publish_url_matches_input_stream(self) -> None:
        """Test RTMP output URL uses same stream ID as RTSP input."""
        from media_service.worker.stream_worker import StreamWorker

        stream_id = "my-unique-stream"
        worker = StreamWorker(stream_id=stream_id, mediamtx_host="mediamtx")

        rtsp_url = worker.get_rtsp_input_url()
        rtmp_url = worker.get_rtmp_output_url()

        # Both should reference the same stream ID
        assert f"/live/{stream_id}/in" in rtsp_url
        assert f"/live/{stream_id}/out" in rtmp_url


class TestWorkerRetryLogic:
    """Test exponential backoff retry logic for RTSP connections."""

    def test_retry_delays_exponential_backoff(self) -> None:
        """Test retry intervals are 1s, 2s, 4s as per spec."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        # Verify exponential backoff delays
        expected_delays = [1.0, 2.0, 4.0]
        assert worker.get_retry_delays() == expected_delays

    def test_max_retries_is_three(self) -> None:
        """Test worker retries exactly 3 times as per spec."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        assert worker.max_retries == 3

    @pytest.mark.asyncio
    async def test_retry_on_connection_failure(self) -> None:
        """Test worker retries on RTSP connection failure."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        # Mock the connection method to fail
        connection_attempts = []

        async def mock_connect() -> None:
            connection_attempts.append(1)
            raise ConnectionError("RTSP connection failed")

        with patch.object(worker, "_connect_rtsp", mock_connect):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await worker.connect_with_retry()

        # Should have attempted 4 times (initial + 3 retries)
        assert len(connection_attempts) == 4
        assert result is False

        # Verify exponential backoff delays were used
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        """Test worker succeeds if connection works on retry."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        # Mock connection to fail first, succeed second
        attempt_count = [0]

        async def mock_connect() -> None:
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ConnectionError("RTSP connection failed")
            # Second attempt succeeds

        with patch.object(worker, "_connect_rtsp", mock_connect):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await worker.connect_with_retry()

        assert result is True
        assert attempt_count[0] == 2

    @pytest.mark.asyncio
    async def test_clean_exit_after_retry_exhaustion(self) -> None:
        """Test worker exits cleanly after all retries exhausted."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        async def mock_connect() -> None:
            raise ConnectionError("RTSP connection failed")

        with patch.object(worker, "_connect_rtsp", mock_connect):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await worker.connect_with_retry()

        # Worker should return False (clean exit) not raise exception
        assert result is False
        assert worker.state == "stopped"


class TestWorkerState:
    """Test worker state management."""

    def test_initial_state_is_idle(self) -> None:
        """Test worker starts in idle state."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        assert worker.state == "idle"

    def test_worker_state_transitions(self) -> None:
        """Test valid worker state transitions."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )

        # idle -> connecting
        worker.set_state("connecting")
        assert worker.state == "connecting"

        # connecting -> running
        worker.set_state("running")
        assert worker.state == "running"

        # running -> stopped
        worker.set_state("stopped")
        assert worker.state == "stopped"

    def test_worker_config_properties(self) -> None:
        """Test worker configuration properties."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
            rtsp_port=8554,
            rtmp_port=1935,
            use_tcp=True,
        )

        assert worker.stream_id == "test"
        assert worker.mediamtx_host == "mediamtx"
        assert worker.rtsp_port == 8554
        assert worker.rtmp_port == 1935
        assert worker.use_tcp is True


class TestWorkerPassthrough:
    """Test worker passthrough pipeline functionality."""

    @pytest.mark.asyncio
    async def test_worker_passthrough_pipeline_creates_correct_urls(self) -> None:
        """Test passthrough pipeline uses correct input/output URLs."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="stream456",
            mediamtx_host="mediamtx",
        )

        # Get pipeline configuration
        config = worker.get_pipeline_config()

        assert config["input_url"] == "rtsp://mediamtx:8554/live/stream456/in"
        assert config["output_url"] == "rtmp://mediamtx:1935/live/stream456/out"
        assert config["mode"] == "passthrough"

    @pytest.mark.asyncio
    async def test_worker_stop_sets_state_to_stopped(self) -> None:
        """Test stop method sets worker state to stopped."""
        from media_service.worker.stream_worker import StreamWorker

        worker = StreamWorker(
            stream_id="test",
            mediamtx_host="mediamtx",
        )
        worker.set_state("running")

        await worker.stop()

        assert worker.state == "stopped"


class TestStreamWorkerFactory:
    """Test StreamWorker factory function."""

    def test_create_worker_from_ready_event(self) -> None:
        """Test creating worker from ReadyEvent."""
        from media_service.models.events import ReadyEvent
        from media_service.worker.stream_worker import create_worker_from_event

        event = ReadyEvent(
            path="live/my-stream/in",
            sourceType="rtmp",
            sourceId="1",
        )

        worker = create_worker_from_event(event, mediamtx_host="mediamtx")

        assert worker.stream_id == "my-stream"
        assert worker.get_rtsp_input_url() == "rtsp://mediamtx:8554/live/my-stream/in"
        assert worker.get_rtmp_output_url() == "rtmp://mediamtx:1935/live/my-stream/out"

    def test_create_worker_with_custom_config(self) -> None:
        """Test creating worker with custom MediaMTX configuration."""
        from media_service.models.events import ReadyEvent
        from media_service.worker.stream_worker import create_worker_from_event

        event = ReadyEvent(
            path="live/test123/in",
            sourceType="rtmp",
            sourceId="1",
        )

        worker = create_worker_from_event(
            event,
            mediamtx_host="custom-host",
            rtsp_port=9554,
            rtmp_port=2935,
            use_tcp=True,
        )

        assert worker.mediamtx_host == "custom-host"
        assert worker.rtsp_port == 9554
        assert worker.rtmp_port == 2935
        assert worker.use_tcp is True
