# Feature Specification: Python Monorepo Directory Setup

**Feature Branch**: `001-python-monorepo-setup`
**Created**: 2025-12-25
**Status**: Draft
**Input**: User description: "Setup the python monorepo layout for 2 services development"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Core Directory Structure (Priority: P1)

As a developer, I need the base monorepo directory structure created so that I can start developing both services independently with proper isolation.

**Why this priority**: This is the foundation - nothing else can be built without the directory structure in place. It's the minimum viable setup.

**Independent Test**: Verify directory structure matches architectural specification
- **Unit test**: `test_directory_structure_exists()` validates all required directories are present
- **Contract test**: `test_directory_layout_matches_spec()` validates structure against specs/001-1-python-monorepo-setup.md
- **Integration test**: `test_services_can_import_shared_libs()` validates Python import paths work correctly
- **Success criteria**: All directories exist, Python can resolve imports, structure matches spec 100%

**Acceptance Scenarios**:

1. **Given** an empty repository root, **When** the setup is executed, **Then** all directories from the architecture spec are created
2. **Given** the directory structure exists, **When** a developer navigates to apps/stream-infrastructure/, **Then** they find pyproject.toml, src/, and tests/ directories
3. **Given** the directory structure exists, **When** a developer navigates to apps/sts-service/, **Then** they find pyproject.toml, src/, and tests/ directories
4. **Given** the directory structure exists, **When** a developer navigates to libs/common/, **Then** they find pyproject.toml, src/dubbing_common/, and tests/
5. **Given** the directory structure exists, **When** a developer navigates to libs/contracts/, **Then** they find pyproject.toml, src/dubbing_contracts/, and tests/

---

### User Story 2 - Initialize Python Package Metadata (Priority: P2)

As a developer, I need all pyproject.toml files created with correct package names and basic metadata so that I can install packages in development mode.

**Why this priority**: Without package metadata, developers cannot install or import the packages. This enables local development setup.

**Independent Test**: Verify package metadata is valid and installable
- **Unit test**: `test_pyproject_toml_syntax_valid()` validates TOML syntax for all pyproject.toml files
- **Contract test**: `test_package_names_match_spec()` validates package names match architectural spec
- **Integration test**: `test_packages_install_in_editable_mode()` validates pip install -e works for all packages
- **Success criteria**: All packages install successfully, no import errors, metadata matches spec

**Acceptance Scenarios**:

1. **Given** pyproject.toml exists in apps/stream-infrastructure/, **When** developer runs pip install -e ., **Then** stream_infrastructure package is installed
2. **Given** pyproject.toml exists in apps/sts-service/, **When** developer runs pip install -e ., **Then** sts_service package is installed
3. **Given** pyproject.toml exists in libs/common/, **When** developer runs pip install -e ., **Then** dubbing_common package is installed
4. **Given** pyproject.toml exists in libs/contracts/, **When** developer runs pip install -e ., **Then** dubbing_contracts package is installed
5. **Given** all packages are installed, **When** developer imports dubbing_common in Python, **Then** import succeeds without errors

---

### User Story 3 - Create Python Package Namespaces (Priority: P3)

As a developer, I need __init__.py files in all package directories so that Python recognizes them as importable modules.

**Why this priority**: This completes the basic Python package setup, making the structure fully functional for development.

**Independent Test**: Verify Python package imports work correctly
- **Unit test**: `test_init_files_exist()` validates __init__.py exists in all package directories
- **Contract test**: `test_package_imports_succeed()` validates all packages can be imported
- **Integration test**: `test_cross_package_imports_work()` validates services can import shared libraries
- **Success criteria**: All imports succeed, no ModuleNotFoundError exceptions

**Acceptance Scenarios**:

1. **Given** __init__.py exists in src/stream_infrastructure/, **When** developer imports stream_infrastructure, **Then** import succeeds
2. **Given** __init__.py exists in src/sts_service/, **When** developer imports sts_service, **Then** import succeeds
3. **Given** __init__.py exists in src/dubbing_common/, **When** developer imports dubbing_common, **Then** import succeeds
4. **Given** __init__.py exists in src/dubbing_contracts/, **When** developer imports dubbing_contracts, **Then** import succeeds
5. **Given** all packages are set up, **When** stream_infrastructure imports dubbing_common, **Then** import succeeds

---

### User Story 4 - Create Development Tooling Configuration (Priority: P4)

As a developer, I need root-level configuration files for linting and type checking so that code quality is consistent across both services.

**Why this priority**: This ensures code quality from day one but doesn't block initial development work.

**Independent Test**: Verify tooling configuration is valid and executable
- **Unit test**: `test_config_files_syntax_valid()` validates pyproject.toml, .gitignore syntax
- **Contract test**: `test_mypy_config_matches_spec()` validates mypy strict mode is enabled
- **Integration test**: `test_linting_runs_successfully()` validates ruff runs without configuration errors
- **Success criteria**: All tools run successfully, configuration matches spec requirements

**Acceptance Scenarios**:

