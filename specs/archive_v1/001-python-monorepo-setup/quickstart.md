# Quick Start Guide: Python Monorepo Development

**Feature**: Python Monorepo Directory Setup
**Branch**: `001-python-monorepo-setup`
**Created**: 2025-12-25

## Overview

This guide helps you get started developing in the live-broadcast-dubbing-cloud Python monorepo. The repository contains 2 services (media-service, sts-service) and 2 shared libraries (common, contracts) with independent dependency trees and isolated virtual environments.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10.x** installed (`python3.10 --version`)
  - **Not** Python 3.11+ or 3.9 (strict requirement: `>=3.10,<3.11`)
- **git** for version control
- **make** for running development commands (macOS/Linux have this by default)
- **A terminal** (Terminal.app, iTerm2, VS Code terminal, etc.)

### Checking Python Version

```bash
python3.10 --version
# Expected: Python 3.10.x (e.g., 3.10.12)

# If python3.10 not found, you may need to install it:
# macOS (Homebrew): brew install python@3.10
# Ubuntu/Debian: sudo apt install python3.10 python3.10-venv
# Windows: Download from python.org
```

## Repository Structure

```
live-broadcast-dubbing-cloud/
├── apps/                       # Service applications
│   ├── media-service/  # EC2 stream worker (CPU-only)
│   └── sts-service/            # RunPod GPU service (GPU-accelerated)
├── libs/                       # Shared libraries
│   ├── common/                 # Common utilities (audio, types, logging)
│   └── contracts/              # API contracts and schemas
├── tests/e2e/                  # End-to-end integration tests
├── deploy/                     # Docker and deployment configs
├── pyproject.toml              # Root linting/type-checking config
├── Makefile                    # Development commands
└── README.md                   # Repository overview
```

## One-Time Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd live-broadcast-dubbing-cloud
```

### 2. Choose Your Service

You'll work on **one service at a time**. Each service has its own virtual environment to avoid dependency conflicts.

- **Stream Infrastructure** (CPU-only PyTorch): `apps/media-service/`
- **STS Service** (GPU PyTorch): `apps/sts-service/`

## Working on Stream Infrastructure (EC2 Service)

### Setup (One-Time)

```bash
# Option 1: Use Makefile (recommended)
make setup-stream

# Option 2: Manual setup
python3.10 -m venv .venv-stream
source .venv-stream/bin/activate  # On Windows: .venv-stream\Scripts\activate
pip install -e libs/common -e libs/contracts  # Install shared libraries first
pip install -e "apps/media-service[dev]"  # Install service + dev dependencies
```

### Activate Virtual Environment

Every time you start working, activate the venv:

```bash
source .venv-stream/bin/activate

# Your prompt should change to show (.venv-stream)
# To deactivate later: deactivate
```

### Run Tests

```bash
# Run all tests for media-service
pytest apps/media-service/tests/

# Run only unit tests
pytest apps/media-service/tests/unit/

# Run with coverage report
pytest apps/media-service/tests/ --cov=media_service --cov-report=html
# Open htmlcov/index.html to view coverage
```

### Run Linting and Type Checking

```bash
# Check code style (from repository root)
make lint

# Auto-format code
make format

# Type check
make type-check
```

### Run the Worker Locally

```bash
# Activate venv first
source .venv-stream/bin/activate

# Run the worker (example command - actual implementation pending)
python -m media_service.worker --config local.yaml
```

## Working on STS Service (RunPod Service)

### Setup (One-Time)

```bash
# Option 1: Use Makefile (recommended)
make setup-sts

# Option 2: Manual setup
python3.10 -m venv .venv-sts
source .venv-sts/bin/activate  # On Windows: .venv-sts\Scripts\activate
pip install -e libs/common -e libs/contracts  # Install shared libraries first
pip install -e "apps/sts-service[dev]"  # Install service + dev dependencies
```

**Note**: The GPU-enabled PyTorch dependencies may take longer to download (2-3 GB).

### Activate Virtual Environment

```bash
source .venv-sts/bin/activate

