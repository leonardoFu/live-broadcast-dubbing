# Python 3.10+ Monorepo Best Practices Research

## Executive Summary

This document provides evidence-based recommendations for structuring a Python 3.10+ monorepo with 2 services and 2 shared libraries. The recommendations prioritize simplicity and the standard pip/setuptools workflow over complex tooling like Pants or Bazel. All recommendations are compatible with modern Python packaging standards (PEP 621) and support strict type checking.

---

## 1. PEP 621 (pyproject.toml) Best Practices

### Decision: Use PEP 621 + setuptools for all packages

Adopt PEP 621 standardized metadata in `pyproject.toml` with setuptools 61.0+ as the build backend for all packages (services and libraries).

### Rationale

- **Industry Standard**: PEP 621 is now the canonical standard for Python packaging, replacing setup.py/setup.cfg. Supported by all major tools (pip, build, setuptools, uv, PDM, Poetry).
- **Single Source of Truth**: Consolidates project metadata, dependencies, and optional configurations in one file, eliminating setup.py, setup.cfg, requirements.txt, and MANIFEST.in.
- **Static Metadata**: Metadata is read without executing code, enabling faster tool startup, deterministic builds, and seamless tool switching.
- **Monorepo-Friendly**: Works naturally with editable installs and local dependency references via path-based dependencies.
- **Setuptools Ecosystem**: Setuptools 61.0+ has mature PEP 621 support with no breaking changes to the standard pip workflow.

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Poetry-only format | Locks users into Poetry; limits tool portability. |
| setup.py/setup.cfg split | Maintainable for new projects and offers no advantages. |
| Hatch/Flit as build backend | Adds unnecessary complexity for a standard pip workflow; Setuptools is more widely tested. |
| Pants/Bazel | Overkill for a 2-service, 2-library monorepo; adds cognitive overhead and CI complexity. |

### Example Configuration

**Root `pyproject.toml` (workspace definition):**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "live-broadcast-dubbing-cloud"
version = "0.1.0"
description = "Live broadcast dubbing cloud platform"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
  { name = "Your Name", email = "your.email@example.com" },
]
keywords = ["broadcast", "dubbing", "audio"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Environment :: Console",
  "License :: OSI Approved :: MIT License",
  "Operating System :: OS Independent",
  "Programming Language :: Python",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Multimedia :: Sound/Audio",
]

# Workspace-level dependencies (optional, for shared dev tools)
dependencies = []

[project.optional-dependencies]
dev = [
  "ruff>=0.1.0",
  "mypy>=1.0.0",
  "pytest>=7.0.0",
  "pytest-cov>=4.0.0",
  "build>=1.0.0",
]
docs = [
  "sphinx>=5.0.0",
  "sphinx-rtd-theme>=1.0.0",
]

[tool.setuptools]
packages = []  # Root workspace has no packages

[project.urls]
Homepage = "https://github.com/yourorg/live-broadcast-dubbing-cloud"
Repository = "https://github.com/yourorg/live-broadcast-dubbing-cloud.git"
Documentation = "https://docs.example.com"

# Tool configurations (covered in sections 3-6)
```

**Service: `apps/sts-service/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sts-service"
version = "0.1.0"
description = "Speech-to-Text-to-Speech service"
requires-python = ">=3.10"
authors = [{ name = "Your Name", email = "your.email@example.com" }]

dependencies = [
  "shared-audio>=0.1.0",  # Local shared library
  "httpx>=0.24.0",
  "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=7.0.0",
  "pytest-cov>=4.0.0",
  "pytest-asyncio>=0.21.0",
]

[tool.setuptools]
packages = ["sts_service"]

[tool.setuptools.package-data]
sts_service = ["py.typed"]
```

**Shared Library: `libs/shared-audio/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "shared-audio"
version = "0.1.0"
description = "Shared audio processing utilities"
requires-python = ">=3.10"
authors = [{ name = "Your Name", email = "your.email@example.com" }]

dependencies = [
  "numpy>=1.22.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=7.0.0",
  "pytest-cov>=4.0.0",
]

[tool.setuptools]
packages = ["shared_audio"]

