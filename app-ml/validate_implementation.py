#!/usr/bin/env python3
"""
Implementation validation script for demand forecasting system.
Checks for port conflicts, missing dependencies, and configuration issues.
"""

import os
import sys
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ImplementationValidator:
    """Validate the complete implementation."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.issues = []
        self.warnings = []

    def validate_all(self) -> Dict[str, any]:
        """Run all validation checks."""
        results = {"status": "PASS", "issues": [], "warnings": [], "checks": {}}

        # Check port conflicts
        port_results = self.check_port_conflicts()
        results["checks"]["ports"] = port_results

        # Check dependencies
        dep_results = self.check_dependencies()
        results["checks"]["dependencies"] = dep_results

        # Check file structure
        struct_results = self.check_file_structure()
        results["checks"]["structure"] = struct_results

        # Check configurations
        config_results = self.check_configurations()
        results["checks"]["configurations"] = config_results

        # Check Python syntax
        syntax_results = self.check_python_syntax()
        results["checks"]["syntax"] = syntax_results

        # Aggregate results
        for check_name, check_result in results["checks"].items():
            if check_result["status"] == "FAIL":
                results["status"] = "FAIL"
                results["issues"].extend(check_result.get("issues", []))
            results["warnings"].extend(check_result.get("warnings", []))

        return results

    def check_port_conflicts(self) -> Dict[str, any]:
        """Check for port conflicts in docker-compose.yml."""
        logger.info("Checking port conflicts...")

        result = {"status": "PASS", "issues": [], "warnings": []}

        try:
            docker_compose_path = self.base_path / "docker-compose.yml"
            if not docker_compose_path.exists():
                result["issues"].append("docker-compose.yml not found")
                result["status"] = "FAIL"
                return result

            with open(docker_compose_path, "r") as f:
                content = f.read()

            # Extract port mappings
            import re

            port_pattern = r'-\s*"(\d+):(\d+)"'
            port_matches = re.findall(port_pattern, content)

            used_ports = {}
            for host_port, container_port in port_matches:
                host_port = int(host_port)
                if host_port in used_ports:
                    result["issues"].append(
                        f"Port conflict: {host_port} used by multiple services: {used_ports[host_port]} and new service"
                    )
                    result["status"] = "FAIL"
                else:
                    used_ports[host_port] = f"container_port:{container_port}"

            # Check for expected ports
            expected_ports = {
                80: "Nginx HTTP",
                8000: "Model Server API",
                8001: "Model Server Metrics",
                8080: "Nginx Status",
                8081: "Airflow Webserver",
                9000: "MinIO API",
                9001: "MinIO Console",
                9090: "Prometheus",
                3000: "Grafana",
                5000: "MLflow",
                5432: "PostgreSQL",
                6379: "Redis",
            }

            for port, service in expected_ports.items():
                if port not in used_ports:
                    result["warnings"].append(
                        f"Expected port {port} ({service}) not found"
                    )

            logger.info(f"Port check completed. Found {len(used_ports)} port mappings.")

        except Exception as e:
            result["issues"].append(f"Error checking ports: {str(e)}")
            result["status"] = "FAIL"

        return result

    def check_dependencies(self) -> Dict[str, any]:
        """Check requirements.txt for missing dependencies."""
        logger.info("Checking dependencies...")

        result = {"status": "PASS", "issues": [], "warnings": []}

        try:
            requirements_path = self.base_path / "requirements.txt"
            if not requirements_path.exists():
                result["issues"].append("requirements.txt not found")
                result["status"] = "FAIL"
                return result

            with open(requirements_path, "r") as f:
                requirements = f.read()

            # Required dependencies for new features
            required_deps = [
                "fastapi",
                "uvicorn",
                "pydantic",
                "prometheus-client",
                "shap",
                "plotly",
                "scipy",
                "pendulum",
                "omegaconf",
            ]

            missing_deps = []
            for dep in required_deps:
                if dep not in requirements.lower():
                    missing_deps.append(dep)

            if missing_deps:
                result["issues"].append(
                    f"Missing required dependencies: {', '.join(missing_deps)}"
                )
                result["status"] = "FAIL"

            logger.info(f"Dependency check completed. Missing: {len(missing_deps)}")

        except Exception as e:
            result["issues"].append(f"Error checking dependencies: {str(e)}")
            result["status"] = "FAIL"

        return result

    def check_file_structure(self) -> Dict[str, any]:
        """Check if required files and directories exist."""
        logger.info("Checking file structure...")

        result = {"status": "PASS", "issues": [], "warnings": []}

        required_files = [
            "docker-compose.yml",
            "requirements.txt",
            "Dockerfile.model-server",
            "nginx/nginx.conf",
            "prometheus/prometheus.yml",
            "prometheus/prometheus_rules.yml",
            "grafana/provisioning/datasources/prometheus.yml",
            "grafana/provisioning/dashboards/dashboards.yml",
            "grafana/dashboards/demand-forecasting-overview.json",
        ]

        required_dirs = [
            "src/demand_forecasting/serving",
            "src/demand_forecasting/monitoring",
            "src/demand_forecasting/explainability",
            "src/demand_forecasting/optimization",
            "src/demand_forecasting/automation",
        ]

        missing_files = []
        for file_path in required_files:
            full_path = self.base_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)

        missing_dirs = []
        for dir_path in required_dirs:
            full_path = self.base_path / dir_path
            if not full_path.exists():
                missing_dirs.append(dir_path)

        if missing_files:
            result["issues"].append(
                f"Missing required files: {', '.join(missing_files)}"
            )
            result["status"] = "FAIL"

        if missing_dirs:
            result["issues"].append(
                f"Missing required directories: {', '.join(missing_dirs)}"
            )
            result["status"] = "FAIL"

        logger.info(
            f"File structure check completed. Missing files: {len(missing_files)}, Missing dirs: {len(missing_dirs)}"
        )

        return result

    def check_configurations(self) -> Dict[str, any]:
        """Check configuration files for syntax errors."""
        logger.info("Checking configurations...")

        result = {"status": "PASS", "issues": [], "warnings": []}

        # Check docker-compose.yml
        try:
            docker_compose_path = self.base_path / "docker-compose.yml"
            if docker_compose_path.exists():
                with open(docker_compose_path, "r") as f:
                    yaml.safe_load(f)
        except yaml.YAMLError as e:
            result["issues"].append(f"docker-compose.yml YAML error: {str(e)}")
            result["status"] = "FAIL"
        except Exception as e:
            result["issues"].append(f"Error reading docker-compose.yml: {str(e)}")
            result["status"] = "FAIL"

        # Check nginx configuration
        try:
            nginx_path = self.base_path / "nginx/nginx.conf"
            if nginx_path.exists():
                with open(nginx_path, "r") as f:
                    content = f.read()
                    # Basic syntax check for nginx config
                    if "events {" not in content or "http {" not in content:
                        result["warnings"].append("nginx.conf may have syntax issues")
        except Exception as e:
            result["issues"].append(f"Error checking nginx.conf: {str(e)}")
            result["status"] = "FAIL"

        # Check Prometheus configuration
        try:
            prometheus_path = self.base_path / "prometheus/prometheus.yml"
            if prometheus_path.exists():
                with open(prometheus_path, "r") as f:
                    yaml.safe_load(f)
        except yaml.YAMLError as e:
            result["issues"].append(f"prometheus.yml YAML error: {str(e)}")
            result["status"] = "FAIL"
        except Exception as e:
            result["issues"].append(f"Error reading prometheus.yml: {str(e)}")
            result["status"] = "FAIL"

        logger.info("Configuration check completed.")

        return result

    def check_python_syntax(self) -> Dict[str, any]:
        """Check Python files for syntax errors."""
        logger.info("Checking Python syntax...")

        result = {"status": "PASS", "issues": [], "warnings": []}

        python_files = [
            "src/demand_forecasting/serving/model_server.py",
            "src/demand_forecasting/serving/model_router.py",
            "src/demand_forecasting/monitoring/drift_detector.py",
            "src/demand_forecasting/explainability/shap_explainer.py",
            "src/demand_forecasting/optimization/multi_objective.py",
            "src/demand_forecasting/optimization/ensemble.py",
            "src/demand_forecasting/automation/retraining_scheduler.py",
        ]

        syntax_errors = []
        for file_path in python_files:
            full_path = self.base_path / file_path
            if full_path.exists():
                try:
                    with open(full_path, "r") as f:
                        compile(f.read(), str(full_path), "exec")
                except SyntaxError as e:
                    syntax_errors.append(f"{file_path}: {str(e)}")
                except Exception as e:
                    result["warnings"].append(f"Could not check {file_path}: {str(e)}")

        if syntax_errors:
            result["issues"].extend(syntax_errors)
            result["status"] = "FAIL"

        logger.info(f"Python syntax check completed. Errors: {len(syntax_errors)}")

        return result


def main():
    """Main validation function."""
    validator = ImplementationValidator()
    results = validator.validate_all()

    print("\n" + "=" * 60)
    print("DEMAND FORECASTING SYSTEM VALIDATION RESULTS")
    print("=" * 60)

    print(f"\nOverall Status: {results['status']}")

    if results["issues"]:
        print(f"\n🚨 ISSUES FOUND ({len(results['issues'])}):")
        for i, issue in enumerate(results["issues"], 1):
            print(f"  {i}. {issue}")

    if results["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for i, warning in enumerate(results["warnings"], 1):
            print(f"  {i}. {warning}")

    print("\n" + "=" * 60)

    # Exit with appropriate code
    if results["status"] == "FAIL":
        print("❌ VALIDATION FAILED - Fix issues before proceeding")
        sys.exit(1)
    else:
        print("✅ VALIDATION PASSED - System ready for deployment")
        sys.exit(0)


if __name__ == "__main__":
    main()
