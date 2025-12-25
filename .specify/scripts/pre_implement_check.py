#!/usr/bin/env python3
"""
Pre-implementation checker for /speckit.implement workflow.

Validates that tests exist and are failing BEFORE implementation begins.
This enforces Constitution Principle VIII at the workflow level.

Usage: Called by /speckit.implement before task execution or manually via `make pre-implement`
"""
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple
import re


def find_test_files(tasks_md: Path) -> List[Path]:
    """
    Parse tasks.md and extract test file paths.

    Looks for task descriptions like:
    - [ ] T010 [P] [US1] Unit tests for ... in `apps/.../tests/unit/test_*.py`
    """
    content = tasks_md.read_text()
    test_files = []

    # Simple regex to extract test file paths in backticks
    pattern = r'`(apps/[^`]+/tests/[^`]+\.py)`'
    matches = re.findall(pattern, content)

    for match in matches:
        test_files.append(Path(match))

    # Also look for root-level test paths
    pattern = r'`(tests/[^`]+\.py)`'
    matches = re.findall(pattern, content)

    for match in matches:
        test_files.append(Path(match))

    return list(set(test_files))  # Remove duplicates


def check_tests_fail(test_files: List[Path]) -> Tuple[bool, List[str]]:
    """
    Run tests and verify they FAIL (as expected before implementation).

    Returns:
        (all_tests_fail, messages)
    """
    if not test_files:
        return False, ["No test files found in tasks.md"]

    messages = []
    all_fail = True

    for test_file in test_files:
        if not test_file.exists():
            messages.append(f"✗ Test file does not exist: {test_file}")
            all_fail = False
            continue

        # Run pytest on this test file
        result = subprocess.run(
            ["python3", "-m", "pytest", str(test_file), "-v"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            # Tests passed - this is BAD (should fail before implementation)
            messages.append(
                f"⚠️  Tests PASSED in {test_file} - implementation may already exist"
            )
            all_fail = False
        else:
            # Tests failed - this is GOOD (expected before implementation)
            messages.append(f"✓ Tests FAIL in {test_file} (expected)")

    return all_fail, messages


def main() -> int:
    """Main entry point."""
    # Find tasks.md in current spec directory
    tasks_md = Path("tasks.md")

    if not tasks_md.exists():
        print("❌ tasks.md not found. Run /speckit.tasks first.")
        return 1

    print("=" * 80)
    print("PRE-IMPLEMENTATION CHECK (Constitution Principle VIII)")
    print("=" * 80)

    test_files = find_test_files(tasks_md)
    print(f"\nFound {len(test_files)} test file(s) in tasks.md")

    if not test_files:
        print("\n⚠️  No test tasks found in tasks.md")
        print("Constitution Principle VIII requires tests before implementation.")
        print("\nOptions:")
        print("1. Add test tasks to tasks.md")
        print("2. If this is a refactor/docs-only change, add justification to PR")
        return 1

    all_fail, messages = check_tests_fail(test_files)

    print("\n--- Test Status ---")
    for msg in messages:
        print(msg)

    print("\n" + "=" * 80)
    if all_fail:
        print("✓ PRE-IMPLEMENTATION CHECK PASSED")
        print("All tests are failing (as expected). Implementation can proceed.")
        return 0
    else:
        print("❌ PRE-IMPLEMENTATION CHECK FAILED")
        print("\nTests must exist and FAIL before implementation begins.")
        print("\nTo fix:")
        print("1. Create missing test files")
        print("2. Write failing tests that define expected behavior")
        print("3. Verify tests fail: pytest <test_file>")
        print("4. Re-run /speckit.implement or make pre-implement")
        return 1


if __name__ == "__main__":
    sys.exit(main())