[tool.setuptools.package-data]
shared_audio = ["py.typed"]
```

### Key Best Practices

1. **Always specify `requires-python`**: Prevents installation on unsupported versions.
2. **Use PEP 508 format for dependencies**: Format: `package[extra]>=1.0.0; sys_platform == "linux"`.
3. **Separate optional-dependencies by use case**: `dev`, `docs`, `testing`, `prod` extras.
4. **Use relative paths for local dependencies** (in workspace setup; see Section 2).
5. **Declare `py.typed` marker**: Include `py.typed` in `package-data` to signal PEP 561 compliance for type checking.
6. **Version field**: Keep version static in pyproject.toml (not computed at runtime).

### References

- [PEP 621 – Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [The Basics of Python Packaging in Early 2023 - DrivenData Labs](https://drivendata.co/blog/python-packaging-2023)
- [How to Specify Local Relative Dependencies in pyproject.toml](https://www.pythontutorials.net/blog/specifying-local-relative-dependency-in-pyproject-toml/)

---

## 2. Python Monorepo Patterns

### Decision: Simple editable installs with separate per-service virtual environments, no complex build tooling

Use `pip install -e .` for each service/library in its own virtual environment with local path-based dependencies. No Pants, Bazel, or workspace tools required. This approach leverages Python's built-in venv and pip, keeping the monorepo simple and maintainable.

### Rationale

- **Built-in Tooling**: Uses only standard Python tools (venv, pip, setuptools). No special learning curve or external dependencies.
- **Immediate Changes**: Editable mode ("living at HEAD") means changes to library code are immediately reflected in dependent services without reinstalling.
- **Transitive Resolution**: When a service (A) installs a library (C) in editable mode, and that library depends on another library (B), pip automatically installs B in editable mode if it's local.
- **Minimal Overhead**: Each service maintains its own isolated environment, reducing version conflicts and simplifying dependency resolution.
- **Familiar Workflow**: Any Python developer understands venv and pip; no new tooling to adopt.
- **Scalability**: Works well for 2-10 services; beyond that, consider uv or Pants.

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Single monorepo venv | Dependency conflicts between services; harder to isolate changes. |
| uv workspaces | Modern but newer; adds one new tool. Good for larger monorepos (10+ services). |
| Poetry workspaces | Works but ties the monorepo to Poetry; less portable. |
| Pants / Bazel | Overkill; designed for 100+ services; steep learning curve. |

### Directory Structure

```
live-broadcast-dubbing-cloud/
├── pyproject.toml                # Root metadata (shared by all packages)
├── Makefile                      # Single entry point for commands
├── .gitignore
├── README.md
├── specs/                        # Design specifications
├── apps/
│   ├── sts-service/
│   │   ├── pyproject.toml        # Service-specific config
│   │   ├── Makefile              # Service-specific tasks
│   │   ├── sts_service/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── config.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── contract/
│   │   │   └── integration/
│   │   └── .venv/                # Isolated service environment
│   └── stream-worker/
│       ├── pyproject.toml
│       ├── Makefile
│       ├── stream_worker/
│       ├── tests/
│       └── .venv/
├── libs/
│   ├── shared-audio/
│   │   ├── pyproject.toml
│   │   ├── shared_audio/
│   │   ├── tests/
│   │   └── .venv/
│   └── shared-utils/
│       ├── pyproject.toml
│       ├── shared_utils/
│       ├── tests/
│       └── .venv/
└── docs/
```

### Setup and Development Workflow

**Initial Setup:**

```bash
# Install each service/library in editable mode with its own venv
cd apps/sts-service
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"  # Installs service + shared-audio in editable mode
deactivate

cd apps/stream-worker
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
deactivate

cd libs/shared-audio
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
deactivate
```

**Dependent Installs:**

When `apps/sts-service` has `dependencies = ["shared-audio>=0.1.0"]`, pip automatically resolves `shared-audio` to the local path and installs it in editable mode if it exists in the monorepo.

**Development Workflow:**

```bash
# Edit shared-audio code
vim libs/shared-audio/shared_audio/audio_processor.py

# Changes are immediately available in sts-service venv (no reinstall needed)
# Just re-run tests or restart the service
source apps/sts-service/.venv/bin/activate
pytest
```

### Key Advantages for This Monorepo

- **2 services can have different dependency versions** if needed (unlike a single monorepo venv).
- **Isolated testing**: Each service tests against its own dependency set.
- **Clear ownership**: Each service/library has its own venv, Makefile, and test suite.
- **No lock file conflicts**: Each venv can have different transitive dependencies.

### References

- [Python Monorepo: an Example. Part 1: Structure and Tooling - Tweag](https://www.tweag.io/blog/2023-04-04-python-monorepo-1/)
- [Beyond Hypermodern: Python is easy now - Chris Arderne](https://rdrn.me/postmodern-python/)
- [GitHub - tweag/python-monorepo-example](https://github.com/tweag/python-monorepo-example)

---

## 3. Ruff Configuration for Strict Typing and Code Quality

### Decision: Ruff for linting + mypy for strict type checking (complementary tools)

Use **Ruff** for fast linting (line length, imports, unused code, style) and **mypy --strict** for comprehensive type checking. Ruff cannot enforce strict typing alone; it checks annotations exist (ANN rules) but mypy validates correctness.

### Rationale

- **Complementary Strengths**: Ruff is 10-100x faster at linting; mypy provides deep type inference and strictness.
- **Mypy Strict Mode**: `strict = true` enables all strict checks at once, catching implicit `Any`, missing type hints, and type mismatches.
- **flake8-annotations (ANN) Rules**: Ruff's ANN rules enforce that type annotations exist; mypy ensures they are correct.
- **CI/CD Efficiency**: Ruff provides instant feedback during development; mypy runs in CI for comprehensive validation.
- **Python 3.10+ Support**: Both tools fully support PEP 604 unions (`str | None`) and PEP 570 positional-only parameters.

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Ruff alone (no mypy) | Ruff cannot validate type correctness, only that annotations exist. Missing subtle type bugs. |
| mypy alone (no Ruff) | Much slower on large codebases; doesn't catch style/import issues. Less developer feedback. |
| Pyright | Good alternative to mypy but less mature in CI contexts; requires separate config. |
| Pyre (Meta) | Excellent but less community adoption; overkill for a 2-service monorepo. |

### Example Configuration

**Root `pyproject.toml` (tools section):**

```toml
[tool.ruff]
target-version = "py310"
line-length = 100
extend-exclude = [".venv", "__pycache__", "build", "dist"]

