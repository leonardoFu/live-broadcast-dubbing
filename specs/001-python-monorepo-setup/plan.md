# Implementation Plan: Python Monorepo Directory Setup

**Branch**: `001-python-monorepo-setup` | **Date**: 2025-12-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-python-monorepo-setup/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create the Python monorepo directory structure and configuration files for two independent services (media-service and sts-service) with shared libraries (common, contracts). This is a foundational setup task that establishes the development environment described in `specs/001-1-python-monorepo-setup.md`. The implementation will create all necessary directories, package metadata files (pyproject.toml), Python package namespaces (__init__.py), development tooling configuration (ruff, mypy, Makefile), and documentation (README.md files).

## Technical Context

**Language/Version**: Python 3.10.x (as specified in constitution and architecture spec)
**Primary Dependencies**: setuptools>=68.0 (build system), ruff>=0.1.0 (linting), mypy>=1.0 (type checking), pytest>=7.0 (testing)
**Storage**: File system (directory and file creation only)
**Testing**: pytest with custom validators for directory structure, TOML syntax, and Python imports
**Target Platform**: Development environment (macOS, Linux, Windows compatible)
**Project Type**: Infrastructure setup (monorepo structure creation)
**Performance Goals**: Instant setup (<5 seconds for all directory and file creation)
**Constraints**: Must preserve existing files (FR-012), must use UTF-8 encoding (FR-011), must match architectural spec 100% (SC-006)
**Scale/Scope**: 4 packages (2 services + 2 libraries), ~50 directories, ~25 files created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (5 user stories with unit/contract/integration tests)
- [x] Mock patterns documented for validation (mock imports, mock pip install, mock file system checks)
- [x] Coverage targets specified (80% minimum per constitution, 100% for this setup task due to deterministic nature)
- [x] Test infrastructure matches constitution requirements (pytest, coverage enforcement via pre-commit)
- [x] Test organization follows standard structure (tests/unit/ for setup validators, tests/integration/ for end-to-end setup validation)

**Principle III - Spec-Driven Development**:
- [x] Architecture spec exists (`specs/001-1-python-monorepo-setup.md`) with complete directory layout
- [x] Feature spec created (`specs/001-python-monorepo-setup/spec.md`) with 15 functional requirements
- [x] Implementation plan (this document) created before any code

**Principle II - Testability Through Isolation**:
- [x] Setup script testable without requiring virtual environments or package installations
- [x] Directory structure validation independent of Python runtime
- [x] File content validation uses deterministic checks (syntax validation, template matching)

**All gates PASSED** - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-python-monorepo-setup/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (technology/pattern research)
├── data-model.md        # Phase 1 output (directory structure model)
├── quickstart.md        # Phase 1 output (developer onboarding guide)
├── contracts/           # Phase 1 output (directory structure schema)
│   └── directory-structure.json  # JSON schema for validation
├── checklists/          # Quality validation checklists
│   └── requirements.md  # Spec quality checklist (already created)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature creates the repository structure itself. The target layout (from `specs/001-1-python-monorepo-setup.md` section 4):

