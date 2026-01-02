"""Prometheus metrics parser for E2E tests.

Parses Prometheus /metrics endpoint responses and provides
utilities for metric assertions in E2E tests.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from config import MediaServiceConfig, TimeoutConfig

logger = logging.getLogger(__name__)


@dataclass
class MetricSample:
    """A single metric sample."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float | None = None


@dataclass
class MetricFamily:
    """A metric family with all its samples."""

    name: str
    help_text: str
    type: str  # counter, gauge, histogram, summary
    samples: list[MetricSample] = field(default_factory=list)


class MetricsParser:
    """Parses and queries Prometheus metrics.

    Provides utilities to fetch, parse, and assert on
    Prometheus metrics from the media-service.

    Usage:
        parser = MetricsParser()
        metrics = parser.fetch()
        assert parser.get_counter("worker_audio_fragments_total") == 10
    """

    def __init__(self, metrics_url: str | None = None) -> None:
        """Initialize metrics parser.

        Args:
            metrics_url: URL to /metrics endpoint
        """
        self.metrics_url = metrics_url or MediaServiceConfig.METRICS_URL
        self._metrics: dict[str, MetricFamily] = {}
        self._raw_text: str = ""

    def fetch(self, timeout: int | None = None) -> dict[str, MetricFamily]:
        """Fetch and parse metrics from endpoint.

        Args:
            timeout: Request timeout in seconds

        Returns:
            Dictionary of metric families

        Raises:
            httpx.HTTPError: If request fails
        """
        timeout = timeout or TimeoutConfig.SERVICE_HEALTH_CHECK

        with httpx.Client(timeout=timeout) as client:
            response = client.get(self.metrics_url)
            response.raise_for_status()
            self._raw_text = response.text

        self._metrics = self._parse_prometheus_text(self._raw_text)
        return self._metrics

    def _parse_prometheus_text(self, text: str) -> dict[str, MetricFamily]:
        """Parse Prometheus text format into MetricFamily objects.

        Args:
            text: Prometheus text format

        Returns:
            Dictionary of metric families
        """
        families: dict[str, MetricFamily] = {}
        current_family: MetricFamily | None = None

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Parse HELP line
            if line.startswith("# HELP "):
                parts = line[7:].split(" ", 1)
                name = parts[0]
                help_text = parts[1] if len(parts) > 1 else ""
                current_family = MetricFamily(
                    name=name,
                    help_text=help_text,
                    type="untyped",
                )
                families[name] = current_family

            # Parse TYPE line
            elif line.startswith("# TYPE "):
                parts = line[7:].split(" ", 1)
                name = parts[0]
                metric_type = parts[1] if len(parts) > 1 else "untyped"
                if name in families:
                    families[name].type = metric_type
                else:
                    families[name] = MetricFamily(
                        name=name,
                        help_text="",
                        type=metric_type,
                    )
                    current_family = families[name]

            # Skip other comments
            elif line.startswith("#"):
                continue

            # Parse metric sample
            else:
                sample = self._parse_sample(line)
                if sample:
                    # Find the base metric name (without suffix like _total, _bucket)
                    base_name = self._get_base_name(sample.name)
                    if base_name in families:
                        families[base_name].samples.append(sample)
                    elif sample.name in families:
                        families[sample.name].samples.append(sample)
                    else:
                        # Create new family for unknown metrics
                        families[sample.name] = MetricFamily(
                            name=sample.name,
                            help_text="",
                            type="untyped",
                            samples=[sample],
                        )

        return families

    def _parse_sample(self, line: str) -> MetricSample | None:
        """Parse a single metric sample line.

        Args:
            line: Metric line (e.g., 'metric_name{label="value"} 123.45')

        Returns:
            MetricSample or None if parsing fails
        """
        # Match pattern: metric_name{labels} value [timestamp]
        # or: metric_name value [timestamp]
        pattern = (
            r'^([a-zA-Z_:][a-zA-Z0-9_:]*)'  # metric name
            r'((?:\{[^}]*\})?)?'  # optional labels
            r'\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'  # value
            r'\s*(\d+)?$'  # optional timestamp
        )
        match = re.match(pattern, line)

        if not match:
            return None

        name = match.group(1)
        labels_str = match.group(2) or ""
        value_str = match.group(3)
        timestamp_str = match.group(4)

        # Parse labels
        labels = {}
        if labels_str:
            labels_str = labels_str.strip("{}")
            # Simple label parsing (assumes no escaped quotes in values)
            label_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"'
            for label_match in re.finditer(label_pattern, labels_str):
                labels[label_match.group(1)] = label_match.group(2)

        # Parse value
        try:
            value = float(value_str)
        except ValueError:
            return None

        # Parse optional timestamp
        timestamp = float(timestamp_str) if timestamp_str else None

        return MetricSample(
            name=name,
            value=value,
            labels=labels,
            timestamp=timestamp,
        )

    def _get_base_name(self, name: str) -> str:
        """Get base metric name (remove suffixes).

        Args:
            name: Full metric name

        Returns:
            Base metric name
        """
        suffixes = ["_total", "_count", "_sum", "_bucket", "_created"]
        for suffix in suffixes:
            if name.endswith(suffix):
                return name[:-len(suffix)]
        return name

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """Get gauge metric value.

        Args:
            name: Metric name
            labels: Optional label filter

        Returns:
            Metric value or None if not found
        """
        return self._get_value(name, labels)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """Get counter metric value.

        Args:
            name: Metric name (can include _total suffix or not)
            labels: Optional label filter

        Returns:
            Counter value or None if not found
        """
        # Try with _total suffix first
        value = self._get_value(f"{name}_total", labels)
        if value is not None:
            return value
        return self._get_value(name, labels)

    def _get_value(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """Get metric value with optional label filtering.

        Args:
            name: Metric name
            labels: Optional label filter

        Returns:
            Metric value or None
        """
        # Check direct name match in samples
        for family in self._metrics.values():
            for sample in family.samples:
                if sample.name == name and (
                    labels is None
                    or all(sample.labels.get(k) == v for k, v in labels.items())
                ):
                    return sample.value

        return None

    def get_all_samples(self, name: str) -> list[MetricSample]:
        """Get all samples for a metric.

        Args:
            name: Metric name

        Returns:
            List of metric samples
        """
        samples = []
        base_name = self._get_base_name(name)

        if base_name in self._metrics:
            samples.extend(self._metrics[base_name].samples)
        if name in self._metrics and name != base_name:
            samples.extend(self._metrics[name].samples)

        return samples

    def get_metric_type(self, name: str) -> str | None:
        """Get metric type.

        Args:
            name: Metric name

        Returns:
            Metric type or None
        """
        base_name = self._get_base_name(name)
        if base_name in self._metrics:
            return self._metrics[base_name].type
        return None

    def assert_counter_equals(
        self,
        name: str,
        expected: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Assert counter equals expected value.

        Args:
            name: Metric name
            expected: Expected value
            labels: Optional label filter

        Raises:
            AssertionError: If counter doesn't match
        """
        actual = self.get_counter(name, labels)
        if actual is None:
            raise AssertionError(f"Counter {name} not found")
        if actual != expected:
            raise AssertionError(
                f"Counter {name} expected {expected}, got {actual}"
            )

    def assert_counter_at_least(
        self,
        name: str,
        minimum: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Assert counter is at least minimum value.

        Args:
            name: Metric name
            minimum: Minimum expected value
            labels: Optional label filter

        Raises:
            AssertionError: If counter is less than minimum
        """
        actual = self.get_counter(name, labels)
        if actual is None:
            raise AssertionError(f"Counter {name} not found")
        if actual < minimum:
            raise AssertionError(
                f"Counter {name} expected at least {minimum}, got {actual}"
            )

    def assert_gauge_in_range(
        self,
        name: str,
        minimum: float,
        maximum: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Assert gauge is within range.

        Args:
            name: Metric name
            minimum: Minimum value
            maximum: Maximum value
            labels: Optional label filter

        Raises:
            AssertionError: If gauge is outside range
        """
        actual = self.get_gauge(name, labels)
        if actual is None:
            raise AssertionError(f"Gauge {name} not found")
        if not minimum <= actual <= maximum:
            raise AssertionError(
                f"Gauge {name} expected in range [{minimum}, {maximum}], got {actual}"
            )

    @property
    def raw_text(self) -> str:
        """Get raw metrics text.

        Returns:
            Raw Prometheus text format
        """
        return self._raw_text

    def get_all_metrics(self) -> dict[str, float]:
        """Get all metrics as a simplified dictionary.

        Fetches metrics from endpoint and returns a flattened view
        of all metric values for easy querying in tests.

        Returns:
            Dictionary mapping metric names (with labels) to their values.
            For metrics with labels, keys are formatted as:
            'metric_name{label1="value1",label2="value2"}'

        Example:
            {
                'media_service_worker_segments_processed_total{stream_id="test",type="audio"}': 5.0,
                'worker_av_sync_delta_ms{stream_id="test"}': 45.5,
            }

        Raises:
            httpx.HTTPError: If metrics fetch fails
        """
        # Fetch metrics if not already fetched
        if not self._metrics:
            self.fetch()

        result = {}

        for family in self._metrics.values():
            for sample in family.samples:
                # Format metric name with labels
                if sample.labels:
                    label_str = ",".join(
                        f'{k}="{v}"' for k, v in sorted(sample.labels.items())
                    )
                    key = f"{sample.name}{{{label_str}}}"
                else:
                    key = sample.name

                result[key] = sample.value

        return result
