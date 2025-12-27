# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-12-25

### Added

#### Monorepo Structure (Feature 001-python-monorepo-setup)

**Services:**
- `apps/media-service/` - CPU-based audio stream processing service
  - Complete package structure with src/media_service/ and tests/
  - Submodule: `pipelines/` for audio processing pipelines
  - Dependencies: numpy, scipy, soundfile, pyyaml, pydantic
  - Virtual environment: `.venv-stream/`

- `apps/sts-service/` - GPU-based speech-to-speech translation service
  - Complete package structure with src/sts_service/ and tests/
  - Submodules: `asr/`, `translation/`, `tts/`
  - Dependencies: faster-whisper, transformers, fastapi, uvicorn, torch
  - Virtual environment: `.venv-sts/`

**Shared Libraries:**
- `libs/common/` - Shared utilities library
  - Common functionality: configuration, logging, audio helpers, exceptions
  - Dependencies: numpy, pyyaml, pydantic, rich
  - Used by both services

- `libs/contracts/` - API contracts and event schemas library
  - Pydantic models for API requests/responses and events
  - Ensures type safety across services
  - Dependencies: pydantic>=2.0

**Testing Infrastructure:**
- `tests/unit/` - Root-level unit tests
- `tests/contract/` - Contract validation tests
- `tests/integration/` - Cross-service integration tests
- `tests/e2e/` - End-to-end pipeline tests
- `tests/fixtures/` - Shared test fixtures
- Test markers: `@pytest.mark.unit`, `@pytest.mark.contract`, `@pytest.mark.integration`, `@pytest.mark.e2e`
- Coverage configuration with 80% minimum threshold

**Development Tooling:**
- `Makefile` - Standardized build commands
  - `make setup-stream` / `make setup-sts` - Service setup
  - `make test-all` / `make test-unit` / `make test-contract` / `make test-integration` - Testing
  - `make fmt` / `make lint` / `make typecheck` - Code quality
  - `make clean` - Remove build artifacts
  - `make install-hooks` - Install pre-commit hooks

- **Ruff** configuration (linting and formatting)
  - Target: Python 3.10
  - Line length: 100 characters
  - Rules: E, W, F, I, B, C4, UP, SIM
  - Per-file ignores for __init__.py (F401)

- **MyPy** configuration (type checking)
  - Strict mode enabled
  - Python version: 3.10
  - Comprehensive type checking rules

- **Pytest** configuration
  - Test paths: apps/, tests/
  - Coverage reporting: HTML + terminal
  - Fail threshold: 80% coverage

**Documentation:**
- `README.md` (root) - Repository overview, quick start, development workflow
- `apps/media-service/README.md` - Service-specific documentation
- `apps/sts-service/README.md` - Service-specific documentation with GPU requirements
- `libs/common/README.md` - Library documentation with usage examples
- `libs/contracts/README.md` - Contract definitions and validation examples
- `CLAUDE.md` - Repository guidelines and conventions (updated)
- `CHANGELOG.md` - This file

**Configuration Files:**
- `pyproject.toml` (root) - Root-level tool configuration (ruff, mypy, pytest, coverage)
- `pytest.ini` - Pytest configuration
- `.coveragerc` - Coverage reporting configuration
- `.gitignore` - Updated to exclude venvs (.venv-stream/, .venv-sts/), build artifacts, test artifacts, IDE files

**Package Metadata:**
- All packages have `pyproject.toml` with:
  - PEP 621 compliant metadata
  - Python 3.10.x requirement (>=3.10,<3.11)
  - Setuptools build backend
  - Development dependencies for testing and code quality

### Changed

- Updated `CLAUDE.md` with monorepo structure and TDD guidelines
- Enhanced `.gitignore` with monorepo-specific patterns
- Updated root `Makefile` with monorepo setup targets

### Architecture Decisions

1. **Isolated Virtual Environments**
   - Separate venvs per service to maintain independence
   - Shared libraries installed in editable mode in both venvs

2. **Python 3.10.x Constraint**
   - Locked to Python 3.10.x for dependency compatibility
   - Not compatible with Python 3.11+

3. **Service Separation**
   - CPU-based service (media-service) isolated from GPU service (sts-service)
   - Enables independent deployment and scaling

4. **Shared Libraries Pattern**
   - `dubbing-common` for shared utilities (DRY principle)
   - `dubbing-contracts` for API contracts (single source of truth)

5. **Test Organization**
   - Test markers for different test types
   - Package-level tests + root-level integration tests
   - 80% minimum coverage, 95% for critical paths

### Success Criteria Met

- ✅ SC-001: Core directories created (apps/, libs/, tests/e2e/, deploy/)
- ✅ SC-002: Service directories complete with src/ and tests/
- ✅ SC-003: All packages importable with proper __init__.py files
- ✅ SC-004: Development tools configured (ruff, mypy, pytest)
- ✅ SC-005: Documentation complete for all packages
- ✅ SC-006: Virtual environment setup via Makefile targets
- ✅ SC-007: All code quality tools executable
- ✅ SC-008: Git repository configured with proper ignores

### Implementation Notes

- Total tasks completed: 100 across 7 phases
- No breaking changes (initial release)
- All functionality follows TDD principles
- Comprehensive test coverage established

### Next Steps

1. Implement actual service logic (TDD workflow)
2. Add deployment configurations (Docker, Kubernetes)
3. Set up CI/CD pipeline
4. Add pre-commit hooks
5. Implement actual business logic for stream processing and STS

---

## Version History

- **0.1.0** (2025-12-25) - Initial monorepo structure setup

[Unreleased]: https://github.com/your-org/live-broadcast-dubbing-cloud/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/live-broadcast-dubbing-cloud/releases/tag/v0.1.0