```text
live-broadcast-dubbing-cloud/
├── apps/                               # Service applications
│   ├── media-service/          # EC2 stream worker (CPU-only)
│   │   ├── pyproject.toml              # Service-specific dependencies
│   │   ├── requirements.txt            # Locked CPU-only dependencies
│   │   ├── requirements-dev.txt        # Dev/test dependencies
│   │   ├── src/
│   │   │   └── media_service/  # Python package namespace
│   │   │       ├── __init__.py
│   │   │       ├── pipelines/          # Module subdirectories
│   │   │       │   └── __init__.py
│   │   │       └── [future: worker.py, sts_client.py, config.py]
│   │   ├── tests/                      # Service-specific tests
│   │   │   ├── unit/
│   │   │   │   └── __init__.py
│   │   │   └── integration/
│   │   │       └── __init__.py
│   │   └── README.md                   # Local setup instructions
│   │
│   └── sts-service/                    # RunPod GPU service
│       ├── pyproject.toml              # Service-specific dependencies (GPU PyTorch)
│       ├── requirements.txt            # Locked GPU dependencies (initially empty)
│       ├── requirements-dev.txt        # Dev/test dependencies
│       ├── src/
│       │   └── sts_service/            # Python package namespace
│       │       ├── __init__.py
│       │       ├── asr/                # Module subdirectories
│       │       │   └── __init__.py
│       │       ├── translation/
│       │       │   └── __init__.py
│       │       ├── tts/
│       │       │   └── __init__.py
│       │       └── [future: api.py, config.py]
│       ├── tests/                      # Service-specific tests
│       │   ├── unit/
│       │   │   └── __init__.py
│       │   └── integration/
│       │       └── __init__.py
│       └── README.md                   # Local setup instructions
│
├── libs/                               # Shared libraries (internal packages)
│   ├── common/                         # Common utilities
│   │   ├── pyproject.toml              # Minimal shared dependencies
│   │   ├── src/
│   │   │   └── dubbing_common/
│   │   │       ├── __init__.py
│   │   │       └── [future: audio.py, types.py, logging.py]
│   │   ├── tests/
│   │   │   └── unit/
│   │   │       └── __init__.py
│   │   └── README.md
│   │
│   └── contracts/                      # API contracts and schemas
│       ├── pyproject.toml
│       ├── src/
│       │   └── dubbing_contracts/
│       │       ├── __init__.py
│       │       └── [future: sts.py, events.py]
│       ├── tests/
│       │   └── unit/
│       │       └── __init__.py
│       └── README.md
│
├── tests/                              # End-to-end integration tests
│   └── e2e/
│       └── __init__.py
│
├── deploy/                             # Docker and deployment configs
│   ├── media-service/
│   │   └── [future: Dockerfile, docker-compose.yml]
│   └── sts-service/
│       └── [future: Dockerfile, docker-compose.yml]
│
├── pyproject.toml                      # Root-level tooling config (ruff, mypy)
├── .gitignore                          # Git ignore patterns
├── Makefile                            # Development workflow commands
└── README.md                           # Repository overview (update existing)
```

**Structure Decision**: This feature implements the monorepo structure from `specs/001-1-python-monorepo-setup.md`. The structure uses a hybrid approach with `apps/` for services (2 applications), `libs/` for shared libraries (2 packages), centralized `tests/e2e/` for end-to-end tests, and `deploy/` for deployment configurations. This layout enables independent service development with shared code reuse while maintaining strict dependency isolation.

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- Target: Directory creation logic, file content generation, template rendering
- Tools: pytest, pytest-mock, pathlib for file system operations
- Coverage: 100% (setup scripts are deterministic and fully testable)
- Mocking: File system operations can be tested with temporary directories
- Location: `tests/unit/test_setup_structure.py`, `tests/unit/test_pyproject_generation.py`, `tests/unit/test_makefile_generation.py`

**Contract Tests** (mandatory):
- Target: Generated file formats (TOML syntax, Makefile syntax, Markdown structure)
- Tools: pytest with toml library for validation, JSON schema for directory structure
- Coverage: 100% of all generated files (pyproject.toml, Makefile, .gitignore, README.md)
- Mocking: Use deterministic fixtures from `contracts/directory-structure.json`
- Location: `tests/contract/test_pyproject_schema.py`, `tests/contract/test_directory_schema.py`

**Integration Tests** (required for workflows):
- Target: Full setup workflow (directory creation → file generation → validation)
- Tools: pytest with temporary directory fixtures
- Coverage: All 5 user stories (P1-P5) have end-to-end integration tests
- Mocking: Use isolated temporary directories for each test
- Location: `tests/integration/test_full_setup.py`

**E2E Tests** (optional, for validation only):
- Target: Running setup in actual repository, validating with pip install, running linters
- Tools: pytest with actual repository root (run in separate test environment)
- Coverage: Critical user journeys only (SC-001 through SC-008)
- When: Run manually before release, not in CI (to avoid polluting repository)
- Location: `tests/e2e/test_repository_setup.py`

### Mock Patterns (Constitution Principle II)

**File System Mocks**:
- `pytest.fixture` with `tmp_path` for isolated directory structures
- Mock `Path.mkdir()`, `Path.write_text()` for unit tests
- Real file operations in temporary directories for integration tests

