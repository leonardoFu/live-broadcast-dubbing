# Implementation Plan: Dual Docker-Compose E2E Test Infrastructure

**Branch**: `019-dual-docker-e2e-infrastructure` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-dual-docker-e2e-infrastructure/spec.md`

## Summary

This plan implements a comprehensive E2E test infrastructure using **two separate docker-compose configurations** to test the full live dubbing pipeline with real services: media-service + MediaMTX + **real STS service** (ASR, Translation, TTS). Unlike spec 018 (Echo STS), this validates the complete integration without mocking.

Key deliverables:
1. Two docker-compose files: `apps/media-service/docker-compose.e2e.yml` and `apps/sts-service/docker-compose.e2e.yml`
2. E2E test suite orchestrating both compositions with session-scoped fixtures (start once, unique stream names)
3. Test fixture: 30-second video with counting phrases "One, two, three... thirty" for deterministic ASR validation
4. Helper utilities for Docker lifecycle, stream publishing, metrics parsing, and audio fingerprinting
5. Dual output validation: Socket.IO event monitoring + spectral fingerprint comparison

Technical approach: Bridge networking with port exposure (`localhost:<port>` for inter-service communication), session-scoped pytest fixtures to amortize STS model loading (30s+), unique stream names per test for isolation without restart overhead.

## Technical Context

**Language/Version**: Python 3.10.x (per constitution `>=3.10,<3.11` and pyproject.toml requirement)
**Primary Dependencies**: pytest>=7.0, pytest-asyncio, python-socketio[client], prometheus_client, docker-py, ffmpeg/ffprobe
**Storage**: Docker volumes for MediaMTX streams + STS model cache, in-memory test state
**Testing**: pytest with dual Docker Compose orchestration, Socket.IO client for event monitoring, spectral analysis for audio fingerprinting
**Target Platform**: Linux/macOS (local dev + CI environment)
**Project Type**: Cross-service E2E test suite (media-service + MediaMTX + real STS service)
**Performance Goals**: 30-second test fixture completes in <180 seconds (including real STS latency), tests run reliably in CI (95% pass rate)
**Constraints**: Tests must handle real STS latency (15s per 6s fragment), session-scoped fixtures reduce startup time, cleanup must work even on test failure
**Scale/Scope**: 5 test files (P1: 3, P2: 3, P3: 2), ~12-15 test cases total, reusable for future STS module testing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (7 user stories mapped to test suites)
- [x] Mock patterns documented (real STS service - no mocking of ASR/Translation/TTS, but Echo STS available for fast iteration per spec 018)
- [x] Coverage targets specified (E2E tests validate integration, not code coverage)
- [x] Test infrastructure matches constitution requirements (pytest, Docker Compose isolation per Principle II)
- [x] Test organization follows standard structure (tests/e2e/ for cross-service tests per monorepo spec)

**Principle II - Testability Through Isolation**:
- [x] E2E tests use isolated Docker Compose environments (two separate compositions)
- [x] Test fixtures are deterministic (30s counting phrases for known ASR outputs)
- [x] Real STS provides no mocks for ASR/Translation/TTS (validation without shortcuts)
- [x] Tests clean up resources in teardown (docker-compose down, unique stream names)

**Principle III - Spec-Driven Development**:
- [x] Spec created first (spec.md) with 5 clarifications resolved, architectural decisions documented
- [x] Implementation plan follows spec (this document)
- [x] Contracts defined for docker-compose files and environment variables

**Principle IV - Observability & Debuggability**:
- [x] Tests validate Prometheus metrics via /metrics endpoint
- [x] Tests capture and analyze container logs for debugging
- [x] Tests verify real transcripts and translations in STS outputs

**Principle V - Graceful Degradation**:
- [x] 30s timeout test validates passthrough fallback (STS latency → original audio)
- [x] Tests confirm pipeline completes with warnings (not hard failures)

**Principle VI - A/V Sync Discipline**:
- [x] A/V sync E2E test validates PTS delta < 120ms throughout pipeline
- [x] Tests verify video passthrough preserves timestamps with real STS processing

**Principle VII - Incremental Delivery**:
- [x] Tests prioritized (P1, P2, P3) for incremental implementation
- [x] P1 tests validate core functionality before resilience testing

**Status**: All constitution gates PASSED. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/019-dual-docker-e2e-infrastructure/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (Docker networking, STS services)
├── data-model.md        # Phase 1 output (test config, docker compose models)
├── contracts/           # Phase 1 output (environment variable schemas)
│   ├── media-service-env.json
│   └── sts-service-env.json
├── quickstart.md        # Phase 1 output (how to run dual-compose E2E tests)
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
tests/e2e/                                    # Cross-service E2E tests (root level)
├── __init__.py
├── conftest.py                               # Shared fixtures (dual Docker Compose)
├── pytest.ini                                # Pytest configuration for E2E tests
├── .env.dual-compose                         # Environment overrides for both services
├── helpers/                                  # Test utilities
│   ├── __init__.py
│   ├── docker_compose_manager.py             # Dual compose lifecycle management
│   ├── stream_publisher.py                   # ffmpeg RTSP publishing with cleanup
│   ├── metrics_parser.py                     # Prometheus metrics parsing
│   ├── stream_analyzer.py                    # ffprobe PTS + audio fingerprinting
│   └── socketio_monitor.py                   # Socket.IO event capture for validation
├── fixtures/                                 # Test data
│   └── test_streams/
│       └── 30s-counting-english.mp4          # 30s H.264 + AAC (counting phrases)
├── test_dual_compose_full_pipeline.py        # P1: Full pipeline E2E
├── test_dual_compose_service_communication.py # P1: Service connectivity
├── test_dual_compose_real_sts_processing.py  # P1: Real ASR/Translation/TTS
├── test_dual_compose_output_validation.py    # P2: Output stream quality
├── test_dual_compose_fixture_management.py   # P2: Fixture publishing
├── test_dual_compose_compose_lifecycle.py    # P2: Independent compositions
└── test_dual_compose_env_configuration.py    # P3: Config flexibility

apps/media-service/                           # Media service docker-compose
├── docker-compose.e2e.yml                    # MediaMTX + media-service
└── .env.e2e.example                          # Example environment variables

apps/sts-service/                             # STS service docker-compose
├── docker-compose.e2e.yml                    # Real STS service (ASR + Translation + TTS)
├── .env.e2e.example                          # Example environment variables
└── deploy/
    └── Dockerfile                            # STS container image (if not exists)
```

