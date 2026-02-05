#!/usr/bin/env python3
"""
Comprehensive test runner for the demand forecasting ML system.
Runs all test suites and provides detailed reporting.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class TestRunner:
    """Comprehensive test runner for the ML system."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_dir = project_root / "tests"
        self.reports_dir = project_root / "test_reports"
        self.reports_dir.mkdir(exist_ok=True)

        # Test suites configuration
        self.test_suites = {
            "unit": {
                "name": "Unit Tests",
                "files": [
                    "test_minio_upload.py",
                    "test_s3_helpers.py",
                    "test_data_processing.py",
                ],
                "description": "Core utility function tests",
            },
            "integration": {
                "name": "Integration Tests",
                "files": [
                    "test_automation.py",
                    "test_core_utilities.py",
                    "test_drift_detection.py",
                ],
                "description": "Component integration tests",
            },
            "ml": {
                "name": "ML Pipeline Tests",
                "files": [
                    "test_model_serving.py",
                    "test_optimization.py",
                    "pipelines/test_data_processing.py",
                ],
                "description": "ML pipeline and model tests",
            },
            "system": {
                "name": "System Tests",
                "files": ["test_integration.py", "test_production_ops.py"],
                "description": "End-to-end system tests",
            },
        }

    def run_all_tests(
        self, verbose: bool = False, coverage: bool = True, html_report: bool = True
    ) -> dict[str, Any]:
        """Run all test suites."""
        print("🚀 Starting Comprehensive ML System Test Suite")
        print("=" * 60)

        start_time = time.time()
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_suites": len(self.test_suites),
            "suites": {},
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
                "duration": 0,
            },
        }

        for suite_name, suite_config in self.test_suites.items():
            print(f"\n📋 Running {suite_config['name']}...")
            print(f"   {suite_config['description']}")

            suite_result = self._run_test_suite(
                suite_name, suite_config, verbose, coverage
            )
            results["suites"][suite_name] = suite_result

            # Update summary
            results["summary"]["total_tests"] += suite_result["summary"]["total"]
            results["summary"]["passed"] += suite_result["summary"]["passed"]
            results["summary"]["failed"] += suite_result["summary"]["failed"]
            results["summary"]["skipped"] += suite_result["summary"]["skipped"]
            results["summary"]["errors"] += suite_result["summary"]["errors"]

        results["summary"]["duration"] = time.time() - start_time

        # Generate HTML report if requested
        if html_report:
            self._generate_html_report(results)

        # Save JSON results
        self._save_results(results)

        # Print final summary
        self._print_final_summary(results)

        return results

    def run_specific_suite(
        self, suite_name: str, verbose: bool = False, coverage: bool = True
    ) -> dict[str, Any]:
        """Run a specific test suite."""
        if suite_name not in self.test_suites:
            available_suites = list(self.test_suites.keys())
            print(f"❌ Suite '{suite_name}' not found. Available: {available_suites}")
            return {}

        suite_config = self.test_suites[suite_name]
        print(f"🎯 Running {suite_config['name']} Suite")
        print(f"   {suite_config['description']}")
        print("-" * 40)

        result = self._run_test_suite(suite_name, suite_config, verbose, coverage)

        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "suite": suite_name,
            "result": result,
        }
        self._save_results(results, f"{suite_name}_results.json")

        return result

    def _run_test_suite(
        self,
        suite_name: str,
        suite_config: dict[str, Any],
        verbose: bool = False,
        coverage: bool = True,
    ) -> dict[str, Any]:
        """Run a single test suite."""
        suite_result = {
            "name": suite_config["name"],
            "description": suite_config["description"],
            "files": suite_config["files"],
            "results": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
                "duration": 0,
            },
        }

        start_time = time.time()

        for test_file in suite_config["files"]:
            test_path = self.test_dir / test_file
            if not test_path.exists():
                print(f"⚠️  Test file not found: {test_file}")
                suite_result["results"][test_file] = {
                    "status": "NOT_FOUND",
                    "error": "File does not exist",
                }
                continue

            print(f"   Running {test_file}...")
            file_result = self._run_test_file(test_path, verbose, coverage)
            suite_result["results"][test_file] = file_result

            # Update suite summary
            suite_result["summary"]["total"] += file_result["summary"]["total"]
            suite_result["summary"]["passed"] += file_result["summary"]["passed"]
            suite_result["summary"]["failed"] += file_result["summary"]["failed"]
            suite_result["summary"]["skipped"] += file_result["summary"]["skipped"]
            suite_result["summary"]["errors"] += file_result["summary"]["errors"]

        suite_result["summary"]["duration"] = time.time() - start_time

        # Print suite summary
        self._print_suite_summary(suite_result)

        return suite_result

    def _run_test_file(
        self, test_path: Path, verbose: bool = False, coverage: bool = True
    ) -> dict[str, Any]:
        """Run a single test file."""
        cmd = [sys.executable, "-m", "pytest", str(test_path)]

        if not verbose:
            cmd.extend(["--tb=short", "-q"])
        else:
            cmd.extend(["--tb=long", "-v"])

        if coverage:
            cmd.extend(
                [
                    "--cov=src/demand_forecasting",
                    "--cov-report=term-missing",
                    "--cov-report=json:coverage.json",
                ]
            )

        # Set environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root / "src")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes per file
            )

            # Parse pytest output
            parsed_result = self._parse_pytest_output(result.stdout, result.stderr)

            return {
                "status": "COMPLETED",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": parsed_result,
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "TIMEOUT",
                "error": "Test execution timed out after 5 minutes",
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 1,
                },
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 1,
                },
            }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> dict[str, int]:
        """Parse pytest output to extract test counts."""
        summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        # Look for the summary line (e.g., "3 passed, 1 failed, 2 skipped")
        lines = stdout.split("\n")
        for line in lines:
            line = line.strip()
            if any(
                keyword in line.lower()
                for keyword in ["passed", "failed", "skipped", "error"]
            ):
                # Parse the line
                parts = line.replace(",", "").split()
                for i, part in enumerate(parts):
                    if part.isdigit():
                        count = int(part)
                        if i + 1 < len(parts):
                            next_word = parts[i + 1].lower()
                            if "passed" in next_word:
                                summary["passed"] = count
                            elif "failed" in next_word:
                                summary["failed"] = count
                            elif "skipped" in next_word:
                                summary["skipped"] = count
                            elif "error" in next_word:
                                summary["errors"] = count

        # Calculate total
        summary["total"] = (
            summary["passed"]
            + summary["failed"]
            + summary["skipped"]
            + summary["errors"]
        )

        return summary

    def _print_suite_summary(self, suite_result: dict[str, Any]):
        """Print summary for a test suite."""
        summary = suite_result["summary"]
        total = summary["total"]
        passed = summary["passed"]
        failed = summary["failed"]
        skipped = summary["skipped"]
        errors = summary["errors"]
        duration = summary["duration"]

        print(f"\n   📊 {suite_result['name']} Results:")
        print(
            f"      Total: {total}, Passed: {passed}, Failed: {failed}, Skipped: {skipped}, Errors: {errors}"
        )
        print(f"      Duration: {duration:.2f}s")
        if failed > 0 or errors > 0:
            print("      ❌ Some tests failed - check details above")
        else:
            print("      ✅ All tests passed")

    def _print_final_summary(self, results: dict[str, Any]):
        """Print final test summary."""
        print("\n" + "=" * 60)
        print("🎯 FINAL TEST SUMMARY")
        print("=" * 60)

        summary = results["summary"]
        total_tests = summary["total_tests"]
        passed = summary["passed"]
        failed = summary["failed"]
        skipped = summary["skipped"]
        errors = summary["errors"]
        duration = summary["duration"]

        print(f"Total Test Suites: {results['total_suites']}")
        print(f"Total Tests Run: {total_tests}")
        print(f"Tests Passed: {passed}")
        print(f"Tests Failed: {failed}")
        print(f"Tests Skipped: {skipped}")
        print(f"Test Errors: {errors}")
        print(f"Total Duration: {results['total_duration']:.2f}s")
        if total_tests > 0:
            success_rate = (passed / total_tests) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        print(f"Timestamp: {results['timestamp']}")

        # Overall status
        if failed == 0 and errors == 0:
            print("\n🎉 ALL TESTS PASSED!")
            print("The ML system is ready for deployment.")
        else:
            print(f"\n⚠️  {failed + errors} tests failed or had errors.")
            print(
                "Please review the test output above and fix issues before deployment."
            )

        print(f"\n📄 Detailed reports saved to: {self.reports_dir}")

    def _generate_html_report(self, results: dict[str, Any]):
        """Generate HTML test report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Demand Forecasting ML System - Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        .summary {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .suite {{ background: white; margin: 15px 0; padding: 15px; border-radius: 6px; border-left: 4px solid #667eea; }}
        .metric {{ display: inline-block; margin: 10px 15px 10px 0; padding: 8px 12px; background: #e8f4f8; border-radius: 4px; }}
        .status-pass {{ color: #28a745; font-weight: bold; }}
        .status-fail {{ color: #dc3545; font-weight: bold; }}
        .status-skip {{ color: #ffc107; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f8f9fa; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Demand Forecasting ML System</h1>
        <h2>Test Report</h2>
        <p>Generated on: {results["timestamp"]}</p>
    </div>

    <div class="summary">
        <h2>📊 Overall Summary</h2>
        <div class="metric">
            <strong>Total Suites:</strong> {results["total_suites"]}
        </div>
        <div class="metric">
            <strong>Total Tests:</strong> {results["summary"]["total_tests"]}
        </div>
        <div class="metric">
            <strong>Passed:</strong> <span class="status-pass">{results["summary"]["passed"]}</span>
        </div>
        <div class="metric">
            <strong>Failed:</strong> <span class="status-fail">{results["summary"]["failed"]}</span>
        </div>
        <div class="metric">
            <strong>Skipped:</strong> <span class="status-skip">{results["summary"]["skipped"]}</span>
        </div>
        <div class="metric">
            <strong>Errors:</strong> <span class="status-fail">{results["summary"]["errors"]}</span>
        </div>
        <div class="metric">
            <strong>Duration:</strong> {results["summary"]["duration"]:.2f}s
        </div>
    </div>

    <h2>📋 Suite Details</h2>
"""

        for suite_name, suite_result in results["suites"].items():
            suite_summary = suite_result["summary"]
            status_class = (
                "status-pass"
                if suite_summary["failed"] == 0 and suite_summary["errors"] == 0
                else "status-fail"
            )

            html_content += f"""
    <div class="suite">
        <h3>{suite_result["name"]} <span class="{status_class}">({suite_summary["passed"]}/{suite_summary["total"]} passed)</span></h3>
        <p>{suite_result["description"]}</p>
        <div class="metric">
            <strong>Total:</strong> {suite_summary["total"]}
        </div>
        <div class="metric">
            <strong>Passed:</strong> <span class="status-pass">{suite_summary["passed"]}</span>
        </div>
        <div class="metric">
            <strong>Failed:</strong> <span class="status-fail">{suite_summary["failed"]}</span>
        </div>
        <div class="metric">
            <strong>Duration:</strong> {suite_summary["duration"]:.2f}s
        </div>

        <table>
            <tr>
                <th>Test File</th>
                <th>Status</th>
                <th>Total</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Skipped</th>
                <th>Errors</th>
            </tr>
"""

            for file_name, file_result in suite_result["results"].items():
                if file_result["status"] == "COMPLETED":
                    file_summary = file_result["summary"]
                    html_content += f"""
            <tr>
                <td>{file_name}</td>
                <td class="status-pass">✅ Completed</td>
                <td>{file_summary["total"]}</td>
                <td class="status-pass">{file_summary["passed"]}</td>
                <td class="status-fail">{file_summary["failed"]}</td>
                <td class="status-skip">{file_summary["skipped"]}</td>
                <td class="status-fail">{file_summary["errors"]}</td>
            </tr>
"""
                else:
                    html_content += f"""
            <tr>
                <td>{file_name}</td>
                <td class="status-fail">❌ {file_result["status"]}</td>
                <td colspan="5">{file_result.get("error", "Unknown error")}</td>
            </tr>
"""

            html_content += """
        </table>
    </div>
"""

        html_content += """
    <div class="footer">
        <p>Report generated by ML System Test Runner</p>
        <p>For questions or issues, check the test output or contact the development team.</p>
    </div>
</body>
</html>
"""

        report_path = self.reports_dir / "comprehensive_test_report.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"📄 HTML report saved to: {report_path}")

    def _save_results(
        self, results: dict[str, Any], filename: str = "comprehensive_test_results.json"
    ):
        """Save test results to JSON file."""
        results_path = self.reports_dir / filename
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"💾 JSON results saved to: {results_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for demand forecasting ML system"
    )
    parser.add_argument(
        "--suite",
        choices=["unit", "integration", "ml", "system"],
        help="Run specific test suite",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--no-coverage", action="store_true", help="Skip coverage reporting"
    )
    parser.add_argument(
        "--no-html", action="store_true", help="Skip HTML report generation"
    )
    parser.add_argument(
        "--project-root",
        type=str,
        help="Project root directory (default: current directory parent)",
    )

    args = parser.parse_args()

    # Determine project root
    if args.project_root:
        project_root = Path(args.project_root)
    else:
        # Assume script is in tests/ directory
        project_root = Path(__file__).parent.parent

    # Initialize test runner
    runner = TestRunner(project_root)

    try:
        if args.suite:
            # Run specific suite
            results = runner.run_specific_suite(
                args.suite, verbose=args.verbose, coverage=not args.no_coverage
            )
        else:
            # Run all tests
            results = runner.run_all_tests(
                verbose=args.verbose,
                coverage=not args.no_coverage,
                html_report=not args.no_html,
            )

        # Exit with appropriate code
        summary = results.get("summary", {})
        if summary.get("failed", 0) > 0 or summary.get("errors", 0) > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
