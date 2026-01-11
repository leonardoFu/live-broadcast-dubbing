# Repository Guidelines

## Project Structure & Module Organization

- `specs/`: Product/architecture specs. Start here before implementing changes.
- `.specify/`: Spec templates and shared "memory" used to generate/maintain specs.

### Standard Directory Structure

This repository follows a strict Python monorepo structure defined in `specs/001-python-monorepo-setup/contracts/directory-structure.json`. All new code MUST conform to this structure:

```
live-broadcast-dubbing-cloud/
├── apps/                          # Service applications (independent deployment)
│   ├── media-service/             # EC2 stream worker (CPU-only GStreamer pipeline)
│   │   ├── pyproject.toml         # Package metadata and dependencies
│   │   ├── requirements.txt       # Locked production dependencies
│   │   ├── requirements-dev.txt   # Locked development/test dependencies
│   │   ├── src/
│   │   │   └── media_service/     # Python package (snake_case)
│   │   │       ├── __init__.py
│   │   │       └── pipelines/     # Subpackages as needed
│   │   ├── tests/
│   │   │   ├── unit/              # Unit tests (mocked dependencies)
│   │   │   │   └── __init__.py
│   │   │   └── integration/       # Integration tests (media-service + MediaMTX)
│   │   │       └── __init__.py
│   │   ├── deploy/                # Deployment configurations
│   │   │   ├── Dockerfile         # Container image definition
│   │   │   └── mediamtx/          # MediaMTX configuration (dependency)
│   │   │       ├── mediamtx.yml   # MediaMTX server config
│   │   │       └── hooks/         # Hook scripts
│   │   ├── docker-compose.yml     # Local dev (media-service + MediaMTX)
│   │   └── README.md
│   │
│   └── sts-service/               # RunPod GPU service (speech-to-speech processing)
│       ├── pyproject.toml
│       ├── requirements.txt
│       ├── requirements-dev.txt
│       ├── src/
│       │   └── sts_service/       # Python package (snake_case)
│       │       ├── __init__.py
│       │       ├── asr/           # Automatic Speech Recognition
│       │       ├── translation/   # Translation engine
│       │       └── tts/           # Text-to-Speech
│       ├── tests/
│       │   └── unit/
│       │       └── __init__.py
│       ├── deploy/                # Deployment configurations
│       │   └── Dockerfile         # Container image definition
│       ├── docker-compose.yml     # Local dev environment
│       └── README.md
│
├── libs/                          # Shared libraries
│   ├── common/                    # Common utilities (audio, types, logging)
│   │   ├── pyproject.toml         # Minimal dependencies only
│   │   ├── src/
│   │   │   └── dubbing_common/    # MUST use dubbing_ prefix
│   │   │       └── __init__.py
│   │   ├── tests/
│   │   │   └── unit/
│   │   │       └── __init__.py
│   │   └── README.md
│   │
│   └── contracts/                 # API contracts and event schemas
│       ├── pyproject.toml
│       ├── src/
│       │   └── dubbing_contracts/ # MUST use dubbing_ prefix
│       │       └── __init__.py
│       ├── tests/
│       │   └── unit/
│       │       └── __init__.py
│       └── README.md
│
├── tests/                         # Cross-service E2E tests only
│   └── e2e/                       # E2E tests spanning multiple services (media + STS)
│       └── __init__.py            # Reserved for full dubbing pipeline tests
│
├── pyproject.toml                 # Root tooling configuration (ruff, mypy)
├── .gitignore                     # Git exclusion patterns
├── Makefile                       # Development workflow commands
└── README.md                      # Repository overview
```

### Naming Conventions

