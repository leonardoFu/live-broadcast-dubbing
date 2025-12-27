# Stream Infrastructure Service

CPU-based audio stream processing service for live broadcast dubbing.

## Description

The stream-infrastructure service handles real-time audio stream processing, including:
- Audio stream ingestion from MediaMTX RTMP sources
- Audio preprocessing and buffering
- Fragment-based audio processing pipeline
- Integration with STS service for speech translation
- Processed audio stream output

This service is designed to run on CPU-only infrastructure and uses GStreamer for audio processing.

## Prerequisites

- Python 3.10.x (required, not compatible with 3.11+)
- Linux environment (for GStreamer dependencies)
- MediaMTX server (for RTMP stream handling)

## Setup

### 1. Install Python 3.10

```bash
# Ubuntu/Debian
sudo apt-get install python3.10 python3.10-venv

# macOS (using Homebrew)
brew install python@3.10
```

### 2. Create Virtual Environment and Install

From the repository root:

```bash
make setup-stream
```

This will:
- Create `.venv-stream` virtual environment
- Install shared libraries (`dubbing-common`, `dubbing-contracts`)
- Install `stream-infrastructure` package with development dependencies

### 3. Activate Virtual Environment

```bash
source .venv-stream/bin/activate
```

## Development Workflow

### Running Tests

```bash
# Run all tests for this service
pytest apps/stream-infrastructure/tests/ -v

# Run only unit tests (fast)
pytest apps/stream-infrastructure/tests/unit/ -m unit -v

# Run integration tests
pytest apps/stream-infrastructure/tests/integration/ -m integration -v

# Run with coverage report
pytest apps/stream-infrastructure/tests/ --cov=stream_infrastructure --cov-report=html
```

### Code Quality

```bash
# Format code
make fmt

# Lint code
make lint

# Type checking
make typecheck
```

### Local Development

1. Ensure MediaMTX is running (see `deploy/` directory)
2. Activate the virtual environment
3. Make code changes in `src/stream_infrastructure/`
4. Run tests to verify changes
5. Test against live RTMP stream (optional)

## Project Structure

```
apps/stream-infrastructure/
├── src/
│   └── stream_infrastructure/
│       ├── __init__.py
│       └── pipelines/          # Audio processing pipelines
│           └── __init__.py
├── tests/
│   ├── unit/                   # Fast, isolated tests
│   ├── integration/            # Cross-component tests
│   └── conftest.py             # Shared test fixtures
├── pyproject.toml              # Package metadata and dependencies
└── README.md                   # This file
```

## Dependencies

### Core Dependencies
- `numpy<2.0` - Audio buffer manipulation
- `scipy` - Signal processing
- `soundfile` - Audio I/O
- `pyyaml` - Configuration management
- `pydantic>=2.0` - Data validation

### Shared Libraries
- `dubbing-common` - Shared utilities and configurations
- `dubbing-contracts` - API contracts and event schemas

### Development Dependencies
- `pytest>=7.0` - Testing framework
- `mypy>=1.0` - Type checking
- `ruff>=0.1.0` - Linting and formatting

## Configuration

Service configuration is managed via YAML files (to be added in implementation phase).

## Related Services

- `sts-service` - Speech-to-speech translation service (GPU-based)
- See repository root README.md for monorepo overview

## License

(Add license information as needed)