# Your prompt should change to show (.venv-sts)
```

### Run Tests (CPU Fallback)

```bash
# Run all tests (will use CPU fallback if no GPU available)
pytest apps/sts-service/tests/

# Run only unit tests
pytest apps/sts-service/tests/unit/

# Run with coverage
pytest apps/sts-service/tests/ --cov=sts_service --cov-report=html
```

### Run the API Server Locally

```bash
# Activate venv first
source .venv-sts/bin/activate

# Run the API server (example command - actual implementation pending)
python -m sts_service.api --port 8000
```

## Switching Between Services

You can only have **one virtual environment active** at a time. To switch:

```bash
# Deactivate current venv
deactivate

# Activate the other venv
source .venv-sts/bin/activate  # Or .venv-stream
```

## Common Development Commands

All commands should be run from the **repository root** directory.

### Using the Makefile

```bash
# Show available commands
make help

# Setup commands
make setup-stream     # Create venv and install media-service
make setup-sts        # Create venv and install sts-service

# Testing commands
make test-all         # Run tests for all packages (both venvs required)
make test-stream      # Run tests for media-service only
make test-sts         # Run tests for sts-service only

# Code quality commands
make lint             # Run ruff linter on all code
make format           # Auto-format all code with ruff
make type-check       # Run mypy type checker on all code

# Cleanup commands
make clean            # Remove build artifacts, caches, etc.
make clean-all        # Remove venvs + build artifacts (destructive)
```

### Manual Commands

```bash
# Linting
ruff check apps/ libs/

# Formatting
ruff format apps/ libs/

# Type checking
mypy apps/media-service/src
mypy apps/sts-service/src
mypy libs/common/src
mypy libs/contracts/src

# Install new dependency
source .venv-stream/bin/activate
pip install some-package
# Add to apps/media-service/pyproject.toml dependencies list
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Write Tests First (TDD)

Before implementing any feature, write failing tests:

```bash
# Example: Adding a new audio processing function
touch apps/media-service/tests/unit/test_audio_processor.py

# Write test cases that will fail
pytest apps/media-service/tests/unit/test_audio_processor.py
# Tests should FAIL (no implementation yet)
```

### 3. Implement the Feature

```bash
# Create the module
touch apps/media-service/src/media_service/audio_processor.py

# Implement until tests pass
pytest apps/media-service/tests/unit/test_audio_processor.py
# Tests should now PASS
```

### 4. Run Full Test Suite

```bash
# Ensure all tests still pass
pytest apps/media-service/tests/

# Check coverage (must be ≥80%)
pytest apps/media-service/tests/ --cov=media_service --cov-fail-under=80
```

### 5. Lint and Format

```bash
make lint    # Should show no errors
make format  # Auto-fix formatting
```

### 6. Commit and Push

```bash
git add .
git commit -m "feat: add audio processor with time-stretch support"
git push origin feature/your-feature-name
```

### 7. Create Pull Request

- Link to relevant spec (e.g., `specs/003-audio-pipeline.md`)
- Describe what changed and why
- Include test evidence (coverage report, logs)

## Troubleshooting

### Import Errors (ModuleNotFoundError)

**Problem**: Cannot import `dubbing_common` or `dubbing_contracts`

**Solution**: Install shared libraries in editable mode

```bash
source .venv-stream/bin/activate  # Or .venv-sts
pip install -e libs/common -e libs/contracts
```

### Python Version Mismatch

**Problem**: `RequiresPythonError: requires Python '>=3.10,<3.11', installed: 3.11.x`

**Solution**: Use Python 3.10.x specifically

```bash
# Recreate venv with correct version
rm -rf .venv-stream
python3.10 -m venv .venv-stream
source .venv-stream/bin/activate
make setup-stream
```

### Permission Denied Creating Virtual Environment

**Problem**: `PermissionError: [Errno 13] Permission denied`

**Solution**: Check directory permissions

```bash
# Ensure you have write access to the repository directory
ls -la .

# If needed, fix permissions
chmod u+w .
```

### Conflicting Dependencies

**Problem**: Installing both services in the same venv causes PyTorch version conflicts

**Solution**: Use separate virtual environments (this is by design)

