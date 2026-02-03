#!/usr/bin/env python3
"""Comprehensive Static Analysis Test Suite.

Tests the complete static analysis toolchain including:
- Ruff (linting, security, complexity)
- MyPy (type checking)
- Bandit (security scanning)
- Coverage reporting
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description, cwd=None):
    """Run a command and return results."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60
        )

        if result.returncode == 0:
            return True, result.stdout, result.stderr
        if result.stderr:
            pass
        return False, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def test_ruff_linting():
    """Test Ruff comprehensive linting configuration."""
    # Test basic linting
    success, stdout, _stderr = run_command(
        ["python", "-m", "ruff", "check", "src/", "--statistics"],
        "Ruff Comprehensive Linting"
    )

    if success:
        # Parse statistics
        lines = stdout.split('\n')
        stats_line = next((line for line in lines if 'Found' in line and 'errors' in line), "")
        if stats_line:
            pass

        # Show key rule categories found
        rule_counts = {}
        for line in lines:
            if '    ' in line and '[' in line and ']' in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    count = parts[0]
                    rule = parts[1]
                    if count.isdigit():
                        rule_counts[rule] = int(count)

        if rule_counts:
            security_rules = {k: v for k, v in rule_counts.items() if k.startswith('S')}
            complexity_rules = {k: v for k, v in rule_counts.items() if k.startswith('C90')}
            docstring_rules = {k: v for k, v in rule_counts.items() if k.startswith('D')}

            if security_rules:
                pass
            if complexity_rules:
                pass
            if docstring_rules:
                pass

    return success

def test_ruff_formatting():
    """Test Ruff formatting."""
    success, _stdout, _stderr = run_command(
        ["python", "-m", "ruff", "format", "src/", "--check"],
        "Ruff Formatting Check"
    )

    if success:
        pass
    else:
        pass

    return success

def test_bandit_security():
    """Test Bandit security scanning."""
    success, stdout, _stderr = run_command(
        ["python", "-m", "bandit", "-r", "src/", "-f", "json"],
        "Bandit Security Analysis"
    )

    if success and stdout:
        try:
            data = json.loads(stdout)
            results = data.get('results', [])

            if results:

                # Group by severity
                high_issues = [r for r in results if r.get('issue_severity') == 'HIGH']
                medium_issues = [r for r in results if r.get('issue_severity') == 'MEDIUM']
                low_issues = [r for r in results if r.get('issue_severity') == 'LOW']

                if high_issues:
                    for _issue in high_issues[:3]:  # Show first 3
                        pass

                if medium_issues:
                    for _issue in medium_issues[:3]:  # Show first 3
                        pass

                if low_issues:
                    for _issue in low_issues[:3]:  # Show first 3
                        pass
            else:
                pass

        except json.JSONDecodeError:
            pass

    return success

def test_mypy_types():
    """Test MyPy type checking."""
    success, _stdout, stderr = run_command(
        ["python", "-m", "mypy", "src/demand_forecasting", "--ignore-missing-imports"],
        "MyPy Type Analysis"
    )

    if success:
        pass
    else:
        # Show first few type errors
        lines = stderr.split('\n')[:10]
        for line in lines:
            if line.strip():
                pass

    return success

def test_coverage() -> bool:
    """Test test coverage configuration."""
    # Check if coverage is configured properly
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        content = pyproject_path.read_text()

        if "fail_under = 80" in content:
            pass
        else:
            pass

        if "source = [\"src/demand_forecasting\"]" in content:
            pass
        else:
            pass

        return True
    return False

def main() -> int:
    """Run all static analysis tests."""
    # Change to app-ml directory
    os.chdir("app-ml")

    results = {}

    # Test all tools
    results['ruff_linting'] = test_ruff_linting()
    results['ruff_formatting'] = test_ruff_formatting()
    results['bandit_security'] = test_bandit_security()
    results['mypy_types'] = test_mypy_types()
    results['coverage'] = test_coverage()

    # Summary

    total_tests = len(results)
    passed_tests = sum(results.values())

    for _tool, _result in results.items():
        pass


    if passed_tests == total_tests:
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
