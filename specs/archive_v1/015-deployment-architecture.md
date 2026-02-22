# 015 — Deployment Architecture (EC2 + RunPod)

Status: Draft
Last updated: 2025-12-24

## 1. Goal

Define a production deployment architecture that splits the live streaming dubbing pipeline into **two separate projects**:

1. **Stream Infrastructure Project** (EC2): Handles stream ingestion, orchestration, and egress
2. **GPU Processing Project** (RunPod.io): Executes GPU-intensive STS processing

This separation optimizes costs by:
- Running lightweight streaming infrastructure on cost-effective EC2 instances
- Running GPU workloads on RunPod.io for better GPU performance and pricing
- Allowing independent scaling of infrastructure vs. GPU processing capacity

---

## 2. Architecture Overview

```
[Publisher]
    |
    v
┌─────────────────────────────────────────────────────────────┐
│ EC2 Instance (Stream Infrastructure Project)                │
│                                                              │
│  [MediaMTX]                                                  │
│      ↓                                                       │
│  (Ingest: /live/<streamId>/in)                              │
│      ↓                                                       │
│  [Stream Orchestrator]                                       │
│      ↓                                                       │
│  [Stream Worker - Lightweight]                               │
│   - Audio/video demux (GStreamer)                           │
│   - Video passthrough                                        │
│   - Audio chunking                                           │
│   - Background separation (CPU)                              │
│   - Audio remixing                                           │
│      ↓                                                       │
│  [STS Client] ──────────────────────────────┐               │
│                                              │               │
└──────────────────────────────────────────────┼───────────────┘
                                               │
                                               │ HTTPS/gRPC
                                               │
                                               v
┌─────────────────────────────────────────────────────────────┐
│ RunPod.io Pod (GPU Processing Project)                      │
│                                                              │
│  [STS Service API]                                           │
│   - ASR (Whisper) - GPU                                      │
│   - Translation (MT) - GPU                                   │
│   - TTS (Synthesis) - GPU                                    │
│   - Time-stretching                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                                               │
                                               │ Result
                                               v
┌─────────────────────────────────────────────────────────────┐
│ EC2 Instance (continued)                                     │
│                                                              │
│  [Stream Worker - Lightweight]                               │
│   - Receive dubbed audio                                     │
│   - Remix with background                                    │
│   - Remux with video                                         │
│      ↓                                                       │
│  (MediaMTX: /live/<streamId>/out)                           │
│      ↓                                                       │
│  [Egress Forwarder]                                          │
│      ↓                                                       │
│  [3rd-party RTMP Destination]                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Project Split: Components by Deployment Target

### 3.1 Stream Infrastructure Project (EC2)

**Repository location**: `apps/media-service/`

**Components**:
- **MediaMTX**: Stream ingestion and republishing
- **Stream Orchestrator**: Hook receiver, worker lifecycle management
- **Stream Worker (Lightweight)**:
  - GStreamer-based audio/video processing
  - Audio chunking and background separation
  - STS client (HTTP/gRPC calls to RunPod)
  - Audio remixing and A/V remuxing
- **Egress Forwarder**: Push to 3rd-party RTMP destinations

**Resource Requirements**:
- Instance type: `t3.medium` to `t3.xlarge` (CPU-focused)
- No GPU required
- Network: High bandwidth for RTMP ingest/egress
- Storage: Minimal (logs, recordings if enabled)

**Dependencies**:
- GStreamer (for A/V processing)
- FFmpeg (for media operations)
- Python 3.10+ runtime
- Docker (for containerized deployment)

---

### 3.2 GPU Processing Project (RunPod.io)

**Repository location**: `apps/sts-service/`

**Components**:
- **STS Service API**: HTTP/gRPC server exposing STS endpoints
  - ASR module (Whisper)
  - Translation module (MT)
  - TTS module (Coqui or alternative)
  - Time-stretching utilities

**Resource Requirements**:
- RunPod template: GPU pod with NVIDIA GPU (A4000, A5000, or better)
- CUDA runtime required
- VRAM: Minimum 8GB (16GB recommended for larger models)
- Storage: Persistent volume for model caches

**Dependencies**:
- PyTorch with CUDA support
- Whisper (OpenAI or faster-whisper)
- HuggingFace Transformers (for MT)
- Coqui TTS (or alternative TTS engine)
- Model caches (HuggingFace, TTS models)

---

## 4. Communication Protocol: EC2 ↔ RunPod

### 4.1 Protocol Choice

**Primary**: HTTP/REST with JSON payloads
**Alternative**: gRPC with Protocol Buffers (for lower latency)

Rationale for HTTP/REST (v1):
- Simple to debug and monitor
- Wide tooling support
- Easy authentication (API keys, JWT)
- Sufficient latency for current targets (3-8s total pipeline)

### 4.2 API Contract (STS Service on RunPod)

**Endpoint**: `POST /api/v1/sts/process`

**Request**:
```json
{
  "fragment_id": "uuid",
  "stream_id": "string",
  "sequence_number": 123,
  "audio": {
    "format": "pcm_s16le",
    "sample_rate_hz": 48000,
    "channels": 2,
    "duration_ms": 1000,
    "data_base64": "..."
  },
  "config": {
    "source_language": "en",
    "target_language": "es",
    "voice_profile": "default"
  },
  "timeout_ms": 8000
}
```

**Response (Success)**:
```json
{
  "fragment_id": "uuid",
  "status": "success",
  "dubbed_audio": {
    "format": "pcm_s16le",
    "sample_rate_hz": 48000,
    "channels": 2,
    "duration_ms": 1000,
    "data_base64": "..."
  },
  "transcript": "Hello world",
  "translated_text": "Hola mundo",
  "processing_time_ms": 2340,
  "metadata": {
    "asr_model": "whisper-medium",
    "translation_model": "opus-mt-en-es",
    "tts_model": "coqui-tts-es"
  }
}
```

**Response (Error)**:
```json
{
  "fragment_id": "uuid",
  "status": "error",
  "error": {
    "code": "TIMEOUT" | "MODEL_ERROR" | "INVALID_INPUT",
    "message": "Description of error",
    "retryable": true
  }
}
```

### 4.3 Authentication & Security

- **API Key**: RunPod service validates requests via API key header
- **HTTPS**: All traffic encrypted in transit
- **IP Allowlist** (optional): Restrict RunPod access to EC2 instance IPs
- **Rate Limiting**: Protect RunPod service from overload

---

## 5. Failure Handling & Resilience

### 5.1 EC2 → RunPod Communication Failures

**Network Timeout**:
- Default timeout: 8s per fragment
- Retry: Up to 1 retry with exponential backoff
- Fallback: Pass-through original audio (configurable)

**RunPod Service Unavailable**:
- Circuit breaker: Open after 5 consecutive failures
- Fallback mode: Continue stream with original audio
- Alert: Emit high-priority alert for manual intervention

**Partial Failures**:
- If STS returns partial result (e.g., ASR succeeded but TTS failed), apply configured fallback

### 5.2 RunPod Pod Failures

**Pod Crash**:
- RunPod auto-restart with health checks
- EC2 worker retries failed requests
- State: Stateless pods allow immediate failover

**Model Loading Failures**:
- Persistent volume ensures model caches survive pod restarts
- Startup health check validates all models loaded before accepting traffic

---

## 6. Deployment & Operations

### 6.1 EC2 Deployment

**Launch**:
- Use Docker Compose or ECS for container orchestration
- Environment variables for configuration (see `specs/013-configuration-and-defaults.md`)
- Persistent volumes: logs, recordings (optional)

**Configuration**:
```env
# Stream Infrastructure
MEDIAMTX_RTSP_ADDRESS=:8554
MEDIAMTX_RTMP_ADDRESS=:1935
ORCH_HTTP_ADDR=0.0.0.0:8080