```bash
# WRONG (don't do this)
pip install -e apps/media-service -e apps/sts-service

# RIGHT (use separate venvs)
# Terminal 1: media-service
source .venv-stream/bin/activate
pip install -e apps/media-service[dev]

# Terminal 2: sts-service
source .venv-sts/bin/activate
pip install -e apps/sts-service[dev]
```

### Makefile Command Not Found

**Problem**: `make: command not found`

**Solution**: Install make (usually pre-installed on macOS/Linux)

```bash
# macOS: Xcode Command Line Tools
xcode-select --install

# Ubuntu/Debian
sudo apt install build-essential

# Windows: Use WSL or Git Bash
```

### Tests Failing After Editing Shared Library

**Problem**: Edited `libs/common/src/dubbing_common/audio.py`, but changes not reflected in tests

**Solution**: Editable installs should auto-update, but if not:

```bash
# Reinstall shared library
source .venv-stream/bin/activate
pip install -e libs/common --force-reinstall --no-deps
```

### Coverage Below 80%

**Problem**: `FAIL Required test coverage of 80% not reached. Total coverage: 75.23%`

**Solution**: Add more tests to cover missing lines

```bash
# See coverage report
pytest apps/media-service/tests/ --cov=media_service --cov-report=html
open htmlcov/index.html  # macOS
# xdg-open htmlcov/index.html  # Linux
# start htmlcov/index.html  # Windows

# Look for red/uncovered lines and write tests for them
```

## Adding a New Module to a Service

### Example: Adding `worker.py` to media-service

1. **Create the module file**:
   ```bash
   touch apps/media-service/src/media_service/worker.py
   ```

2. **Write tests first** (TDD):
   ```bash
   touch apps/media-service/tests/unit/test_worker.py
   ```

3. **Implement the module**:
   ```python
   # apps/media-service/src/media_service/worker.py
   def process_stream(stream_id: str) -> None:
       """Process a live stream with dubbing."""
       pass
   ```

4. **Run tests**:
   ```bash
   pytest apps/media-service/tests/unit/test_worker.py
   ```

5. **No reinstall needed** - editable install automatically picks up new files!

## Adding a New Shared Library

### Example: Adding `audio.py` to `libs/common/`

1. **Create the module file**:
   ```bash
   touch libs/common/src/dubbing_common/audio.py
   ```

2. **Write tests first**:
   ```bash
   touch libs/common/tests/unit/test_audio.py
   ```

3. **Implement utility functions**:
   ```python
   # libs/common/src/dubbing_common/audio.py
   import numpy as np

   def normalize_audio(audio: np.ndarray) -> np.ndarray:
       """Normalize audio to [-1, 1] range."""
       return audio / np.max(np.abs(audio))
   ```

4. **Use in services** (automatic via editable install):
   ```python
   # apps/media-service/src/media_service/worker.py
   from dubbing_common.audio import normalize_audio

   normalized = normalize_audio(audio_chunk)
   ```

5. **No reinstall needed** - changes are immediately available!

## Next Steps

After completing the setup:

1. **Read the specifications**: `specs/` directory contains architectural details
2. **Explore the code**: Navigate `apps/` and `libs/` directories
3. **Run existing tests**: `make test-all` to understand test patterns
4. **Pick a task**: Check issue tracker or ask your team lead
5. **Follow TDD**: Write tests → implement → verify coverage → commit

## Resources

- **Constitution**: `.specify/memory/constitution.md` (project principles)
- **CLAUDE.md**: `CLAUDE.md` (repository guidelines)
- **Architecture Spec**: `specs/001-1-python-monorepo-setup.md` (monorepo design)
- **Feature Specs**: `specs/*/spec.md` (individual feature requirements)

## Getting Help

- **Stuck on setup?** Check this guide's Troubleshooting section
- **Questions about architecture?** Read `specs/` directory
- **Code review feedback?** Consult `.specify/memory/constitution.md` for principles
- **Need examples?** Look at existing test files in `tests/unit/` and `tests/integration/`

---

**Happy coding!** Remember: Write tests first, keep services isolated, and run `make lint` before committing. 🚀
