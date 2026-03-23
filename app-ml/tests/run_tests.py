"""Comprehensive test execution and reporting script.

Provides test runner with coverage reporting, performance benchmarking,
and detailed test result analysis for the app-ml system.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class TestRunner:
    """Comprehensive test runner for app-ml system."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_dir = project_root / "tests"
        self.coverage_dir = project_root / "coverage_report"
        self.results = {}

    def run_all_tests(
        self,
        include_slow: bool = False,
        include_mlflow: bool = False,
        include_optuna: bool = False,
    ) -> dict[str, Any]:
        """Run all tests with specified options."""
        # Build pytest command
        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-v",
            "--tb=short",
            "--cov=src/demand_forecasting",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=json",
            f"--cov-fail-under={self.coverage_dir}/coverage.json",
            "--junit-xml=test_results.xml",
        ]

        # Add optional markers
        markers = []
        if include_slow:
            markers.append("slow")
        if include_mlflow:
            markers.append("mlflow")
        if include_optuna:
            markers.append("optuna")

        if markers:
            cmd.extend(["-m", " or ".join(markers)])

        # Set environment variables
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root / "src")

        # Run tests
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes timeout
            )

            end_time = time.time()
            duration = end_time - start_time

            # Parse results
            self.results = {
                "exit_code": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "markers": markers,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            self._print_results()
            self._generate_report()

            return self.results

        except subprocess.TimeoutExpired:
            return {"exit_code": 1, "error": "timeout"}
        except Exception as e:
            return {"exit_code": 1, "error": str(e)}

    def run_specific_tests(self, test_files: list[str]) -> dict[str, Any]:
        """Run specific test files."""
        cmd = [
            "python",
            "-m",
            "pytest",
            *[str(self.test_dir / f) for f in test_files],
            "-v",
            "--tb=short",
            "--cov=src/demand_forecasting",
            "--cov-report=term-missing",
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root / "src")

        result = subprocess.run(cmd, cwd=self.project_root, env=env, text=True)

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _print_results(self):
        """Print test results summary."""
        if self.results["exit_code"] == 0:
            pass
        else:
            pass

        if self.results["stderr"]:
            pass

        # Parse test statistics from stdout
        stdout_lines = self.results["stdout"].split("\n")
        for line in stdout_lines:
            if "passed" in line and "failed" in line and "error" in line:
                break

    def _generate_report(self):
        """Generate detailed test report."""
        report_dir = self.project_root / "test_reports"
        report_dir.mkdir(exist_ok=True)

        report = {
            "summary": {
                "exit_code": self.results["exit_code"],
                "duration": self.results["duration"],
                "timestamp": self.results["timestamp"],
                "markers": self.results["markers"],
            },
            "coverage": self._parse_coverage(),
            "performance": self._analyze_performance(),
            "recommendations": self._generate_recommendations(),
        }

        # Save JSON report
        with open(report_dir / "test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Save HTML report
        self._generate_html_report(report, report_dir)

    def _parse_coverage(self) -> dict[str, Any]:
        """Parse coverage information."""
        coverage_file = self.project_root / "coverage.json"
        if coverage_file.exists():
            try:
                with open(coverage_file) as f:
                    coverage_data = json.load(f)

                totals = coverage_data.get("totals", {})
                return {
                    "percent_covered": totals.get("percent_covered", 0),
                    "lines_covered": totals.get("covered_lines", 0),
                    "lines_missing": totals.get("missing_lines", 0),
                    "total_lines": totals.get("num_statements", 0),
                }
            except Exception:
                pass

        return {"percent_covered": 0, "lines_covered": 0, "lines_missing": 0}

    def _analyze_performance(self) -> dict[str, Any]:
        """Analyze test performance."""
        stdout = self.results.get("stdout", "")

        # Extract timing information from pytest output
        performance = {
            "slowest_tests": [],
            "average_test_time": 0,
            "total_test_time": 0,
        }

        # Parse slowest tests (if available)
        lines = stdout.split("\n")
        for line in lines:
            if "slowest" in line.lower() and "test" in line.lower():
                performance["slowest_tests"].append(line.strip())

        return performance

    def _generate_recommendations(self) -> list[str]:
        """Generate test recommendations."""
        recommendations = []

        coverage = self._parse_coverage()

        if coverage["percent_covered"] < 80:
            recommendations.append(
                f"📊 Coverage is {coverage['percent_covered']:.1f}%. "
                "Aim for >80% coverage by adding more test cases."
            )

        if self.results["exit_code"] != 0:
            recommendations.append(
                "🔧 Some tests failed. Review the error output and fix failing tests."
            )

        if self.results["duration"] > 300:  # 5 minutes
            recommendations.append(
                "⚡ Tests are slow. Consider using pytest-xdist for parallel execution."
            )

        if not recommendations:
            recommendations.append("🎉 Excellent test coverage and performance!")

        return recommendations

    def _generate_html_report(self, report: dict[str, Any], report_dir: Path):
        """Generate HTML test report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>app-ml Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .success {{ color: #28a745; }}
        .failure {{ color: #dc3545; }}
        .warning {{ color: #ffc107; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #e9ecef; border-radius: 3px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 app-ml Demand Forecasting System Test Report</h1>
        <p>Generated on: {report["summary"]["timestamp"]}</p>
    </div>

    <div class="section">
        <h2>📊 Test Summary</h2>
        <div class="metric">
            <strong>Status:</strong>
            <span class="{"success" if report["summary"]["exit_code"] == 0 else "failure"}">
                {"✅ PASSED" if report["summary"]["exit_code"] == 0 else "❌ FAILED"}
            </span>
        </div>
        <div class="metric">
            <strong>Duration:</strong> {report["summary"]["duration"]:.2f} seconds
        </div>
        <div class="metric">
            <strong>Markers:</strong> {", ".join(report["summary"]["markers"]) if report["summary"]["markers"] else "All"}
        </div>
    </div>

    <div class="section">
        <h2>📈 Code Coverage</h2>
        <div class="metric">
            <strong>Coverage:</strong> {report["coverage"]["percent_covered"]:.1f}%
        </div>
        <div class="metric">
            <strong>Lines Covered:</strong> {report["coverage"]["lines_covered"]}
        </div>
        <div class="metric">
            <strong>Lines Missing:</strong> {report["coverage"]["lines_missing"]}
        </div>
    </div>

    <div class="section">
        <h2>🎯 Recommendations</h2>
        <ul>
            {"".join(f"<li>{rec}</li>" for rec in report["recommendations"])}
        </ul>
    </div>
</body>
</html>
        """

        with open(report_dir / "test_report.html", "w") as f:
            f.write(html_content)


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for app-ml system"
    )
    parser.add_argument(
        "--include-slow", action="store_true", help="Include slow tests"
    )
    parser.add_argument(
        "--include-mlflow", action="store_true", help="Include MLflow tests"
    )
    parser.add_argument(
        "--include-optuna", action="store_true", help="Include Optuna tests"
    )
    parser.add_argument("--specific", nargs="+", help="Run specific test files")
    parser.add_argument("--project-root", type=str, help="Project root directory")

    args = parser.parse_args()

    # Determine project root
    if args.project_root:
        project_root = Path(args.project_root)
    else:
        # Default to script directory parent
        project_root = Path(__file__).parent.parent

    # Initialize test runner
    runner = TestRunner(project_root)

    # Run tests
    if args.specific:
        results = runner.run_specific_tests(args.specific)
    else:
        results = runner.run_all_tests(
            include_slow=args.include_slow,
            include_mlflow=args.include_mlflow,
            include_optuna=args.include_optuna,
        )

    # Exit with appropriate code
    sys.exit(results.get("exit_code", 1))


if __name__ == "__main__":
    main()