1. **Given** root pyproject.toml exists, **When** developer runs ruff check, **Then** tool executes without configuration errors
2. **Given** root pyproject.toml exists, **When** developer runs mypy --strict, **Then** tool executes with strict mode enabled
3. **Given** .gitignore exists, **When** developer creates .venv-stream/, **Then** virtual environment is not tracked by git
4. **Given** Makefile exists, **When** developer runs make lint, **Then** linting executes on all packages
5. **Given** Makefile exists, **When** developer runs make format, **Then** code formatting is applied consistently

---

### User Story 5 - Create Documentation Files (Priority: P5)

As a developer, I need README.md files in each service and shared library so that setup instructions are discoverable.

**Why this priority**: Documentation improves developer experience but doesn't block initial implementation.

**Independent Test**: Verify documentation exists and is complete
- **Unit test**: `test_readme_files_exist()` validates README.md exists in all expected locations
- **Contract test**: `test_readme_contains_setup_instructions()` validates each README has setup steps
- **Integration test**: `test_documentation_links_valid()` validates cross-references between docs work
- **Success criteria**: All READMEs exist, contain setup instructions, internal links work

**Acceptance Scenarios**:

1. **Given** README.md exists in apps/stream-infrastructure/, **When** developer opens it, **Then** they find local setup instructions
2. **Given** README.md exists in apps/sts-service/, **When** developer opens it, **Then** they find local setup instructions
3. **Given** README.md exists in libs/common/, **When** developer opens it, **Then** they find library usage documentation
4. **Given** README.md exists in repository root, **When** developer opens it, **Then** they find overview and getting started guide
5. **Given** Makefile exists, **When** developer runs make help, **Then** they see list of available commands

---

### Edge Cases

- What happens when a developer tries to import a service from another service (should fail)?
- What happens when pyproject.toml has invalid syntax (should fail pip install)?
- What happens when __init__.py is missing in a package directory (should fail imports)?
- What happens when virtual environments have naming conflicts (should be isolated by different names)?
- What happens when developer tries to install both services in the same virtual environment (should install but may have dependency conflicts)?
- What happens when directory permissions are restricted (should fail with clear error message)?
- What happens when Python version is not 3.10.x (should fail with version requirement error)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create all directories specified in specs/001-1-python-monorepo-setup.md section 4 (Repository Layout)
- **FR-002**: System MUST create pyproject.toml for each service (apps/stream-infrastructure/, apps/sts-service/) with correct package name and Python version constraint (>=3.10,<3.11)
- **FR-003**: System MUST create pyproject.toml for each shared library (libs/common/, libs/contracts/) with minimal dependencies
- **FR-004**: System MUST create __init__.py files in all Python package source directories to enable imports
- **FR-005**: System MUST create test directories (unit/, integration/) under each service's tests/ folder
- **FR-006**: System MUST create root-level pyproject.toml with mypy and ruff configuration matching spec requirements
- **FR-007**: System MUST create .gitignore to exclude virtual environments (.venv-stream, .venv-sts), __pycache__, and build artifacts
- **FR-008**: System MUST create Makefile with targets: setup-stream, setup-sts, test-all, lint, format
- **FR-009**: System MUST create README.md in repository root with overview and setup instructions
- **FR-010**: System MUST create README.md in each service directory with service-specific setup instructions
- **FR-011**: System MUST ensure all created files use UTF-8 encoding
- **FR-012**: System MUST preserve existing files and directories (do not overwrite)
- **FR-013**: System MUST create deploy/ directory with subdirectories for each service (stream-infrastructure/, sts-service/)
- **FR-014**: System MUST create tests/e2e/ directory for end-to-end integration tests
- **FR-015**: System MUST ensure all package names follow Python naming conventions (lowercase with underscores)

### Key Entities

- **Service Package**: A deployable Python application (stream-infrastructure, sts-service) with its own dependency tree, test suite, and deployment configuration
- **Shared Library**: An internal Python package (common, contracts) providing shared utilities and data structures reusable across services
- **Virtual Environment**: An isolated Python environment per service containing service-specific dependencies
- **Project Configuration**: Metadata files (pyproject.toml) defining package identity, dependencies, and build requirements
- **Development Tools**: Linters, formatters, and type checkers (ruff, mypy) ensuring code quality standards

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can create two separate virtual environments and install both services without manual directory creation (full directory structure exists)
- **SC-002**: Developers can run pip install -e on all four packages (2 services + 2 libraries) without errors (all pyproject.toml files are valid)
- **SC-003**: Developers can import dubbing_common and dubbing_contracts from both service codebases without errors (Python package structure is correct)
- **SC-004**: Developers can run make lint and make format commands successfully from repository root (tooling configuration is complete)
- **SC-005**: Developers can find setup instructions by opening README.md files in any service directory (documentation is complete)
- **SC-006**: Repository structure matches specs/001-1-python-monorepo-setup.md section 4 with 100% accuracy (all required directories and files exist)
- **SC-007**: Git status shows only necessary files tracked, with virtual environments and build artifacts properly ignored (gitignore is correct)
- **SC-008**: Developers can switch between working on different services by activating different virtual environments without conflicts (service isolation works correctly)