[tool.ruff.lint]
# Start with recommended rules, add strict type checking
select = [
  "E",      # pycodestyle errors
  "W",      # pycodestyle warnings
  "F",      # Pyflakes (unused imports, variables)
  "I",      # isort (import sorting)
  "N",      # pep8-naming
  "D",      # pydocstyle (docstring conventions)
  "UP",     # pyupgrade (modern Python syntax)
  "B",      # flake8-bugbear (likely bugs)
  "C4",     # flake8-comprehensions
  "ANN",    # flake8-annotations (type annotation presence)
  "RUF",    # Ruff-specific rules
  "T201",   # print statements (should use logging)
  "T203",   # pprint (debugging artifact)
]

ignore = [
  "ANN101",  # self parameter annotation (not needed)
  "ANN102",  # cls parameter annotation (not needed)
  "D100",    # Missing module docstring
  "D104",    # Missing package docstring
]

# isort configuration
[tool.ruff.lint.isort]
known-first-party = ["sts_service", "stream_worker", "shared_audio", "shared_utils"]
known-local-folder = ["."]
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]

# pydocstyle configuration
[tool.ruff.lint.pydocstyle]
convention = "google"  # Use Google-style docstrings

[tool.mypy]
python_version = "3.10"
strict = true  # Enable ALL strict checks
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_calls = true
check_untyped_defs = true
no_implicit_optional = true
strict_optional = true
warn_unused_ignores = true
warn_no_return = true

# Per-module exceptions for untyped external libraries
[[tool.mypy.overrides]]
module = [
  "gstreamer.*",
  "rtmp.*",
]
ignore_missing_imports = true
```

**Service-level `apps/sts-service/pyproject.toml`:**

```toml
# Service can override with more specific mypy config if needed
[tool.mypy]
# Inherits from root, but can override specific service requirements
plugins = ["pydantic.mypy"]  # If using Pydantic

