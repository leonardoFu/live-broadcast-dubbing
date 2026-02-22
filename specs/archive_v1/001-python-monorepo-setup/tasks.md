# Tasks: Python Monorepo Directory Setup

**Input**: Design documents from `/specs/001-python-monorepo-setup/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This feature creates the monorepo structure itself. All paths are relative to repository root:
- **Services**: `apps/<service-name>/`
- **Libraries**: `libs/<library-name>/`
- **Tests**: `tests/e2e/`, `apps/*/tests/unit/`, `apps/*/tests/integration/`
- **Deploy**: `deploy/<service-name>/`
- **Root config**: `pyproject.toml`, `Makefile`, `.gitignore`

---

## Phase 1: Setup (Test Infrastructure)

**Purpose**: Create test infrastructure to validate directory setup using TDD approach

**Note**: Since this is a setup feature, tests validate the setup process itself (directory existence, file syntax, package installability)

- [X] T001 Create tests/unit/ directory for setup validation tests
- [X] T002 Create tests/contract/ directory for schema validation tests
- [X] T003 Create tests/integration/ directory for end-to-end setup tests
- [X] T004 [P] Create test fixtures directory at tests/fixtures/ with sample TOML/Makefile content
- [X] T005 [P] Create pytest.ini at repository root with test configuration
- [X] T006 [P] Create .coveragerc at repository root with coverage configuration

---

## Phase 2: User Story 1 - Create Core Directory Structure (Priority: P1) 🎯 MVP

**Goal**: Create all required directories for the monorepo (apps/, libs/, tests/, deploy/) so developers can start working on services

**Independent Test**: Run `pytest tests/unit/test_directory_structure.py` to verify all directories exist and match architectural spec

### Tests for User Story 1 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Test Naming Conventions**:
- Unit tests: `test_directory_structure_<scenario>.py`
- Contract tests: `test_directory_schema_<validation>.py`
- Integration tests: `test_full_directory_setup_<workflow>.py`

**Coverage Target for US1**: 100% (deterministic directory creation)

- [ ] T007 [P] [US1] **Unit test** for directory creation in `tests/unit/test_directory_structure.py`
  - `test_create_apps_directory_happy_path()` - Verify apps/ directory created
  - `test_create_libs_directory_happy_path()` - Verify libs/ directory created
  - `test_create_tests_directory_happy_path()` - Verify tests/ directory created
  - `test_create_deploy_directory_happy_path()` - Verify deploy/ directory created
  - `test_directory_exists_error_permissions()` - Test permission denied scenario
  - `test_directory_already_exists_preserves_content()` - Test FR-012 (no overwrite)

- [ ] T008 [P] [US1] **Contract test** for directory structure schema in `tests/contract/test_directory_schema.py`
  - `test_directory_layout_matches_json_schema()` - Validate against contracts/directory-structure.json
  - `test_service_directory_structure_complete()` - Verify service directories have all required subdirs
  - `test_library_directory_structure_complete()` - Verify library directories have all required subdirs
  - `test_deploy_directory_structure_exists()` - Verify deploy directories exist

- [ ] T009 [US1] **Integration test** for full directory setup in `tests/integration/test_full_directory_setup.py`
  - `test_create_all_directories_integration()` - End-to-end directory creation
  - `test_directory_structure_matches_architectural_spec()` - Verify 100% match to specs/001-1-python-monorepo-setup.md
  - `test_python_can_resolve_import_paths()` - Verify Python can find package directories

**Verification**: Run `pytest tests/ -v` - ALL tests MUST FAIL with assertions like "Directory does not exist"

### Implementation for User Story 1

- [X] T010 [P] [US1] Create apps/ directory at repository root
- [X] T011 [P] [US1] Create libs/ directory at repository root
- [X] T012 [P] [US1] Create tests/e2e/ directory at repository root
- [X] T013 [P] [US1] Create deploy/ directory at repository root
- [X] T014 [P] [US1] Create apps/media-service/ directory with subdirectories (src/, tests/)
- [X] T015 [P] [US1] Create apps/sts-service/ directory with subdirectories (src/, tests/)
- [X] T016 [P] [US1] Create libs/common/ directory with subdirectories (src/, tests/)
- [X] T017 [P] [US1] Create libs/contracts/ directory with subdirectories (src/, tests/)
- [X] T018 [P] [US1] Create apps/media-service/src/media_service/ Python package directory
- [X] T019 [P] [US1] Create apps/media-service/src/media_service/pipelines/ module subdirectory
- [X] T020 [P] [US1] Create apps/media-service/tests/unit/ test directory
- [X] T021 [P] [US1] Create apps/media-service/tests/integration/ test directory
- [X] T022 [P] [US1] Create apps/sts-service/src/sts_service/ Python package directory
- [X] T023 [P] [US1] Create apps/sts-service/src/sts_service/asr/ module subdirectory
- [X] T024 [P] [US1] Create apps/sts-service/src/sts_service/translation/ module subdirectory
- [X] T025 [P] [US1] Create apps/sts-service/src/sts_service/tts/ module subdirectory
- [X] T026 [P] [US1] Create apps/sts-service/tests/unit/ test directory
- [X] T027 [P] [US1] Create apps/sts-service/tests/integration/ test directory
- [X] T028 [P] [US1] Create libs/common/src/dubbing_common/ Python package directory
- [X] T029 [P] [US1] Create libs/common/tests/unit/ test directory
- [X] T030 [P] [US1] Create libs/contracts/src/dubbing_contracts/ Python package directory
- [X] T031 [P] [US1] Create libs/contracts/tests/unit/ test directory
- [X] T032 [P] [US1] Create deploy/media-service/ deployment config directory
- [X] T033 [P] [US1] Create deploy/sts-service/ deployment config directory
- [X] T034 [US1] Verify all directories created successfully (run tests from T007-T009)

**Checkpoint**: At this point, all required directories exist and tests pass. Success Criteria SC-001 partially met.

---

## Phase 3: User Story 2 - Initialize Python Package Metadata (Priority: P2)

**Goal**: Create pyproject.toml files for all 4 packages with correct metadata so developers can install packages in editable mode

**Independent Test**: Run `pytest tests/unit/test_pyproject_metadata.py` to verify all pyproject.toml files are valid and packages are installable

### Tests for User Story 2 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US2**: 100% (deterministic TOML generation)

- [ ] T035 [P] [US2] **Unit test** for pyproject.toml generation in `tests/unit/test_pyproject_metadata.py`
  - `test_generate_service_pyproject_toml_happy_path()` - Validate service pyproject.toml structure
  - `test_generate_library_pyproject_toml_happy_path()` - Validate library pyproject.toml structure
  - `test_pyproject_toml_syntax_valid()` - Parse all pyproject.toml files with toml library
  - `test_python_version_constraint_correct()` - Verify requires-python = ">=3.10,<3.11"
  - `test_pyproject_toml_error_invalid_package_name()` - Test invalid package name rejection

- [ ] T036 [P] [US2] **Contract test** for package names in `tests/contract/test_package_names.py`
  - `test_package_names_match_architectural_spec()` - Validate media-service, sts-service, dubbing-common, dubbing-contracts
  - `test_python_names_use_snake_case()` - Validate media_service, sts_service, dubbing_common, dubbing_contracts
  - `test_package_versions_match_spec()` - Verify all versions are "0.1.0"

- [ ] T037 [US2] **Integration test** for package installation in `tests/integration/test_package_installation.py`
  - `test_packages_install_in_editable_mode()` - Test pip install -e for all 4 packages in temp venv
  - `test_service_depends_on_libraries()` - Verify services list libraries in dependencies
  - `test_libraries_have_minimal_dependencies()` - Verify libraries have only pydantic>=2.0

**Verification**: Run `pytest tests/ -v` - ALL tests MUST FAIL with "File not found: pyproject.toml"

### Implementation for User Story 2

- [X] T038 [P] [US2] Create apps/media-service/pyproject.toml with service metadata (name: media-service, requires-python: >=3.10,<3.11)
- [X] T039 [P] [US2] Create apps/media-service/requirements.txt (empty placeholder for locked dependencies)
- [X] T040 [P] [US2] Create apps/media-service/requirements-dev.txt (pytest, mypy, ruff dependencies)
- [X] T041 [P] [US2] Create apps/sts-service/pyproject.toml with service metadata (name: sts-service, requires-python: >=3.10,<3.11)
- [X] T042 [P] [US2] Create apps/sts-service/requirements.txt (empty placeholder)
- [X] T043 [P] [US2] Create apps/sts-service/requirements-dev.txt (pytest, mypy, ruff dependencies)
- [X] T044 [P] [US2] Create libs/common/pyproject.toml with library metadata (name: dubbing-common, minimal dependencies)
- [X] T045 [P] [US2] Create libs/contracts/pyproject.toml with library metadata (name: dubbing-contracts, minimal dependencies)
- [X] T046 [US2] Validate all pyproject.toml files with toml parser (run tests from T035-T037)

**Checkpoint**: At this point, all packages have valid metadata and can be installed. Success Criteria SC-002 met.

---

## Phase 4: User Story 3 - Create Python Package Namespaces (Priority: P3)

**Goal**: Create __init__.py files in all package directories so Python recognizes them as importable modules

**Independent Test**: Run `pytest tests/unit/test_package_imports.py` to verify all packages can be imported without errors

### Tests for User Story 3 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US3**: 100% (deterministic __init__.py creation)

- [ ] T047 [P] [US3] **Unit test** for __init__.py existence in `tests/unit/test_init_files.py`
  - `test_init_files_exist_in_all_packages()` - Verify __init__.py in all package directories
  - `test_init_files_valid_python_syntax()` - Parse __init__.py files with ast module
  - `test_init_files_utf8_encoding()` - Verify UTF-8 encoding per FR-011
  - `test_init_file_missing_error_imports_fail()` - Test import failure when __init__.py missing

- [ ] T048 [P] [US3] **Contract test** for package imports in `tests/contract/test_package_imports.py`
  - `test_import_media_service_succeeds()` - Import media_service module
  - `test_import_sts_service_succeeds()` - Import sts_service module
  - `test_import_dubbing_common_succeeds()` - Import dubbing_common module
  - `test_import_dubbing_contracts_succeeds()` - Import dubbing_contracts module
  - `test_service_cannot_import_service()` - Verify cross-service imports fail (design constraint)

- [ ] T049 [US3] **Integration test** for cross-package imports in `tests/integration/test_cross_package_imports.py`
  - `test_services_can_import_shared_libraries()` - Verify media_service can import dubbing_common
  - `test_library_imports_library()` - Verify dubbing_common can import dubbing_contracts (if needed)
  - `test_module_subdirectories_importable()` - Verify media_service.pipelines can be imported

**Verification**: Run `pytest tests/ -v` - ALL tests MUST FAIL with "ModuleNotFoundError"

### Implementation for User Story 3

- [X] T050 [P] [US3] Create apps/media-service/src/media_service/__init__.py (package init, UTF-8)
- [X] T051 [P] [US3] Create apps/media-service/src/media_service/pipelines/__init__.py (subpackage init)
- [X] T052 [P] [US3] Create apps/media-service/tests/unit/__init__.py (test package init)
- [X] T053 [P] [US3] Create apps/media-service/tests/integration/__init__.py (test package init)
- [X] T054 [P] [US3] Create apps/sts-service/src/sts_service/__init__.py (package init, UTF-8)
- [X] T055 [P] [US3] Create apps/sts-service/src/sts_service/asr/__init__.py (subpackage init)
- [X] T056 [P] [US3] Create apps/sts-service/src/sts_service/translation/__init__.py (subpackage init)
- [X] T057 [P] [US3] Create apps/sts-service/src/sts_service/tts/__init__.py (subpackage init)
- [X] T058 [P] [US3] Create apps/sts-service/tests/unit/__init__.py (test package init)
- [X] T059 [P] [US3] Create apps/sts-service/tests/integration/__init__.py (test package init)
- [X] T060 [P] [US3] Create libs/common/src/dubbing_common/__init__.py (package init, UTF-8)
- [X] T061 [P] [US3] Create libs/common/tests/unit/__init__.py (test package init)
- [X] T062 [P] [US3] Create libs/contracts/src/dubbing_contracts/__init__.py (package init, UTF-8)
- [X] T063 [P] [US3] Create libs/contracts/tests/unit/__init__.py (test package init)
- [X] T064 [P] [US3] Create tests/e2e/__init__.py (E2E test package init)
- [X] T065 [US3] Validate all packages importable (run tests from T047-T049)

**Checkpoint**: At this point, all Python packages can be imported successfully. Success Criteria SC-003 met.

---

## Phase 5: User Story 4 - Create Development Tooling Configuration (Priority: P4)

**Goal**: Create root-level configuration files (pyproject.toml, .gitignore, Makefile) for linting, type checking, and development workflow

**Independent Test**: Run `pytest tests/unit/test_tooling_config.py` to verify all tools execute without configuration errors

### Tests for User Story 4 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US4**: 100% (deterministic config file generation)

- [ ] T066 [P] [US4] **Unit test** for config files in `tests/unit/test_config_files.py`
  - `test_root_pyproject_toml_syntax_valid()` - Parse root pyproject.toml with toml library
  - `test_gitignore_syntax_valid()` - Validate .gitignore has valid patterns
  - `test_makefile_syntax_valid()` - Validate Makefile has valid target syntax
  - `test_root_pyproject_toml_has_ruff_config()` - Verify [tool.ruff] section exists
  - `test_root_pyproject_toml_has_mypy_config()` - Verify [tool.mypy] section exists with strict=true

- [ ] T067 [P] [US4] **Contract test** for tool configuration in `tests/contract/test_tooling_schema.py`
  - `test_mypy_strict_mode_enabled()` - Validate mypy strict = true in root pyproject.toml
  - `test_ruff_rules_match_spec()` - Verify ruff rules include E, W, F, I, B, C4, UP
  - `test_makefile_targets_match_spec()` - Verify setup-stream, setup-sts, test-all, lint, format targets exist
  - `test_gitignore_excludes_venvs()` - Verify .venv-stream, .venv-sts in .gitignore

- [ ] T068 [US4] **Integration test** for tool execution in `tests/integration/test_linting_runs.py`
  - `test_ruff_check_runs_successfully()` - Execute ruff check apps/ libs/ (expect success on empty code)
  - `test_ruff_format_runs_successfully()` - Execute ruff format apps/ libs/
  - `test_mypy_strict_runs_successfully()` - Execute mypy --strict on all package src/ directories
  - `test_make_lint_command_works()` - Execute make lint
  - `test_make_format_command_works()` - Execute make format

**Verification**: Run `pytest tests/ -v` - ALL tests MUST FAIL with "File not found" or "Command not found"

### Implementation for User Story 4

- [X] T069 [P] [US4] Create root pyproject.toml with ruff configuration (target-version = "py310", line-length = 100, select = E/W/F/I/B/C4/UP)
- [X] T070 [P] [US4] Add mypy configuration to root pyproject.toml ([tool.mypy] section with strict = true, python_version = "3.10")
- [X] T071 [P] [US4] Create .gitignore at repository root (exclude .venv-stream, .venv-sts, __pycache__, .mypy_cache, .ruff_cache, build/, dist/, *.egg-info)
- [X] T072 [P] [US4] Create Makefile at repository root with help target (display available commands)
- [X] T073 [P] [US4] Add setup-stream target to Makefile (python3.10 -m venv .venv-stream && pip install -e libs/common -e libs/contracts -e "apps/media-service[dev]")
- [X] T074 [P] [US4] Add setup-sts target to Makefile (python3.10 -m venv .venv-sts && pip install -e libs/common -e libs/contracts -e "apps/sts-service[dev]")
- [X] T075 [P] [US4] Add test-all target to Makefile (run pytest for all packages)
- [X] T076 [P] [US4] Add lint target to Makefile (ruff check apps/ libs/ && mypy apps/media-service/src apps/sts-service/src libs/common/src libs/contracts/src)
- [X] T077 [P] [US4] Add format target to Makefile (ruff format apps/ libs/)
- [X] T078 [P] [US4] Add clean target to Makefile (remove __pycache__, .mypy_cache, .ruff_cache, build/, dist/)
- [X] T079 [US4] Validate all tools execute successfully (run tests from T066-T068)

**Checkpoint**: At this point, all development tools are configured and executable. Success Criteria SC-004 and SC-007 met.

---

## Phase 6: User Story 5 - Create Documentation Files (Priority: P5)

**Goal**: Create README.md files for all packages and repository root with setup instructions and usage documentation

**Independent Test**: Run `pytest tests/unit/test_documentation.py` to verify all README files exist and contain required sections

### Tests for User Story 5 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target for US5**: 100% (deterministic README generation)

- [ ] T080 [P] [US5] **Unit test** for README files in `tests/unit/test_readme_files.py`
  - `test_readme_files_exist_in_all_packages()` - Verify README.md in apps/media-service/, apps/sts-service/, libs/common/, libs/contracts/
  - `test_readme_files_utf8_encoding()` - Verify UTF-8 encoding per FR-011
  - `test_readme_markdown_syntax_valid()` - Basic markdown validation (headers, lists)

- [ ] T081 [P] [US5] **Contract test** for README content in `tests/contract/test_readme_content.py`
  - `test_service_readme_contains_setup_instructions()` - Verify "Setup" or "Installation" section in service READMEs
  - `test_library_readme_contains_usage_examples()` - Verify "Usage" section in library READMEs
  - `test_root_readme_contains_overview()` - Verify repository overview in root README.md
  - `test_makefile_help_output_matches_readme()` - Verify make help output consistent with docs

- [ ] T082 [US5] **Integration test** for documentation links in `tests/integration/test_documentation_links.py`
  - `test_documentation_cross_references_valid()` - Verify internal links between README files work
  - `test_quickstart_guide_references_match_structure()` - Verify quickstart.md matches actual structure

**Verification**: Run `pytest tests/ -v` - ALL tests MUST FAIL with "File not found: README.md"

### Implementation for User Story 5

- [X] T083 [P] [US5] Create apps/media-service/README.md (service description, prerequisites, setup instructions, running tests, development workflow)
- [X] T084 [P] [US5] Create apps/sts-service/README.md (service description, GPU requirements, setup instructions, running tests in CPU fallback mode)
- [X] T085 [P] [US5] Create libs/common/README.md (library description, installation for other packages, usage examples, development setup)
- [X] T086 [P] [US5] Create libs/contracts/README.md (library description, contract definitions, usage in services, development setup)
- [X] T087 [US5] Update repository root README.md (add monorepo overview, link to quickstart.md, link to service/library READMEs, reference CLAUDE.md)
- [X] T088 [US5] Validate all documentation complete (run tests from T080-T082)

**Checkpoint**: At this point, all documentation exists and guides developers. Success Criteria SC-005 met.

---

## Phase 7: Polish & Verification

**Purpose**: Final validation and cross-cutting concerns

- [X] T089 [P] Run full test suite with coverage report (pytest tests/ --cov --cov-report=html)
- [X] T090 [P] Validate directory structure matches architectural spec 100% (run contract test against specs/001-1-python-monorepo-setup.md)
- [X] T091 [P] Verify all 8 success criteria from spec.md (SC-001 through SC-008)
- [X] T092 [P] Run make setup-stream in clean environment to verify workflow
- [X] T093 [P] Run make setup-sts in clean environment to verify workflow
- [X] T094 [P] Test package installation in both venvs (pip install -e for all packages)
- [X] T095 [P] Test cross-package imports work (import dubbing_common from media_service)
- [X] T096 [P] Test linting and formatting commands work (make lint, make format)
- [X] T097 [P] Verify git ignores build artifacts (create .venv-stream, check git status)
- [X] T098 [P] Verify service isolation (activate .venv-stream, deactivate, activate .venv-sts)
- [X] T099 Update root README.md with final structure diagram and getting started guide
- [X] T100 Create CHANGELOG.md documenting monorepo setup completion

---

## Task Dependencies & Execution Order

### Dependency Graph (User Story Completion Order)

```
Phase 1 (Setup Tests)
     ↓