**Structure Decision**: Two docker-compose files placed in their respective service directories (`apps/media-service/`, `apps/sts-service/`) for independent development. E2E test suite at repository root `tests/e2e/` orchestrates both compositions via pytest fixtures. This matches monorepo spec: "E2E tests spanning multiple services (media-service + sts-service)".

## Test Strategy

### Test Levels for This Feature

**E2E Tests** (primary focus):
- Target: Full pipeline integration with real STS service (no mocking of ASR/Translation/TTS)
- Tools: pytest, Docker Compose (2 files), ffmpeg, ffprobe, python-socketio client, spectral analysis libraries
- Coverage: 7 user stories from spec (full pipeline, service discovery, real STS, fixtures, compose lifecycle, output validation, env config)
- Mocking: None for STS modules (real Whisper ASR, real Translation, real Coqui TTS)
- Location: `tests/e2e/`
- Validation: Metrics endpoint, log analysis, output stream inspection, PTS verification, Socket.IO event monitoring, audio fingerprinting

**Unit/Integration Tests** (reference only - not created in this feature):
- STS service modules (ASR, Translation, TTS) already tested in specs 005, 006, 008
- Media-service integration tests already exist in spec 018

### Test Fixtures

**Primary Fixture**:
- File: `tests/fixtures/test_streams/30s-counting-english.mp4`
- Duration: 30 seconds
- Video: H.264, 1280x720, 30fps
- Audio: AAC, 48kHz stereo, English counting phrases "One, two, three... thirty" (~1 number/second)
- Expected Segments: 5 (6 seconds each)
- Purpose: Deterministic ASR validation (known transcripts), continuous speech across segments

**Fixture Creation Strategy** (if not exists):
Generate synthetic video with ffmpeg using text-to-speech or record counting audio:
```bash
# Option 1: Generate synthetic audio with espeak/festival
espeak "One, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve, thirteen, fourteen, fifteen, sixteen, seventeen, eighteen, nineteen, twenty, twenty-one, twenty-two, twenty-three, twenty-four, twenty-five, twenty-six, twenty-seven, twenty-eight, twenty-nine, thirty" -w /tmp/counting.wav -s 30

# Option 2: Record manually and combine with test pattern video
ffmpeg -f lavfi -i testsrc=duration=30:size=1280x720:rate=30 -i /tmp/counting.wav -c:v libx264 -c:a aac -shortest 30s-counting-english.mp4
```

