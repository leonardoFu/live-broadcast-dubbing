# Prometheus Metrics Contract

**Feature**: Stream Worker Implementation
**Date**: 2025-12-28
**Endpoint**: GET /metrics (default port 8000)

## Overview

The stream worker exposes Prometheus metrics at the `/metrics` endpoint for observability and alerting. All metrics include a `stream_id` label for per-stream monitoring.

## Counters

### worker_audio_fragments_total

Total number of audio fragments processed (successfully or with fallback).

| Property | Value |
|----------|-------|
| Type | Counter |
| Labels | `stream_id` |
| Unit | fragments |

**Usage**:
```promql
# Rate of fragments processed per stream
rate(worker_audio_fragments_total{stream_id="my-stream"}[1m])
```

### worker_fallback_total

Total number of fallback activations (original audio used instead of dubbed).

| Property | Value |
|----------|-------|
| Type | Counter |
| Labels | `stream_id` |
| Unit | activations |

**Usage**:
```promql
# Fallback rate over 5 minutes
rate(worker_fallback_total{stream_id="my-stream"}[5m])

# Alert: High fallback rate
(rate(worker_fallback_total[5m]) / rate(worker_audio_fragments_total[5m])) > 0.1
```

### worker_gst_bus_errors_total

Total GStreamer bus errors encountered.

| Property | Value |
|----------|-------|
| Type | Counter |
| Labels | `stream_id`, `error_type` |
| Unit | errors |

**Error Types**:
- `pipeline_error` - GStreamer pipeline error
- `element_error` - Element-specific error
- `stream_error` - Stream discontinuity or EOS
- `negotiation_error` - Caps negotiation failure

**Usage**:
```promql
# Total errors by type
sum by (error_type) (worker_gst_bus_errors_total)
```

## Gauges

### worker_inflight_fragments

Number of audio fragments currently being processed by STS.

| Property | Value |
|----------|-------|
| Type | Gauge |
| Labels | `stream_id` |
| Unit | fragments |
| Expected Range | 0-5 |

**Usage**:
```promql
# Alert: Too many in-flight fragments (potential backpressure)
worker_inflight_fragments > 3
```

### worker_av_sync_delta_ms

Current audio/video synchronization delta.

| Property | Value |
|----------|-------|
| Type | Gauge |
| Labels | `stream_id` |
| Unit | milliseconds |
| Warning Threshold | 80ms |
| Critical Threshold | 120ms |

**Usage**:
```promql
# Alert: A/V sync degraded
worker_av_sync_delta_ms > 80

# Alert: A/V sync critical
worker_av_sync_delta_ms > 120
```

### worker_sts_breaker_state

Circuit breaker state for STS Service.

| Property | Value |
|----------|-------|
| Type | Gauge |
| Labels | `stream_id` |
| Values | 0=closed, 1=half_open, 2=open |

**Usage**:
```promql
# Alert: Circuit breaker open
worker_sts_breaker_state == 2

# Count streams with open breaker
count(worker_sts_breaker_state == 2)
```

## Histograms

### worker_sts_rtt_ms

STS Service round-trip time distribution.

| Property | Value |
|----------|-------|
| Type | Histogram |
| Labels | `stream_id` |
| Unit | milliseconds |
| Buckets | 50, 100, 250, 500, 1000, 2000, 4000, 8000 |

**Usage**:
```promql
# p95 STS latency
histogram_quantile(0.95, rate(worker_sts_rtt_ms_bucket[5m]))

# p50 STS latency
histogram_quantile(0.50, rate(worker_sts_rtt_ms_bucket[5m]))

# Alert: STS latency too high
histogram_quantile(0.95, rate(worker_sts_rtt_ms_bucket[5m])) > 4000
```

## Labels

### stream_id

Stream identifier from MediaMTX path.

| Property | Value |
|----------|-------|
| Type | string |
| Pattern | `[a-zA-Z0-9_-]+` |
| Example | `broadcast-123`, `test_stream` |

### error_type

GStreamer error classification (used with `worker_gst_bus_errors_total`).

| Property | Value |
|----------|-------|
| Type | string |
| Values | `pipeline_error`, `element_error`, `stream_error`, `negotiation_error` |

## Endpoint Response Format

```text
# HELP worker_audio_fragments_total Total audio fragments processed
# TYPE worker_audio_fragments_total counter
worker_audio_fragments_total{stream_id="test-stream"} 120

# HELP worker_fallback_total Total fallback activations
# TYPE worker_fallback_total counter
worker_fallback_total{stream_id="test-stream"} 3

# HELP worker_gst_bus_errors_total GStreamer bus errors
# TYPE worker_gst_bus_errors_total counter
worker_gst_bus_errors_total{stream_id="test-stream",error_type="stream_error"} 1

# HELP worker_inflight_fragments Currently in-flight fragments
# TYPE worker_inflight_fragments gauge
worker_inflight_fragments{stream_id="test-stream"} 2

# HELP worker_av_sync_delta_ms Current A/V sync delta in milliseconds
# TYPE worker_av_sync_delta_ms gauge
worker_av_sync_delta_ms{stream_id="test-stream"} 45.5

# HELP worker_sts_breaker_state Circuit breaker state: 0=closed, 1=half_open, 2=open
# TYPE worker_sts_breaker_state gauge
worker_sts_breaker_state{stream_id="test-stream"} 0

# HELP worker_sts_rtt_ms STS round-trip time in milliseconds
# TYPE worker_sts_rtt_ms histogram
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="50"} 5
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="100"} 15
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="250"} 45
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="500"} 80
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="1000"} 100
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="2000"} 115
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="4000"} 118
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="8000"} 120
worker_sts_rtt_ms_bucket{stream_id="test-stream",le="+Inf"} 120
worker_sts_rtt_ms_sum{stream_id="test-stream"} 48500
worker_sts_rtt_ms_count{stream_id="test-stream"} 120
```

## Scrape Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'stream-worker'
    static_configs:
      - targets: ['media-service:8000']
    scrape_interval: 15s
    metrics_path: /metrics
```

## Alerting Rules

```yaml
# alerts.yml
groups:
  - name: stream-worker
    rules:
      - alert: StreamWorkerCircuitBreakerOpen
        expr: worker_sts_breaker_state == 2
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker open for stream {{ $labels.stream_id }}"
          description: "STS service failures have triggered the circuit breaker"

      - alert: StreamWorkerAVSyncDegraded
        expr: worker_av_sync_delta_ms > 80
        for: 30s
        labels:
          severity: warning
        annotations:
          summary: "A/V sync degraded for stream {{ $labels.stream_id }}"
          description: "A/V sync delta is {{ $value }}ms (threshold: 80ms)"

      - alert: StreamWorkerAVSyncCritical
        expr: worker_av_sync_delta_ms > 120
        for: 10s
        labels:
          severity: critical
        annotations:
          summary: "A/V sync critical for stream {{ $labels.stream_id }}"
          description: "A/V sync delta is {{ $value }}ms (threshold: 120ms)"

      - alert: StreamWorkerHighFallbackRate
        expr: >
          (rate(worker_fallback_total[5m]) / rate(worker_audio_fragments_total[5m])) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High fallback rate for stream {{ $labels.stream_id }}"
          description: "More than 10% of fragments are using fallback audio"

      - alert: StreamWorkerSTSLatencyHigh
        expr: histogram_quantile(0.95, rate(worker_sts_rtt_ms_bucket[5m])) > 4000
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High STS latency for stream {{ $labels.stream_id }}"
          description: "p95 STS latency is {{ $value }}ms (threshold: 4000ms)"
```