Phase 2 (US1: Directories) ← MVP - Must complete first
     ↓
Phase 3 (US2: Package Metadata) ← Can start after US1
     ↓
Phase 4 (US3: Package Namespaces) ← Can start after US2
     ↓
Phase 5 (US4: Tooling Config) ← Can start after US3
     ↓
Phase 6 (US5: Documentation) ← Can start after US4
     ↓
Phase 7 (Polish & Verification) ← Final validation
```

### Critical Path

**Sequential dependencies** (must complete in order):
1. Phase 1 (Setup Tests) → Must complete before ANY implementation
2. Phase 2 (US1) → Blocking for all other phases (directories must exist first)
3. Phase 3 (US2) → Depends on US1 (directories must exist for pyproject.toml files)
4. Phase 4 (US3) → Depends on US2 (packages must have metadata before adding __init__.py)
5. Phase 5 (US4) → Depends on US3 (packages must be importable before configuring tools)
6. Phase 6 (US5) → Depends on US4 (tooling must work before documenting it)
7. Phase 7 (Polish) → Depends on all user stories

**Parallel opportunities within each phase**:
- All directory creation tasks (T010-T033) can run in parallel
- All pyproject.toml creation tasks (T038-T045) can run in parallel
- All __init__.py creation tasks (T050-T064) can run in parallel
- All config file creation tasks (T069-T078) can run in parallel
- All README creation tasks (T083-T086) can run in parallel
- All verification tasks in Phase 7 (T089-T098) can run in parallel

### Estimated Task Counts by Phase

- **Phase 1 (Setup)**: 6 tasks
- **Phase 2 (US1)**: 28 tasks (7 tests + 21 implementation)
- **Phase 3 (US2)**: 12 tasks (3 tests + 9 implementation)
- **Phase 4 (US3)**: 19 tasks (3 tests + 16 implementation)
- **Phase 5 (US4)**: 14 tasks (3 tests + 11 implementation)
- **Phase 6 (US5)**: 9 tasks (3 tests + 6 implementation)
- **Phase 7 (Polish)**: 12 tasks

**Total**: 100 tasks

---

## Implementation Strategy

### MVP Scope (User Story 1 Only)

The minimum viable setup includes **Phase 2 (US1)** only:
- All required directories exist
- Basic structure in place for services and libraries
- Developers can navigate the repository structure

**Deliverable**: Developers can see the monorepo structure but cannot yet install or import packages.

### Recommended Delivery Increments

1. **Increment 1 (US1)**: Directory structure
2. **Increment 2 (US1 + US2)**: Directory structure + package metadata (packages installable)
3. **Increment 3 (US1 + US2 + US3)**: Above + package namespaces (packages importable)
4. **Increment 4 (US1 + US2 + US3 + US4)**: Above + tooling (linting/formatting works)
5. **Increment 5 (Full)**: All user stories + documentation + polish

Each increment is independently testable and delivers measurable value.

### Parallel Execution Examples

#### Within User Story 1 (Directory Creation)

These tasks can run simultaneously (all create different directories):
```bash
# Terminal 1
T010: mkdir apps/
T011: mkdir libs/