**Docker Environment** (two separate compositions):

Media Service Composition (`apps/media-service/docker-compose.e2e.yml`):
- MediaMTX: RTSP server (port 8554), RTMP server (port 1935), API (port 9997)
- media-service: WorkerRunner with metrics endpoint (port 8080)
- Network: Bridge networking with container names for internal communication
- Volumes: segments-data (shared storage)

STS Service Composition (`apps/sts-service/docker-compose.e2e.yml`):
- sts-service: Socket.IO server (port 3000), ASR + Translation + TTS
- Network: Bridge networking with port exposure to host
- Volumes: model-cache (persist Whisper + TTS models across runs)

**Helper Fixtures** (conftest.py):
- `media_compose_env`: Start/stop media-service docker-compose (session scope)
- `sts_compose_env`: Start/stop sts-service docker-compose (session scope)
- `dual_compose_env`: Combined fixture ensuring both environments running
- `publish_test_fixture`: Publish 30s counting fixture to unique stream name per test
- `metrics_client`: Query /metrics endpoint
- `socketio_monitor`: Capture Socket.IO fragment:processed events
- `log_capture`: Capture container logs for assertions
- `cleanup_resources`: Ensure teardown even on test failure

### Mock Patterns (Real STS Service - No Mocking)

**Real STS Processing** (spec 005, 006, 008):
- ASR: Real Whisper model (whisper-small for speed/accuracy balance)
- Translation: Real translation provider (Google Translate or equivalent)
- TTS: Real Coqui TTS model (tts_models/en/ljspeech/tacotron2-DDC)
- Processing Time: ~15s per 6s fragment (real latency, no mocks)

**Output Validation Strategy** (dual approach per spec clarification Q4):
1. **Socket.IO Event Monitoring**: Capture all `fragment:processed` events, verify `dubbed_audio` field present for all 5 segments
2. **Audio Fingerprinting**: Extract output audio, compute spectral hash (chromaprint or similar), compare against original to confirm audio differs

**No Mocking of STS Components**: This is the defining feature of this spec vs. spec 018. Real ASR, real translation, real TTS - full integration testing.

### Coverage Enforcement

**E2E Test Success Criteria**:
- All P1 tests pass (full pipeline, service communication, real STS)
- All P2 tests pass (output validation, fixtures, compose lifecycle)
- P3 tests pass (env configuration) for production readiness
- Tests run reliably in CI (95% pass rate over 10 runs)
- Test suite completes in <10 minutes total (30s fixture + real STS latency)

**No Code Coverage Metrics**:
E2E tests validate integration behavior, not line coverage. Unit tests in service modules provide coverage.

### Test Naming Conventions

Follow spec user story mapping:
- `test_full_pipeline_media_to_sts_to_output()` - User Story 1 (P1)
- `test_services_can_communicate()` - User Story 2 (P1)
- `test_sts_processes_real_audio()` - User Story 3 (P1)
- `test_fixture_properties()` - User Story 4 (P2)
- `test_media_service_compose_starts()` - User Story 5 (P2)
- `test_output_stream_is_playable()` - User Story 6 (P2)
- `test_env_config_overrides()` - User Story 7 (P3)

## Complexity Tracking

No constitution violations. E2E test suite aligns with:
- Principle II (isolated Docker environments, deterministic fixtures)
- Principle VIII (test strategy defined before implementation)
- Spec-driven development (spec.md with 5 clarifications resolved first)

No additional complexity introduced. Dual docker-compose pattern is standard for microservices testing.

## Phase 0: Research & Unknowns

**Research Tasks**:

1. **Dual Docker Compose Orchestration**: How to manage two separate docker-compose files in pytest?
   - Research subprocess-based docker-compose lifecycle (up, down, logs)
   - Find patterns for health check coordination across compositions
   - Investigate docker-compose project naming to avoid conflicts

2. **Session-Scoped Fixtures with Unique Stream Names**: How to balance startup cost vs. isolation?
   - Research pytest fixture scopes (session vs. function)
   - Find patterns for test isolation with shared infrastructure (unique stream names)
   - Investigate cleanup strategies for session-scoped fixtures

