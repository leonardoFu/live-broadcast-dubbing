# Full STS Service - Quick Start Guide

**Feature**: Real-time speech-to-speech dubbing service with Socket.IO integration
**Version**: 1.0.0
**Last Updated**: 2026-01-02

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Developer Setup](#3-developer-setup)
4. [Configuration](#4-configuration)
5. [Running Locally](#5-running-locally)
6. [Testing](#6-testing)
7. [Testing with Socket.IO Client](#7-testing-with-socketio-client)
8. [Deployment to RunPod](#8-deployment-to-runpod)
9. [Troubleshooting](#9-troubleshooting)
10. [API Reference](#10-api-reference)

---

## 1. Overview

The Full STS Service provides real-time speech-to-speech translation and dubbing capabilities:

- **ASR (Automatic Speech Recognition)**: faster-whisper (OpenAI Whisper)
- **Translation**: DeepL API
- **TTS (Text-to-Speech)**: Coqui TTS (XTTS v2)
- **Communication**: Socket.IO (WebSocket-based)
- **Observability**: Prometheus metrics + structured logging

**Key Features**:
- GPU-accelerated processing (10-20x faster than CPU)
- Duration matching with time-stretching (A/V sync)
- Backpressure management (prevents GPU overload)
- In-order fragment delivery (maintains sequence)
- Artifact logging for debugging

**Architecture**:
```
Worker (media-service) ─[Socket.IO]→ Full STS Service ─[GPU]→ ASR → Translation → TTS → Dubbed Audio
```

---

## 2. Prerequisites

### Required

- **Operating System**: Linux (Ubuntu 22.04 recommended) or macOS
- **Python**: 3.10.x (required)
- **Docker**: Docker 24.0+ with Docker Compose v2
- **GPU** (for production):
  - NVIDIA GPU with CUDA 12.1+ support
  - NVIDIA Docker runtime ([installation guide](https://github.com/NVIDIA/nvidia-docker))
- **DeepL API Key**: Free or Pro account ([signup](https://www.deepl.com/pro-api))

### Optional (for development)

- **CPU-only mode**: Works without GPU (slower, for testing only)
- **Git**: For version control
- **Make**: For convenience commands

### System Requirements

**Minimum (CPU-only testing)**:
- 8GB RAM
- 20GB disk space

**Recommended (GPU production)**:
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM (RTX 3060 or better)
- 50GB disk space (for models)

---

## 3. Developer Setup

### Step 1: Clone Repository

```bash
# Clone the monorepo
git clone https://github.com/your-org/live-broadcast-dubbing-cloud.git
cd live-broadcast-dubbing-dubbing-cloud

# Navigate to sts-service
cd apps/sts-service
```

### Step 2: Install System Dependencies (Ubuntu)

```bash
# Python 3.10
sudo apt update
sudo apt install -y python3.10 python3.10-dev python3-pip

# GStreamer (for future RTMP support)
sudo apt install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Audio libraries
sudo apt install -y ffmpeg libsndfile1 rubberband-cli librubberband-dev

# Build tools
sudo apt install -y build-essential git curl
```

### Step 3: Install Python Dependencies

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install shared libraries (from monorepo root)
cd ../..  # Back to monorepo root
pip install -e libs/common -e libs/contracts

# Install sts-service dependencies
cd apps/sts-service
pip install -r requirements.txt

# Install with GPU support (CUDA 12.1)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step 4: Download Models (Optional)

**Option A: Auto-download on first run** (slower startup, recommended for dev)
- Models will download automatically to `~/.cache/huggingface/`
- First run takes 5-10 minutes

**Option B: Pre-download** (faster startup, recommended for production)
```bash
# Download faster-whisper model (ASR)
python3 -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu', compute_type='int8')"

# Download XTTS v2 model (TTS)
python3 -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2', gpu=False)"
```

---

## 4. Configuration

### Step 1: Create Environment File

```bash
cd apps/sts-service
cp .env.example .env
```

### Step 2: Edit .env File

**Required Variables**:
```bash
# DeepL API Key (REQUIRED)
DEEPL_AUTH_KEY=your-actual-deepl-api-key-here
```

**GPU Configuration**:
```bash
# GPU mode (recommended)
ASR_DEVICE=cuda
TTS_DEVICE=cuda

# CPU mode (slower, for testing without GPU)
# ASR_DEVICE=cpu
# TTS_DEVICE=cpu
```

**Model Selection**:
```bash
# ASR model size: tiny, base, small, medium, large-v2, large-v3
# Larger = better accuracy, slower processing
ASR_MODEL_SIZE=medium  # Recommended balance
```

**Full Configuration** (see `.env.example` for all options):
- Server settings (host, port, timeouts)
- Duration matching thresholds
- Backpressure thresholds
- Artifact logging settings

### Step 3: Create Voice Profiles (Optional)

Voice profiles define target voices for TTS. Create `config/voices.json`:

```json
{
  "spanish_male_1": {
    "language": "es",
    "gender": "male",
    "reference_audio": "/path/to/spanish_male_reference.wav"
  },
  "french_female_1": {
    "language": "fr",
    "gender": "female",
    "reference_audio": "/path/to/french_female_reference.wav"
  }
}
```

**Default**: If no `voices.json` exists, the service will use default XTTS voices.

---

## 5. Running Locally

### Option A: Docker Compose (Recommended)

```bash
cd apps/sts-service

# Start service
docker compose -f docker-compose.full.yml up

# Start in background
docker compose -f docker-compose.full.yml up -d

# View logs
docker compose -f docker-compose.full.yml logs -f full-sts-service

# Stop service
docker compose -f docker-compose.full.yml down
```

**First Run**: Docker will build the image (5-10 minutes) and download models.

### Option B: Direct Python Execution

```bash
cd apps/sts-service
source venv/bin/activate

# Load environment variables
export $(cat .env | xargs)

# Run service
python -m sts_service.full
```

### Verify Service is Running

```bash
# Health check
curl http://localhost:8000/health
# Response: {"status": "healthy"}

# Metrics endpoint
curl http://localhost:8000/metrics
# Response: Prometheus format metrics

# Socket.IO endpoint
curl http://localhost:8000/socket.io/
# Response: WebSocket upgrade response
```

---

## 6. Testing

### Unit Tests

```bash
cd apps/sts-service

# Run all unit tests
pytest tests/unit/full/ -v

# Run specific test file
pytest tests/unit/full/test_pipeline_coordinator.py -v

# Run with coverage
pytest tests/unit/full/ --cov=sts_service.full --cov-report=term-missing
```

### Integration Tests

```bash
# Run integration tests (requires Docker)
pytest tests/integration/full/ -v

# Run full pipeline test (requires GPU or CPU fallback)
pytest tests/integration/full/test_full_pipeline_asr_to_tts.py -v
```

### E2E Tests

```bash
# Start all services (MediaMTX + media-service + Full STS)
make e2e-up

# Run E2E tests
pytest tests/e2e/test_full_pipeline.py -v --log-cli-level=INFO

# Stop services
make e2e-down
```

---

## 7. Testing with Socket.IO Client

### Python Client Example

```python
import asyncio
import socketio
import base64

async def test_full_sts():
    # Create Socket.IO client
    sio = socketio.AsyncClient()

    # Event handlers
    @sio.on('stream:ready')
    async def on_stream_ready(data):
        print(f"Stream ready: {data}")
        # Send first fragment
        await send_fragment()

    @sio.on('fragment:ack')
    async def on_fragment_ack(data):
        print(f"Fragment acknowledged: {data}")

    @sio.on('fragment:processed')
    async def on_fragment_processed(data):
        print(f"Fragment processed: {data}")
        # Decode dubbed audio
        if data['status'] == 'success':
            dubbed_audio = base64.b64decode(data['dubbed_audio'])
            print(f"Received {len(dubbed_audio)} bytes of dubbed audio")

    # Connect to Full STS Service
    await sio.connect('http://localhost:8000', headers={
        'X-Stream-ID': 'test-stream-123',
        'X-Worker-ID': 'test-worker-1'
    })

    # Initialize stream
    await sio.emit('stream:init', {
        'source_language': 'en',
        'target_language': 'es',
        'voice_profile': 'spanish_male_1',
        'chunk_duration_ms': 6000,
        'sample_rate_hz': 16000,
        'channels': 1,
        'format': 'pcm_s16le'
    })

    async def send_fragment():
        # Load 6-second audio file (English speech)
        with open('test_audio.wav', 'rb') as f:
            audio_data = f.read()

        # Encode to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Send fragment
        await sio.emit('fragment:data', {
            'fragment_id': 'frag-001',
            'stream_id': 'test-stream-123',
            'sequence_number': 1,
            'timestamp': 0,
            'audio': audio_base64,
            'sample_rate': 16000,
            'channels': 1,
            'format': 'pcm_s16le',
            'duration_ms': 6000
        })

    # Wait for processing
    await asyncio.sleep(10)

    # End stream
    await sio.emit('stream:end')
    await asyncio.sleep(2)

    # Disconnect
    await sio.disconnect()

# Run client
asyncio.run(test_full_sts())
```

### Expected Output

```
Connected to Full STS Service
Stream ready: {'session_id': 'sess-abc123', 'max_inflight': 3, 'capabilities': ['asr', 'translation', 'tts', 'duration_matching']}
Fragment acknowledged: {'fragment_id': 'frag-001', 'status': 'queued', 'timestamp': 1704230400}
Fragment processed: {
  'fragment_id': 'frag-001',
  'status': 'success',
  'dubbed_audio': 'base64-encoded-audio...',
  'transcript': 'Hello world',
  'translated_text': 'Hola mundo',
  'metadata': {
    'original_duration_ms': 6000,
    'dubbed_duration_ms': 6200,
    'duration_variance_percent': 3.3,
    'speed_ratio': 0.97
  },
  'processing_time_ms': 4500,
  'stage_timings': {
    'asr_ms': 2500,
    'translation_ms': 150,
    'tts_ms': 1800
  }
}
Received 192000 bytes of dubbed audio
```

---

## 8. Deployment to RunPod

### Step 1: Build Docker Image

```bash
cd /path/to/live-broadcast-dubbing-cloud

# Build image
docker build -f apps/sts-service/deploy/Dockerfile.full \
  -t your-registry/full-sts-service:v1.0.0 .

# Test locally first
docker run --gpus all -p 8000:8000 \
  -e DEEPL_AUTH_KEY=your-key \
  your-registry/full-sts-service:v1.0.0
```

### Step 2: Push to Container Registry

```bash
# Login to registry (Docker Hub, AWS ECR, etc.)
docker login your-registry

# Push image
docker push your-registry/full-sts-service:v1.0.0
```

### Step 3: Deploy to RunPod

**RunPod Template Configuration**:

- **Container Image**: `your-registry/full-sts-service:v1.0.0`
- **GPU Type**: NVIDIA RTX 3090 or better (8GB+ VRAM)
- **Expose Ports**: `8000` (HTTP + WebSocket)
- **Environment Variables**:
  ```
  DEEPL_AUTH_KEY=your-actual-deepl-api-key
  ASR_MODEL_SIZE=medium
  ASR_DEVICE=cuda
  TTS_DEVICE=cuda
  LOG_LEVEL=INFO
  ```
- **Volume Mounts** (optional, for model caching):
  - Container Path: `/root/.cache/huggingface`
  - Volume Size: 20GB

### Step 4: Verify Deployment

```bash
# Get RunPod pod URL (e.g., https://your-pod-id.runpod.net)
RUNPOD_URL=https://your-pod-id.runpod.net

# Health check
curl $RUNPOD_URL/health

# Metrics
curl $RUNPOD_URL/metrics

# Socket.IO connection test
python3 test_socketio_client.py --url $RUNPOD_URL
```

---

## 9. Troubleshooting

### Issue: GPU Out of Memory (OOM)

**Symptoms**:
```
RuntimeError: CUDA out of memory. Tried to allocate X MiB
```

**Solutions**:
1. **Use smaller ASR model**:
   ```bash
   ASR_MODEL_SIZE=small  # or base
   ```

2. **Reduce backpressure threshold**:
   ```bash
   BACKPRESSURE_THRESHOLD_CRITICAL=5  # Limit in-flight fragments
   ```

3. **Use CPU fallback for ASR** (TTS still on GPU):
   ```bash
   ASR_DEVICE=cpu  # TTS_DEVICE=cuda
   ```

### Issue: DeepL API Errors

**Symptoms**:
```
fragment:processed status=failed, error.code="RATE_LIMIT_EXCEEDED"
```

**Solutions**:
1. **Check API key**:
   ```bash
   curl -X POST https://api-free.deepl.com/v2/translate \
     -H "Authorization: DeepL-Auth-Key your-key" \
     -d "text=Hello&target_lang=ES"
   ```

2. **Monitor quota**:
   - Free tier: 500,000 characters/month
   - Check usage: https://www.deepl.com/account/usage

3. **Implement retry logic** (already built-in):
   - Workers should retry on `retryable=true` errors

### Issue: Voice Profile Not Found

**Symptoms**:
```
error.code="INVALID_VOICE_PROFILE"
```

**Solutions**:
1. **Check voices.json**:
   ```bash
   cat config/voices.json
   ```

2. **Use default voice** (omit `voice_profile` in `stream:init`):
   ```json
   {
     "source_language": "en",
     "target_language": "es"
     // voice_profile omitted → use default
   }
   ```

### Issue: Slow Processing (>10s per fragment)

**Symptoms**:
- `processing_time_ms > 10000`
- Backpressure events

**Solutions**:
1. **Verify GPU is being used**:
   ```bash
   nvidia-smi
   # Should show Python process using GPU
   ```

2. **Check model size**:
   ```bash
   ASR_MODEL_SIZE=medium  # Not large-v3
   ```

3. **Monitor metrics**:
   ```bash
   curl http://localhost:8000/metrics | grep sts_asr_duration
   # Should be <3s for GPU, <15s for CPU
   ```

### Issue: Duration Mismatch Exceeded

**Symptoms**:
```
fragment:processed status=failed, error.code="DURATION_MISMATCH_EXCEEDED"
```

**Explanation**: Dubbed audio duration differs from original by >20%.

**Solutions**:
1. **Adjust thresholds** (if acceptable):
   ```bash
   DURATION_VARIANCE_PARTIAL_MAX=0.25  # Allow 25% variance
   ```

2. **Check TTS settings**: May need better voice cloning or language pair.

3. **Fallback to original audio** (worker-side logic):
   - If status=failed, use original audio instead of dubbed

### Issue: Docker Build Fails

**Symptoms**:
```
ERROR: failed to solve: failed to fetch ...
```

**Solutions**:
1. **Check network**:
   ```bash
   docker build --network=host ...
   ```

2. **Clear cache**:
   ```bash
   docker builder prune -a
   ```

3. **Build with --no-cache**:
   ```bash
   docker build --no-cache -f deploy/Dockerfile.full .
   ```

---

## 10. API Reference

### Socket.IO Events

#### Client → Server

**stream:init**
```json
{
  "source_language": "en",
  "target_language": "es",
  "voice_profile": "spanish_male_1",  // optional
  "chunk_duration_ms": 6000,
  "sample_rate_hz": 16000,
  "channels": 1,
  "format": "pcm_s16le"
}
```

**fragment:data**
```json
{
  "fragment_id": "frag-001",
  "stream_id": "stream-123",
  "sequence_number": 1,
  "timestamp": 0,
  "audio": "base64-encoded-pcm-audio",
  "sample_rate": 16000,
  "channels": 1,
  "format": "pcm_s16le",
  "duration_ms": 6000
}
```

**stream:pause** / **stream:resume** / **stream:end**
```json
{}  // Empty payload
```

#### Server → Client

**stream:ready**
```json
{
  "session_id": "sess-abc123",
  "max_inflight": 3,
  "capabilities": ["asr", "translation", "tts", "duration_matching"]
}
```

**fragment:ack**
```json
{
  "fragment_id": "frag-001",
  "status": "queued",
  "timestamp": 1704230400
}
```

**fragment:processed** (success)
```json
{
  "fragment_id": "frag-001",
  "status": "success",
  "dubbed_audio": "base64-encoded-dubbed-audio",
  "transcript": "Hello world",
  "translated_text": "Hola mundo",
  "metadata": {
    "original_duration_ms": 6000,
    "dubbed_duration_ms": 6200,
    "duration_variance_percent": 3.3,
    "speed_ratio": 0.97
  },
  "processing_time_ms": 4500,
  "stage_timings": {
    "asr_ms": 2500,
    "translation_ms": 150,
    "tts_ms": 1800
  }
}
```

**fragment:processed** (failed)
```json
{
  "fragment_id": "frag-001",
  "status": "failed",
  "error": {
    "stage": "asr",
    "code": "TIMEOUT",
    "message": "ASR processing exceeded timeout of 5000ms",
    "retryable": true
  }
}
```

**backpressure**
```json
{
  "stream_id": "stream-123",
  "severity": "medium",
  "action": "slow_down",
  "current_inflight": 5,
  "max_inflight": 3,
  "threshold_exceeded": "medium"
}
```

### HTTP Endpoints

**GET /health**
- **Response**: `{"status": "healthy"}`
- **Use**: Health checks, load balancer probes

**GET /metrics**
- **Response**: Prometheus format metrics
- **Use**: Observability, monitoring

**Metrics Available**:
- `sts_fragment_processing_seconds` - Processing time histogram
- `sts_asr_duration_seconds` - ASR stage latency
- `sts_translation_duration_seconds` - Translation stage latency
- `sts_tts_duration_seconds` - TTS stage latency
- `sts_fragments_in_flight` - Current in-flight fragments
- `sts_fragment_errors_total` - Error counter by stage and code
- `sts_gpu_utilization_percent` - GPU utilization gauge
- `sts_gpu_memory_used_bytes` - GPU memory usage gauge

---

## Next Steps

1. **Production Deployment**: Follow [Deployment to RunPod](#8-deployment-to-runpod)
2. **Integration with media-service**: See `tests/e2e/test_full_pipeline.py` for example
3. **Voice Cloning**: Create custom voice profiles in `config/voices.json`
4. **Monitoring**: Set up Prometheus + Grafana for metrics visualization
5. **Scaling**: Deploy multiple RunPod pods with load balancer

**Support**: See [Troubleshooting](#9-troubleshooting) or open an issue on GitHub.
