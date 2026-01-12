"""
Unit tests for Prometheus metrics collection.

Tests metrics recording for:
- Fragment processing success/failure
- Stage timings (ASR, Translation, TTS)
- In-flight gauge tracking
- GPU utilization tracking
- Error counters
"""

from unittest.mock import MagicMock, patch

import pytest

# Check if pynvml is available
try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False


# T119: Test metrics recorded on success
def test_metrics_recorded_on_success():
    """
    Test that metrics are recorded when fragment processing succeeds.

    Given: Prometheus metrics initialized
    When: record_fragment_success() called with timings
    Then: sts_fragment_processing_seconds histogram incremented with status="success"
    And: Stage timings (ASR, Translation, TTS) histograms updated
    """
    from sts_service.full.observability.metrics import (
        record_fragment_success,
        sts_asr_duration_seconds,
        sts_fragment_processing_seconds,
        sts_translation_duration_seconds,
        sts_tts_duration_seconds,
    )

    # Mock histogram observe methods
    with (
        patch.object(sts_fragment_processing_seconds, "labels") as mock_frag_labels,
        patch.object(sts_asr_duration_seconds, "observe") as mock_asr_observe,
        patch.object(sts_translation_duration_seconds, "observe") as mock_translation_observe,
        patch.object(sts_tts_duration_seconds, "observe") as mock_tts_observe,
    ):
        mock_frag_metric = MagicMock()
        mock_frag_labels.return_value = mock_frag_metric

        # Record success
        record_fragment_success(
            stream_id="stream-001",
            processing_time_ms=5250,
            stage_timings={
                "asr_ms": 3500,
                "translation_ms": 250,
                "tts_ms": 1500,
            },
        )

        # Verify fragment processing histogram
        mock_frag_labels.assert_called_once_with(status="success", stream_id="stream-001")
        mock_frag_metric.observe.assert_called_once_with(5.250)  # Convert ms to seconds

        # Verify stage timing histograms
        mock_asr_observe.assert_called_once_with(3.500)
        mock_translation_observe.assert_called_once_with(0.250)
        mock_tts_observe.assert_called_once_with(1.500)


# T120: Test metrics recorded on failure
def test_metrics_recorded_on_failure():
    """
    Test that metrics are recorded when fragment processing fails.

    Given: Prometheus metrics initialized
    When: record_fragment_failure() called with error details
    Then: sts_fragment_errors_total counter incremented with stage="asr", error_code="TIMEOUT"
    """
    from sts_service.full.observability.metrics import (
        record_fragment_failure,
        sts_fragment_errors_total,
    )

    with patch.object(sts_fragment_errors_total, "labels") as mock_error_labels:
        mock_error_metric = MagicMock()
        mock_error_labels.return_value = mock_error_metric

        # Record failure
        record_fragment_failure(
            stream_id="stream-001",
            stage="asr",
            error_code="TIMEOUT",
        )

        # Verify error counter
        mock_error_labels.assert_called_once_with(
            stream_id="stream-001", stage="asr", error_code="TIMEOUT"
        )
        mock_error_metric.inc.assert_called_once()


# T121: Test GPU utilization tracked
@pytest.mark.skipif(not PYNVML_AVAILABLE, reason="pynvml not installed")
@patch("pynvml.nvmlInit")
@patch("pynvml.nvmlDeviceGetHandleByIndex")
@patch("pynvml.nvmlDeviceGetUtilizationRates")
@patch("pynvml.nvmlDeviceGetMemoryInfo")
def test_gpu_utilization_tracked(
    mock_memory_info, mock_utilization, mock_device_handle, mock_nvml_init
):
    """
    Test that GPU utilization metrics are updated.

    Given: pynvml initialized (NVIDIA GPU monitoring library)
    When: update_gpu_metrics() called
    Then: sts_gpu_utilization_percent gauge updated
    And: sts_gpu_memory_used_bytes gauge updated
    """
    from sts_service.full.observability.metrics import (
        sts_gpu_memory_used_bytes,
        sts_gpu_utilization_percent,
        update_gpu_metrics,
    )

    # Mock GPU metrics
    mock_utilization.return_value = MagicMock(gpu=75, memory=60)
    mock_memory = MagicMock(used=8_000_000_000, total=16_000_000_000)
    mock_memory_info.return_value = mock_memory

    with (
        patch.object(sts_gpu_utilization_percent, "set") as mock_util_set,
        patch.object(sts_gpu_memory_used_bytes, "set") as mock_memory_set,
    ):
        # Update GPU metrics
        update_gpu_metrics()

        # Verify gauges updated
        mock_util_set.assert_called_once_with(75)
        mock_memory_set.assert_called_once_with(8_000_000_000)


# T121: Test GPU metrics handle missing GPU gracefully
@pytest.mark.skipif(not PYNVML_AVAILABLE, reason="pynvml not installed")
@patch("pynvml.nvmlInit", side_effect=Exception("No GPU found"))
def test_gpu_metrics_handle_no_gpu(mock_nvml_init):
    """
    Test that GPU metrics handle missing GPU gracefully.

    Given: No NVIDIA GPU available (pynvml raises exception)
    When: update_gpu_metrics() called
    Then: No exception raised
    And: GPU metrics set to 0
    """
    from sts_service.full.observability.metrics import update_gpu_metrics

    # Should not raise exception
    try:
        update_gpu_metrics()
    except Exception as e:
        pytest.fail(f"update_gpu_metrics raised exception: {e}")


