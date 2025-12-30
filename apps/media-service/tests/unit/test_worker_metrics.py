"""
Unit tests for WorkerMetrics class.

Tests T074-T079 from tasks.md - validating Prometheus metrics.
"""

from __future__ import annotations

from media_service.metrics.prometheus import WorkerMetrics


class TestWorkerMetricsInit:
    """Tests for WorkerMetrics initialization."""

    def test_default_stream_id(self) -> None:
        """Test default stream_id is 'unknown'."""
        metrics = WorkerMetrics()

        assert metrics.stream_id == "unknown"

    def test_custom_stream_id(self) -> None:
        """Test custom stream_id is set."""
        metrics = WorkerMetrics(stream_id="test-stream-123")

        assert metrics.stream_id == "test-stream-123"

    def test_set_stream_id(self) -> None:
        """Test set_stream_id updates stream_id."""
        metrics = WorkerMetrics()

        metrics.set_stream_id("new-stream")

        assert metrics.stream_id == "new-stream"


class TestWorkerMetricsSegments:
    """Tests for segment metrics."""

    def test_record_segment_processed_video(self) -> None:
        """Test recording video segment processed."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_segment_processed("video", 1024)

    def test_record_segment_processed_audio(self) -> None:
        """Test recording audio segment processed."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_segment_processed("audio", 2048)


class TestWorkerMetricsSts:
    """Tests for STS metrics."""

    def test_record_sts_fragment_sent(self) -> None:
        """Test recording STS fragment sent."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_sts_fragment_sent()

    def test_record_sts_fragment_processed_success(self) -> None:
        """Test recording successful STS processing."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_sts_fragment_processed("success", 1.5)

    def test_record_sts_fragment_processed_failed(self) -> None:
        """Test recording failed STS processing."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_sts_fragment_processed("failed", 8.0)

    def test_set_sts_inflight(self) -> None:
        """Test setting STS inflight count."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_sts_inflight(3)


class TestWorkerMetricsCircuitBreaker:
    """Tests for circuit breaker metrics."""

    def test_set_circuit_breaker_state_closed(self) -> None:
        """Test setting circuit breaker to closed."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_circuit_breaker_state(0)

    def test_set_circuit_breaker_state_open(self) -> None:
        """Test setting circuit breaker to open."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_circuit_breaker_state(2)

    def test_record_circuit_breaker_failure(self) -> None:
        """Test recording circuit breaker failure."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_circuit_breaker_failure()

    def test_record_circuit_breaker_fallback(self) -> None:
        """Test recording circuit breaker fallback."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_circuit_breaker_fallback()


class TestWorkerMetricsAvSync:
    """Tests for A/V sync metrics."""

    def test_set_av_sync_delta(self) -> None:
        """Test setting A/V sync delta."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_av_sync_delta(50.5)

    def test_record_av_sync_correction(self) -> None:
        """Test recording A/V sync correction."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_av_sync_correction()

    def test_set_av_buffer_sizes(self) -> None:
        """Test setting A/V buffer sizes."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_av_buffer_sizes(video_size=2, audio_size=1)


class TestWorkerMetricsErrors:
    """Tests for error metrics."""

    def test_record_error(self) -> None:
        """Test recording error by type."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_error("connection_failed")
        metrics.record_error("timeout")
        metrics.record_error("audio_processing")


class TestWorkerMetricsPipeline:
    """Tests for pipeline state metrics."""

    def test_set_pipeline_state_running(self) -> None:
        """Test setting pipeline to running."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_pipeline_state("input", 1)
        metrics.set_pipeline_state("output", 1)

    def test_set_pipeline_state_stopped(self) -> None:
        """Test setting pipeline to stopped."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_pipeline_state("input", 0)
        metrics.set_pipeline_state("output", 0)

    def test_set_pipeline_state_error(self) -> None:
        """Test setting pipeline to error."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_pipeline_state("input", 2)


class TestWorkerMetricsBackpressure:
    """Tests for backpressure metrics."""

    def test_record_backpressure_event_slow_down(self) -> None:
        """Test recording slow_down backpressure event."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_backpressure_event("slow_down")

    def test_record_backpressure_event_pause(self) -> None:
        """Test recording pause backpressure event."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_backpressure_event("pause")

    def test_record_backpressure_event_none(self) -> None:
        """Test recording none (resume) backpressure event."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.record_backpressure_event("none")


class TestWorkerMetricsInfo:
    """Tests for worker info metric."""

    def test_set_worker_info(self) -> None:
        """Test setting worker info."""
        metrics = WorkerMetrics(stream_id="test")

        # Should not raise
        metrics.set_worker_info(version="0.1.0", host="worker-1")