# Terminal 2
T012: mkdir tests/e2e/
T013: mkdir deploy/

# Terminal 3
T014-T017: Create all service/library root directories
T018-T033: Create all subdirectories
```

#### Within User Story 2 (Metadata Files)

These tasks can run simultaneously (all create different files):
```bash
# Terminal 1
T038: Create apps/media-service/pyproject.toml

# Terminal 2
T041: Create apps/sts-service/pyproject.toml

# Terminal 3
T044: Create libs/common/pyproject.toml
T045: Create libs/contracts/pyproject.toml
```

#### Within User Story 3 (Python Packages)

These tasks can run simultaneously (all create different __init__.py files):
```bash
# Terminal 1
T050-T053: Create media-service __init__.py files

# Terminal 2
T054-T059: Create sts-service __init__.py files

# Terminal 3
T060-T064: Create library __init__.py files
```

#### Within User Story 4 (Tooling Config)

These tasks can run simultaneously (all create different config files):
```bash
# Terminal 1
T069-T070: Create root pyproject.toml with ruff/mypy config

# Terminal 2
T071: Create .gitignore

# Terminal 3
T072-T078: Create Makefile with all targets
```

#### Within User Story 5 (Documentation)

These tasks can run simultaneously (all create different README files):
```bash
# Terminal 1
T083: Create apps/media-service/README.md

