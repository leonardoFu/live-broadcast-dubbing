"""
Prometheus metrics for stream worker.

Provides observability metrics for the dubbing pipeline.

Per spec 003:
- Segment processing counters
- STS latency histograms
- Circuit breaker state gauge
- A/V sync delta gauge
- Error counters by type
"""

from __future__ import annotations

import logging
from typing import ClassVar

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, Info

logger = logging.getLogger(__name__)


# Module-level singleton metrics - created once and reused
# This avoids Prometheus "Duplicated timeseries" errors in tests
_METRICS_INITIALIZED = False


def _get_or_create_metric(
    metric_class, name: str, description: str, labels: list[str] | None = None, **kwargs
):
    """Get existing metric or create new one.

    This handles the case where metrics are already registered
    (e.g., in tests or when module is reloaded).
    """
    # Check if metric already exists in registry
    for collector in REGISTRY._get_names():
        if name in collector:
            # Find and return existing metric
            for c in list(REGISTRY._collector_to_names.keys()):
                names = REGISTRY._collector_to_names.get(c, [])
                if name in names or any(name in n for n in names):
                    return c

    # Create new metric
    if labels:
        return metric_class(name, description, labels, **kwargs)
    else:
        return metric_class(name, description, **kwargs)


class WorkerMetrics:
    """Prometheus metrics for stream worker.

    Provides comprehensive metrics for monitoring:
    - Segment processing (video/audio)
    - STS communication (fragments, latency)
    - Circuit breaker state
    - A/V synchronization
    - Error tracking

    All metrics use the 'media_service_' prefix for namespace isolation.

    Note: Metrics are class-level singletons to avoid Prometheus
    "Duplicated timeseries" errors when creating multiple instances.
    """

    # Metric namespace and subsystem
    NAMESPACE = "media_service"
    SUBSYSTEM = "worker"

    # Class-level metric singletons (initialized on first use)
    _worker_info: ClassVar[Info | None] = None
    _segments_processed: ClassVar[Counter | None] = None
    _segments_bytes: ClassVar[Counter | None] = None
    _sts_fragments_sent: ClassVar[Counter | None] = None
    _sts_fragments_processed: ClassVar[Counter | None] = None
    _sts_processing_latency: ClassVar[Histogram | None] = None
    _sts_inflight: ClassVar[Gauge | None] = None
    _circuit_breaker_state: ClassVar[Gauge | None] = None
    _circuit_breaker_failures: ClassVar[Counter | None] = None
    _circuit_breaker_fallbacks: ClassVar[Counter | None] = None
    _av_sync_delta_ms: ClassVar[Gauge | None] = None
    _av_sync_corrections: ClassVar[Counter | None] = None
    _av_buffer_video_size: ClassVar[Gauge | None] = None
    _av_buffer_audio_size: ClassVar[Gauge | None] = None
    _errors: ClassVar[Counter | None] = None
    _pipeline_state: ClassVar[Gauge | None] = None
    _backpressure_events: ClassVar[Counter | None] = None
    _metrics_initialized: ClassVar[bool] = False

    def __init__(self, stream_id: str | None = None) -> None:
        """Initialize worker metrics.

        Args:
            stream_id: Stream identifier for labels (optional)
        """
        self.stream_id = stream_id or "unknown"
        self._ensure_metrics_initialized()

    @classmethod
    def _ensure_metrics_initialized(cls) -> None:
        """Initialize all Prometheus metrics (once per class)."""
        if cls._metrics_initialized:
            return

        prefix = f"{cls.NAMESPACE}_{cls.SUBSYSTEM}"

        # Info metric for worker metadata
        cls._worker_info = Info(
            f"{prefix}_info",
            "Worker instance information",
        )

        # Segment counters
        cls._segments_processed = Counter(
            f"{prefix}_segments_processed_total",
            "Total segments processed",
            ["stream_id", "type"],  # values: video|audio
        )

        cls._segments_bytes = Counter(
            f"{prefix}_segments_bytes_total",
            "Total bytes processed in segments",
            ["stream_id", "type"],
        )

        # STS metrics
        cls._sts_fragments_sent = Counter(
            f"{prefix}_sts_fragments_sent_total",
            "Total fragments sent to STS",
            ["stream_id"],
        )

        cls._sts_fragments_processed = Counter(
            f"{prefix}_sts_fragments_processed_total",
            "Total fragments processed by STS",
            ["stream_id", "status"],  # status: success|partial|failed
        )

        cls._sts_processing_latency = Histogram(
            f"{prefix}_sts_processing_latency_seconds",
            "STS processing latency in seconds",
            ["stream_id"],
            buckets=[0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0],
        )

        cls._sts_inflight = Gauge(
            f"{prefix}_sts_inflight_fragments",
            "Current number of in-flight STS fragments",
            ["stream_id"],
        )

        # Circuit breaker metrics
        cls._circuit_breaker_state = Gauge(
            f"{prefix}_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=half_open, 2=open)",
            ["stream_id"],
        )

        cls._circuit_breaker_failures = Counter(
            f"{prefix}_circuit_breaker_failures_total",
            "Total circuit breaker failure count",
            ["stream_id"],
        )

        cls._circuit_breaker_fallbacks = Counter(
            f"{prefix}_circuit_breaker_fallbacks_total",
            "Total fallbacks due to open circuit",
            ["stream_id"],
        )

        # A/V sync metrics
        cls._av_sync_delta_ms = Gauge(
            f"{prefix}_av_sync_delta_ms",
            "Current A/V sync delta in milliseconds",
            ["stream_id"],
        )

        cls._av_sync_corrections = Counter(
            f"{prefix}_av_sync_corrections_total",
            "Total A/V sync drift corrections applied",
            ["stream_id"],
        )

        cls._av_buffer_video_size = Gauge(
            f"{prefix}_av_buffer_video_size",
            "Video segments waiting for audio",
            ["stream_id"],
        )

        cls._av_buffer_audio_size = Gauge(
            f"{prefix}_av_buffer_audio_size",
            "Audio segments waiting for video",
            ["stream_id"],
        )

        # Error metrics
        cls._errors = Counter(
            f"{prefix}_errors_total",
            "Total errors by type",
            ["stream_id", "error_type"],
        )

        # Pipeline state
        cls._pipeline_state = Gauge(
            f"{prefix}_pipeline_state",
            "Pipeline state (0=stopped, 1=running, 2=error)",
            ["stream_id", "pipeline"],  # pipeline: input|output
        )

        # Backpressure metrics
        cls._backpressure_events = Counter(
            f"{prefix}_backpressure_events_total",
            "Total backpressure events received",
            ["stream_id", "action"],  # action: slow_down|pause|none
        )

        cls._metrics_initialized = True

    # Property accessors for metrics (for backwards compatibility)
    @property
    def worker_info(self) -> Info:
        return self._worker_info

    @property
    def segments_processed(self) -> Counter:
        return self._segments_processed

    @property
    def segments_bytes(self) -> Counter:
        return self._segments_bytes

    @property
    def sts_fragments_sent(self) -> Counter:
        return self._sts_fragments_sent

    @property
    def sts_fragments_processed(self) -> Counter:
        return self._sts_fragments_processed

    @property
    def sts_processing_latency(self) -> Histogram:
        return self._sts_processing_latency

    @property
    def sts_inflight(self) -> Gauge:
        return self._sts_inflight

    @property
    def circuit_breaker_state(self) -> Gauge:
        return self._circuit_breaker_state

    @property
    def circuit_breaker_failures(self) -> Counter:
        return self._circuit_breaker_failures

    @property
    def circuit_breaker_fallbacks(self) -> Counter:
        return self._circuit_breaker_fallbacks

    @property
    def av_sync_delta_ms(self) -> Gauge:
        return self._av_sync_delta_ms

    @property
    def av_sync_corrections(self) -> Counter:
        return self._av_sync_corrections

    @property
    def av_buffer_video_size(self) -> Gauge:
        return self._av_buffer_video_size

    @property
    def av_buffer_audio_size(self) -> Gauge:
        return self._av_buffer_audio_size

    @property
    def errors(self) -> Counter:
        return self._errors

    @property
    def pipeline_state(self) -> Gauge:
        return self._pipeline_state

    @property
    def backpressure_events(self) -> Counter:
        return self._backpressure_events

    def set_stream_id(self, stream_id: str) -> None:
        """Update stream ID for metric labels.

        Args:
            stream_id: New stream identifier
        """
        self.stream_id = stream_id

    def set_worker_info(
        self,
        version: str = "0.1.0",
        host: str = "unknown",
    ) -> None:
        """Set worker info metric.

        Args:
            version: Worker version
            host: Host identifier
        """
        self.worker_info.info({
            "version": version,
            "stream_id": self.stream_id,
            "host": host,
        })

    def record_segment_processed(
        self,
        segment_type: str,
        size_bytes: int,
    ) -> None:
        """Record segment processing.

        Args:
            segment_type: "video" or "audio"
            size_bytes: Segment size in bytes
        """
        self.segments_processed.labels(
            stream_id=self.stream_id,
            type=segment_type,
        ).inc()

        self.segments_bytes.labels(
            stream_id=self.stream_id,
            type=segment_type,
        ).inc(size_bytes)

    def record_sts_fragment_sent(self) -> None:
        """Record fragment sent to STS."""
        self.sts_fragments_sent.labels(stream_id=self.stream_id).inc()

    def record_sts_fragment_processed(
        self,
        status: str,
        latency_seconds: float,
    ) -> None:
        """Record STS fragment processing result.

        Args:
            status: "success", "partial", or "failed"
            latency_seconds: Processing time in seconds
        """
        self.sts_fragments_processed.labels(
            stream_id=self.stream_id,
            status=status,
        ).inc()

        self.sts_processing_latency.labels(
            stream_id=self.stream_id,
        ).observe(latency_seconds)

    def set_sts_inflight(self, count: int) -> None:
        """Set current in-flight fragment count.

        Args:
            count: Number of in-flight fragments
        """
        self.sts_inflight.labels(stream_id=self.stream_id).set(count)

    def set_circuit_breaker_state(self, state_value: int) -> None:
        """Set circuit breaker state gauge.

        Args:
            state_value: 0=closed, 1=half_open, 2=open
        """
        self.circuit_breaker_state.labels(stream_id=self.stream_id).set(state_value)

    def record_circuit_breaker_failure(self) -> None:
        """Record circuit breaker failure."""
        self.circuit_breaker_failures.labels(stream_id=self.stream_id).inc()

    def record_circuit_breaker_fallback(self) -> None:
        """Record circuit breaker fallback."""
        self.circuit_breaker_fallbacks.labels(stream_id=self.stream_id).inc()

    def set_av_sync_delta(self, delta_ms: float) -> None:
        """Set A/V sync delta gauge.

        Args:
            delta_ms: Sync delta in milliseconds
        """
        self.av_sync_delta_ms.labels(stream_id=self.stream_id).set(delta_ms)

    def record_av_sync_correction(self) -> None:
        """Record A/V sync drift correction."""
        self.av_sync_corrections.labels(stream_id=self.stream_id).inc()

    def set_av_buffer_sizes(self, video_size: int, audio_size: int) -> None:
        """Set A/V buffer size gauges.

        Args:
            video_size: Video segments waiting
            audio_size: Audio segments waiting
        """
        self.av_buffer_video_size.labels(stream_id=self.stream_id).set(video_size)
        self.av_buffer_audio_size.labels(stream_id=self.stream_id).set(audio_size)

    def record_error(self, error_type: str) -> None:
        """Record error by type.

        Args:
            error_type: Error type identifier
        """
        self.errors.labels(
            stream_id=self.stream_id,
            error_type=error_type,
        ).inc()

    def set_pipeline_state(self, pipeline: str, state: int) -> None:
        """Set pipeline state gauge.

        Args:
            pipeline: "input" or "output"
            state: 0=stopped, 1=running, 2=error
        """
        self.pipeline_state.labels(
            stream_id=self.stream_id,
            pipeline=pipeline,
        ).set(state)

    def record_backpressure_event(self, action: str) -> None:
        """Record backpressure event.

        Args:
            action: "slow_down", "pause", or "none"
        """
        self.backpressure_events.labels(
            stream_id=self.stream_id,
            action=action,
        ).inc()
