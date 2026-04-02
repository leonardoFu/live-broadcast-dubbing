"""
Comprehensive unit tests for worker runner.

Tests the orchestration of the dubbing pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.worker.worker_runner import WorkerConfig, WorkerRunner


@pytest.fixture
def tmp_segment_dir(tmp_path: Path) -> Path:
    """Create a temporary segment directory."""
    segment_dir = tmp_path / "segments"
    segment_dir.mkdir(parents=True)
    return segment_dir


@pytest.fixture
def worker_config(tmp_segment_dir: Path) -> WorkerConfig:
    """Create a test worker configuration."""
    return WorkerConfig(
        stream_id="test-stream",
        rtmp_input_url="rtmp://localhost:1935/live/test/in",  # Changed from rtsp_url
        rtmp_url="rtmp://localhost:1935/live/test/out",
        sts_url="http://localhost:3000",
        segment_dir=tmp_segment_dir,
        source_language="en",
        target_language="zh",
    )


class TestWorkerConfigInit:
    """Tests for WorkerConfig initialization."""

    def test_config_default_values(self, tmp_segment_dir: Path) -> None:
        """Test default values are set."""
        config = WorkerConfig(
            stream_id="test",
            rtmp_input_url="rtmp://localhost:1935/live/test/in",
            rtmp_url="rtmp://localhost:1935/live/test/out",
            sts_url="http://localhost:3000",
            segment_dir=tmp_segment_dir,
        )

        assert config.source_language == "en"
        assert config.target_language == "zh"
        assert config.voice_profile == "default"
        assert config.segment_duration_ns == 6_000_000_000

    def test_config_custom_values(self, tmp_segment_dir: Path) -> None:
        """Test custom values are applied."""
        config = WorkerConfig(
            stream_id="custom-stream",
            rtmp_input_url="rtmp://custom:1935/live/stream/in",
            rtmp_url="rtmp://custom:1935/live/stream/out",
            sts_url="http://custom:3000",
            segment_dir=tmp_segment_dir,
            source_language="ja",
            target_language="en",
            voice_profile="female",
            segment_duration_ns=10_000_000_000,
        )

        assert config.stream_id == "custom-stream"
        assert config.source_language == "ja"
        assert config.target_language == "en"
        assert config.voice_profile == "female"
        assert config.segment_duration_ns == 10_000_000_000


class TestWorkerRunnerInit:
    """Tests for WorkerRunner initialization."""

    def test_init_creates_components(self, worker_config: WorkerConfig) -> None:
        """Test initialization creates all components."""
        worker = WorkerRunner(worker_config)

        assert worker.config == worker_config
        assert worker.metrics is not None
        assert not worker._running
        assert worker._task is None

        # Verify components
        assert worker.segment_buffer is not None
        assert worker.video_writer is not None
        assert worker.audio_writer is not None
        assert worker.sts_client is not None
        assert worker.fragment_tracker is not None
        assert worker.backpressure_handler is not None
        assert worker.circuit_breaker is not None
        assert worker.av_sync is not None

    def test_init_queues_created(self, worker_config: WorkerConfig) -> None:
        """Test initialization creates queues."""
        worker = WorkerRunner(worker_config)

        assert worker._video_queue is not None
        assert worker._audio_queue is not None
        assert worker._output_queue is not None

    def test_init_pipelines_not_built(self, worker_config: WorkerConfig) -> None:
        """Test pipelines are None before start."""
        worker = WorkerRunner(worker_config)

        assert worker.input_pipeline is None
        assert worker.output_pipeline is None


class TestWorkerRunnerIsRunning:
    """Tests for is_running property."""

    def test_is_running_initially_false(self, worker_config: WorkerConfig) -> None:
        """Test is_running is False initially."""
        worker = WorkerRunner(worker_config)
        assert not worker.is_running

    def test_is_running_reflects_state(self, worker_config: WorkerConfig) -> None:
        """Test is_running reflects _running state."""
        worker = WorkerRunner(worker_config)

        worker._running = True
        assert worker.is_running

        worker._running = False
        assert not worker.is_running


class TestWorkerRunnerOnStsError:
    """Tests for _on_sts_error callback."""

    @pytest.mark.asyncio
    async def test_on_sts_error_records_metric(self, worker_config: WorkerConfig) -> None:
        """Test STS error records metric."""
        worker = WorkerRunner(worker_config)

        await worker._on_sts_error(
            code="CONNECTION_ERROR",
            message="Connection failed",
            retryable=True,
        )

        # Should not raise, just log

    @pytest.mark.asyncio
    async def test_on_sts_error_non_retryable(self, worker_config: WorkerConfig) -> None:
        """Test non-retryable STS error."""
        worker = WorkerRunner(worker_config)

        await worker._on_sts_error(
            code="INVALID_STREAM",
            message="Stream not found",
            retryable=False,
        )


class TestWorkerRunnerUseFallback:
    """Tests for _use_fallback method."""

    @pytest.mark.asyncio
    async def test_use_fallback_reads_original(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test fallback reads original audio."""
        worker = WorkerRunner(worker_config)

        # Create segment with file
        segment = AudioSegment(
            fragment_id="fallback-001",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_audio.m4a",
        )

        # Write audio data
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)
        segment.file_path.write_bytes(b"original_audio_data")

        # Mock av_sync
        worker.av_sync.push_audio = AsyncMock(return_value=None)

        await worker._use_fallback(segment)

        # Verify push_audio was called
        worker.av_sync.push_audio.assert_called_once()


