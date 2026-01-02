# Research: Dual Docker-Compose E2E Infrastructure

**Feature**: 019-dual-docker-e2e-infrastructure
**Date**: 2026-01-01

This document captures research findings for Phase 0 unknowns identified in the implementation plan.

## 1. Dual Docker Compose Orchestration

**Question**: How to manage two separate docker-compose files in pytest?

**Research Findings**:

### Subprocess-Based Lifecycle Management

**Recommended Approach**: Use Python `subprocess` module to invoke `docker-compose` commands:

```python
import subprocess
import time

class DockerComposeManager:
    def __init__(self, compose_file: str, project_name: str):
        self.compose_file = compose_file
        self.project_name = project_name

    def up(self, detach: bool = True):
        """Start docker-compose services."""
        cmd = [
            "docker-compose",
            "-f", self.compose_file,
            "-p", self.project_name,
            "up", "-d" if detach else ""
        ]
        subprocess.run(cmd, check=True)

    def down(self, volumes: bool = True):
        """Stop and remove docker-compose services."""
        cmd = [
            "docker-compose",
            "-f", self.compose_file,
            "-p", self.project_name,
            "down"
        ]
        if volumes:
            cmd.append("-v")
        subprocess.run(cmd, check=False)  # Don't fail on cleanup

    def wait_for_health(self, timeout: int = 60) -> bool:
        """Wait for all services to be healthy."""
        start = time.time()
        while time.time() - start < timeout:
            result = subprocess.run([
                "docker-compose",
                "-f", self.compose_file,
                "-p", self.project_name,
                "ps", "--filter", "health=healthy"
            ], capture_output=True, text=True)

            # Count healthy services (simple heuristic)
            healthy_count = result.stdout.count("healthy")
            expected_count = self._get_service_count()

            if healthy_count >= expected_count:
                return True

            time.sleep(2)

        return False
```

**Project Naming**: Use `-p` flag to assign unique project names and avoid conflicts:
- Media service: `e2e-media-019`
- STS service: `e2e-sts-019`

**Health Check Coordination**: Poll each composition's health checks independently, then proceed when both are ready.

**Decision**: Use subprocess-based management with unique project names. Simpler than docker-py library, better error messages.

---

## 2. Session-Scoped Fixtures with Unique Stream Names

**Question**: How to balance startup cost vs. isolation?

**Research Findings**:

### Pytest Fixture Scope Strategies

**Session Scope** (chosen for this feature):
- Start docker-compose environments once at session start
- All tests share the same running containers
- Amortize STS model loading cost (30s+) across all tests
- Isolation via unique stream names per test

**Unique Stream Name Pattern**:
```python
import time

@pytest.fixture
def publish_test_fixture(request):
    """Publish test fixture to unique stream name."""
    test_name = request.node.name
    timestamp = int(time.time())
    stream_name = f"test_{test_name}_{timestamp}"

    rtsp_url = f"rtsp://localhost:8554/live/{stream_name}/in"
    rtmp_url = f"rtmp://localhost:1935/live/{stream_name}/out"

    # Publish stream, yield URLs, cleanup
    ...

    yield {"rtsp": rtsp_url, "rtmp": rtmp_url, "stream_name": stream_name}

    # Cleanup: stop ffmpeg, delete stream from MediaMTX
    ...
```

**Cleanup Strategy for Session-Scoped Fixtures**:
```python
@pytest.fixture(scope="session")
def dual_compose_env():
    """Start both docker-compose environments."""
    media_manager = DockerComposeManager(
        "apps/media-service/docker-compose.e2e.yml",
        "e2e-media-019"
    )
    sts_manager = DockerComposeManager(
        "apps/sts-service/docker-compose.e2e.yml",
        "e2e-sts-019"
    )

    # Start both
    media_manager.up()
    sts_manager.up()

    # Wait for health
    assert media_manager.wait_for_health(timeout=60), "Media services not healthy"
    assert sts_manager.wait_for_health(timeout=60), "STS service not healthy"

    yield {"media": media_manager, "sts": sts_manager}

    # Cleanup: always runs even if tests fail
    media_manager.down(volumes=True)
    sts_manager.down(volumes=True)
```

**Decision**: Session scope with unique stream names provides optimal performance without sacrificing isolation.

---

## 3. Real STS Service Performance

**Question**: What are realistic latency expectations for CPU-only processing?

**Research Findings**:

### Expected Latency Breakdown (per 6s audio fragment)

**ASR (Whisper-small on CPU)**:
- Model: openai/whisper-small (244M parameters)
- CPU inference time: 5-10 seconds per 6s audio
- Source: Whisper benchmarks on CPU (Intel i7 8-core)

**Translation (Google Translate API)**:
- API latency: 500ms - 2s for short text (<100 words)
- Network overhead: 200ms - 500ms
- Total: 1-2.5s

**TTS (Coqui TTS on CPU)**:
- Model: Tacotron2-DDC (lightweight vocoder)
- CPU synthesis time: 3-5s per 6s audio
- Source: Coqui TTS benchmarks on CPU

**Total Expected Latency**: 10-17 seconds per 6s fragment (worst case: 17.5s)

### Test Timeout Recommendations

Based on latency analysis:
- Fragment timeout: 30s (per spec clarification Q3, allows for variance)
- Full pipeline (5 segments): 180s maximum (30s fixture + 5 × 17s processing + overhead)
- Health check timeout: 60s (STS model loading takes 30-40s)

**Decision**: Use 30s fragment timeout (matches spec), 180s total test timeout, 60s health check timeout.

---

## 4. Audio Fingerprinting for Output Validation

**Question**: How to verify dubbed audio vs. original?

**Research Findings**:

### Chromaprint/AcoustID (Industry Standard)

