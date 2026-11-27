#!/usr/bin/env python
import requests


def main() -> None:
    """Manual smoke test against a running local Airflow instance."""
    requests.get("http://localhost:8081/api/v1/dags", timeout=5)
    requests.get(
        "http://localhost:8081/api/v1/dags", auth=("admin", "admin"), timeout=5
    )
    requests.get("http://localhost:8081/health", timeout=5)


if __name__ == "__main__":
    main()