- **Services** (apps/*): Use kebab-case for directories, snake_case for Python packages
  - Example: `apps/media-service/src/media_service/`
- **Libraries** (libs/*): Use kebab-case for directories, snake_case with `dubbing_` prefix for packages
  - Example: `libs/common/src/dubbing_common/`
- **Test files**: Must start with `test_` prefix
  - Example: `test_pipeline.py`, `test_audio_utils.py`
- **Python modules**: snake_case only
  - Example: `audio_utils.py`, `stream_processor.py`

## Build, Test, and Development Commands

### Quick Reference

| Command | What It Does | When to Use |
|---------|--------------|-------------|
| `make setup` | Install all dependencies | First time setup |
| `make media-test-unit` | Fast unit tests | During development (TDD) |
| `make media-test-integration` | Integration tests with Docker | Before committing |
| `make e2e-test-p1` | Full pipeline E2E test | Before PR (critical path) |
| `make e2e-test-full` | E2E with auto service management | CI/CD pipeline |
| `make fmt && make lint` | Format and lint code | Before every commit |
| `make media-dev` | Start media-service locally | Local development |
| `make e2e-up` | Start all E2E services | Debugging E2E issues |
| `make e2e-logs` | View service logs | Troubleshooting |

**Pro tip**: Run `make help` to see all available commands with descriptions.

### Setup

```bash
make setup        # Create root venv and install all services
make media-setup  # Setup media-service venv only
```

After setup, activate the environment:
```bash
source .venv/bin/activate  # Root venv
# OR
source apps/media-service/venv/bin/activate  # Media service only
```

### Docker (Media Service)

```bash
make media-dev    # Start media-service with Docker Compose
make media-down   # Stop media-service Docker services
make media-logs   # View media-service Docker logs (follows last 200 lines)
make media-ps     # List media-service Docker containers
```

### Code Quality

```bash
make fmt          # Format code with ruff
make lint         # Lint code with ruff
make typecheck    # Type check with mypy
make clean        # Remove build artifacts and caches
make clean-artifacts  # Remove debug artifacts (.artifacts/)
```

### Testing (Media Service)

**Unit Tests** (fast, mocked dependencies):
```bash
make media-test-unit  # Run unit tests only
# Test path: apps/media-service/tests/unit/
```

**Integration Tests** (requires Docker - media-service + MediaMTX):
```bash
make media-test-integration  # Run integration tests
# Test path: apps/media-service/tests/integration/
```

**All Tests** (unit + integration):
```bash
make media-test          # Run all tests
make media-test-coverage # Run with coverage report (80% required)
```

### Testing (STS Service)

```bash
make sts-test          # Run all sts-service tests
make sts-test-unit     # Run unit tests only
make sts-test-e2e      # Run sts-service E2E tests
make sts-test-coverage # Run with coverage (80% required)
make sts-echo          # Start Echo STS Service (for E2E testing)
```

### Testing (E2E - Cross-Service)

E2E tests validate the complete dubbing pipeline across multiple services:
- **MediaMTX**: RTSP/RTMP media server (input/output streams)
- **media-service**: GStreamer pipeline (stream processing, segmentation)
- **sts-service**: Speech-to-speech processing (ASR, translation, TTS)

**Quick E2E Test** (requires services already running):
```bash
make e2e-test  # Run E2E tests (services must be up)
# Test path: tests/e2e/
# Flow: Test fixture → MediaMTX → media-service → STS → output validation
```

**Full E2E Test** (auto manages Docker services):
```bash
make e2e-test-full  # Start services, run tests, cleanup
```

**Manual E2E Workflow** (for debugging):
```bash
make e2e-up         # Start all E2E services (MediaMTX + STS + media-service)
make e2e-ps         # Check service status
make e2e-logs       # View logs (follows last 200 lines)
make e2e-test       # Run tests while services are running
make e2e-down       # Stop and cleanup services
```

**Priority-based E2E Tests**:
```bash
# P1 (Critical) - Full pipeline end-to-end
make e2e-test-p1
# Tests: Complete dubbing flow (RTSP→segments→STS→dubbed output)
#        A/V synchronization, fragment processing, output quality

# P2 (High) - Resilience & fault tolerance
make e2e-test-p2
# Tests: Circuit breaker (STS failure handling)
#        Backpressure (STS overload handling)
#        Fragment tracker (in-flight request management)

# P3 (Medium) - Connection resilience
make e2e-test-p3
# Tests: MediaMTX reconnection after disconnect
#        STS reconnection after network failure
#        Stream recovery and continuation
```

**Running Specific E2E Tests**:
```bash
# Run a specific test file
pytest tests/e2e/test_full_pipeline.py -v --log-cli-level=INFO

# Run a specific test function
pytest tests/e2e/test_full_pipeline.py::test_full_pipeline_media_to_sts_to_output -v

# Run tests matching a pattern
pytest tests/e2e/ -k "full_pipeline" -v
```

### Observability (Media Service)

```bash
make api-status  # Query MediaMTX Control API for active streams
make metrics     # Query Prometheus metrics endpoint
```

## Common Development Workflows

### Quick Start (First Time Setup)
```bash
make setup                # Install all dependencies
source .venv/bin/activate # Activate environment
make fmt && make lint     # Verify code quality
make media-test-unit      # Run quick unit tests
```

### Before Committing
```bash
make fmt                  # Format code
make lint                 # Check linting
make typecheck            # Type check
make media-test-coverage  # Ensure 80%+ coverage
```

### Debugging E2E Test Failures
```bash
make e2e-up               # Start services
make e2e-logs             # View logs in real-time
# In another terminal:
pytest tests/e2e/test_full_pipeline.py::test_full_pipeline_media_to_sts_to_output -v -s
make e2e-down             # Cleanup when done
```

### Testing a Specific Feature
```bash
# Example: Testing audio pipeline changes
make media-test-unit -k "audio"           # Run audio-related unit tests
make media-test-integration -k "audio"    # Run audio integration tests
make e2e-test -k "full_pipeline"          # Run E2E pipeline test
```

### Rebuilding Docker Images After Code Changes
```bash
# For E2E tests (rebuilds both media-service and sts-service):
make e2e-down                                      # Stop old containers
docker compose -f tests/e2e/docker-compose.yml build --no-cache  # Rebuild
make e2e-up                                        # Start with new images

# For media-service dev:
make media-down
make media-dev  # Automatically rebuilds with --build flag
```

## Coding Style & Naming Conventions

- Specs: keep headings stable, prefer short sections, and use fenced code blocks for pipelines/commands.
- Paths: use kebab-case for spec filenames (e.g., `specs/002-audio-pipeline.md`).
- If you introduce code, add a formatter/linter early and make it runnable via a single command (e.g., `make fmt`, `make lint`).

## Testing Guidelines

**TDD is mandatory** (Constitution Principle VIII). Tests MUST be written BEFORE implementation.

### Quick TDD Workflow

```bash
# 1. Write failing tests first
# 2. Run tests - verify they FAIL
# 3. Implement code
# 4. Run tests - verify they PASS
# 5. Check coverage (80% minimum, 95% for critical paths)
# 6. Commit (pre-commit hooks will validate)
```

See [TDD Quick Start Guide](docs/tdd-quickstart.md) for complete workflow.

### Test Organization

**Unit Tests** - Fast, isolated, mocked dependencies:
```
apps/media-service/tests/unit/
├── test_pipeline.py          # GStreamer pipeline unit tests
├── test_segment_buffer.py    # Segment buffering logic
└── test_av_sync.py           # A/V sync unit tests

apps/sts-service/tests/unit/
├── test_asr.py               # ASR module tests
├── test_translation.py       # Translation tests
└── test_tts.py               # TTS module tests
```

**Integration Tests** - Service + dependencies (requires Docker):
```
apps/media-service/tests/integration/
├── test_rtsp_input.py        # media-service + MediaMTX RTSP
└── test_segment_writing.py   # Segment file I/O with Docker volumes
```

**E2E Tests** - Cross-service tests (media-service + STS-service):
```
tests/e2e/
├── test_full_pipeline.py               # P1: Full dubbing pipeline (real STS)
│                                       # - RTSP stream ingestion
│                                       # - Segment generation (6s chunks)
│                                       # - STS processing (ASR→Translation→TTS)
│                                       # - A/V sync verification
│                                       # - RTMP output validation
│
├── test_pipeline_echo.py               # P1: Pipeline with Echo STS (basic test)
│
├── test_resilience.py                  # P2: Fault tolerance
│                                       # - Circuit breaker (open/half-open/closed)
│                                       # - Backpressure handling (STS overload)
│                                       # - Fragment tracking (max 3 in-flight)
│                                       # - Fallback to original audio
│
├── test_reconnection.py                # P3: Connection resilience
│                                       # - MediaMTX disconnect/reconnect
│                                       # - STS service restart handling
│                                       # - Stream state recovery
│
├── conftest_dual_compose.py            # E2E fixtures & Docker management
├── fixtures/test_streams/              # Test video files
│   ├── 1-min-nfl.mp4                   # Main e2e test stream
│   └── big-buck-bunny.mp4              # Long-form test
│
└── helpers/                            # E2E test utilities
    ├── docker_compose_manager.py       # Docker service lifecycle
    ├── socketio_monitor.py             # Socket.IO event monitoring
    ├── stream_publisher.py             # RTMP stream publishing
    ├── stream_analyzer.py              # ffprobe wrapper for validation
    └── metrics_parser.py               # Prometheus metrics parsing
```

**Test File Naming**:
- All test files MUST start with `test_` prefix
- Use descriptive names: `test_audio_pipeline.py`, `test_fragment_tracker.py`
- Match tested module name when possible: `segment_buffer.py` → `test_segment_buffer.py`

### Key Commands

- `make media-test` - Run all media-service tests (unit + integration)
- `make media-test-unit` - Run media-service unit tests only
- `make media-test-integration` - Run media-service integration tests (requires Docker)
- `make media-test-coverage` - Run tests with coverage report (80% required)
- `make install-hooks` - Install pre-commit hooks (enforces TDD)

### Mock Fixtures

Prefer deterministic tests; avoid requiring live RTMP endpoints. Mock STS events (`fragment:data`, `fragment:processed`) using fixtures from `.specify/templates/test-fixtures/`.

### Enforcement

- **Pre-commit hooks**: Block commits without tests
- **CI/CD**: Block PR merges if coverage <80% or tests missing
- **Constitution**: See Principle VIII for full TDD requirements

## Troubleshooting

### E2E Tests Failing

**Symptom**: E2E tests timeout or fail with "services not ready"
```bash
# Check service health
make e2e-ps        # Verify all containers are running
make e2e-logs      # Check for errors in logs

# Common fixes:
make e2e-down      # Clean shutdown
docker system prune -f  # Remove old containers/networks
make e2e-up        # Fresh start
```

**Symptom**: "No such container" errors
```bash
# Ensure services are running
make e2e-ps        # Should show 3+ containers
# If empty, start services first:
make e2e-up
```

**Symptom**: Tests pass locally but fail in CI
- Check Docker Compose file paths in `tests/e2e/`
- Verify all required fixtures exist in `tests/e2e/fixtures/`
- Ensure timeout values account for CI environment

### GStreamer Pipeline Issues

**Symptom**: "Failed to create element" errors
```bash
# Verify GStreamer plugins installed (in Docker container):
docker exec e2e-media-service gst-inspect-1.0 rtspsrc
docker exec e2e-media-service gst-inspect-1.0 rtpmp4gdepay
docker exec e2e-media-service gst-inspect-1.0 aacparse
```

**Symptom**: No audio/video samples received
```bash
# Enable GStreamer debug logging:
# In docker-compose.e2e.yml, add:
# environment:
#   - GST_DEBUG=3  # or GST_DEBUG=rtspsrc:5,rtpmp4gdepay:5
```

### MediaMTX Connection Issues

**Symptom**: "Connection refused" to MediaMTX
```bash
# Check MediaMTX health
curl http://localhost:8889/v3/paths/list
# Should return JSON with active streams

# Verify MediaMTX container is running:
docker ps | grep mediamtx
```

### Coverage Reports

**Symptom**: Coverage below 80% threshold
```bash
# Generate detailed HTML report:
make media-test-coverage
# Open: htmlcov/index.html in browser
# Focus on files with low coverage shown in red
```

## Git Workflow Guidelines

### Git Worktrees

When creating new git worktrees, **always** use the `.worktrees/` directory:

```bash
# Create a new worktree for a feature branch
git worktree add .worktrees/feature-branch-name feature-branch-name

# Create a new worktree and branch simultaneously
git worktree add -b new-feature .worktrees/new-feature

# List all worktrees
git worktree list

# Remove a worktree when done
git worktree remove .worktrees/feature-branch-name
```

**Why `.worktrees/`?**
- Keeps worktrees organized in a single location
- Prevents clutter in the repository root
- Already ignored by `.gitignore`
- Makes cleanup easier

### Commit & Pull Request Guidelines

- Git history is not established yet; use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`) going forward.
- PRs should link the relevant spec (e.g., `specs/001-spec.md`) and describe: local run steps, latency/AV-sync impact, and any config changes.
- Do not commit secrets (RTMP stream keys, API tokens). Add `.env.example` when introducing new required env vars.


## Active Technologies
- Python 3.10.x (as specified in constitution and architecture spec) + setuptools>=68.0 (build system), ruff>=0.1.0 (linting), mypy>=1.0 (type checking), pytest>=7.0 (testing) (001-python-monorepo-setup)
- File system (directory and file creation only) (001-python-monorepo-setup)
- Python 3.10.x (per constitution and pyproject.toml requirement `>=3.10,<3.11`) + python-socketio>=5.0, uvicorn>=0.24.0, pydantic>=2.0 (017-echo-sts-service)
- N/A (stateless, in-memory session state only) (017-echo-sts-service)
- Python 3.10.x + pytest>=7.0, pytest-asyncio, python-socketio[client], prometheus_client, Docker Compose v2, ffmpeg/ffprobe (stream analysis) (018-e2e-stream-handler-tests)
- Docker volumes for MediaMTX streams, in-memory test state (018-e2e-stream-handler-tests)
- Python 3.10.x (per constitution and existing monorepo setup) + TTS (Coqui TTS library), pydub (audio processing), rubberband (time-stretch), pydantic>=2.0 (data models), numpy (audio manipulation) (008-tts-module)
- In-memory model cache + optional debug artifacts to local filesystem (when debug_artifacts=True) (008-tts-module)
- Python 3.10 (per constitution and pyproject.toml requirement >=3.10,<3.11) + GStreamer 1.0 (PyGObject >= 3.44.0), rtmpsrc (gst-plugins-bad), flvdemux (gst-plugins-good) (020-rtmp-stream-pull)
- N/A (in-memory pipeline state, segment buffers written to disk via existing SegmentBuffer) (020-rtmp-stream-pull)
- Python 3.10.x (per constitution and pyproject.toml requirement `>=3.10,<3.11`) + GStreamer 1.0 (PyGObject >= 3.44.0), gst-plugins-good (level element), pydantic >= 2.0, prometheus_clien (023-vad-audio-segmentation)
- N/A (in-memory accumulator, existing segment files) (023-vad-audio-segmentation)
- Python 3.10.x (per constitution and pyproject.toml requirement `>=3.10,<3.11`) + asyncio (async buffer operations), bisect (sorted list), dataclasses (buffer entries) (024-pts-av-pairing)
- In-memory buffers only (sorted list for audio, deque for video) (024-pts-av-pairing)

## Recent Changes
- 001-python-monorepo-setup: Added Python 3.10.x (as specified in constitution and architecture spec) + setuptools>=68.0 (build system), ruff>=0.1.0 (linting), mypy>=1.0 (type checking), pytest>=7.0 (testing)
- 018-e2e-stream-handler-tests: Added E2E test infrastructure with Docker Compose, pytest-asyncio, python-socketio client, prometheus_client for metrics parsing, ffmpeg/ffprobe for stream analysis