**Library**: `pyacoustid` + `fpcalc` binary

**Pros**:
- Robust spectral fingerprinting (Chromaprint algorithm)
- Works well for audio comparison
- Perceptually-based (detects content changes, not just bit differences)

**Cons**:
- External dependency (fpcalc binary)
- Heavyweight for simple E2E tests

### Simple FFT-Based Fingerprint (Numpy)

**Implementation**:
```python
import numpy as np
from scipy.io import wavfile
from scipy.fft import rfft

def compute_audio_fingerprint(audio_file: str) -> str:
    """Compute simple spectral hash of audio file."""
    sample_rate, audio = wavfile.read(audio_file)

    # Convert to mono if stereo
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    # Compute FFT for first 5 seconds (enough to detect dubbed audio)
    chunk = audio[:5 * sample_rate]
    spectrum = np.abs(rfft(chunk))

    # Hash top 100 frequency bins (perceptual hash)
    top_bins = np.argsort(spectrum)[-100:]
    fingerprint = hash(tuple(top_bins))

    return str(fingerprint)
```

**Pros**:
- No external dependencies (numpy + scipy already required)
- Fast and simple
- Sufficient for "audio differs from original" validation

**Cons**:
- Less robust than Chromaprint for perceptual similarity

### Decision: Dual Validation Strategy

1. **Primary**: Monitor Socket.IO `fragment:processed` events (confirms dubbing occurred)
2. **Secondary**: Simple FFT fingerprint comparison (confirms output audio differs from input)

Rationale: Socket.IO events provide strong signal (dubbing happened), fingerprint confirms it was applied to output stream.

---

## 5. Socket.IO Event Monitoring in Tests

**Question**: How to capture fragment:processed events?

**Research Findings**:

### Python SocketIO Client Pattern

**Library**: `python-socketio[client]`

**Event Capture with Asyncio Queue**:
```python
import asyncio
from socketio import AsyncClient

class SocketIOMonitor:
    def __init__(self, url: str):
        self.url = url
        self.client = AsyncClient()
        self.events = asyncio.Queue()

    async def connect(self):
        """Connect to STS service and register event handlers."""
        @self.client.on("fragment:processed")
        async def on_fragment_processed(data):
            await self.events.put(data)

        await self.client.connect(self.url)

    async def wait_for_events(self, count: int, timeout: float = 180) -> list:
        """Wait for N fragment:processed events."""
        collected = []
        deadline = asyncio.get_event_loop().time() + timeout

        while len(collected) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Only received {len(collected)}/{count} events")

            try:
                event = await asyncio.wait_for(self.events.get(), timeout=remaining)
                collected.append(event)
            except asyncio.TimeoutError:
                break

        return collected

    async def disconnect(self):
        """Disconnect from STS service."""
        await self.client.disconnect()
```

**Usage in Tests**:
```python
@pytest.mark.asyncio
async def test_full_pipeline_media_to_sts_to_output(dual_compose_env, publish_test_fixture):
    monitor = SocketIOMonitor("http://localhost:3000")
    await monitor.connect()

    # Wait for 5 fragment:processed events (30s / 6s = 5 segments)
    events = await monitor.wait_for_events(count=5, timeout=180)

    # Validate all events have dubbed_audio field
    for event in events:
        assert "dubbed_audio" in event, f"Event missing dubbed_audio: {event}"
        assert len(event["dubbed_audio"]) > 0, "Empty dubbed_audio"

    await monitor.disconnect()
```

**Decision**: Use AsyncClient with asyncio.Queue for event capture. Clean, testable, handles timeouts gracefully.

---

## 6. Bridge Networking with host.docker.internal

**Question**: How does media-service reach STS on host?

**Research Findings**:

### Docker Bridge Networking + extra_hosts

**Configuration** (apps/media-service/docker-compose.e2e.yml):
```yaml
services:
  media-service:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - STS_SERVICE_URL=http://host.docker.internal:3000
```

**How it works**:
- `host.docker.internal` resolves to host machine's gateway IP
- `host-gateway` is Docker magic keyword for host IP
- Works on Docker Desktop (macOS/Windows) and Linux (Docker 20.10+)

**Alternative for Linux < 20.10**:
```yaml
extra_hosts:
  - "host.docker.internal:172.17.0.1"  # Docker bridge gateway IP
```

**Why not service names?**: Services are in separate docker-compose files (different networks by default). Could use shared network, but port exposure simpler for development.

### STS Service Listens on 0.0.0.0

**Configuration** (apps/sts-service/docker-compose.e2e.yml):
```yaml
services:
  sts-service:
    environment:
      - HOST=0.0.0.0  # Listen on all interfaces
      - PORT=3000
    ports:
      - "3000:3000"   # Expose to host
```

**Why 0.0.0.0**: Allows connections from both localhost (pytest) and host.docker.internal (media-service container).

**Decision**: Use bridge networking with `extra_hosts` for media-service. Port exposure for both services. Simple, portable, production-like.

---

## Summary of Decisions

| Research Area | Decision | Rationale |
|---------------|----------|-----------|
| Docker Compose Orchestration | Subprocess-based management with unique project names | Simple, good error messages |
| Fixture Scope | Session scope + unique stream names | Performance (amortize STS loading) + isolation |
| STS Performance | 30s timeout per fragment, 180s total | Based on real CPU latency benchmarks |
| Audio Fingerprinting | Socket.IO events + simple FFT hash | Dual validation without heavy dependencies |
| Socket.IO Monitoring | AsyncClient with asyncio.Queue | Clean, testable, handles timeouts |
| Bridge Networking | extra_hosts + host.docker.internal | Portable, simple, production-like |

All decisions documented in plan.md Phase 1 design.
