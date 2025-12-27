# Live Broadcast Dubbing - Cloud Services

Real-time speech-to-speech translation platform for live broadcast dubbing.

## Overview

This repository contains a Python monorepo with multiple services and shared libraries for processing live audio streams and performing real-time speech translation.

### System Architecture

The platform consists of two main services:

- **Media Service** (CPU-based) - Handles audio stream ingestion, preprocessing, and pipeline orchestration
- **STS Service** (GPU-based) - Performs speech-to-speech translation (ASR → Translation → TTS)

These services share common functionality through two libraries:

- **dubbing-common** - Shared utilities, configuration, and logging
- **dubbing-contracts** - API contracts and event schemas

## Quick Start

### Prerequisites

- **Python 3.10.x** (required, not compatible with 3.11+)
- **Git** for version control
- **Make** for build automation
- **NVIDIA GPU with CUDA** (optional, for STS service in production mode)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd live-broadcast-dubbing-cloud
   ```

2. **Choose your service and set up the environment**

   For Media Service (CPU-based):
   ```bash
   make setup-stream
   source .venv-stream/bin/activate
   ```

   For STS Service (GPU-based, or CPU fallback):
   ```bash
   make setup-sts
   source .venv-sts/bin/activate
   ```

3. **Verify installation**
   ```bash
   # Run all tests
   make test-all

   # Check code quality
   make lint
   make typecheck
   ```

## Repository Structure

```
.
├── apps/
│   ├── media-service/            # CPU-based media processing service
│   │   ├── src/media_service/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── sts-service/              # GPU-based STS service
│       ├── src/sts_service/
│       ├── tests/
│       ├── pyproject.toml
│       └── README.md
├── libs/
│   ├── common/                   # Shared utilities library
│   │   ├── src/dubbing_common/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── contracts/                # API contracts library
│       ├── src/dubbing_contracts/
│       ├── tests/
│       ├── pyproject.toml
│       └── README.md
├── tests/
│   └── e2e/                      # End-to-end integration tests
├── deploy/                       # Deployment configurations
├── specs/                        # Product and architecture specs
├── .specify/                     # Spec templates and tooling
├── Makefile                      # Build automation
├── pyproject.toml                # Root-level tool configuration
├── pytest.ini                    # Test configuration
├── .coveragerc                   # Coverage configuration
└── README.md                     # This file
```

## Development Workflow

### Virtual Environments

This monorepo uses **isolated virtual environments per service** to maintain independence:

- `.venv-stream/` - For media-service
- `.venv-sts/` - For sts-service

Both environments include the shared libraries (`dubbing-common`, `dubbing-contracts`) installed in editable mode.

### Available Commands

```bash
# Setup
make setup-stream          # Set up media-service
make setup-sts             # Set up sts-service

# Testing
make test                  # Run all tests (quick)
make test-all              # Run all tests (comprehensive)
make test-unit             # Run only unit tests
make test-contract         # Run contract tests
make test-integration      # Run integration tests
make test-coverage         # Run tests with coverage report

# Code Quality
make fmt                   # Format code with ruff
make lint                  # Lint code with ruff
make typecheck             # Type check with mypy
make clean                 # Remove build artifacts

# Development Tools
make install-hooks         # Install pre-commit hooks
make pre-implement         # Verify TDD compliance before implementing

# Docker (for running dependent services)
make dev                   # Start services with Docker Compose
make down                  # Stop Docker services
make logs                  # View Docker logs
make ps                    # List Docker containers

# Help
make help                  # Show all available commands
```

### Test-Driven Development (TDD)

This project follows strict TDD practices:

1. **Write tests first** - Tests must be written before implementation
2. **Verify tests fail** - Run tests to ensure they fail before implementing
3. **Implement code** - Write minimal code to make tests pass
4. **Verify tests pass** - Run tests to ensure implementation is correct
5. **Check coverage** - Maintain 80%+ test coverage (95% for critical paths)

See [TDD Quick Start Guide](docs/tdd-quickstart.md) for complete workflow.

### Test Organization

Tests are organized by type using pytest markers:

- `@pytest.mark.unit` - Fast, isolated tests with mocked dependencies
- `@pytest.mark.contract` - API/event schema validation tests
- `@pytest.mark.integration` - Cross-service workflows with mocks
- `@pytest.mark.e2e` - Full pipeline validation (optional)

## Service Documentation

Each service and library has detailed documentation:

- [Media Service](apps/media-service/README.md) - CPU-based audio processing
- [STS Service](apps/sts-service/README.md) - GPU-based speech translation
- [Common Library](libs/common/README.md) - Shared utilities
- [Contracts Library](libs/contracts/README.md) - API contracts and schemas

## Specifications

Product requirements and architecture specs are in the `specs/` directory:

- `specs/001-python-monorepo-setup/` - Monorepo setup specification
- See [CLAUDE.md](CLAUDE.md) for repository guidelines and conventions

## Configuration

### Linting and Formatting (Ruff)

- **Target**: Python 3.10
- **Line length**: 100 characters
- **Rules**: E, W, F, I, B, C4, UP, SIM
- **Configuration**: `pyproject.toml` (root)

### Type Checking (MyPy)

- **Mode**: Strict
- **Python version**: 3.10
- **Configuration**: `pyproject.toml` (root)

### Testing (Pytest)

- **Test paths**: `apps/`, `tests/`
- **Coverage target**: 80% minimum
- **Configuration**: `pytest.ini`, `.coveragerc`

## Python Version Requirement

**IMPORTANT**: This project requires Python 3.10.x specifically.

```bash
# Check your Python version
python3.10 --version  # Should be 3.10.x

# If not installed:
# Ubuntu/Debian
sudo apt-get install python3.10 python3.10-venv

# macOS (Homebrew)
brew install python@3.10
```

Python 3.11+ is not compatible due to dependency constraints.

## Deployment

Deployment configurations are in the `deploy/` directory:

- Docker Compose configurations for local development
- Kubernetes manifests (to be added)
- CI/CD pipeline definitions (to be added)

See deployment-specific documentation for production setup.

## Troubleshooting

### Virtual Environment Issues

If you encounter issues with virtual environments:

```bash
# Remove existing venvs
rm -rf .venv-stream .venv-sts

# Re-run setup
make setup-stream  # or make setup-sts
```

### Import Errors

Ensure packages are installed in editable mode:

```bash
# Check installed packages
pip list | grep dubbing

# Should see:
# dubbing-common     0.1.0  /path/to/libs/common
# dubbing-contracts  0.1.0  /path/to/libs/contracts
# media-service 0.1.0  /path/to/apps/media-service
# (or sts-service, depending on which venv you're in)
```

### Test Failures

```bash
# Run tests with verbose output
pytest -vv

# Run specific test file
pytest apps/media-service/tests/unit/test_example.py -v

# Run with debugging
pytest --pdb
```

## Contributing

1. Review [CLAUDE.md](CLAUDE.md) for repository guidelines
2. Follow TDD workflow (tests first!)
3. Ensure all tests pass: `make test-all`
4. Check code quality: `make lint && make typecheck`
5. Maintain 80%+ test coverage
6. Use conventional commits: `feat:`, `fix:`, `docs:`, etc.

## License

(Add license information as needed)

## Contact

(Add contact information or links to documentation as needed)