3. **Real STS Service Performance**: What are realistic latency expectations for CPU-only processing?
   - Research Whisper-small inference time on CPU (expected: 5-10s per 6s fragment)
   - Find Translation API latency baselines (expected: 1-2s)
   - Research Coqui TTS synthesis time (expected: 3-5s per 6s audio)
   - Total expected: 10-17s per fragment (inform test timeouts)

4. **Audio Fingerprinting for Output Validation**: How to verify dubbed audio vs. original?
   - Research chromaprint/acoustid libraries for spectral hashing
   - Alternative: Simple FFT-based fingerprint with numpy
   - Find patterns for "audio differs from original" validation (hash comparison)

5. **Socket.IO Event Monitoring in Tests**: How to capture fragment:processed events?
   - Research python-socketio client subscription patterns
   - Find patterns for event capture in pytest (asyncio queues, callbacks)
   - Investigate timeout strategies for "wait for N events"

6. **Bridge Networking with host.docker.internal**: How does media-service reach STS on host?
   - Research Docker bridge networking + extra_hosts configuration
   - Find patterns for cross-compose communication via localhost ports
   - Investigate macOS vs. Linux differences (host.docker.internal support)

**Output**: research.md documenting decisions for each research task

## Phase 1: Design & Implementation Structure

### Data Model (Test Configuration & Docker Compose Models)

**Entities** (see data-model.md):

1. **Dual Compose Environment Configuration**
   - media_compose_config: Docker Compose config for media-service + MediaMTX
   - sts_compose_config: Docker Compose config for sts-service
   - Environment variables: MEDIAMTX_RTSP_PORT, MEDIAMTX_RTMP_PORT, STS_PORT, STS_SERVICE_URL
   - Health check endpoints: MediaMTX /v3/paths/list, media-service /health, sts-service /health

2. **Test Fixture Metadata**
   - File path: tests/fixtures/test_streams/30s-counting-english.mp4
   - Properties: duration, video_codec, audio_codec, sample_rate
   - Expected ASR output: Known transcripts for each 6s segment (segment 1: "One, two, three, four, five, six", etc.)
   - Publishing config: RTSP URL format, ffmpeg command template

3. **Service Endpoint Configuration**
   - MediaMTX endpoints: rtsp://localhost:8554 (external), rtsp://mediamtx:8554 (internal to media-service)
   - STS endpoint: http://localhost:3000 (external), http://host.docker.internal:3000 (from media-service container)
   - Metrics endpoint: http://localhost:8080/metrics
   - Stream URLs: Input rtsp://localhost:8554/live/{test_name}/in, Output rtmp://localhost:1935/live/{test_name}/out

4. **Pipeline Validation Metrics**
   - Socket.IO events: fragment:processed count, dubbed_audio field presence
   - Prometheus metrics: worker_audio_fragments_total{status=processed}, worker_av_sync_delta_ms
   - Output stream properties: ffprobe duration, codec validation, PTS deltas
   - Audio fingerprint: Spectral hash of output audio, comparison against original

5. **Session State Tracking**
   - Composition lifecycle: started_at, health_check_passed_at, stopped_at
   - Test stream registry: Map test_name → stream_name for isolation
   - Cleanup tracking: Processes to kill (ffmpeg), volumes to remove, logs to collect

### API Contracts

**Media Service Docker Compose Environment Variables** (see contracts/media-service-env.json):
```json
{
  "MEDIAMTX_RTSP_PORT": "8554",
  "MEDIAMTX_RTMP_PORT": "1935",
  "MEDIAMTX_API_PORT": "9997",
  "MEDIA_SERVICE_PORT": "8080",
  "STS_SERVICE_URL": "http://host.docker.internal:3000",
  "LOG_LEVEL": "DEBUG",
  "SEGMENT_DIR": "/tmp/segments"
}
```

**STS Service Docker Compose Environment Variables** (see contracts/sts-service-env.json):
```json
{
  "STS_PORT": "3000",
  "HOST": "0.0.0.0",
  "LOG_LEVEL": "INFO",
  "ASR_MODEL": "whisper-small",
  "TRANSLATION_PROVIDER": "google",
  "TTS_PROVIDER": "coqui",
  "TTS_MODEL": "tts_models/en/ljspeech/tacotron2-DDC",
  "DEVICE": "cpu",
  "MAX_INFLIGHT": "3",
  "PROCESSING_TIMEOUT": "30"
}
```