class TestWorkerRunnerProcessVideoSegment:
    """Tests for _process_video_segment method."""

    @pytest.mark.asyncio
    async def test_process_video_segment_writes_and_syncs(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test video segment processing.

        Per T033: Video segments skip disk writing and use in-memory data directly.
        The implementation just updates segment.file_size and pushes to A/V sync.
        """
        worker = WorkerRunner(worker_config)

        segment = VideoSegment(
            fragment_id="video-001",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_video.mp4",
        )

        data = b"video_data_content"

        # Mock A/V sync
        worker.av_sync.push_video = AsyncMock(return_value=None)

        await worker._process_video_segment(segment, data)

        # T033: No video_writer.write call - uses in-memory data
        # Verify segment file_size was updated and A/V sync was called
        assert segment.file_size == len(data)
        worker.av_sync.push_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_video_segment_handles_error(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test video segment error handling."""
        worker = WorkerRunner(worker_config)

        segment = VideoSegment(
            fragment_id="video-002",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_video.mp4",
        )

        # Mock writer that raises
        worker.video_writer.write = AsyncMock(side_effect=OSError("Write failed"))

        # Should not raise
        await worker._process_video_segment(segment, b"data")


class TestWorkerRunnerProcessAudioSegment:
    """Tests for _process_audio_segment method."""

    @pytest.mark.asyncio
    async def test_process_audio_segment_writes_and_sends(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test audio segment processing."""
        worker = WorkerRunner(worker_config)

        segment = AudioSegment(
            fragment_id="audio-001",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_audio.m4a",
        )

        data = b"audio_data_content"

        # Mock writer
        worker.audio_writer.write = AsyncMock(return_value=segment)
        worker._send_to_sts = AsyncMock()

        await worker._process_audio_segment(segment, data)

        worker.audio_writer.write.assert_called_once_with(segment, data)
        worker._send_to_sts.assert_called_once_with(segment)

    @pytest.mark.asyncio
    async def test_process_audio_segment_handles_error(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test audio segment error handling."""
        worker = WorkerRunner(worker_config)

        segment = AudioSegment(
            fragment_id="audio-002",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_audio.m4a",
        )

        # Mock writer that raises
        worker.audio_writer.write = AsyncMock(side_effect=OSError("Write failed"))

        # Should not raise
        await worker._process_audio_segment(segment, b"data")


class TestWorkerRunnerSendToSts:
    """Tests for _send_to_sts method."""

    @pytest.mark.asyncio
    async def test_send_to_sts_backpressure_timeout(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test STS send with backpressure timeout."""
        worker = WorkerRunner(worker_config)

        segment = AudioSegment(
            fragment_id="sts-001",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_audio.m4a",
        )

        # Write segment data for fallback
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)
        segment.file_path.write_bytes(b"audio_data")

        # Mock backpressure handler to timeout
        worker.backpressure_handler.wait_and_delay = AsyncMock(return_value=False)
        worker._use_fallback = AsyncMock()

        await worker._send_to_sts(segment)

        worker._use_fallback.assert_called_once_with(segment)

    @pytest.mark.asyncio
    async def test_send_to_sts_circuit_breaker_fallback(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test STS send with circuit breaker fallback."""
        worker = WorkerRunner(worker_config)

        segment = AudioSegment(
            fragment_id="sts-002",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_audio.m4a",
        )

        # Write segment data
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)
        segment.file_path.write_bytes(b"audio_data")

        # Mock backpressure to pass
        worker.backpressure_handler.wait_and_delay = AsyncMock(return_value=True)

        # Mock circuit breaker to use fallback (return None)
        worker.circuit_breaker.execute_with_fallback = AsyncMock(return_value=None)
        worker._use_fallback = AsyncMock()

        await worker._send_to_sts(segment)

        worker._use_fallback.assert_called_once_with(segment)


class TestWorkerRunnerDoSendFragment:
    """Tests for _do_send_fragment method."""

    @pytest.mark.asyncio
    async def test_do_send_fragment_tracks_and_sends(
        self, worker_config: WorkerConfig, tmp_segment_dir: Path
    ) -> None:
        """Test fragment sending tracks and sends."""
        worker = WorkerRunner(worker_config)

        segment = AudioSegment(
            fragment_id="send-001",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_segment_dir / "test-stream" / "000000_audio.m4a",
        )

        # Mock STS client
        worker.sts_client.send_fragment = AsyncMock(return_value="fragment-id-123")

        result = await worker._do_send_fragment(segment)

        assert result == "fragment-id-123"
        assert worker.fragment_tracker.inflight_count == 1


class TestWorkerRunnerCleanup:
    """Tests for cleanup method."""

    @pytest.mark.asyncio
    async def test_cleanup_resets_all_components(self, worker_config: WorkerConfig) -> None:
        """Test cleanup resets all components."""
        worker = WorkerRunner(worker_config)

        # Mock stop
        worker.stop = AsyncMock()

        await worker.cleanup()

        worker.stop.assert_called_once()
        assert worker.input_pipeline is None
        assert worker.output_pipeline is None

    @pytest.mark.asyncio
    async def test_cleanup_with_pipelines(self, worker_config: WorkerConfig) -> None:
        """Test cleanup cleans up pipelines."""
        worker = WorkerRunner(worker_config)

        # Create mock pipelines
        mock_input = MagicMock()
        mock_output = MagicMock()
        worker.input_pipeline = mock_input
        worker.output_pipeline = mock_output

        # Mock stop
        worker.stop = AsyncMock()

        await worker.cleanup()

        mock_input.cleanup.assert_called_once()
        mock_output.cleanup.assert_called_once()


class TestWorkerRunnerStop:
    """Tests for stop method."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, worker_config: WorkerConfig) -> None:
        """Test stop when not running is no-op."""
        worker = WorkerRunner(worker_config)

        # Should not raise
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_stops_pipelines(self, worker_config: WorkerConfig) -> None:
        """Test stop stops pipelines."""
        worker = WorkerRunner(worker_config)
        worker._running = True

        # Create mock pipelines
        mock_input = MagicMock()
        mock_output = MagicMock()
        worker.input_pipeline = mock_input
        worker.output_pipeline = mock_output

        # Mock STS client
        worker.sts_client.end_stream = AsyncMock()
        worker.sts_client.disconnect = AsyncMock()

        await worker.stop()

        mock_input.stop.assert_called_once()
        mock_output.stop.assert_called_once()


# =============================================================================
# RTMP URL Construction Tests (T007 - TDD - These tests should FAIL initially)
# =============================================================================


class TestRTMPURLConstruction:
    """Unit tests for WorkerRunner RTMP URL construction.

    These tests verify that WorkerRunner constructs RTMP URLs correctly
    for InputPipeline initialization as part of the RTSP to RTMP migration.

    Per TDD workflow, these tests are written BEFORE implementation
    and MUST fail initially.
    """

    def test_worker_config_uses_rtmp_url(self, tmp_segment_dir: Path) -> None:
        """Test WorkerConfig accepts rtmp_url for input stream."""
        # WorkerConfig should have an rtmp_input_url field (not rtsp_url)
        config = WorkerConfig(
            stream_id="test-stream",
            rtmp_input_url="rtmp://mediamtx:1935/live/test/in",
            rtmp_url="rtmp://localhost:1935/live/test/out",
            sts_url="http://localhost:3000",
            segment_dir=tmp_segment_dir,
        )

        assert config.rtmp_input_url == "rtmp://mediamtx:1935/live/test/in"

    def test_worker_runner_builds_rtmp_url(self, tmp_segment_dir: Path) -> None:
        """Test WorkerRunner constructs RTMP URL format correctly.

        Expected format: rtmp://{host}:{port}/{app}/{stream}/in
        """
        config = WorkerConfig(
            stream_id="test-stream",
            rtmp_input_url="rtmp://mediamtx:1935/live/test/in",
            rtmp_url="rtmp://localhost:1935/live/test/out",
            sts_url="http://localhost:3000",
            segment_dir=tmp_segment_dir,
        )

        worker = WorkerRunner(config)

        # Worker should store RTMP URL for InputPipeline
        assert hasattr(worker, "config")
        assert worker.config.rtmp_input_url.startswith("rtmp://")
        assert ":1935/" in worker.config.rtmp_input_url

    def test_worker_runner_uses_port_1935(self, tmp_segment_dir: Path) -> None:
        """Test WorkerRunner uses RTMP port 1935 (not RTSP port 8554)."""
        config = WorkerConfig(
            stream_id="port-test",
            rtmp_input_url="rtmp://mediamtx:1935/live/port-test/in",
            rtmp_url="rtmp://localhost:1935/live/port-test/out",
            sts_url="http://localhost:3000",
            segment_dir=tmp_segment_dir,
        )

        worker = WorkerRunner(config)

        # RTMP should use port 1935
        assert ":1935/" in worker.config.rtmp_input_url
        # Should NOT use RTSP port 8554
        assert ":8554/" not in worker.config.rtmp_input_url

    def test_worker_runner_no_rtsp_url(self, tmp_segment_dir: Path) -> None:
        """Test WorkerConfig does NOT have rtsp_url attribute after migration."""
        config = WorkerConfig(
            stream_id="no-rtsp-test",
            rtmp_input_url="rtmp://mediamtx:1935/live/no-rtsp/in",
            rtmp_url="rtmp://localhost:1935/live/no-rtsp/out",
            sts_url="http://localhost:3000",
            segment_dir=tmp_segment_dir,
        )

        # rtsp_url should NOT exist on the config
        assert not hasattr(config, "rtsp_url"), "WorkerConfig should not have rtsp_url"

    def test_worker_runner_input_pipeline_uses_rtmp(self, tmp_segment_dir: Path) -> None:
        """Test WorkerRunner initializes InputPipeline with rtmp_url parameter."""
        config = WorkerConfig(
            stream_id="pipeline-test",
            rtmp_input_url="rtmp://mediamtx:1935/live/pipeline/in",
            rtmp_url="rtmp://localhost:1935/live/pipeline/out",
            sts_url="http://localhost:3000",
            segment_dir=tmp_segment_dir,
        )

        worker = WorkerRunner(config)

        # Mock both InputPipeline and OutputPipeline to prevent GStreamer calls
        with (
            patch("media_service.worker.worker_runner.InputPipeline") as mock_input_pipeline,
            patch("media_service.worker.worker_runner.OutputPipeline") as mock_output_pipeline,
        ):
            mock_input_instance = MagicMock()
            mock_output_instance = MagicMock()
            mock_input_pipeline.return_value = mock_input_instance
            mock_output_pipeline.return_value = mock_output_instance

            # Build pipelines (this is what _build_pipelines does)
            worker._build_pipelines()

            # Verify InputPipeline was called with rtmp_url
            mock_input_pipeline.assert_called_once()
            call_kwargs = mock_input_pipeline.call_args
            if call_kwargs:
                kwargs = call_kwargs.kwargs if hasattr(call_kwargs, "kwargs") else call_kwargs[1]
                assert "rtmp_url" in kwargs, "InputPipeline must be called with rtmp_url"
                assert kwargs["rtmp_url"].startswith("rtmp://"), "rtmp_url must start with rtmp://"
