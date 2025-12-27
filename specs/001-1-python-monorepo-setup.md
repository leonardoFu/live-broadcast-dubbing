# Python Monorepo Setup (Stream Infrastructure + STS Service)

## 1. Goal

Define a **Python monorepo structure** that supports two independent services with conflicting dependencies in a single repository:

- **Stream Infrastructure Project** (`apps/media-service/`): CPU-only, lightweight stream processing
- **STS Service** (`apps/sts-service/`): GPU-accelerated speech-to-speech processing

The setup must provide:
- **Isolated dependency trees** (CPU-only vs GPU-enabled PyTorch, different system requirements)
- **Shared code reuse** (common utilities, data contracts, configuration schemas)
- **Independent deployment** (separate Docker images, different cloud targets)
- **Type safety and testability** (strict typing, comprehensive test coverage)
- **Efficient local development** (single checkout, easy switching between services)

This spec is complementary to:
- `specs/001-2-docker-repo-setup.md` (container strategy)
- `specs/008-libraries-and-dependencies.md` (dependency baseline)
- `specs/015-deployment-architecture.md` (deployment split rationale)

---

## 2. Non-Goals

- Python version polyglot support (standardize on Python 3.10.x across all services).
- Full language polyglot support (no mixing Python with Go/Rust/Node in this spec).
- Microservice-per-module granularity (only two top-level services).
- Dynamic plugin systems or runtime module discovery.

---

## 3. Design Principles (Python Monorepo Best Practices)

- **Service isolation**: Each service has independent `pyproject.toml` / `setup.py` with its own dependency tree.
- **Shared code as internal packages**: Common utilities live in `libs/` and are installed as editable packages.
- **Strict typing**: All packages enforce `mypy --strict` to catch interface mismatches early.
- **Reproducible environments**: Lock files (`requirements.txt` or `poetry.lock`) per service for deterministic builds.
- **No implicit cross-service imports**: Services depend on shared libs explicitly, not on each other.
- **Test isolation**: Each service and library has its own test suite; integration tests are separate.

---

## 4. Repository Layout

```
live-broadcast-dubbing-cloud/
├── apps/
│   ├── media-service/          # EC2 stream worker (CPU-only)
│   │   ├── pyproject.toml              # Service-specific dependencies
│   │   ├── requirements.txt            # Locked CPU-only dependencies
│   │   ├── requirements-dev.txt        # Dev/test dependencies
│   │   ├── src/
│   │   │   └── media_service/  # Python package namespace
│   │   │       ├── __init__.py
│   │   │       ├── worker.py           # GStreamer worker entrypoint
│   │   │       ├── sts_client.py       # HTTP client for STS service
│   │   │       ├── pipelines/          # GStreamer pipeline implementations
│   │   │       └── config.py           # Service-specific config models
│   │   ├── tests/                      # Service-specific tests
│   │   │   ├── unit/
│   │   │   └── integration/
│   │   └── README.md                   # Local setup instructions
│   │
│   └── sts-service/                    # RunPod GPU service
│       ├── pyproject.toml              # Service-specific dependencies (GPU PyTorch)
│       ├── requirements.txt            # Locked GPU dependencies
│       ├── requirements-dev.txt        # Dev/test dependencies
│       ├── src/
│       │   └── sts_service/            # Python package namespace
│       │       ├── __init__.py
│       │       ├── api.py              # HTTP/gRPC API server
│       │       ├── asr/                # ASR module (Whisper)
│       │       ├── translation/        # Translation module (MT)
│       │       ├── tts/                # TTS module (Coqui)
│       │       └── config.py           # Service-specific config models
│       ├── tests/                      # Service-specific tests
│       │   ├── unit/
│       │   └── integration/
│       └── README.md                   # Local setup instructions
│
├── libs/                               # Shared libraries (internal packages)
│   ├── common/                         # Common utilities
│   │   ├── pyproject.toml              # Minimal shared dependencies
│   │   ├── src/
│   │   │   └── dubbing_common/
│   │   │       ├── __init__.py
│   │   │       ├── audio.py            # Audio format utilities
│   │   │       ├── types.py            # Shared data types
│   │   │       └── logging.py          # Logging configuration
│   │   └── tests/
│   │
│   └── contracts/                      # API contracts and schemas
│       ├── pyproject.toml
│       ├── src/
│       │   └── dubbing_contracts/
│       │       ├── __init__.py
│       │       ├── sts.py              # STS API request/response models
│       │       └── events.py           # Event schemas (MediaMTX hooks, etc.)
│       └── tests/
│
├── tests/                              # End-to-end integration tests
│   └── e2e/
│       ├── test_stream_pipeline.py     # Full pipeline tests
│       └── fixtures/
│
├── deploy/                             # Docker and deployment configs
│   ├── media-service/
│   │   └── Dockerfile                  # CPU-only image
│   └── sts-service/
│       └── Dockerfile                  # GPU-enabled image
│
├── pyproject.toml                      # Root-level tooling config (ruff, mypy)
├── Makefile                            # Development workflow commands
└── README.md                           # Repository overview
```

