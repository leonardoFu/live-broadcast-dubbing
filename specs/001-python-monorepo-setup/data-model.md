# Data Model: Python Monorepo Directory Structure

**Feature**: Python Monorepo Directory Setup
**Branch**: `001-python-monorepo-setup`
**Created**: 2025-12-25

## Overview

This document defines the "data model" for the Python monorepo setup feature. Since this is an infrastructure setup task, the data model represents the directory structure itself - the entities are directories, files, and Python packages that must be created to establish the monorepo development environment.

## Entity Definitions

### 1. Directory Entity

Represents a directory in the file system that must be created as part of the monorepo structure.

**Attributes**:
- `path` (string): Absolute or relative path from repository root
- `purpose` (string): Human-readable description of what this directory contains
- `required` (boolean): Whether this directory is mandatory for the feature
- `naming_convention` (string): Expected naming pattern (kebab-case, snake_case, etc.)

**Relationships**:
- `parent` (Directory): The containing directory (null for root-level directories)
- `children` (List[Directory]): Subdirectories within this directory
- `files` (List[File]): Configuration/documentation files in this directory

**Validation Rules**:
- All required directories must exist after setup
- Directory names must match architectural spec (`specs/001-1-python-monorepo-setup.md` section 4)
- Permissions must allow read/write for the creating user

**State Transitions**:
- `not_exists` → `created` (via `mkdir -p` or equivalent)
- `created` → `not_exists` (only during cleanup, not normal operation)

### 2. File Entity

Represents a configuration or documentation file that must be created.

**Attributes**:
- `path` (string): Absolute or relative path from repository root
- `content_type` (enum): Type of file content
  - `toml`: Python package metadata (pyproject.toml)
  - `markdown`: Documentation (README.md)
  - `makefile`: Build automation (Makefile)
  - `gitignore`: Git exclusion patterns (.gitignore)
  - `python`: Python module initialization (__init__.py)
  - `requirements`: Dependency lock file (requirements.txt, requirements-dev.txt)
- `template` (string): Template name or content to use for generation
- `encoding` (string): File encoding (default: UTF-8 per FR-011)
- `required` (boolean): Whether this file is mandatory

**Relationships**:
- `parent_directory` (Directory): The directory containing this file
- `package` (Package): The Python package this file belongs to (if applicable)

**Validation Rules**:
- All generated files must use UTF-8 encoding (FR-011)
- TOML files must pass syntax validation (parseable by Python `toml` library)
- Python files (__init__.py) must be valid Python syntax
- Markdown files should pass linting (optional)
- Makefile must have valid target syntax

**State Transitions**:
- `not_exists` → `created` (during setup)
- `created` → `updated` (only if template changes - not in initial setup)
- Never overwrite existing files (FR-012 - preserve existing files)

### 3. Package Entity

Represents a Python package (service or shared library) with its complete structure.