# STS Client (points to RunPod)
STS_SERVICE_URL=https://<runpod-id>.runpod.io/api/v1/sts
STS_API_KEY=<secret>
STS_TIMEOUT_MS=8000
STS_MAX_RETRIES=1

# Shared
LOG_LEVEL=info
LOG_DIR=/var/log/media-service
```

**Scaling**:
- Vertical: Upgrade EC2 instance type for more streams
- Horizontal: Multiple EC2 instances behind load balancer (requires coordination layer)

### 6.2 RunPod Deployment

**Pod Template**:
- Base image: CUDA-enabled Python image
- Entrypoint: STS service HTTP server
- Persistent volume: `/models` (for caches)
- Health check: `GET /health` returns 200 when ready

**Configuration**:
```env
# GPU Processing
CUDA_VISIBLE_DEVICES=0
MODEL_CACHE_DIR=/models
WHISPER_MODEL=medium
TTS_MODEL=coqui-es

# API Server
API_PORT=8000
API_KEY=<secret>
MAX_WORKERS=4

# Shared
LOG_LEVEL=info
```

**Scaling**:
- Vertical: Use larger GPU for faster processing (A5000, A6000)
- Horizontal: Multiple RunPod pods behind load balancer

---

## 7. Cost Optimization

### 7.1 EC2 Costs

**Instance Type Selection**:
- `t3.medium`: ~$30/month for development/low-traffic
- `t3.xlarge`: ~$120/month for production (2-3 concurrent streams)
- `c5.xlarge`: ~$120/month (CPU-optimized alternative)

**Optimizations**:
- Spot instances for non-critical environments (70% savings)
- Reserved instances for predictable workloads (40% savings)

### 7.2 RunPod Costs

**GPU Pricing** (as of 2024, approximate):
- RTX A4000 (16GB): ~$0.34/hour (~$245/month if always on)
- RTX A5000 (24GB): ~$0.44/hour (~$317/month if always on)

**Optimizations**:
- On-demand pods: Start/stop based on stream activity
- Spot pods: Lower cost but may be preempted (use with circuit breaker fallback)
- Serverless: Pay per request (higher latency, lower idle cost)

**Cost Comparison**:
- On-demand GPU (always on): ~$245-317/month
- Spot GPU (80% uptime): ~$150-200/month
- Serverless GPU (1000 req/day, 3s avg): ~$100-150/month

---

## 8. Monitoring & Observability

### 8.1 EC2 Metrics

- Stream health: active streams, worker uptime
- Network: RTMP ingest/egress bandwidth
- STS client: request latency, error rate, circuit breaker state
- A/V sync: drift metrics per stream

### 8.2 RunPod Metrics

- GPU utilization: % GPU, VRAM usage
- Request throughput: requests/second, queue depth
- Processing latency: ASR time, MT time, TTS time
- Model performance: cache hit rate, model load time

### 8.3 End-to-End Monitoring

- Fragment processing latency (EC2 → RunPod → EC2)
- End-to-end stream latency (publisher → viewer)
- Fallback rate: % of fragments using fallback audio
- Cost per stream-hour (EC2 + RunPod combined)

---

## 9. Migration Path from Single-Host Architecture

### Phase 1: Refactor STS Module
- Extract STS logic from stream worker into standalone module
- Define API contract (HTTP endpoints)
- Implement STS client in stream worker

### Phase 2: Local Two-Process Deployment
- Run STS service as separate process on same host
- Validate communication, latency, error handling
- Test fallbacks and circuit breaker

### Phase 3: Deploy STS to RunPod
- Build RunPod Docker image with STS service
- Deploy pod with persistent volume for models
- Update EC2 worker to point to RunPod URL

### Phase 4: Optimize & Scale
- Tune timeouts and retries based on real latency
- Implement on-demand pod scaling
- Add monitoring and alerting

---

## 10. Acceptance Criteria

- Stream infrastructure runs on EC2 without GPU dependencies
- STS processing runs on RunPod with GPU acceleration
- Communication between EC2 and RunPod is reliable with < 5% error rate
- Circuit breaker prevents cascading failures when RunPod is unavailable
- End-to-end latency remains within 3-8s target
- Cost per stream-hour is measurable and optimized
- Both projects can be deployed and scaled independently

---

## 11. References

- `specs/001-spec.md` (overall architecture)
- `specs/003-gstreamer-stream-worker.md` (stream worker design)
- `specs/004-sts-pipeline-design.md` (STS module contracts)
- `specs/013-configuration-and-defaults.md` (configuration standards)
- RunPod documentation: https://docs.runpod.io/