**Python Import Mocks**:
- Mock `importlib.import_module()` to validate package imports without installing
- Use `sys.path` manipulation in temporary directories for import validation

**Validation Mocks**:
- Mock `subprocess.run()` for linting/type-checking commands (unit tests)
- Real execution in temporary venvs for integration tests (optional)

### Coverage Enforcement

**Pre-commit**: Run `pytest --cov=setup --cov-fail-under=100` - fail if coverage < 100%
**CI**: Run `pytest --cov=setup --cov-fail-under=100` - block merge if fails
**Critical paths**: All setup code → 100% coverage (no exceptions - this is deterministic setup)

### Test Naming Conventions

Follow conventions from `tasks-template.md`:
- `test_create_directory_structure_happy_path()` - Normal directory creation
- `test_create_directory_structure_error_permissions()` - Permission denied scenario
- `test_generate_pyproject_error_invalid_package_name()` - Invalid package name
- `test_setup_integration_all_packages_installable()` - Full workflow validation

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**No violations** - This feature aligns with all constitution principles.

---

## Phase 0: Research & Technology Decisions

### Research Questions

1. **Python Package Metadata Standards**: What are the current best practices for `pyproject.toml` in Python 3.10+ projects?
2. **Monorepo Tooling**: What are the best practices for managing multiple Python packages in a single repository?
3. **Editable Install Patterns**: How to structure editable installs (`pip install -e`) for shared libraries?
4. **Linting Configuration**: What are the recommended ruff rules for strict type-checked Python projects?
5. **Makefile Patterns**: What are the best practices for Python project Makefiles with multiple services?
6. **Git Ignore Patterns**: What files should be excluded for Python projects with virtual environments and build artifacts?

### Research Tasks

*These will be resolved in `research.md` (Phase 0 output)*

1. **Task**: Research PEP 621 (pyproject.toml specification) and setuptools>=68.0 best practices
   - **Output**: Recommended `pyproject.toml` structure for services and libraries
   - **Decision criteria**: PEP compliance, setuptools compatibility, simplicity

2. **Task**: Research Python monorepo patterns (Google-style monorepo, Pants, Bazel, vs simple editable installs)
   - **Output**: Chosen pattern (simple editable installs with separate venvs)
   - **Decision criteria**: No extra tooling, standard pip workflow, clear separation

3. **Task**: Research ruff configuration for strict typing and code quality
   - **Output**: Recommended ruff rules and mypy strict mode configuration
   - **Decision criteria**: Catch common bugs, enforce type hints, avoid false positives

4. **Task**: Research Makefile patterns for multi-service Python projects
   - **Output**: Makefile template with setup-*, test-*, lint, format targets
   - **Decision criteria**: Simple commands, parallel test execution, clear documentation

5. **Task**: Research .gitignore patterns for Python monorepos
   - **Output**: Comprehensive .gitignore covering venvs, build artifacts, IDE files
   - **Decision criteria**: Standard Python patterns + monorepo-specific exclusions

6. **Task**: Research directory structure validation approaches
   - **Output**: JSON schema for directory structure validation in tests
   - **Decision criteria**: Machine-readable, easy to validate, maintainable

---

## Phase 1: Design Artifacts

### Data Model (`data-model.md`)

The "data model" for this feature is the directory structure itself. The data model document will define:

1. **Directory Entity**: Represents a directory in the file system
   - Attributes: `path` (string), `purpose` (string), `required` (boolean)
   - Relationships: `parent` (Directory), `children` (List[Directory])

2. **File Entity**: Represents a configuration/documentation file
   - Attributes: `path` (string), `content_type` (string: toml/markdown/makefile/gitignore), `template` (string)
   - Relationships: `parent_directory` (Directory)

3. **Package Entity**: Represents a Python package (service or library)
   - Attributes: `name` (string), `type` (service/library), `dependencies` (List[string])
   - Relationships: `directory` (Directory), `metadata_file` (File: pyproject.toml)

### Contracts (`contracts/directory-structure.json`)