**Attributes**:
- `name` (string): Package name (e.g., "media-service", "dubbing-common")
- `python_name` (string): Import name (e.g., "media_service", "dubbing_common")
- `type` (enum): Package type
  - `service`: Deployable application (apps/*)
  - `library`: Shared library (libs/*)
- `version` (string): Package version (default: "0.1.0")
- `python_version_constraint` (string): Required Python version (e.g., ">=3.10,<3.11")
- `dependencies` (List[string]): Package dependencies in PEP 508 format
- `dev_dependencies` (List[string]): Development/testing dependencies

**Relationships**:
- `root_directory` (Directory): Top-level package directory
- `src_directory` (Directory): Source code directory (src/<python_name>/)
- `test_directory` (Directory): Test directory (tests/)
- `metadata_file` (File): pyproject.toml file
- `readme_file` (File): README.md file

**Validation Rules**:
- Package `name` must use kebab-case (e.g., "media-service")
- Python `python_name` must use snake_case (e.g., "media_service")
- `python_name` must be a valid Python identifier (no hyphens, no leading digits)
- All packages must have pyproject.toml, src/, tests/, README.md (per contract)
- Services must have both tests/unit/ and tests/integration/
- Libraries must have at least tests/unit/

**Dependency Rules** (from architectural spec):
- Services can depend on libraries (e.g., media-service → dubbing-common)
- Services CANNOT depend on other services (cross-service imports forbidden)
- Libraries can depend on other libraries (e.g., common → contracts is allowed)
- Circular dependencies between packages are forbidden

**State Transitions**:
- `not_exists` → `scaffolded` (directory structure created)
- `scaffolded` → `configured` (pyproject.toml written)
- `configured` → `installable` (can be installed with `pip install -e .`)

### 4. Virtual Environment Entity

Represents an isolated Python environment for a service.

**Attributes**:
- `name` (string): Virtual environment directory name (e.g., ".venv-stream", ".venv-sts")
- `python_version` (string): Python interpreter version (must be 3.10.x)
- `service` (string): Associated service name

**Relationships**:
- `service_package` (Package): The service this venv is for
- `installed_packages` (List[Package]): Packages installed in this venv (service + libraries)

**Validation Rules**:
- Virtual environment directories must be excluded from git (.gitignore)
- Each service should have its own separate venv (no shared venvs)
- Python version must match constraint (>=3.10,<3.11)

**Lifecycle** (NOT created by this feature, but documented for completeness):
- Created by developers after setup via `python3.10 -m venv .venv-stream`
- Activated via `source .venv-stream/bin/activate`
- Packages installed via `pip install -e libs/common -e libs/contracts -e .`

## Directory Structure Model

### Top-Level Structure

```
Repository Root/
├── apps/           # Service applications (type: directory, required: true)
├── libs/           # Shared libraries (type: directory, required: true)
├── tests/          # End-to-end tests (type: directory, required: true)
├── deploy/         # Deployment configs (type: directory, required: true)
├── specs/          # Specifications (type: directory, required: true - already exists)
├── .specify/       # Spec templates (type: directory, required: true - already exists)
├── pyproject.toml  # Root tooling config (type: file, content_type: toml, required: true)
├── .gitignore      # Git exclusions (type: file, content_type: gitignore, required: true)
├── Makefile        # Build automation (type: file, content_type: makefile, required: true)
└── README.md       # Repository docs (type: file, content_type: markdown, required: false - may exist)
```

### Package Structure (Service Pattern)

**Template** for `apps/<service-name>/`:

```
apps/<service-name>/                    # type: Package (service)
├── pyproject.toml                      # metadata_file (required)
├── requirements.txt                    # dependency lock file (initially empty)
├── requirements-dev.txt                # dev dependency lock file (initially empty)
├── README.md                           # readme_file (required)
├── src/                                # src_directory (required)
│   └── <python_name>/                  # Python package namespace
│       ├── __init__.py                 # Package init (required)
│       └── <module_dirs>/              # Module subdirectories (optional)
│           └── __init__.py
└── tests/                              # test_directory (required)
    ├── unit/                           # Unit tests (required for services)
    │   └── __init__.py
    └── integration/                    # Integration tests (required for services)
        └── __init__.py
```

**Instances**:
1. `apps/media-service/` (service package)
   - Python name: `media_service`
   - Module subdirectories: `pipelines/`

2. `apps/sts-service/` (service package)
   - Python name: `sts_service`
   - Module subdirectories: `asr/`, `translation/`, `tts/`

### Package Structure (Library Pattern)

**Template** for `libs/<library-name>/`:

```
libs/<library-name>/                    # type: Package (library)
├── pyproject.toml                      # metadata_file (required)
├── README.md                           # readme_file (required)
├── src/                                # src_directory (required)
│   └── dubbing_<library_name>/         # Python package namespace (prefixed)
│       ├── __init__.py                 # Package init (required)
│       └── [future module files]       # Implementation (not created by this feature)
└── tests/                              # test_directory (required)
    └── unit/                           # Unit tests (required for libraries)
        └── __init__.py
```

**Instances**:
1. `libs/common/` (library package)
   - Python name: `dubbing_common`
   - Future modules: `audio.py`, `types.py`, `logging.py`

2. `libs/contracts/` (library package)
   - Python name: `dubbing_contracts`
   - Future modules: `sts.py`, `events.py`

### Deployment Structure

**Template** for `deploy/<service-name>/`:

```
deploy/<service-name>/                  # type: Directory (deployment configs)
└── [future: Dockerfile, docker-compose.yml]
```

**Instances**:
1. `deploy/media-service/` (empty directory for now)
2. `deploy/sts-service/` (empty directory for now)

### Test Structure

**Root-level end-to-end tests**:

```
tests/                                  # type: Directory (E2E tests)
└── e2e/                                # E2E test directory
    └── __init__.py                     # Package init
```

## File Content Templates

### pyproject.toml (Service)

**Location**: `apps/<service-name>/pyproject.toml`

**Template Variables**:
- `{service_name}`: Kebab-case service name (e.g., "media-service")
- `{python_name}`: Snake_case Python name (e.g., "media_service")
- `{dependencies}`: List of package dependencies

**Minimal Required Sections** (from research.md):
```toml
[project]
name = "{service_name}"
version = "0.1.0"
requires-python = ">=3.10,<3.11"
dependencies = [
    # Core dependencies
    "numpy<2.0",
    "pyyaml",
    "pydantic>=2.0",
    "rich",
    # Shared libraries
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

### pyproject.toml (Library)

**Location**: `libs/<library-name>/pyproject.toml`

**Minimal Required Sections**:
```toml
[project]
name = "dubbing-{library_name}"
version = "0.1.0"
requires-python = ">=3.10,<3.11"
dependencies = [
    # Minimal shared dependencies only
    "pydantic>=2.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

### pyproject.toml (Root - Tooling Only)

**Location**: `pyproject.toml` (repository root)

**Purpose**: Linting and type-checking configuration (not a package)

**Required Sections** (from research.md):
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
"__init__.py" = ["F401"]  # Allow unused imports

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### Makefile (Root)

**Location**: `Makefile` (repository root)

**Required Targets** (from FR-008 and research.md):
- `help`: Display available commands
- `setup-stream`: Create venv and install media-service service
- `setup-sts`: Create venv and install sts-service
- `test-all`: Run tests for all packages
- `lint`: Run ruff check on all code
- `format`: Auto-format all code with ruff

### .gitignore

**Location**: `.gitignore` (repository root)

**Required Patterns** (from FR-007 and research.md):
- Virtual environments: `.venv-stream`, `.venv-sts`, `.venv/`, `env/`, `venv/`
- Python bytecode: `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`
- Build artifacts: `build/`, `dist/`, `*.egg-info/`, `*.egg`
- Test artifacts: `.pytest_cache/`, `.coverage`, `htmlcov/`
- Tool caches: `.mypy_cache/`, `.ruff_cache/`
- IDE files: `.vscode/`, `.idea/`, `*.swp`, `.DS_Store`

### README.md (Service)

**Location**: `apps/<service-name>/README.md`

**Required Sections**:
1. Service description and purpose
2. Prerequisites (Python 3.10.x)
3. Local setup instructions (create venv, install dependencies)
4. Running tests
5. Development workflow

### README.md (Library)

**Location**: `libs/<library-name>/README.md`

**Required Sections**:
1. Library description and purpose
2. Installation instructions (for other packages)
3. Usage examples
4. Development setup

## Dependency Graph

```
┌──────────────────────────────────────────────────────────┐
│                    Repository Root                        │
│  (pyproject.toml, Makefile, .gitignore, README.md)       │
└──────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬─────────────┐
        │               │               │             │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
   │  apps/  │    │  libs/  │    │ tests/  │   │ deploy/ │
   └────┬────┘    └────┬────┘    └────┬────┘   └────┬────┘
        │              │              │             │
   ┌────┴────┐    ┌────┴────┐        │        ┌────┴────┐
   │         │    │         │        │        │         │
┌──▼──┐  ┌──▼──┐ │ common/ │ contracts/     e2e/     (empty)
│stream│  │sts  │ │         │   │         │
│infra.│  │svc. │ └────┬────┘   └─┬───────┘
└──┬───┘  └──┬──┘      │          │
   │         │         │          │
   │         │         │          │
   └─────────┴─────────┴──────────┘
             │
        [imports]
   dubbing_common, dubbing_contracts
```

**Import Rules**:
- ✅ Services → Libraries (allowed)
- ❌ Services → Services (forbidden - FR-012 violation)
- ✅ Libraries → Libraries (allowed)
- ❌ Circular imports (forbidden)

## Validation Schema

The complete JSON schema for directory structure validation is defined in `contracts/directory-structure.json`. Key validation rules:

1. **Required directories**: apps/, libs/, tests/, deploy/
2. **Required packages**:
   - Services: apps/media-service/, apps/sts-service/
   - Libraries: libs/common/, libs/contracts/
3. **Required files per package**:
   - pyproject.toml (valid TOML syntax)
   - README.md (non-empty)
   - src/<python_name>/__init__.py (valid Python)
   - tests/unit/__init__.py (for all packages)
   - tests/integration/__init__.py (for services only)

## Success Criteria Mapping

Each success criteria from spec.md maps to entities in this data model:

- **SC-001**: Virtual Environment entities can be created independently
- **SC-002**: All Package entities are installable (valid pyproject.toml)
- **SC-003**: Package dependency graph allows cross-imports (services → libraries)
- **SC-004**: Root-level File entities (Makefile, pyproject.toml) enable tooling
- **SC-005**: All Package entities have README.md files
- **SC-006**: Directory structure matches this data model 100%
- **SC-007**: .gitignore File entity excludes all generated directories
- **SC-008**: Virtual Environment entities are isolated (separate venvs per service)

## Implementation Order

Based on entity dependencies, the implementation should follow this order:

1. **Create Directory entities** (P1):
   - apps/, libs/, tests/, deploy/ (top-level)
   - Service and library root directories
   - src/ and tests/ subdirectories

2. **Create Package metadata** (P2):
   - pyproject.toml files for all 4 packages
   - Package entities become "configured"

3. **Create Package namespaces** (P3):
   - __init__.py files in all Python package directories
   - Package entities become "installable"

4. **Create Root tooling** (P4):
   - Root pyproject.toml (ruff, mypy config)
   - .gitignore
   - Makefile

5. **Create Documentation** (P5):
   - README.md files for all packages
   - Update repository root README.md

This order ensures each phase builds on the previous one, matching the user story priorities (P1-P5) from spec.md.
