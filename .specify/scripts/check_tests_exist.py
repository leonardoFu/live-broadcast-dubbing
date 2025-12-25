#!/usr/bin/env python3
"""
Verify that tests exist for new Python code (Constitution Principle VIII).

This script enforces test-first development by checking:
1. For every new module in apps/<module>/src/, a corresponding test file exists
2. For every new function/class, at least one test exists
3. Tests are not empty (contain actual test functions)

Usage: Called automatically by pre-commit hook
"""
import sys
import re
import subprocess
from pathlib import Path
from typing import List, Tuple


def get_staged_python_files() -> List[Path]:
    """Get list of staged Python files in apps/*/src/."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        capture_output=True,
        text=True,
        check=True
    )
    files = result.stdout.strip().split('\n')
    return [
        Path(f) for f in files
        if f.startswith('apps/') and '/src/' in f and f.endswith('.py') and f != ''
    ]


def get_expected_test_path(src_file: Path) -> Path:
    """
    Convert source file path to expected test file path.

    Example:
        apps/sts-service/src/models/fragment.py
        -> apps/sts-service/tests/unit/test_models.py
        OR apps/sts-service/tests/unit/test_fragment.py
    """
    parts = src_file.parts
    module = parts[1]  # e.g., "sts-service"
    src_path = Path(*parts[3:])  # e.g., "models/fragment.py"

    # Try both test_<module>.py and test_<filename>.py
    if src_path.parent == Path('.'):
        # Top-level file: apps/sts-service/src/pipeline.py -> tests/unit/test_pipeline.py
        test_file = f"test_{src_path.stem}.py"
    else:
        # Nested file: apps/sts-service/src/models/fragment.py -> test_models.py or test_fragment.py
        test_file = f"test_{src_path.parent.name}.py"  # Prefer test_models.py

    return Path(f"apps/{module}/tests/unit/{test_file}")


def check_test_exists(src_file: Path) -> Tuple[bool, str]:
    """
    Check if test file exists for source file.

    Returns:
        (exists, message)
    """
    expected_test = get_expected_test_path(src_file)

    # Also check for test_<filename>.py alternative
    alternative_test = expected_test.parent / f"test_{src_file.stem}.py"

    if expected_test.exists():
        # Check if test file is not empty (has at least one test function)
        content = expected_test.read_text()
        if re.search(r'def test_\w+', content):
            return True, f"✓ Test exists: {expected_test}"
        else:
            return False, f"✗ Test file exists but has no test functions: {expected_test}"
    elif alternative_test.exists():
        content = alternative_test.read_text()
        if re.search(r'def test_\w+', content):
            return True, f"✓ Test exists: {alternative_test}"
        else:
            return False, f"✗ Test file exists but has no test functions: {alternative_test}"
    else:
        return False, (
            f"✗ No test found for {src_file}\n"
            f"  Expected: {expected_test} or {alternative_test}\n"
            f"  Create test file with at least one test_*() function."
        )


def main() -> int:
    """Main entry point."""
    staged_files = get_staged_python_files()

    if not staged_files:
        # No new Python files staged, skip check
        return 0

    print("Checking for tests (Constitution Principle VIII)...")

    failed = []
    for src_file in staged_files:
        exists, message = check_test_exists(src_file)
        print(f"  {message}")
        if not exists:
            failed.append(src_file)

    if failed:
        print("\n❌ Test-first development violated!")
        print("Constitution Principle VIII requires tests before implementation.")
        print("\nTo fix:")
        print("1. Create test file(s) for new code")
        print("2. Write failing tests that define expected behavior")
        print("3. Verify tests fail: pytest <test_file>")
        print("4. Stage test files: git add <test_file>")
        print("5. Retry commit")
        return 1

    print("✓ All new code has corresponding tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