JSON Schema defining the expected directory structure for validation:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["apps", "libs", "tests", "deploy"],
  "properties": {
    "apps": {
      "type": "object",
      "required": ["media-service", "sts-service"],
      "properties": {
        "media-service": {
          "$ref": "#/definitions/service"
        },
        "sts-service": {
          "$ref": "#/definitions/service"
        }
      }
    },
    "libs": {
      "type": "object",
      "required": ["common", "contracts"],
      "properties": {
        "common": {
          "$ref": "#/definitions/library"
        },
        "contracts": {
          "$ref": "#/definitions/library"
        }
      }
    }
  },
  "definitions": {
    "service": {
      "type": "object",
      "required": ["pyproject.toml", "src", "tests", "README.md"],
      "properties": {
        "src": {
          "type": "object",
          "required": ["__init__.py"]
        },
        "tests": {
          "type": "object",
          "required": ["unit", "integration"]
        }
      }
    },
    "library": {
      "type": "object",
      "required": ["pyproject.toml", "src", "tests", "README.md"]
    }
  }
}
```

### Quick Start Guide (`quickstart.md`)

Developer onboarding guide covering:

1. **Prerequisites**: Python 3.10.x, git
2. **Initial Setup**: Clone repository, run `make setup-stream` or `make setup-sts`
3. **Development Workflow**: Create venv, install packages, run tests, run linters
4. **Common Tasks**: Adding new modules, running tests, switching between services
5. **Troubleshooting**: Common errors (version mismatch, import errors, permission issues)

---

## Phase 2: Task Breakdown

*Tasks will be generated by `/speckit.tasks` command (not part of this plan)*

The task breakdown will follow the 5 user story priorities (P1-P5) and create implementation tasks for:

1. **P1 Tasks**: Create all directories from architectural spec
2. **P2 Tasks**: Generate pyproject.toml for all 4 packages
3. **P3 Tasks**: Create __init__.py files in all package namespaces
4. **P4 Tasks**: Generate root tooling config (pyproject.toml, .gitignore, Makefile)
5. **P5 Tasks**: Generate README.md files for all packages and repository root

Each task will include:
- Test requirements (unit, contract, integration)
- Acceptance criteria from spec
- Dependencies on previous tasks
- Estimated complexity (all tasks are simple for this feature)

---

## Implementation Notes

### Design Decisions

1. **No automation script**: This setup will be implemented as a series of manual file creations (via Write tool) rather than a Python script. This aligns with the constitution's preference for simplicity and allows each file to be reviewed individually.

2. **Template-based approach**: All generated files (pyproject.toml, README.md, Makefile) will use templates defined in Phase 0 research rather than hardcoded strings.

3. **Incremental validation**: After each file/directory creation, run validation tests to ensure correctness before proceeding.

4. **Preserve existing files**: Check for existing files before creating (FR-012). If repository already has partial structure, preserve it and only create missing pieces.

### Risk Mitigation

1. **Risk**: Overwriting existing files
   - **Mitigation**: Check `Path.exists()` before every `write_text()`, fail if file exists

2. **Risk**: Invalid TOML syntax in generated pyproject.toml
   - **Mitigation**: Use `toml` library to generate, validate immediately after creation

3. **Risk**: Directory structure doesn't match spec
   - **Mitigation**: Use JSON schema validation from `contracts/directory-structure.json`

4. **Risk**: Packages not installable after setup
   - **Mitigation**: Include integration test that creates venv and runs `pip install -e` for all packages

### Success Metrics

All 8 success criteria from spec must pass:

- **SC-001**: Two venvs can be created and both services installed ✓
- **SC-002**: All 4 packages install with `pip install -e` ✓
- **SC-003**: Cross-package imports work (services import shared libs) ✓
- **SC-004**: Linting and formatting commands work ✓
- **SC-005**: README.md files exist with setup instructions ✓
- **SC-006**: Structure matches architectural spec 100% ✓
- **SC-007**: Git ignores venvs and build artifacts ✓
- **SC-008**: Services isolated (switching venvs works) ✓

---

## Agent Context Update

After Phase 1 completion, run:

```bash
.specify/scripts/bash/update-agent-context.sh claude
```

This will update the agent-specific context file with:
- New directory structure knowledge
- Python 3.10.x monorepo patterns
- Package dependency relationships
- Development workflow commands (from Makefile)
