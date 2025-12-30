"""
Metrics module for Prometheus observability.

This module provides Prometheus metrics for monitoring the stream worker,
including counters, gauges, and histograms for key performance indicators.

Components:
- WorkerMetrics: Prometheus metric definitions and helpers
"""

from __future__ import annotations

from media_service.metrics.prometheus import WorkerMetrics

__all__ = [
    "WorkerMetrics",
]