**Docker Compose Health Check Contracts**:
- MediaMTX: `GET http://localhost:9997/v3/paths/list` → 200 OK
- media-service: `GET http://localhost:8080/health` → 200 OK
- sts-service: `GET http://localhost:3000/health` → 200 OK

### Test Implementation Phases

**Phase 1: Infrastructure Setup** (P0 - prerequisite for all tests)
- Create `apps/media-service/docker-compose.e2e.yml` with MediaMTX + media-service
- Create `apps/sts-service/docker-compose.e2e.yml` with real STS service
- Create `tests/e2e/conftest.py` with dual compose session-scoped fixtures
- Create helpers/ for Docker Compose lifecycle, stream publishing, metrics, Socket.IO monitoring
- Validate dual environment startup/teardown with health checks

**Phase 2: P1 Tests** (core functionality)
- test_dual_compose_full_pipeline.py: Validate 30s counting fixture → real STS → output stream
- test_dual_compose_service_communication.py: Validate health checks, Socket.IO connection
- test_dual_compose_real_sts_processing.py: Validate ASR transcripts, translations, TTS output

**Phase 3: P2 Tests** (output validation & fixtures)
- test_dual_compose_output_validation.py: Validate playable stream, A/V sync, audio fingerprint
- test_dual_compose_fixture_management.py: Validate fixture publishing, cleanup
- test_dual_compose_compose_lifecycle.py: Validate independent compose startup

**Phase 4: P3 Tests** (configuration)
- test_dual_compose_env_configuration.py: Validate environment variable overrides

**Phase 5: CI Integration** (production readiness)
- Add dual-compose E2E test suite to CI pipeline
- Validate 95% pass rate over 10 runs
- Document timeout tuning for real STS latency

### Quickstart Guide

See quickstart.md for:
- Prerequisites (Docker, Docker Compose v2, ffmpeg, Python 3.10)
- Running dual-compose E2E tests locally
- Debugging test failures (logs, metrics, stream inspection)
- Adding new dual-compose E2E tests
- Troubleshooting common issues (port conflicts, model download failures)

## Dependencies

**External Services**:
- MediaMTX (containerized via apps/media-service/docker-compose.e2e.yml)
- Real STS Service (containerized via apps/sts-service/docker-compose.e2e.yml)
  - ASR: Whisper-small model
  - Translation: Google Translate or equivalent
  - TTS: Coqui TTS model

**Python Libraries**:
- pytest>=7.0
- pytest-asyncio
- python-socketio[client]>=5.0
- prometheus_client (metrics parsing)
- docker>=6.0 (Python Docker client for compose management)
- numpy (audio fingerprinting)
- scipy (spectral analysis)
- PyYAML (docker-compose parsing)

**Infrastructure**:
- Docker Engine
- Docker Compose v2
- ffmpeg (stream publishing)
- ffprobe (PTS analysis, stream inspection)

**Specifications**:
- specs/003-gstreamer-stream-worker/spec.md (WorkerRunner behavior)
- specs/005-audio-transcription-module/spec.md (ASR module)
- specs/006-translation-component/spec.md (Translation module)
- specs/008-tts-module/spec.md (TTS module)
- specs/016-websocket-audio-protocol.md (Socket.IO protocol)
- specs/017-echo-sts-service/spec.md (Echo STS for fast testing - reference only)
- specs/018-e2e-stream-handler-tests/spec.md (E2E tests with Echo STS - reference for patterns)

## Out of Scope

- GPU-based STS service testing (CPU-only for simplicity, accepting slower processing)
- Performance benchmarking (latency optimization, throughput limits)
- Load testing (multiple concurrent streams)
- Multi-worker orchestration (only single worker instance)
- Production deployment automation (K8s, service mesh)
- Custom error injection beyond timeout testing
- Multiple language combinations (primary: English → Spanish only)
- Real-time streaming from live sources (only pre-recorded fixtures)

## Next Steps

After /speckit.plan completion:
1. Execute Phase 0 research (see research.md)
2. Generate data-model.md (dual compose environment, test fixtures)
3. Generate contracts/media-service-env.json and contracts/sts-service-env.json
4. Generate quickstart.md (dual-compose E2E test execution guide)
5. Run /speckit.tasks to break down implementation into tasks
6. Run /speckit.checklist to generate validation checklist
