"""Dataset Monitoring and Alerting Utility.

This module provides tools for monitoring dataset updates, freshness,
and quality metrics in Airflow pipelines.

Best Practices Implemented:
- Track dataset update frequency
- Alert on stale data
- Monitor data quality metrics
- Log dataset lineage events
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import s3fs
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class DatasetMonitor:
    """Monitors dataset freshness and logs update events.
    Now supports S3 file timestamp checking for accurate freshness monitoring.
    """

    def __init__(
        self,
        metrics_dir: str = "/opt/airflow/data/dataset_metrics",
        s3_endpoint: str = "http://host.docker.internal:9000",
        s3_key: str | None = None,
        s3_secret: str | None = None,
        s3_bucket: str = "demand-forecasting",
    ):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # S3 filesystem for actual file timestamp checking
        self.s3_endpoint = s3_endpoint
        self.s3_key = s3_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
        self.s3_secret = s3_secret or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        self.s3_bucket = s3_bucket

        # Initialize S3 filesystem
        try:
            self.fs = s3fs.S3FileSystem(
                client_kwargs={"endpoint_url": s3_endpoint},
                key=self.s3_key,
                secret=self.s3_secret,
            )
            logger.info(f"S3 filesystem initialized for endpoint: {s3_endpoint}")
        except Exception as e:
            logger.warning(f"Failed to initialize S3 filesystem: {e}")
            self.fs = None

        self.metrics_file = self.metrics_dir / "dataset_metrics.json"
        self.events_file = self.metrics_dir / "dataset_events.jsonl"

    def log_dataset_update(
        self,
        dataset_uri: str,
        task_id: str,
        dag_id: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        """Log a dataset update event.

        Args:
            dataset_uri: URI of the dataset
            task_id: Task that produced the dataset
            dag_id: DAG that produced the dataset
            run_id: DAG run ID
            metadata: Additional metadata (size, rows, schema, etc.)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "dataset_uri": dataset_uri,
            "dag_id": dag_id,
            "task_id": task_id,
            "run_id": run_id,
            "event_type": "dataset_update",
            "metadata": metadata or {},
        }

        # Append to events log
        with self.events_file.open("a") as f:
            f.write(json.dumps(event) + "\n")

        logger.info(
            f"Dataset update logged: {dataset_uri} by {dag_id}.{task_id} at {event['timestamp']}"
        )

        # Update metrics file
        self._update_metrics(dataset_uri, event)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _get_s3_file_timestamp(self, dataset_uri: str) -> datetime | None:
        """Get actual file modification timestamp from S3.

        Args:
            dataset_uri: S3 URI (e.g., s3://demand-forecasting/01_raw/raw_data_full.parquet)

        Returns:
            File modification timestamp or None if file doesn't exist
        """
        if not self.fs:
            return None

        try:
            # Convert S3 URI to S3FS path
            if dataset_uri.startswith("s3://"):
                # Remove s3:// prefix and extract bucket and path
                uri_parts = dataset_uri.replace("s3://", "").split("/", 1)
                bucket = uri_parts[0]
                path = uri_parts[1] if len(uri_parts) > 1 else ""

                # Construct correct S3FS path
                if bucket != self.s3_bucket:
                    logger.warning(
                        f"Dataset bucket {bucket} != configured bucket {self.s3_bucket}"
                    )

                s3_path = f"{bucket}/{path}"
            else:
                s3_path = f"{self.s3_bucket}/{dataset_uri.lstrip('/')}"

            # Get file info
            file_info = self.fs.stat(s3_path)
            return datetime.fromtimestamp(file_info["LastModified"].timestamp())

        except Exception as e:
            logger.debug(f"Could not get S3 timestamp for {dataset_uri}: {e}")
            return None

    def check_dataset_freshness(
        self, dataset_uri: str, max_age_hours: int = 24, alert: bool = True
    ) -> tuple[bool, float | None]:
        """Check if dataset is fresh (updated within max_age_hours).
        Now checks actual S3 file timestamps first, falls back to logged metrics.

        Args:
            dataset_uri: URI of the dataset to check
            max_age_hours: Maximum acceptable age in hours
            alert: Whether to log a warning if stale

        Returns:
            Tuple of (is_fresh, hours_since_update)
        """
        # First try to get actual S3 file timestamp
        s3_timestamp = self._get_s3_file_timestamp(dataset_uri)

        if s3_timestamp:
            # Use actual S3 file timestamp
            now = datetime.utcnow()
            hours_since_update = (now - s3_timestamp).total_seconds() / 3600
            is_fresh = hours_since_update <= max_age_hours

            logger.info(
                f"S3 freshness check for {dataset_uri}: {hours_since_update:.1f}h old (S3 timestamp)"
            )

            # Update metrics with S3 timestamp for consistency
            self._update_s3_timestamp(dataset_uri, s3_timestamp)

        else:
            # Fall back to logged metrics
            logger.debug(f"Using logged metrics for {dataset_uri} (S3 check failed)")
            metrics = self._load_metrics()

            if dataset_uri not in metrics:
                logger.warning(f"No update history found for dataset: {dataset_uri}")
                return False, None

            last_update_str = metrics[dataset_uri].get("last_update")
            if not last_update_str:
                logger.warning(f"No last_update timestamp for dataset: {dataset_uri}")
                return False, None

            last_update = datetime.fromisoformat(last_update_str)
            now = datetime.utcnow()
            hours_since_update = (now - last_update).total_seconds() / 3600
            is_fresh = hours_since_update <= max_age_hours

        if not is_fresh and alert:
            logger.warning(
                f"⚠️  STALE DATA ALERT: Dataset {dataset_uri} is {hours_since_update:.1f} hours old "
                f"(threshold: {max_age_hours} hours)."
            )

        return is_fresh, hours_since_update

    def log_dataset_metrics(
        self,
        dataset_uri: str,
        metrics: dict[str, Any],
        task_id: str | None = None,
        dag_id: str | None = None,
    ):
        """Log quality metrics for a dataset.

        Args:
            dataset_uri: URI of the dataset
            metrics: Dictionary of metrics (e.g., {"rows": 1000, "missing_pct": 0.02})
            task_id: Optional task ID that produced metrics
            dag_id: Optional DAG ID
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "dataset_uri": dataset_uri,
            "event_type": "metrics_update",
            "dag_id": dag_id,
            "task_id": task_id,
            "metrics": metrics,
        }

        # Append to events log
        with self.events_file.open("a") as f:
            f.write(json.dumps(event) + "\n")

        logger.info(f"Dataset metrics logged: {dataset_uri} - {metrics}")

        # Update metrics summary
        self._update_metrics_summary(dataset_uri, metrics)

    def get_dataset_history(
        self, dataset_uri: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get update history for a dataset.

        Args:
            dataset_uri: URI of the dataset
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries, newest first
        """
        if not self.events_file.exists():
            return []

        events = []
        with self.events_file.open() as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event.get("dataset_uri") == dataset_uri:
                        events.append(event)
                except json.JSONDecodeError:
                    continue

        # Return newest first, limited
        return sorted(events, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_dataset_statistics(self, dataset_uri: str) -> dict[str, Any]:
        """Get statistics for a dataset (update frequency, avg size, etc.).

        Args:
            dataset_uri: URI of the dataset

        Returns:
            Dictionary of statistics
        """
        history = self.get_dataset_history(dataset_uri, limit=1000)

        if not history:
            return {"error": "No history found"}

        # Calculate statistics
        update_events = [e for e in history if e.get("event_type") == "dataset_update"]

        stats = {
            "dataset_uri": dataset_uri,
            "total_updates": len(update_events),
            "first_update": update_events[-1]["timestamp"] if update_events else None,
            "last_update": update_events[0]["timestamp"] if update_events else None,
        }

        # Calculate update frequency
        if len(update_events) >= 2:
            timestamps = [datetime.fromisoformat(e["timestamp"]) for e in update_events]
            time_diffs = [
                (timestamps[i] - timestamps[i + 1]).total_seconds() / 3600
                for i in range(len(timestamps) - 1)
            ]
            stats["avg_update_frequency_hours"] = sum(time_diffs) / len(time_diffs)
            stats["min_update_frequency_hours"] = min(time_diffs)
            stats["max_update_frequency_hours"] = max(time_diffs)

        # Get latest metrics
        metrics_events = [e for e in history if e.get("event_type") == "metrics_update"]
        if metrics_events:
            stats["latest_metrics"] = metrics_events[0].get("metrics", {})

        return stats

    def check_all_datasets_freshness(
        self, max_age_hours: int = 24
    ) -> dict[str, tuple[bool, float | None]]:
        """Check freshness for all tracked datasets.

        Args:
            max_age_hours: Maximum acceptable age in hours

        Returns:
            Dictionary mapping dataset_uri to (is_fresh, hours_since_update)
        """
        metrics = self._load_metrics()
        results = {}

        for dataset_uri in metrics:
            results[dataset_uri] = self.check_dataset_freshness(
                dataset_uri, max_age_hours, alert=False
            )

        return results

    def _update_s3_timestamp(self, dataset_uri: str, timestamp: datetime):
        """Update metrics with S3 timestamp for consistency.

        Args:
            dataset_uri: URI of the dataset
            timestamp: S3 file modification timestamp
        """
        try:
            metrics = self._load_metrics()
            if dataset_uri not in metrics:
                metrics[dataset_uri] = {}

            metrics[dataset_uri]["last_update"] = timestamp.isoformat()
            metrics[dataset_uri]["last_s3_check"] = datetime.utcnow().isoformat()

            with self.metrics_file.open("w") as f:
                json.dump(metrics, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to update S3 timestamp for {dataset_uri}: {e}")

    def get_stale_datasets(self, max_age_hours: int = 24) -> list[dict[str, Any]]:
        """Get list of stale datasets (older than max_age_hours).

        Args:
            max_age_hours: Maximum acceptable age in hours

        Returns:
            List of dictionaries with dataset info
        """
        freshness_results = self.check_all_datasets_freshness(max_age_hours)
        stale = []

        for dataset_uri, (is_fresh, hours_old) in freshness_results.items():
            if not is_fresh and hours_old is not None:
                stale.append(
                    {
                        "dataset_uri": dataset_uri,
                        "hours_since_update": round(hours_old, 2),
                        "threshold_hours": max_age_hours,
                    }
                )

        return sorted(stale, key=lambda x: x["hours_since_update"], reverse=True)

    def generate_freshness_report(self, max_age_hours: int = 24) -> str:
        """Generate a human-readable freshness report for all datasets.

        Args:
            max_age_hours: Maximum acceptable age in hours

        Returns:
            Formatted report string
        """
        freshness_results = self.check_all_datasets_freshness(max_age_hours)

        report = ["=" * 80]
        report.append("DATASET FRESHNESS REPORT")
        report.append(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        report.append(f"Freshness Threshold: {max_age_hours} hours")
        report.append("=" * 80)
        report.append("")

        fresh_count = sum(1 for is_fresh, _ in freshness_results.values() if is_fresh)
        total_count = len(freshness_results)

        report.append(f"Summary: {fresh_count}/{total_count} datasets are fresh")
        report.append("")

        for dataset_uri, (is_fresh, hours_old) in freshness_results.items():
            status = "✅ FRESH" if is_fresh else "⚠️  STALE"
            hours_str = f"{hours_old:.1f}h" if hours_old is not None else "N/A"
            report.append(f"{status} | {hours_str:>8} | {dataset_uri}")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def export_metrics_to_csv(self, output_path: str):
        """Export dataset metrics to CSV for analysis.

        Args:
            output_path: Path to save CSV file
        """
        if not self.events_file.exists():
            logger.warning("No events file found, cannot export")
            return

        events = []
        with self.events_file.open() as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        if not events:
            logger.warning("No events to export")
            return

        df = pd.json_normalize(events)
        df.to_csv(output_path, index=False)
        logger.info(f"Exported {len(events)} events to {output_path}")

    def _load_metrics(self) -> dict[str, Any]:
        """Load metrics from JSON file."""
        if not self.metrics_file.exists():
            return {}

        try:
            with self.metrics_file.open() as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Corrupted metrics file, starting fresh")
            return {}

    def _save_metrics(self, metrics: dict[str, Any]):
        """Save metrics to JSON file."""
        with self.metrics_file.open("w") as f:
            json.dump(metrics, f, indent=2)

    def _update_metrics(self, dataset_uri: str, event: dict[str, Any]):
        """Update metrics summary with new event."""
        metrics = self._load_metrics()

        if dataset_uri not in metrics:
            metrics[dataset_uri] = {
                "first_update": event["timestamp"],
                "update_count": 0,
            }

        metrics[dataset_uri]["last_update"] = event["timestamp"]
        metrics[dataset_uri]["update_count"] = (
            metrics[dataset_uri].get("update_count", 0) + 1
        )
        metrics[dataset_uri]["last_task"] = event.get("task_id")
        metrics[dataset_uri]["last_dag"] = event.get("dag_id")

        if event.get("metadata"):
            metrics[dataset_uri]["last_metadata"] = event["metadata"]

        self._save_metrics(metrics)

    def _update_metrics_summary(self, dataset_uri: str, new_metrics: dict[str, Any]):
        """Update metrics summary with new quality metrics."""
        metrics = self._load_metrics()

        if dataset_uri not in metrics:
            metrics[dataset_uri] = {}

        if "metrics_history" not in metrics[dataset_uri]:
            metrics[dataset_uri]["metrics_history"] = []

        metrics[dataset_uri]["metrics_history"].append(
            {"timestamp": datetime.utcnow().isoformat(), "metrics": new_metrics}
        )

        # Keep only last 100 metrics
        metrics[dataset_uri]["metrics_history"] = metrics[dataset_uri][
            "metrics_history"
        ][-100:]

        metrics[dataset_uri]["latest_metrics"] = new_metrics

        self._save_metrics(metrics)


def create_monitor(
    metrics_dir: str = "/opt/airflow/data/dataset_metrics",
) -> DatasetMonitor:
    """Factory function to create a DatasetMonitor instance.

    Args:
        metrics_dir: Directory to store metrics

    Returns:
        DatasetMonitor instance
    """
    return DatasetMonitor(metrics_dir=metrics_dir)


# Convenience functions for common operations
def check_freshness(dataset_uri: str, max_age_hours: int = 24) -> bool:
    """Quick check if a dataset is fresh.

    Args:
        dataset_uri: URI of the dataset
        max_age_hours: Maximum acceptable age

    Returns:
        True if fresh, False if stale
    """
    monitor = create_monitor()
    is_fresh, _ = monitor.check_dataset_freshness(dataset_uri, max_age_hours)
    return is_fresh


def log_update(
    dataset_uri: str,
    task_id: str,
    dag_id: str,
    run_id: str,
    metadata: dict[str, Any] | None = None,
):
    """Quick log of a dataset update.

    Args:
        dataset_uri: URI of the dataset
        task_id: Task ID
        dag_id: DAG ID
        run_id: Run ID
        metadata: Optional metadata
    """
    monitor = create_monitor()
    monitor.log_dataset_update(dataset_uri, task_id, dag_id, run_id, metadata)


def get_stale_datasets(max_age_hours: int = 24) -> list[dict[str, Any]]:
    """Get list of stale datasets.

    Args:
        max_age_hours: Maximum acceptable age

    Returns:
        List of stale dataset info
    """
    monitor = create_monitor()
    return monitor.get_stale_datasets(max_age_hours)
