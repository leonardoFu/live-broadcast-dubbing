# TDD Quick Start Guide

This project enforces **test-first development** (Constitution Principle VIII). Tests MUST be written BEFORE implementation.

## Quick Reference

```bash
# 1. Write failing tests first
vim apps/sts-service/tests/unit/test_fragment.py

# 2. Run tests - verify they FAIL
pytest apps/sts-service/tests/unit/test_fragment.py

# 3. Implement code to make tests pass
vim apps/sts-service/src/fragment.py

# 4. Run tests - verify they PASS
pytest apps/sts-service/tests/unit/test_fragment.py

# 5. Check coverage
make test-coverage

# 6. Commit (pre-commit hooks will validate)
git add apps/sts-service/tests/unit/test_fragment.py
git add apps/sts-service/src/fragment.py
git commit -m "feat: add fragment processing"
```

## Test Organization

```
apps/<module>/
└── tests/
    ├── conftest.py          # Module fixtures
    ├── unit/                # Fast, isolated tests
    │   └── test_*.py
    ├── contract/            # API/event schema tests
    │   └── test_*.py
    └── integration/         # Service integration tests
        └── test_*.py

tests/                       # Cross-module integration
├── integration/
└── e2e/
```

## Test Naming Conventions

```python
# Happy path
def test_chunk_audio_happy_path():
    """Test audio chunking with valid 1s PCM input."""
    pass

# Error handling
def test_chunk_audio_error_invalid_sample_rate():
    """Test audio chunking raises ValueError for sample_rate < 8000."""
    pass

# Edge cases
def test_chunk_audio_edge_zero_duration():
    """Test audio chunking returns empty list for zero-duration input."""
    pass
```

## Using Mock Fixtures

```python
from .specify.templates.test_fixtures.sts_events import mock_fragment_data_event

def test_process_fragment(sample_pcm_audio):
    """Test fragment processing with mock STS event."""
    fragment = mock_fragment_data_event(
        fragment_id="test-001",
        duration_ms=1000
    )
    result = process_fragment(fragment)
    assert result["status"] == "success"
```

## Coverage Requirements

- **New modules**: 80% minimum
- **Critical paths** (A/V sync, STS pipeline): 95% minimum
- **Utility functions**: 100% (no excuses)

Check coverage:
```bash
make test-coverage
open coverage/index.html  # View HTML report
```

## Pre-commit Hooks

Hooks automatically run on `git commit`:
1. Ruff (linting + formatting)
2. MyPy (type checking)
3. Pytest (unit + contract tests)
4. Test existence check

Install hooks:
```bash
make install-hooks
```

Skip hooks (NOT RECOMMENDED):
```bash
git commit --no-verify
```

## CI/CD Enforcement

GitHub Actions runs on every PR:
- All tests (unit, contract, integration)
- Coverage check (fails if <80%)
- Critical path coverage (fails if <95%)
- Test existence check

PRs cannot merge if CI fails.

## Troubleshooting

### "Tests must exist before implementation"
Write test file first, ensure it fails, then implement.

### "Coverage <80%"
Add more tests to cover untested code paths.

### "Pre-commit hook failed"
Fix the error (lint, type, test) before committing.

### "How to test GStreamer code?"
Mock GStreamer elements in unit tests. Use real pipeline with mock sources in integration tests.

## Example: Adding a New Feature

1. **Spec** → `/speckit.specify`
2. **Plan** → `/speckit.plan`
3. **Tasks** → `/speckit.tasks`
4. **Tests First** → Write failing tests
5. **Implement** → `/speckit.implement`
6. **Verify** → `make test-coverage`
7. **Commit** → Pre-commit hooks validate
8. **PR** → CI validates
9. **Merge** → Coverage maintained

## Exemptions

Only allowed with explicit justification in PR:
- Prototype/spike code (separate branch, never merged)
- Generated code (clearly marked)
- Vendor code (separate directory)

All other code MUST have tests.

## Common Make Targets

```bash
make test              # Run all tests (quick)
make test-unit         # Run unit tests only
make test-contract     # Run contract tests only
make test-integration  # Run integration tests only
make test-coverage     # Run tests with coverage report
make pre-implement     # Verify tests exist and fail before implementing
make install-hooks     # Install pre-commit hooks
```

## See Also

- [Constitution Principle VIII](.specify/memory/constitution.md#viii-test-first-development-non-negotiable) - TDD mandate
- [Test Examples](./test-examples/) - Example unit and contract tests
- [Test Fixtures](../.specify/templates/test-fixtures/) - Mock STS events

## Questions?

Refer to:
- Constitution Principle VIII for TDD requirements
- tasks-template.md for test organization standards
- plan-template.md for test strategy guidelines
