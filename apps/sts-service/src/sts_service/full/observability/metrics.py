"""Prometheus metrics for Full STS Service.

Defines and exports metrics for monitoring:
- Fragment processing latency (histogram)
- Stage timings (ASR, Translation, TTS histograms)
- Error counts (counter)
- In-flight fragments (gauge)
- Active sessions (gauge)
- GPU utilization and memory (gauges)

Tasks: T119-T122, T126-T127
"""

import logging
from typing import Dict

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Fragment Processing Metrics
# -----------------------------------------------------------------------------

sts_fragment_processing_seconds = Histogram(
    "sts_fragment_processing_seconds",
    "Fragment processing latency in seconds",
    labelnames=["status", "stream_id"],
    buckets=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0, float("inf")),
)

sts_fragments_in_flight = Gauge(
    "sts_fragments_in_flight",
    "Current number of in-flight fragments",
    labelnames=["stream_id"],
)

sts_fragment_errors_total = Counter(
    "sts_fragment_errors_total",
    "Total fragment processing errors",
    labelnames=["stream_id", "stage", "error_code"],
)

# -----------------------------------------------------------------------------
# Stage Timing Metrics
# -----------------------------------------------------------------------------

sts_asr_duration_seconds = Histogram(
    "sts_asr_duration_seconds",
    "ASR processing duration in seconds",
    buckets=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0, float("inf")),
)

sts_translation_duration_seconds = Histogram(
    "sts_translation_duration_seconds",
    "Translation processing duration in seconds",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 4.0, float("inf")),
)

sts_tts_duration_seconds = Histogram(
    "sts_tts_duration_seconds",
    "TTS processing duration in seconds",
    buckets=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0, float("inf")),
)

# -----------------------------------------------------------------------------
# Session Metrics
# -----------------------------------------------------------------------------

sts_sessions_active = Gauge(
    "sts_sessions_active",
    "Current number of active sessions",
)

# -----------------------------------------------------------------------------
# GPU Metrics
# -----------------------------------------------------------------------------

sts_gpu_utilization_percent = Gauge(
    "sts_gpu_utilization_percent",
    "GPU utilization percentage",
)

sts_gpu_memory_used_bytes = Gauge(
    "sts_gpu_memory_used_bytes",
    "GPU memory used in bytes",
)

# -----------------------------------------------------------------------------
# Metric Recording Functions
# -----------------------------------------------------------------------------


def record_fragment_success(
    stream_id: str,
    processing_time_ms: int,
    stage_timings: Dict[str, int],
) -> None:
    """Record successful fragment processing metrics.

    Args:
        stream_id: Stream identifier
        processing_time_ms: Total processing time in milliseconds
        stage_timings: Stage-level timings (asr_ms, translation_ms, tts_ms)
    """
    try:
        # Record total processing time
        processing_time_s = processing_time_ms / 1000.0
        sts_fragment_processing_seconds.labels(status="success", stream_id=stream_id).observe(
            processing_time_s
        )

        # Record stage timings
        if "asr_ms" in stage_timings:
            sts_asr_duration_seconds.observe(stage_timings["asr_ms"] / 1000.0)

        if "translation_ms" in stage_timings:
            sts_translation_duration_seconds.observe(stage_timings["translation_ms"] / 1000.0)

        if "tts_ms" in stage_timings:
            sts_tts_duration_seconds.observe(stage_timings["tts_ms"] / 1000.0)

    except Exception as e:
        logger.error(f"Failed to record success metrics: {e}")


def record_fragment_failure(
    stream_id: str,
    stage: str,
    error_code: str,
) -> None:
    """Record fragment processing failure metrics.

    Args:
        stream_id: Stream identifier
        stage: Stage where error occurred (asr, translation, tts)
        error_code: Error code (TIMEOUT, RATE_LIMIT_EXCEEDED, etc.)
    """
    try:
        sts_fragment_errors_total.labels(
            stream_id=stream_id, stage=stage, error_code=error_code
        ).inc()
    except Exception as e:
        logger.error(f"Failed to record failure metrics: {e}")


def record_stage_timing(stage: str, duration_ms: int) -> None:
    """Record individual stage timing.

    Args:
        stage: Stage name (asr, translation, tts)
        duration_ms: Duration in milliseconds
    """
    try:
        duration_s = duration_ms / 1000.0

        if stage == "asr":
            sts_asr_duration_seconds.observe(duration_s)
        elif stage == "translation":
            sts_translation_duration_seconds.observe(duration_s)
        elif stage == "tts":
            sts_tts_duration_seconds.observe(duration_s)
        else:
            logger.warning(f"Unknown stage for timing: {stage}")

    except Exception as e:
        logger.error(f"Failed to record stage timing: {e}")


def increment_inflight(stream_id: str) -> None:
    """Increment in-flight fragment count.

    Args:
        stream_id: Stream identifier
    """
    try:
        sts_fragments_in_flight.labels(stream_id=stream_id).inc()
    except Exception as e:
        logger.error(f"Failed to increment inflight: {e}")


def decrement_inflight(stream_id: str) -> None:
    """Decrement in-flight fragment count.

    Args:
        stream_id: Stream identifier
    """
    try:
        sts_fragments_in_flight.labels(stream_id=stream_id).dec()
    except Exception as e:
        logger.error(f"Failed to decrement inflight: {e}")


def increment_active_sessions() -> None:
    """Increment active sessions count."""
    try:
        sts_sessions_active.inc()
    except Exception as e:
        logger.error(f"Failed to increment active sessions: {e}")


def decrement_active_sessions() -> None:
    """Decrement active sessions count."""
    try:
        sts_sessions_active.dec()
    except Exception as e:
        logger.error(f"Failed to decrement active sessions: {e}")


def update_gpu_metrics() -> None:
    """Update GPU utilization and memory metrics.

    Uses pynvml (NVIDIA Management Library) to query GPU stats.
    Handles missing GPU gracefully (sets metrics to 0).
    """
    try:
        import pynvml

        pynvml.nvmlInit()

        # Get first GPU device (index 0)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # Get utilization rates
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        sts_gpu_utilization_percent.set(utilization.gpu)

        # Get memory info
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        sts_gpu_memory_used_bytes.set(memory_info.used)

        logger.debug(f"GPU metrics updated: util={utilization.gpu}%, mem={memory_info.used} bytes")

    except Exception as e:
        # GPU not available or pynvml not installed - graceful degradation
        logger.debug(f"GPU metrics unavailable: {e}")
        # Set metrics to 0
        sts_gpu_utilization_percent.set(0)
        sts_gpu_memory_used_bytes.set(0)