---

## 5. Dependency Management Strategy

### 5.1 Service-Level Dependencies

Each service in `apps/` has:

- **`pyproject.toml`** (or `setup.py`): Declares direct dependencies and metadata
- **`requirements.txt`**: Locked dependencies for production (generated via `pip-compile` or `poetry export`)
- **`requirements-dev.txt`**: Dev/test dependencies (pytest, mypy, ruff, etc.)

#### Example: `apps/media-service/pyproject.toml`

```toml
[project]
name = "media-service"
version = "0.1.0"
requires-python = ">=3.10,<3.11"
dependencies = [
    "numpy<2.0",
    "scipy",
    "soundfile",
    "pyyaml",
    "pydantic>=2.0",
    "rich",
    "typer",
    # CPU-only PyTorch (lighter weight)
    "torch==2.1.0+cpu",
    "torchaudio==2.1.0+cpu",
    # Shared internal packages
    "dubbing-common",
    "dubbing-contracts",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio",
    "mypy>=1.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

#### Example: `apps/sts-service/pyproject.toml`

```toml
[project]
name = "sts-service"
version = "0.1.0"
requires-python = ">=3.10,<3.11"
dependencies = [
    "numpy<2.0",
    "scipy",
    "soundfile",
    "pyyaml",
    "pydantic>=2.0",
    "rich",
    # GPU-enabled PyTorch (CUDA 11.8)
    "torch==2.1.0+cu118",
    "torchaudio==2.1.0+cu118",
    # ML models
    "faster-whisper>=0.10.0",
    "transformers>=4.35.0",
    "sentencepiece",
    "coqui-tts==0.27.2",
    # API server
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    # Shared internal packages
    "dubbing-common",
    "dubbing-contracts",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio",
    "mypy>=1.0",
    "ruff>=0.1.0",
    "httpx",  # For API testing
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

### 5.2 Shared Library Dependencies

Libraries in `libs/` have **minimal dependencies** (only what's truly shared):

#### Example: `libs/common/pyproject.toml`

```toml
[project]
name = "dubbing-common"
version = "0.1.0"
requires-python = ">=3.10,<3.11"
dependencies = [
    "numpy<2.0",
    "pyyaml",
    "pydantic>=2.0",
    "rich",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

#### Example: `libs/contracts/pyproject.toml`

```toml
[project]
name = "dubbing-contracts"
version = "0.1.0"
requires-python = ">=3.10,<3.11"
dependencies = [
    "pydantic>=2.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

### 5.3 Avoiding Dependency Conflicts

**Problem**: `media-service` uses CPU-only PyTorch, `sts-service` uses GPU PyTorch.

**Solution**: Each service has its own virtual environment or container.

- **Local development**: Use separate virtual environments per service
- **CI/CD**: Use separate jobs/containers per service
- **Production**: Services deploy to different environments (EC2 vs RunPod)

**Shared libraries** must not depend on conflicting packages (e.g., no PyTorch in `libs/common`).

---

## 6. Local Development Workflows

### 6.1 Initial Setup (One-Time)

```bash
# Clone the repository
git clone <repo-url>
cd live-broadcast-dubbing-cloud

# Install shared libraries in editable mode (required by both services)
cd libs/common && pip install -e . && cd ../..
cd libs/contracts && pip install -e . && cd ../..
```

### 6.2 Working on Stream Infrastructure (EC2 Service)

```bash
# Create and activate virtual environment
python3.10 -m venv .venv-stream
source .venv-stream/bin/activate  # On Windows: .venv-stream\Scripts\activate

# Install service + shared libs in editable mode
cd apps/media-service
pip install -e ../../libs/common -e ../../libs/contracts
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run the worker locally
python -m media_service.worker --config local.yaml
```

### 6.3 Working on STS Service (RunPod Service)

```bash
# Create and activate virtual environment (SEPARATE from media-service)
python3.10 -m venv .venv-sts
source .venv-sts/bin/activate

# Install service + shared libs in editable mode
cd apps/sts-service
pip install -e ../../libs/common -e ../../libs/contracts
pip install -e ".[dev]"

# Run tests (CPU fallback mode for local testing)
pytest tests/

# Run the API server locally
python -m sts_service.api --port 8000
```

### 6.4 Recommended Makefile Targets

**Root-level `Makefile`**:

```makefile
.PHONY: help setup-stream setup-sts test-all lint format

help:
	@echo "Targets:"
	@echo "  setup-stream    - Set up media-service venv"
	@echo "  setup-sts       - Set up sts-service venv"
	@echo "  test-all        - Run all tests (requires both venvs)"
	@echo "  lint            - Run mypy and ruff on all code"
	@echo "  format          - Auto-format all code with ruff"

setup-stream:
	python3.10 -m venv .venv-stream
	.venv-stream/bin/pip install -e libs/common -e libs/contracts
	.venv-stream/bin/pip install -e "apps/media-service[dev]"

setup-sts:
	python3.10 -m venv .venv-sts
	.venv-sts/bin/pip install -e libs/common -e libs/contracts
	.venv-sts/bin/pip install -e "apps/sts-service[dev]"

test-all:
	.venv-stream/bin/pytest apps/media-service/tests/
	.venv-sts/bin/pytest apps/sts-service/tests/
	pytest tests/e2e/  # Run with either venv

lint:
	ruff check apps/ libs/
	mypy apps/media-service/src
	mypy apps/sts-service/src
	mypy libs/common/src
	mypy libs/contracts/src

format:
	ruff format apps/ libs/ tests/
```

---

## 7. Testing Strategy

### 7.1 Unit Tests (Per Service/Library)

Each service and library has its own `tests/` directory:

- **Location**: `apps/<service>/tests/unit/` or `libs/<lib>/tests/`
- **Dependencies**: Only the service/library under test + its direct dependencies
- **Execution**: Run within the service's virtual environment

Example:
```bash
# Test media-service
source .venv-stream/bin/activate
pytest apps/media-service/tests/unit/

# Test sts-service
source .venv-sts/bin/activate
pytest apps/sts-service/tests/unit/
```

### 7.2 Integration Tests (Per Service)

Test interactions between components within a service:

- **Location**: `apps/<service>/tests/integration/`
- **Scope**: Test service internals + external dependencies (mock STS API, mock MediaMTX)

Example:
```bash
# Test stream worker with mock STS service
source .venv-stream/bin/activate
pytest apps/media-service/tests/integration/test_sts_client.py
```

### 7.3 End-to-End Tests

Test the full pipeline (requires both services):

- **Location**: `tests/e2e/`
- **Scope**: Full pipeline from RTMP ingest → MediaMTX → Worker → STS → Egress
- **Environment**: Docker Compose or local services

Example:
```bash
# Start both services via Docker Compose
docker compose -f deploy/media-service/docker-compose.yml up -d
docker compose -f deploy/sts-service/docker-compose.yml up -d

# Run E2E tests
pytest tests/e2e/

# Tear down
docker compose -f deploy/media-service/docker-compose.yml down
docker compose -f deploy/sts-service/docker-compose.yml down
```

---

## 8. Type Safety and Linting

### 8.1 Strict Typing with MyPy

All code must pass `mypy --strict`. Root-level `pyproject.toml` configures MyPy globally:

**Root `pyproject.toml`**:

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

# Per-module overrides (if needed for gradual typing)
[[tool.mypy.overrides]]
module = "coqui_tts.*"
ignore_missing_imports = true
```

### 8.2 Linting and Formatting with Ruff

Use `ruff` for fast linting and formatting:

**Root `pyproject.toml`**:

```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__.py
```

Run linting:
```bash
make lint      # Check all code
make format    # Auto-format all code
```

---

## 9. Docker Build Strategy (Cross-Reference)

Each service has its own `Dockerfile` (detailed in `specs/001-2-docker-repo-setup.md`):

### 9.1 Stream Infrastructure Dockerfile

**Location**: `deploy/media-service/Dockerfile`

```dockerfile
FROM python:3.10-slim

# Install system dependencies (GStreamer, FFmpeg, rubberband)
RUN apt-get update && apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gi \
    gir1.2-gst-rtsp-server-1.0 \
    ffmpeg \
    rubberband-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared libraries
COPY libs/common libs/common
COPY libs/contracts libs/contracts

# Install shared libraries
RUN pip install --no-cache-dir ./libs/common ./libs/contracts

# Copy service code
COPY apps/media-service apps/media-service

# Install service dependencies (CPU-only PyTorch)
RUN pip install --no-cache-dir ./apps/media-service

ENTRYPOINT ["python", "-m", "media_service.worker"]
```

### 9.2 STS Service Dockerfile

**Location**: `deploy/sts-service/Dockerfile`

```dockerfile
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Install Python 3.10
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared libraries
COPY libs/common libs/common
COPY libs/contracts libs/contracts

# Install shared libraries
RUN pip install --no-cache-dir ./libs/common ./libs/contracts

# Copy service code
COPY apps/sts-service apps/sts-service

# Install service dependencies (GPU PyTorch)
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cu118 \
    ./apps/sts-service

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

ENTRYPOINT ["python", "-m", "sts_service.api"]
```

---

## 10. CI/CD Pipeline Strategy

### 10.1 Separate Build Jobs

**GitHub Actions Example** (`.github/workflows/ci.yml`):

```yaml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      - name: Install ruff and mypy
        run: pip install ruff mypy
      - name: Lint
        run: |
          ruff check apps/ libs/
          mypy apps/media-service/src
          mypy apps/sts-service/src
          mypy libs/common/src
          mypy libs/contracts/src

  test-media-service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y gstreamer1.0-tools python3-gi
          pip install -e libs/common -e libs/contracts
          pip install -e "apps/media-service[dev]"
      - name: Run tests
        run: pytest apps/media-service/tests/

  test-sts-service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      - name: Install dependencies
        run: |
          pip install -e libs/common -e libs/contracts
          pip install -e "apps/sts-service[dev]"
      - name: Run tests (CPU fallback)
        run: pytest apps/sts-service/tests/

  build-media-service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -f deploy/media-service/Dockerfile -t media-service:${{ github.sha }} .

  build-sts-service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -f deploy/sts-service/Dockerfile -t sts-service:${{ github.sha }} .
```

### 10.2 Independent Deployment

- **Stream Infrastructure**: Deploy to EC2 via GitHub Actions → ECR → EC2 instance
- **STS Service**: Deploy to RunPod via Docker image push → RunPod template update

---

## 11. Common Pitfalls and Solutions

### 11.1 Pitfall: Importing Service Code Across Services

**Wrong**:
```python
# In apps/sts-service/src/sts_service/api.py
from media_service.worker import SomeUtil  # BAD: cross-service import
```

**Right**:
```python
# Move SomeUtil to libs/common
from dubbing_common.utils import SomeUtil  # GOOD: shared library
```

### 11.2 Pitfall: Mixed PyTorch Versions

**Problem**: Installing both services in the same venv causes PyTorch conflict.

**Solution**: Always use separate virtual environments per service.

### 11.3 Pitfall: Shared Library Dependency Bloat

**Problem**: Adding heavy dependencies (e.g., PyTorch, Whisper) to `libs/common`.

**Solution**: Keep shared libraries minimal. Heavy dependencies stay in service-level `pyproject.toml`.

### 11.4 Pitfall: Missing Editable Installs

**Problem**: Edits to shared libraries don't reflect in services.

**Solution**: Always install shared libraries with `-e` flag:
```bash
pip install -e ../../libs/common -e ../../libs/contracts
```

---

## 12. Success Criteria

- **Independent builds**: Each service can be built and tested independently without the other service's dependencies.
- **Shared code reuse**: Common utilities and contracts are accessible to both services via shared libraries.
- **Type safety**: All code passes `mypy --strict` with no errors.
- **Reproducible environments**: Lock files ensure deterministic builds across dev/CI/prod.
- **Fast local iteration**: Developers can work on one service without building the other.
- **CI/CD efficiency**: Separate build jobs allow parallel testing and deployment.

---

## 13. References

- `specs/001-2-docker-repo-setup.md` (container build strategy)
- `specs/008-libraries-and-dependencies.md` (dependency baseline)
- `specs/015-deployment-architecture.md` (deployment split rationale)
- Python Packaging Guide: https://packaging.python.org/
- MyPy Documentation: https://mypy.readthedocs.io/
- Ruff Documentation: https://docs.astral.sh/ruff/