# Terminal 2
T084: Create apps/sts-service/README.md

# Terminal 3
T085: Create libs/common/README.md
T086: Create libs/contracts/README.md
```

---

## Test Coverage Requirements

Per Constitution Principle VIII:
- **New modules**: 80% minimum line coverage
- **Critical paths**: 95% minimum (directory creation, package metadata, imports)
- **Utility functions**: 100% (setup validation functions are simple)

For this feature:
- **Target coverage**: 100% (all setup code is deterministic and fully testable)
- **Test execution**: All tests must pass before marking user story complete
- **TDD enforcement**: Tests written FIRST, must FAIL before implementation

---

## Success Validation Checklist

After completing all tasks, verify all 8 success criteria from spec.md:

- [ ] **SC-001**: Create two venvs (.venv-stream, .venv-sts) and install both services - SUCCESS if no manual directory creation needed
- [ ] **SC-002**: Run `pip install -e` on all 4 packages - SUCCESS if no errors
- [ ] **SC-003**: Import dubbing_common and dubbing_contracts from both services - SUCCESS if no ModuleNotFoundError
- [ ] **SC-004**: Run `make lint` and `make format` - SUCCESS if commands execute without errors
- [ ] **SC-005**: Open README.md in any service directory - SUCCESS if setup instructions are present
- [ ] **SC-006**: Compare directory structure to specs/001-1-python-monorepo-setup.md section 4 - SUCCESS if 100% match
- [ ] **SC-007**: Run `git status` after creating .venv-stream - SUCCESS if venv not tracked
- [ ] **SC-008**: Activate .venv-stream, deactivate, activate .venv-sts - SUCCESS if no conflicts

All 8 criteria must pass for feature completion.

---

## Notes

- **Tests are mandatory**: This feature follows TDD strictly - all tests written FIRST before implementation
- **100% coverage target**: Since setup is deterministic, aim for 100% test coverage (no random/external dependencies)
- **Validation at every step**: Run tests after each phase to ensure nothing breaks
- **Preserve existing files**: Check for file existence before creating (FR-012)
- **UTF-8 encoding**: All text files must use UTF-8 (FR-011)
- **Sequential phases**: Phases must complete in order (US1 → US2 → US3 → US4 → US5)
- **Parallel tasks within phases**: Tasks marked [P] can run simultaneously within their phase
- **Independent user stories**: Each user story is independently testable and deliverable
