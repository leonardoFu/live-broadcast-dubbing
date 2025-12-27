# Repository Guidelines

## Project Structure & Module Organization

- `specs/`: Product/architecture specs. Start here before implementing changes.
- `.specify/`: Spec templates and shared “memory” used to generate/maintain specs.
- `.codex/`: Local agent prompts/workflows for this repo.

Planned runtime components (not all may exist yet):
- `apps/sts-service/`: Speech→Text→Speech service referenced by `specs/001-spec.md`.
- `apps/stream-worker/`: GStreamer-based stream worker that pulls from MediaMTX, processes audio, and republishes.
- `infra/` or `deploy/`: Container/runtime configuration (e.g., MediaMTX, compose files).

## Build, Test, and Development Commands

This repository currently contains specifications and templates only; build/test scripts may be added as implementation lands. When adding a runnable component, provide a minimal local workflow and document it here (examples):

- `make dev`: Run the service locally (preferred entrypoint if you add a Makefile).
- `docker compose up`: Start dependent services (e.g., MediaMTX) for local integration.
- `make test` / `npm test` / `pytest`: Run the module’s test suite.

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

- **Unit tests**: `apps/<module>/tests/unit/` - Fast, isolated, mocked dependencies
- **Contract tests**: `apps/<module>/tests/contract/` - API/event schema validation
- **Integration tests**: `tests/integration/` - Cross-service workflows with mocks
- **E2E tests**: `tests/e2e/` - Optional, full pipeline validation

### Key Commands

- `make test` - Run all tests
- `make test-coverage` - Run tests with coverage report (80% required)
- `make install-hooks` - Install pre-commit hooks (enforces TDD)
- `make pre-implement` - Verify tests exist and fail before implementing

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

## Recent Changes
- 001-python-monorepo-setup: Added Python 3.10.x (as specified in constitution and architecture spec) + setuptools>=68.0 (build system), ruff>=0.1.0 (linting), mypy>=1.0 (type checking), pytest>=7.0 (testing)