[[tool.mypy.overrides]]
module = "sts_service.generated.*"
ignore_errors = true  # Generated code often isn't strictly typed
```

### Ruff Linting Rules Explained

| Rule Set | Purpose | Examples |
|---|---|---|
| E/W | Style conventions | Line length, indentation, whitespace |
| F | Unused code | Unused imports, undefined names, unused variables |
| I | Import sorting | Enforces isort ordering (stdlib, third-party, local) |
| N | Naming | `snake_case` for functions, `PascalCase` for classes |
| D | Docstrings | Require docstrings on public modules/functions/classes |
| UP | Syntax modernization | Replace `Union[A, B]` with `A \| B` (PEP 604) |
| B | Likely bugs | Mutable default arguments, loop variable reuse |
| ANN | Type annotations | Enforce that all functions have type hints |
| RUF | Ruff-specific | Unnecessary `pass`, unused `noqa` comments |

### Mypy Strict Mode Checks

| Option | Effect |
|---|---|
| `strict = true` | Enables all options below at once |
| `disallow_untyped_defs` | All function definitions must have type hints |
| `disallow_untyped_calls` | Cannot call untyped functions from typed code |
| `disallow_incomplete_defs` | Decorated functions need explicit type hints |
| `strict_optional` | `Optional[T]` must be checked for `None` before use |
| `no_implicit_optional` | Default `None` parameters must be `Optional[T]` |
| `warn_return_any` | Warn if function returns `Any` |
| `check_untyped_defs` | Check the bodies of untyped functions |

### Enforcement in CI/CD

**Pre-commit hook** (see Section 5):

```bash
#!/bin/bash
# .git/hooks/pre-commit
set -e
for service in apps/*/; do
  cd "$service"
  source .venv/bin/activate
  ruff check --fix .
  mypy .
  cd - > /dev/null
done
```

### References

- [FAQ | Ruff](https://docs.astral.sh/ruff/faq/)
- [MyPy Configuration for Strict Typing](https://hrekov.com/blog/mypy-configuration-for-strict-typing)
- [Settings | Ruff](https://docs.astral.sh/ruff/settings/)

---

## 4. Makefile Patterns for Multi-Service Python Projects

### Decision: Root Makefile with service delegation + service-specific Makefiles

Use a root `Makefile` as the entry point for common commands (`make test`, `make lint`, `make dev`), which delegates to service-specific Makefiles. Service Makefiles handle isolated setup, testing, and linting for their environment.

### Rationale

- **Single Entry Point**: Developers run `make test` from the repo root; the Makefile handles service discovery.
- **DRY (Don't Repeat Yourself)**: Common patterns (venv setup, test runners, linters) are defined once.
- **Service Isolation**: Each service can have specific dependencies or test configurations without affecting others.
- **Incremental Development**: Developers can also `cd apps/sts-service && make test` for faster feedback during service development.
- **CI/CD Integration**: Root Makefile makes it easy to run all checks in CI without special scripting.

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| No Makefile, use shell scripts | Less discoverable; harder to document with `make help`. |
| Single service Makefile | Doesn't scale; makes root-level commands ambiguous. |
| GNU Make include patterns | More complex; overkill for 2-4 services. |
| Invoke (Python task runner) | Good alternative; adds Python dependency for task running. Use if teams prefer Python over shell. |

### Example Configuration

**Root `Makefile`:**

```makefile
.PHONY: help install lint format test test-coverage clean dev stop

SERVICES = apps/sts-service apps/stream-worker
LIBS = libs/shared-audio libs/shared-utils
PACKAGES = $(SERVICES) $(LIBS)

help:
	@echo "Live Broadcast Dubbing Cloud - Common Tasks"
	@echo "=============================================="
	@echo ""
	@echo "Setup & Development:"
	@echo "  make install          Install all services/libs in editable mode with venvs"
	@echo "  make install-hooks    Install pre-commit hooks"
	@echo "  make clean            Remove all venvs, __pycache__, .pytest_cache"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run Ruff linting on all packages"
	@echo "  make format           Auto-fix Ruff issues (imports, formatting)"
	@echo "  make type-check       Run mypy strict type checking on all packages"
	@echo "  make check            Run lint + type-check (no fixes)"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests with pytest"
	@echo "  make test-coverage    Run tests with coverage report (80% required)"
	@echo ""
	@echo "Running Services:"
	@echo "  make dev              Start all services locally (requires docker-compose)"
	@echo "  make stop             Stop running services"
	@echo ""
	@echo "Service-specific commands:"
	@echo "  cd apps/sts-service && make test"
	@echo "  cd apps/stream-worker && make lint"
	@echo ""

# ============ Setup & Installation ============

install:
	@echo "Installing all services and libraries..."
	@for pkg in $(PACKAGES); do \
		echo "Installing $$pkg..."; \
		cd $$pkg && \
		python3.10 -m venv .venv && \
		.venv/bin/pip install --upgrade pip setuptools wheel && \
		.venv/bin/pip install -e ".[dev]" && \
		cd - > /dev/null; \
	done
	@echo "All packages installed. Run 'make install-hooks' to enable pre-commit checks."

install-hooks:
	@echo "Installing pre-commit hooks..."
	@mkdir -p .git/hooks
	@cp .codex/hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hooks installed."

clean:
	@echo "Removing virtual environments, cache, and artifacts..."
	@for pkg in $(PACKAGES); do \
		rm -rf $$pkg/.venv $$pkg/__pycache__ $$pkg/.pytest_cache $$pkg/.mypy_cache $$pkg/.coverage; \
		find $$pkg -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true; \
		find $$pkg -name "*.pyc" -delete; \
	done
	@rm -rf .coverage htmlcov/ .pytest_cache __pycache__ build/ dist/ *.egg-info
	@echo "Cleaned."

# ============ Code Quality ============

lint:
	@echo "Running Ruff linter on all packages..."
	@for pkg in $(PACKAGES); do \
		echo "Linting $$pkg..."; \
		cd $$pkg && .venv/bin/ruff check . && cd - > /dev/null; \
	done
	@echo "Linting passed."

format:
	@echo "Auto-fixing Ruff issues (imports, formatting)..."
	@for pkg in $(PACKAGES); do \
		echo "Formatting $$pkg..."; \
		cd $$pkg && .venv/bin/ruff check --fix . && cd - > /dev/null; \
	done
	@echo "Formatting complete."

type-check:
	@echo "Running mypy strict type checking..."
	@for pkg in $(PACKAGES); do \
		echo "Type-checking $$pkg..."; \
		cd $$pkg && .venv/bin/mypy . && cd - > /dev/null; \
	done
	@echo "Type checking passed."

check: lint type-check
	@echo "All checks passed."

# ============ Testing ============

test:
	@echo "Running tests on all packages..."
	@for pkg in $(PACKAGES); do \
		echo "Testing $$pkg..."; \
		cd $$pkg && .venv/bin/pytest tests/ -v && cd - > /dev/null; \
	done
	@echo "All tests passed."

test-coverage:
	@echo "Running tests with coverage (80% required)..."
	@for pkg in $(PACKAGES); do \
		echo "Testing $$pkg with coverage..."; \
		cd $$pkg && \
		.venv/bin/pytest tests/ --cov=$$(basename $$pkg) --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=80 && \
		cd - > /dev/null; \
	done
	@echo "Coverage reports available in each package's htmlcov/ directory."

# ============ Running Services ============

dev:
	@echo "Starting services with docker-compose..."
	docker-compose -f infra/docker-compose.local.yml up

stop:
	@echo "Stopping services..."
	docker-compose -f infra/docker-compose.local.yml down

.PHONY: $(SERVICES) $(LIBS)
```

**Service Makefile: `apps/sts-service/Makefile`:**

```makefile
.PHONY: help install lint format test test-coverage type-check check dev clean

# Relative paths from service directory
VENV = .venv
VENV_BIN = $(VENV)/bin
PYTHON = $(VENV_BIN)/python
PIP = $(VENV_BIN)/pip
RUFF = $(VENV_BIN)/ruff
MYPY = $(VENV_BIN)/mypy
PYTEST = $(VENV_BIN)/pytest
SERVICE_NAME = sts_service

help:
	@echo "STS Service - Development Tasks"
	@echo "================================"
	@echo ""
	@echo "  make install       Install service with dev dependencies in .venv"
	@echo "  make lint          Run Ruff linting"
	@echo "  make format        Auto-fix code with Ruff"
	@echo "  make type-check    Run mypy strict type checking"
	@echo "  make check         Run lint + type-check"
	@echo "  make test          Run pytest"
	@echo "  make test-coverage Run tests with coverage report"
	@echo "  make clean         Remove .venv, cache, and artifacts"
	@echo "  make dev           Run service locally (requires other services via docker-compose)"
	@echo ""

install:
	@echo "Setting up STS Service virtual environment..."
	python3.10 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"
	@echo "STS Service ready. Run 'make dev' or 'make test'."

lint:
	@echo "Linting with Ruff..."
	$(RUFF) check $(SERVICE_NAME) tests/

format:
	@echo "Auto-fixing with Ruff..."
	$(RUFF) check --fix $(SERVICE_NAME) tests/

type-check:
	@echo "Type-checking with mypy..."
	$(MYPY) $(SERVICE_NAME)

check: lint type-check
	@echo "Check passed."

test:
	@echo "Running tests..."
	$(PYTEST) tests/ -v

test-coverage:
	@echo "Running tests with coverage (80% required)..."
	$(PYTEST) tests/ --cov=$(SERVICE_NAME) --cov-report=term-missing --cov-report=html --cov-fail-under=80
	@echo "Coverage report: htmlcov/index.html"

clean:
	@echo "Cleaning up..."
	rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .coverage htmlcov/ build/ dist/ *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "Cleaned."

dev:
	@echo "Starting STS Service..."
	$(PYTHON) -m sts_service.main

.PHONY: install lint format test test-coverage type-check check dev clean help
```

**Library Makefile: `libs/shared-audio/Makefile`**

```makefile
# Similar to service Makefile, but without dev target
.PHONY: help install lint format test type-check check clean

VENV = .venv
VENV_BIN = $(VENV)/bin
PYTHON = $(VENV_BIN)/python
PIP = $(VENV_BIN)/pip
RUFF = $(VENV_BIN)/ruff
MYPY = $(VENV_BIN)/mypy
PYTEST = $(VENV_BIN)/pytest
LIB_NAME = shared_audio

help:
	@echo "Shared Audio Library - Development Tasks"
	@echo "=========================================="
	@echo ""
	@echo "  make install       Install library with dev dependencies"
	@echo "  make lint          Run Ruff linting"
	@echo "  make format        Auto-fix code with Ruff"
	@echo "  make type-check    Run mypy strict type checking"
	@echo "  make check         Run lint + type-check"
	@echo "  make test          Run pytest"
	@echo "  make test-coverage Run tests with coverage"
	@echo "  make clean         Remove venv and artifacts"
	@echo ""

install:
	@echo "Setting up Shared Audio Library..."
	python3.10 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"
	@echo "Shared Audio Library ready."

lint:
	$(RUFF) check $(LIB_NAME) tests/

format:
	$(RUFF) check --fix $(LIB_NAME) tests/

type-check:
	$(MYPY) $(LIB_NAME)

check: lint type-check
	@echo "Check passed."

test:
	$(PYTEST) tests/ -v

test-coverage:
	$(PYTEST) tests/ --cov=$(LIB_NAME) --cov-report=term-missing --cov-fail-under=80

clean:
	rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .coverage htmlcov/ build/ dist/ *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

.PHONY: install lint format test type-check check clean help
```

### Key Makefile Patterns

| Pattern | Benefit |
|---|---|
| `.PHONY` target declaration | Ensures make runs the target even if a file with that name exists |
| `$(VAR)` variables | Simplifies maintenance; change once, updates all uses |
| `@echo` prefix suppression | Suppresses echoing the command itself, only the output |
| `&&` sequential execution | Stops on first error (safer than `;` which continues) |
| `for pkg in $(PACKAGES)` loops | Iterate over services/libraries; easy to add/remove |
| `.SILENT` vs `.VERBOSE` | Can suppress or show all commands for debugging |

### References

- [GitHub - matanby/python-monorepo-template](https://github.com/matanby/python-monorepo-template)
- [TIL: Monorepo Makefile inheritance with shared variables and targets](https://tommorris.org/posts/2023/til-makefile-inheritance-and-overriding/)

---

## 5. .gitignore Patterns for Python Monorepos with Virtual Environments

### Decision: Centralized .gitignore in repo root with service-specific overrides (optional)

Create a single `.gitignore` at the repo root that covers all Python artifacts, virtual environments across all services, and IDE files. Service-level `.gitignore` files are rarely needed unless a service has unique exclusions.

### Rationale

- **Single Source of Truth**: One `.gitignore` prevents inconsistent exclusions across services.
- **Prevents Accidental Commits**: Virtual environments (.venv/), bytecode (__pycache__), and test artifacts are never committed.
- **Standard Patterns**: GitHub's official Python.gitignore covers 99% of use cases.
- **Monorepo-Aware**: Patterns like `.venv/`, `**/__pycache__`, and `htmlcov/` work at any directory depth.
- **Platform-Agnostic**: Covers both Unix (*.pyc) and Windows (Scripts/, Lib/) venv artifacts.

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| No .gitignore | Risks committing venvs, which are megabytes of binary files. |
| Service-level .gitignore | Unnecessary duplication; root .gitignore with patterns handles all cases. |
| Python .gitignore generator | Adds online dependency; manual maintenance is simpler. |

### Example Configuration

**Root `.gitignore`:**

```gitignore
# ============ Python Virtual Environments ============
# Virtual environment directories (per-service isolation)
.venv/
.env/
env/
ENV/
venv/
pip-log.txt
pip-delete-this-directory.txt