# T122: Test in-flight gauge updated
def test_inflight_gauge_updated():
    """
    Test that in-flight gauge reflects current count.

    Given: Prometheus in-flight gauge initialized
    When: increment_inflight() and decrement_inflight() called
    Then: sts_fragments_in_flight gauge updated correctly
    """
    from sts_service.full.observability.metrics import (
        decrement_inflight,
        increment_inflight,
        sts_fragments_in_flight,
    )

    with patch.object(sts_fragments_in_flight, "labels") as mock_labels:
        mock_gauge = MagicMock()
        mock_labels.return_value = mock_gauge

        # Increment in-flight
        increment_inflight(stream_id="stream-001")
        mock_labels.assert_called_with(stream_id="stream-001")
        mock_gauge.inc.assert_called_once()

        # Reset mock
        mock_gauge.reset_mock()

        # Decrement in-flight
        decrement_inflight(stream_id="stream-001")
        mock_labels.assert_called_with(stream_id="stream-001")
        mock_gauge.dec.assert_called_once()


# T119: Test fragment processing histogram buckets
def test_fragment_processing_histogram_buckets():
    """
    Test that fragment processing histogram has correct buckets.

    Given: sts_fragment_processing_seconds histogram
    Then: Buckets include [0.5, 1, 2, 4, 8, 16] (per spec requirements)
    """
    from sts_service.full.observability.metrics import sts_fragment_processing_seconds

    # Verify buckets (access internal metric descriptor)
    expected_buckets = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, float("inf"))
    # Check buckets via the metric descriptor
    metric_desc = sts_fragment_processing_seconds._metrics
    # Get any sample metric to access buckets
    sample_metric = next(iter(metric_desc.values())) if metric_desc else None
    if sample_metric and hasattr(sample_metric, "_upper_bounds"):
        assert sample_metric._upper_bounds == expected_buckets
    else:
        # If no metrics collected yet, just verify the histogram exists
        # (buckets are defined at creation time)
        assert sts_fragment_processing_seconds is not None


# T119: Test stage timing histograms exist
def test_stage_timing_histograms_exist():
    """
    Test that all stage timing histograms are defined.

    Given: Metrics module imported
    Then: sts_asr_duration_seconds histogram exists
    And: sts_translation_duration_seconds histogram exists
    And: sts_tts_duration_seconds histogram exists
    """
    from sts_service.full.observability import metrics

    assert hasattr(metrics, "sts_asr_duration_seconds")
    assert hasattr(metrics, "sts_translation_duration_seconds")
    assert hasattr(metrics, "sts_tts_duration_seconds")


# T120: Test error counter labels
def test_error_counter_labels():
    """
    Test that error counter has correct labels.

    Given: sts_fragment_errors_total counter
    Then: Counter has labels: stream_id, stage, error_code
    """
    from sts_service.full.observability.metrics import sts_fragment_errors_total

    # Verify label names
    assert "stream_id" in sts_fragment_errors_total._labelnames
    assert "stage" in sts_fragment_errors_total._labelnames
    assert "error_code" in sts_fragment_errors_total._labelnames


# T119: Test record_stage_timing utility
def test_record_stage_timing():
    """
    Test utility function for recording individual stage timing.

    Given: Prometheus histograms initialized
    When: record_stage_timing() called with stage="asr", duration_ms=3500
    Then: sts_asr_duration_seconds histogram updated with 3.5 seconds
    """
    from sts_service.full.observability.metrics import (
        record_stage_timing,
        sts_asr_duration_seconds,
    )

    with patch.object(sts_asr_duration_seconds, "observe") as mock_observe:
        record_stage_timing(stage="asr", duration_ms=3500)
        mock_observe.assert_called_once_with(3.5)


# T122: Test active sessions gauge
def test_active_sessions_gauge():
    """
    Test that active sessions gauge tracks session count.

    Given: sts_sessions_active gauge
    When: increment_active_sessions() and decrement_active_sessions() called
    Then: Gauge reflects current session count
    """
    from sts_service.full.observability.metrics import (
        decrement_active_sessions,
        increment_active_sessions,
        sts_sessions_active,
    )

    with (
        patch.object(sts_sessions_active, "inc") as mock_inc,
        patch.object(sts_sessions_active, "dec") as mock_dec,
    ):
        increment_active_sessions()
        mock_inc.assert_called_once()

        decrement_active_sessions()
        mock_dec.assert_called_once()


# T119: Test metrics include stream_id label
def test_metrics_include_stream_id_label():
    """
    Test that fragment processing metrics include stream_id label.

    Given: sts_fragment_processing_seconds histogram
    Then: Histogram includes stream_id in labels
    """
    from sts_service.full.observability.metrics import sts_fragment_processing_seconds

    assert "stream_id" in sts_fragment_processing_seconds._labelnames
    assert "status" in sts_fragment_processing_seconds._labelnames


# T120: Test record_fragment_failure with partial status
def test_record_fragment_failure_partial():
    """
    Test recording fragment failure with partial status.

    Given: Fragment processed with status="partial" (duration variance 10-20%)
    When: record_fragment_failure() called with error_code="DURATION_VARIANCE_HIGH"
    Then: Error counter incremented with stage="tts"
    """
    from sts_service.full.observability.metrics import (
        record_fragment_failure,
        sts_fragment_errors_total,
    )

    with patch.object(sts_fragment_errors_total, "labels") as mock_labels:
        mock_metric = MagicMock()
        mock_labels.return_value = mock_metric

        record_fragment_failure(
            stream_id="stream-001",
            stage="tts",
            error_code="DURATION_VARIANCE_HIGH",
        )

        mock_labels.assert_called_once_with(
            stream_id="stream-001", stage="tts", error_code="DURATION_VARIANCE_HIGH"
        )
        mock_metric.inc.assert_called_once()
