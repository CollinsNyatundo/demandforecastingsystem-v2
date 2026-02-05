#!/usr/bin/env python3
"""Test runner for core pipeline utilities.

Usage:
    python scripts/run_core_tests.py
    python scripts/run_core_tests.py --verbose
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests(verbose=False):
    """Run the core utilities tests."""
    project_root = Path(__file__).parent.parent
    test_file = project_root / "tests" / "test_core_utilities.py"

    if not test_file.exists():
        return 1

    # Set up environment
    env = {
        "PYTHONPATH": str(project_root / "src"),
        "MINIO_ROOT_USER": "test_user",
        "MINIO_ROOT_PASSWORD": "test_pass",
        "MINIO_ENDPOINT": "http://test:9000",
    }

    # Build test command
    cmd = [sys.executable, str(test_file)]
    if verbose:
        cmd.append("-v")

    try:
        # Run tests
        result = subprocess.run(cmd, env=env, capture_output=False, text=True)

        if result.returncode == 0:
            pass
        else:
            pass

        return result.returncode

    except Exception:
        return 1


def main():
    parser = argparse.ArgumentParser(description="Run core pipeline utilities tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    return run_tests(verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