# ============ Python Bytecode & Compiled Files ============
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# ============ Testing & Coverage ============
.pytest_cache/
.coverage
.coverage.*
coverage.xml
htmlcov/
.tox/
nosetests.xml
pytest-*.txt
.hypothesis/

# ============ Type Checking & Linting ============
.mypy_cache/
.dmypy.json
dmypy.json
.pyre/
.ruff_cache/
.flake8

# ============ IDE & Editor ============
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
.project
.pydevproject
.settings/
*.sublime-project
*.sublime-workspace

# ============ Documentation ============
docs/_build/
site/

# ============ Environment Variables ============
.env
.env.local
.env.*.local

# ============ OS-Specific ============
*.pyo
.AppleDouble
.LSOverride
.TemporaryItems
.Trashes
.VolumeIcon.icns
.fseventsd
thumbs.db

# ============ Application-Specific ============
# RTMP stream artifacts, temporary caches, logs
*.log
logs/
tmp/
temp/
cache/
*.tmp
```

### Service-Specific Additions (Optional)

If a service has unique exclusions, add a service-level `.gitignore`. Example: `apps/sts-service/.gitignore`

```gitignore
# Service-specific exclusions (if needed)
models/  # Downloaded ML models
output_audio/  # Generated audio files
.local/  # Service-specific local data
```

### Rationale for Each Pattern

| Pattern | Reason |
|---|---|
| `.venv/` | Each service has its own venv; always exclude. |
| `__pycache__/` | Bytecode is regenerated on import; never commit. |
| `*.pyc`, `*.pyo` | Compiled Python files; regenerated. |
| `*.egg-info/`, `dist/`, `build/` | Build artifacts; regenerated by setuptools. |
| `.pytest_cache/`, `htmlcov/` | Test artifacts; recreated on next test run. |
| `.mypy_cache/`, `.ruff_cache/` | Tool caches; safe to delete. |
| `.env` | Secrets; never commit (use .env.example instead). |
| `.vscode/`, `.idea/` | IDE settings; personal preferences. |

### Validation

To ensure `.gitignore` is working:

```bash
# List all tracked files (should not include venvs, __pycache__, etc.)
git ls-files | grep -E "(venv|__pycache__|\.pyc|\.coverage)" && echo "ERROR: Excluded files are tracked!" || echo "OK"

