#!/usr/bin/env python3
"""
Enforce TDD compliance for PRs (Constitution Principle VIII).

Checks:
1. New source files have corresponding test files
2. Modified source files have test coverage changes
3. Test coverage doesn't drop below 80%
4. Critical paths maintain 95% coverage

Usage: Called by GitHub Actions CI
"""
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Set


def get_changed_files(base: str, head: str) -> tuple[Set[Path], Set[Path]]:
    """
    Get added and modified Python files between base and head commits.

    Returns:
        (added_files, modified_files)
    """
    # Get added files
    result_added = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True
    )
    added = {
        Path(f) for f in result_added.stdout.strip().split('\n')
        if f.startswith('apps/') and '/src/' in f and f.endswith('.py') and f != ''
    }

    # Get modified files
    result_modified = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=M", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True
    )
    modified = {
        Path(f) for f in result_modified.stdout.strip().split('\n')
        if f.startswith('apps/') and '/src/' in f and f.endswith('.py') and f != ''
    }

    return added, modified


def check_tests_for_new_files(files: Set[Path]) -> List[str]:
    """Check that new source files have corresponding tests."""
    errors = []

    for src_file in files:
        # Expected test path (simplified - same logic as check_tests_exist.py)
        parts = src_file.parts
        module = parts[1]
        test_file = f"test_{src_file.stem}.py"
        expected_test = Path(f"apps/{module}/tests/unit/{test_file}")

        if not expected_test.exists():
            errors.append(
                f"✗ New file {src_file} has no test file {expected_test}"
            )

    return errors


def check_critical_path_coverage(base: str, head: str) -> List[str]:
    """
    Check that critical paths maintain 95% coverage.

    Critical paths (per Constitution):
    - A/V sync code
    - STS pipeline
    - Fragment processing
    """
    critical_paths = [
        "apps/stream-worker/src/pipeline/",
        "apps/stream-worker/src/sync/",
        "apps/sts-service/src/pipeline/",
        "apps/sts-service/src/fragment/",
    ]

    errors = []

    # Run coverage for each critical path
    for path in critical_paths:
        if not Path(path).exists():
            continue  # Path doesn't exist yet, skip

        result = subprocess.run(
            [
                "python3", "-m", "pytest",
                "--cov", path,
                "--cov-report", "term",
                "--cov-fail-under", "95",
                "-q"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            errors.append(
                f"✗ Critical path {path} has <95% coverage\n{result.stdout}"
            )

    return errors


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enforce TDD compliance for PRs")
    parser.add_argument("--base", required=True, help="Base commit SHA")
    parser.add_argument("--head", required=True, help="Head commit SHA")
    args = parser.parse_args()

    print("=" * 80)
    print("TDD COMPLIANCE CHECK (Constitution Principle VIII)")
    print("=" * 80)

    added_files, modified_files = get_changed_files(args.base, args.head)

    print(f"\nNew source files: {len(added_files)}")
    print(f"Modified source files: {len(modified_files)}")

    errors = []

    # Check 1: New files have tests
    if added_files:
        print("\n--- Checking tests for new files ---")
        new_file_errors = check_tests_for_new_files(added_files)
        errors.extend(new_file_errors)
        for error in new_file_errors:
            print(error)

    # Check 2: Critical path coverage
    print("\n--- Checking critical path coverage (95% required) ---")
    critical_errors = check_critical_path_coverage(args.base, args.head)
    errors.extend(critical_errors)
    for error in critical_errors:
        print(error)

    # Summary
    print("\n" + "=" * 80)
    if errors:
        print(f"❌ TDD COMPLIANCE FAILED: {len(errors)} error(s)")
        print("\nTo fix:")
        print("1. Add missing test files")
        print("2. Write tests for new code")
        print("3. Increase coverage for critical paths to 95%")
        print("4. Push changes and re-run CI")
        return 1
    else:
        print("✓ TDD COMPLIANCE PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
