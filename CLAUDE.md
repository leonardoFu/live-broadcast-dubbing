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

### Setup

- `make setup` - Create root venv and install all services
- `make media-setup` - Setup media-service venv only

### Docker (Media Service)

- `make media-dev` - Start media-service with Docker Compose
- `make media-down` - Stop media-service Docker services
- `make media-logs` - View media-service Docker logs
- `make media-ps` - List media-service Docker containers

### Code Quality

- `make fmt` - Format code with ruff
- `make lint` - Lint code with ruff
- `make typecheck` - Type check with mypy
- `make clean` - Remove build artifacts and caches

### Testing (Media Service)

- `make media-test` - Run all media-service tests (unit + integration)
- `make media-test-unit` - Run media-service unit tests only
- `make media-test-integration` - Run media-service integration tests (requires Docker)
- `make media-test-coverage` - Run media-service tests with coverage report

### Testing (E2E - Cross-Service)

- `make e2e-test` - Run E2E tests spanning multiple services (media + STS)

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

- **Unit tests**: `apps/<service>/tests/unit/` - Fast, isolated, mocked dependencies
- **Integration tests**: `apps/<service>/tests/integration/` - Service + dependencies (e.g., media-service + MediaMTX)
- **E2E tests**: `tests/e2e/` - Cross-service tests spanning multiple services (media-service + sts-service)

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

## Commit & Pull Request Guidelines

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

## Recent Changes
- 001-python-monorepo-setup: Added Python 3.10.x (as specified in constitution and architecture spec) + setuptools>=68.0 (build system), ruff>=0.1.0 (linting), mypy>=1.0 (type checking), pytest>=7.0 (testing)
- 018-e2e-stream-handler-tests: Added E2E test infrastructure with Docker Compose, pytest-asyncio, python-socketio client, prometheus_client for metrics parsing, ffmpeg/ffprobe for stream analysis