# Check for untracked excluded files (sanity check)
git status --ignored
```

### References

- [gitignore/Global/VirtualEnv.gitignore - GitHub](https://github.com/github/gitignore/blob/main/Global/VirtualEnv.gitignore)
- [Mastering `.gitignore` for Python Projects - CodeRivers](https://coderivers.org/blog/git-ignore-python/)

---

## 6. Directory Structure Validation Approaches

### Decision: dirschema + JSON schema for validation, with optional runtime checks

Use **dirschema** (a Python library) to define and validate the monorepo structure against a JSON schema. This ensures the monorepo layout conforms to expected patterns at development and CI time. Combine with optional runtime checks in Makefiles.

### Rationale

- **Schema-Based**: JSON schema is a well-known, tool-agnostic standard for validation.
- **Both CLI and Python API**: `dirschema` supports both command-line validation (for CI) and programmatic checks.
- **Early Detection**: Catch structural issues (missing pyproject.toml, incorrect nesting) before they cause subtle bugs.
- **Documentation**: Schema serves as living documentation of required directory structure.
- **Lightweight**: `dirschema` has minimal dependencies; works in Python 3.8+.
- **Regex + JSON**: Supports complex patterns (e.g., "each service must have tests/unit/, tests/integration/").

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| No validation | Risk of structural drift; new contributors may add files/dirs in wrong places. |
| `directory-schema` (Python) | Simpler but less mature; fewer features than dirschema. |
| Custom Python script | Duplicates logic; harder to maintain and document. |
| Bash script + find/grep | Hard to read; no schema documentation. |

### Example Configuration

**Schema: `.schemas/monorepo-structure.json`**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Live Broadcast Dubbing Cloud Monorepo Structure",
  "type": "object",
  "description": "Validates the monorepo directory structure and required files.",

  "properties": {
    "README.md": {
      "type": "object",
      "description": "Root README required"
    },
    "pyproject.toml": {
      "type": "object",
      "description": "Root pyproject.toml with workspace metadata"
    },
    "Makefile": {
      "type": "object",
      "description": "Root Makefile with common tasks"
    },
    ".gitignore": {
      "type": "object",
      "description": "Root .gitignore for Python artifacts"
    },
    "specs": {
      "type": "object",
      "description": "Product and architecture specifications",
      "properties": {
        "^[0-9]{3}-.*\\.md$": {
          "type": "object",
          "description": "Specification files (kebab-case naming)"
        }
      }
    },
    ".codex": {
      "type": "object",
      "description": "Local agent prompts and workflows",
      "properties": {
        "^.*\\.md$": {
          "type": "object"
        }
      }
    },
    ".specify": {
      "type": "object",
      "description": "Spec templates and shared memory",
      "properties": {
        "templates": {
          "type": "object",
          "description": "Reusable spec templates"
        },
        "test-fixtures": {
          "type": "object",
          "description": "Test fixtures for mock data"
        }
      }
    },
    "apps": {
      "type": "object",
      "description": "Service applications",
      "properties": {
        "^[a-z0-9-]+$": {
          "type": "object",
          "description": "Service directory (kebab-case)",
          "properties": {
            "pyproject.toml": {
              "type": "object",
              "description": "Service-specific pyproject.toml"
            },
            "Makefile": {
              "type": "object",
              "description": "Service-specific Makefile"
            },
            "^[a-z0-9_]+$": {
              "type": "object",
              "description": "Package directory (snake_case)",
              "properties": {
                "__init__.py": {
                  "type": "object",
                  "description": "Python package marker"
                },
                "^[a-z0-9_]\\.py$": {
                  "type": "object",
                  "description": "Python modules"
                }
              }
            },
            "tests": {
              "type": "object",
              "description": "Service test suite",
              "properties": {
                "unit": {
                  "type": "object",
                  "description": "Unit tests (fast, isolated)"
                },
                "contract": {
                  "type": "object",
                  "description": "Contract/API tests"
                },
                "integration": {
                  "type": "object",
                  "description": "Integration tests (cross-service)"
                }
              }
            }
          }
        }
      }
    },
    "libs": {
      "type": "object",
      "description": "Shared libraries",
      "properties": {
        "^[a-z0-9-]+$": {
          "type": "object",
          "description": "Library directory (kebab-case)",
          "properties": {
            "pyproject.toml": {
              "type": "object"
            },
            "^[a-z0-9_]+$": {
              "type": "object",
              "description": "Package directory (snake_case)"
            },
            "tests": {
              "type": "object"
            }
          }
        }
      }
    }
  },

  "required": ["README.md", "pyproject.toml", "Makefile", ".gitignore", "specs", "apps", "libs"]
}
```

**Schema YAML Alternative (more readable): `.schemas/monorepo-structure.yaml`**

```yaml
# Using dirschema YAML format (more intuitive than JSON)
title: Live Broadcast Dubbing Cloud Monorepo Structure
path: /
description: Validates monorepo layout and required files

dirs:
  # Root directories
  - name: specs
    description: Product and architecture specifications
    optional: false
  - name: apps
    description: Service applications
    optional: false
    dirs:
      - name: "^[a-z0-9-]+$"  # Service name: kebab-case
        description: Individual service
        required_files:
          - pyproject.toml
          - Makefile
        dirs:
          - name: "^[a-z0-9_]+$"  # Package name: snake_case
            required_files:
              - __init__.py
          - name: tests
            dirs:
              - name: unit
              - name: contract
              - name: integration

  - name: libs
    description: Shared libraries
    optional: false
    dirs:
      - name: "^[a-z0-9-]+$"  # Library name: kebab-case
        required_files:
          - pyproject.toml
        dirs:
          - name: "^[a-z0-9_]+$"  # Package name: snake_case
          - name: tests

  - name: .codex
    description: Local agent prompts
    optional: false

  - name: .specify
    description: Spec templates
    optional: false
    dirs:
      - name: templates
      - name: test-fixtures

  - name: infra
    description: Deployment and runtime configuration
    optional: true

  - name: docs
    description: Documentation
    optional: true

files:
  - name: README.md
    required: true
  - name: pyproject.toml
    required: true
  - name: Makefile
    required: true
  - name: .gitignore
    required: true
  - name: CLAUDE.md
    required: false
```

**Validation Script: `scripts/validate-structure.py`**

```python
#!/usr/bin/env python3
"""
Validate monorepo structure against schema.

Usage:
    python scripts/validate-structure.py
    python scripts/validate-structure.py --schema .schemas/monorepo-structure.yaml
    python scripts/validate-structure.py --fix  # (auto-correct minor issues)
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from dirschema.validate import DSValidator
except ImportError:
    print("ERROR: dirschema not installed. Run: pip install dirschema")
    sys.exit(1)


def validate_structure(
    repo_root: Path = Path.cwd(),
    schema_path: str = ".schemas/monorepo-structure.yaml",
) -> Tuple[bool, List[str]]:
    """
    Validate monorepo structure.

    Args:
        repo_root: Root directory of the monorepo.
        schema_path: Path to schema file (relative to repo_root).

    Returns:
        (is_valid, error_messages)
    """
    schema_file = repo_root / schema_path

    if not schema_file.exists():
        return False, [f"Schema file not found: {schema_file}"]

    try:
        validator = DSValidator(str(schema_file))
        validator.validate(str(repo_root))
        return True, []
    except Exception as e:
        return False, [str(e)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate monorepo structure against schema"
    )
    parser.add_argument(
        "--schema",
        default=".schemas/monorepo-structure.yaml",
        help="Path to schema file",
    )
    parser.add_argument(
        "--repo", default=".", help="Path to monorepo root"
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    is_valid, errors = validate_structure(repo, args.schema)

    if is_valid:
        print(f"✓ Structure valid: {repo}")
        sys.exit(0)
    else:
        print(f"✗ Structure validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
```

**Integration with Makefile:**

```makefile
# In root Makefile, add:

validate-structure:
	@echo "Validating monorepo structure..."
	@python3 scripts/validate-structure.py --repo .
	@echo "Structure valid."

.PHONY: validate-structure
```

**CI Integration (GitHub Actions example):**

```yaml
# .github/workflows/validate.yml
name: Validate Structure

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      - run: pip install dirschema
      - run: make validate-structure
```

### Runtime Directory Validation

Optional: Add a runtime check in service initialization to ensure expected directories exist.

**Example: `apps/sts-service/sts_service/validate_structure.py`**

```python
"""Runtime validation of service structure."""

from pathlib import Path
from typing import List


def validate_service_structure(service_root: Path) -> List[str]:
    """
    Validate that all required directories exist at runtime.

    Catches issues like "tests/ directory missing" early in the test run.
    """
    errors: List[str] = []

    required_dirs = [
        "tests/unit",
        "tests/contract",
    ]

    for dir_path in required_dirs:
        full_path = service_root / dir_path
        if not full_path.exists():
            errors.append(f"Missing directory: {dir_path}")

    required_files = [
        "pyproject.toml",
        "Makefile",
    ]

    for file_path in required_files:
        full_path = service_root / file_path
        if not full_path.exists():
            errors.append(f"Missing file: {file_path}")

    return errors


if __name__ == "__main__":
    import sys

    service_root = Path(__file__).parent.parent
    errors = validate_service_structure(service_root)

    if errors:
        print("Structure validation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("Service structure valid.")
```

### Key Schema Benefits

| Feature | Benefit |
|---|---|
| Regex patterns | Enforce naming conventions (kebab-case for dirs, snake_case for packages) |
| Nested validation | Ensures internal structure of each service (tests/ has unit/, integration/) |
| Required files | Catches missing pyproject.toml, Makefile, __init__.py |
| Optional dirs | Allows infra/, docs/ without requiring them |
| YAML readability | Schema is clear to humans; easier to update than JSON |
| CI integration | Can fail PR if structure is invalid |

### References

- [dirschema | PyPI](https://pypi.org/project/dirschema/)
- [GitHub - jpoehnelt/directory-schema-validator](https://github.com/jpoehnelt/directory-schema-validator)

---

## Summary Table: Decisions & Rationale

| Topic | Decision | Key Rationale | Tools/Stack |
|---|---|---|---|
| **PEP 621** | PEP 621 + setuptools | Industry standard, single source of truth, tool-agnostic | setuptools 61.0+, pip, build |
| **Monorepo Pattern** | Editable installs + per-service venvs | Built-in tooling, immediate changes, isolated environments | pip, venv, setuptools |
| **Linting & Type Checking** | Ruff + mypy --strict | Complementary: Ruff for speed, mypy for correctness | Ruff, mypy, pytest |
| **Build Automation** | Root + service Makefiles | Single entry point, service isolation, DRY | GNU Make |
| **.gitignore** | Centralized root .gitignore | Single source of truth, prevents accidental commits | git |
| **Structure Validation** | dirschema + JSON schema | Schema-based, early detection, documentation | dirschema, pytest |

---

## Implementation Checklist

- [ ] Create root `pyproject.toml` with PEP 621 metadata (Section 1)
- [ ] Create service `pyproject.toml` files with dependencies (Section 1)
- [ ] Create root `Makefile` with install, lint, test targets (Section 4)
- [ ] Create service Makefiles (Section 4)
- [ ] Create root `.gitignore` with Python/venv patterns (Section 5)
- [ ] Create `pyproject.toml` `[tool.ruff]` and `[tool.mypy]` config (Section 3)
- [ ] Create `.schemas/monorepo-structure.yaml` (Section 6)
- [ ] Create `scripts/validate-structure.py` (Section 6)
- [ ] Run `make install` to verify venv setup works (Section 2)
- [ ] Run `make check` to verify linting/type-checking works (Section 3)
- [ ] Run `make validate-structure` to verify schema validation (Section 6)
- [ ] Add pre-commit hook for TDD enforcement (CLAUDE.md Section: Testing Guidelines)
- [ ] Document in README.md: local dev setup, common commands, troubleshooting

---

## References

### PEP 621 & Packaging
- [PEP 621 – Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [The Basics of Python Packaging in Early 2023 - DrivenData Labs](https://drivendata.co/blog/python-packaging-2023)
- [The Center of Your Python Project: Understanding pyproject.toml](https://mcginniscommawill.com/posts/2025-01-26-pyproject-toml-explained/)

### Monorepo Patterns
- [Python Monorepo: an Example. Part 1: Structure and Tooling - Tweag](https://www.tweag.io/blog/2023-04-04-python-monorepo-1/)
- [Beyond Hypermodern: Python is easy now - Chris Arderne](https://rdrn.me/postmodern-python/)
- [GitHub - tweag/python-monorepo-example](https://github.com/tweag/python-monorepo-example)

### Ruff & Mypy
- [FAQ | Ruff](https://docs.astral.sh/ruff/faq/)
- [MyPy Configuration for Strict Typing](https://hrekov.com/blog/mypy-configuration-for-strict-typing)
- [Settings | Ruff](https://docs.astral.sh/ruff/settings/)

### Makefiles
- [GitHub - matanby/python-monorepo-template](https://github.com/matanby/python-monorepo-template)
- [TIL: Monorepo Makefile inheritance with shared variables and targets](https://tommorris.org/posts/2023/til-makefile-inheritance-and-overriding/)

### .gitignore
- [gitignore/Global/VirtualEnv.gitignore - GitHub](https://github.com/github/gitignore/blob/main/Global/VirtualEnv.gitignore)
- [Mastering `.gitignore` for Python Projects - CodeRivers](https://coderivers.org/blog/git-ignore-python/)

### Directory Structure Validation
- [dirschema | PyPI](https://pypi.org/project/dirschema/)
- [GitHub - jpoehnelt/directory-schema-validator](https://github.com/jpoehnelt/directory-schema-validator)

---

**Document generated:** 2025-12-25
**Target Python versions:** 3.10, 3.11, 3.12, 3.13
**Monorepo scope:** 2 services (sts-service, stream-worker), 2 libraries (shared-audio, shared-utils)
