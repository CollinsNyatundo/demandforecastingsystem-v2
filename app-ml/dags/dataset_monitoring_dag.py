"""Dataset Monitoring and Alerting DAG.

This DAG monitors all datasets in the demand forecasting pipeline:
- Checks dataset freshness (last update time)
- Validates data quality metrics
- Sends alerts for stale or problematic datasets
- Generates daily freshness reports

Best Practices Implemented:
- Regular monitoring schedule (hourly)
- Email alerts for stale data
- Comprehensive reporting
- Independent from main ML pipeline
"""

import logging
import os
from datetime import datetime, timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.utils.email import send_email

# Dataset monitoring utilities
from demand_forecasting.utils import (
    DatasetMonitor,
    check_freshness,
    create_monitor,
)

logger = logging.getLogger(__name__)

# Dataset URIs to monitor (matches Enhanced DAG outputs)
MONITORED_DATASETS = {
    "raw_data": {
        "uri": "s3://demand-forecasting/01_raw/raw_data_full.parquet",
        "max_age_hours": 24,
        "critical": True,
    },
    "preprocessed_data": {
        "uri": "s3://demand-forecasting/02_intermediate/preprocessed_data.parquet",
        "max_age_hours": 24,
        "critical": False,
    },
    "model_input": {
        "uri": "s3://demand-forecasting/03_primary/model_input.parquet",
        "max_age_hours": 24,
        "critical": False,
    },
    "trained_model_latest": {
        "uri": "s3://demand-forecasting/06_models/regressor.pickle",
        "max_age_hours": 48,  # Models can be older
        "critical": True,
    },
    "trained_model_timestamped": {
        "uri": "s3://demand-forecasting/06_models/regressor_",  # Prefix for timestamped models
        "max_age_hours": 48,
        "critical": True,
        "is_prefix": True,  # Flag to indicate this is a prefix, not exact file
    },
}


def _check_prefix_freshness(
    monitor: DatasetMonitor, prefix_uri: str, max_age_hours: int
) -> tuple[bool, float]:
    """Check freshness of datasets matching a prefix (for timestamped models).

    Args:
        monitor: DatasetMonitor instance
        prefix_uri: S3 prefix URI (e.g., s3://demand-forecasting/06_models/regressor_)
        max_age_hours: Maximum age in hours

    Returns:
        Tuple of (is_fresh, hours_old_of_newest_file)
    """
    if not monitor.fs:
        logger.warning(
            f"S3 filesystem not available for prefix monitoring: {prefix_uri}"
        )
        return False, float("inf")

    try:
        # Convert S3 URI to S3FS path
        if prefix_uri.startswith("s3://"):
            uri_parts = prefix_uri.replace("s3://", "").split("/", 1)
            bucket = uri_parts[0]
            path_prefix = uri_parts[1] if len(uri_parts) > 1 else ""
            s3_prefix = f"{bucket}/{path_prefix}"
        else:
            s3_prefix = f"{monitor.s3_bucket}/{prefix_uri.lstrip('/')}"

        # List files with the prefix
        files = monitor.fs.glob(f"{s3_prefix}*.pickle")

        if not files:
            logger.info(f"No files found for prefix: {prefix_uri}")
            return False, float("inf")

        # Find the newest file
        newest_time = None
        newest_file = None

        for file_path in files:
            try:
                file_info = monitor.fs.stat(file_path)
                file_time = datetime.fromtimestamp(
                    file_info["LastModified"].timestamp()
                )
                if newest_time is None or file_time > newest_time:
                    newest_time = file_time
                    newest_file = file_path
            except Exception as e:
                logger.debug(f"Could not stat file {file_path}: {e}")
                continue

        if newest_time is None:
            logger.warning(
                f"Could not get timestamps for any files in prefix: {prefix_uri}"
            )
            return False, float("inf")

        # Calculate age
        now = datetime.now()
        hours_old = (now - newest_time).total_seconds() / 3600
        is_fresh = hours_old <= max_age_hours

        logger.info(
            f"Prefix {prefix_uri}: newest file {newest_file.split('/')[-1]} is {hours_old:.1f}h old"
        )
        return is_fresh, hours_old

    except Exception as e:
        logger.error(f"Error checking prefix freshness for {prefix_uri}: {e}")
        return False, float("inf")


# Get alert emails from environment variable
# IMPORTANT: Set AIRFLOW_ALERT_EMAIL in production - no hardcoded fallback
_alert_email = os.getenv("AIRFLOW_ALERT_EMAIL", "")
if not _alert_email:
    logging.warning(
        "AIRFLOW_ALERT_EMAIL not set. Email alerts will be disabled. "
        "Set this environment variable to enable email notifications."
    )
    ALERT_EMAILS = []
else:
    ALERT_EMAILS = [e.strip() for e in _alert_email.split(",") if e.strip()]

default_args = {
    "owner": "data-ops",
    "start_date": pendulum.today("UTC").add(days=-1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email": ALERT_EMAILS,
    "email_on_failure": True,
    "email_on_retry": False,
}


@dag(
    dag_id="dataset_monitoring",
    default_args=default_args,
    schedule="@hourly",  # Run every hour
    catchup=False,
    tags=["monitoring", "datasets", "ops"],
    doc_md="""
    ## Dataset Monitoring DAG

    **Purpose:** Monitor data freshness and quality across all pipeline datasets

    **Schedule:** Hourly checks for data staleness

    **Alerts:**
    - Email notifications for stale critical datasets
    - Daily freshness reports
    - Quality metric tracking

    **Monitored Datasets:**
    1. Raw data (critical, max age: 24h)
    2. Preprocessed data (max age: 24h)
    3. Model input (max age: 24h)
    4. Search space (max age: 24h)
    5. Trained model (critical, max age: 48h)

    **Contact:** Set AIRFLOW_ALERT_EMAIL environment variable for alerts
    **Alerts:** Email on stale critical datasets (requires AIRFLOW_ALERT_EMAIL)
    """,
)
def dataset_monitoring_dag():
    @task()
    def check_dataset_freshness():
        """Check freshness of all monitored datasets.

        Returns:
            Dictionary of dataset freshness results
        """
        monitor = create_monitor()
        results = {}

        for name, config in MONITORED_DATASETS.items():
            uri = config["uri"]
            max_age = config["max_age_hours"]
            is_prefix = config.get("is_prefix", False)

            if is_prefix:
                # Handle prefix-based monitoring (for timestamped models)
                is_fresh, hours_old = _check_prefix_freshness(monitor, uri, max_age)
            else:
                # Handle exact file monitoring
                is_fresh, hours_old = monitor.check_dataset_freshness(
                    uri, max_age, alert=True
                )

            results[name] = {
                "uri": uri,
                "is_fresh": is_fresh,
                "hours_old": hours_old,
                "max_age_hours": max_age,
                "critical": config["critical"],
                "is_prefix": is_prefix,
            }

            logger.info(
                f"Dataset {name}: {'✅ Fresh' if is_fresh else '⚠️  Stale'} "
                f"({hours_old:.1f}h old, threshold: {max_age}h)"
                + (" [prefix]" if is_prefix else "")
            )

        return results

    @task()
    def identify_stale_datasets(freshness_results: dict):
        """Identify stale datasets that need attention.

        Args:
            freshness_results: Results from check_dataset_freshness

        Returns:
            List of stale dataset information
        """
        stale = []

        for name, result in freshness_results.items():
            if not result["is_fresh"]:
                stale.append(
                    {
                        "name": name,
                        "uri": result["uri"],
                        "hours_old": result["hours_old"],
                        "max_age_hours": result["max_age_hours"],
                        "critical": result["critical"],
                    }
                )

        if stale:
            logger.warning(f"Found {len(stale)} stale datasets")
            for ds in stale:
                level = "🔴 CRITICAL" if ds["critical"] else "⚠️  WARNING"
                logger.warning(
                    f"{level} - {ds['name']}: {ds['hours_old']:.1f}h old "
                    f"(threshold: {ds['max_age_hours']}h)"
                )
        else:
            logger.info("✅ All datasets are fresh!")

        return stale

    @task()
    def send_stale_data_alerts(stale_datasets: list) -> str:
        """Send email alerts for stale datasets.

        Args:
            stale_datasets: List of stale dataset information
        """
        if not stale_datasets:
            logger.info("No stale datasets, skipping alerts")
            return "No alerts needed"

        # Separate critical and non-critical
        critical = [ds for ds in stale_datasets if ds["critical"]]
        warnings = [ds for ds in stale_datasets if not ds["critical"]]

        # Build email content
        email_lines = [
            "<h2>⚠️  Dataset Staleness Alert</h2>",
            f"<p><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>",
            f"<p><strong>Total Stale Datasets:</strong> {len(stale_datasets)}</p>",
        ]

        if critical:
            email_lines.append("<h3>🔴 CRITICAL - Immediate Action Required</h3>")
            email_lines.append("<table border='1' cellpadding='5' cellspacing='0'>")
            email_lines.append(
                "<tr><th>Dataset</th><th>Age</th><th>Threshold</th><th>URI</th></tr>"
            )
            for ds in critical:
                email_lines.append(
                    f"<tr>"
                    f"<td><strong>{ds['name']}</strong></td>"
                    f"<td>{ds['hours_old']:.1f} hours</td>"
                    f"<td>{ds['max_age_hours']} hours</td>"
                    f"<td><code>{ds['uri']}</code></td>"
                    f"</tr>"
                )
            email_lines.append("</table>")

        if warnings:
            email_lines.append("<h3>⚠️  Warnings - Monitor Closely</h3>")
            email_lines.append("<table border='1' cellpadding='5' cellspacing='0'>")
            email_lines.append(
                "<tr><th>Dataset</th><th>Age</th><th>Threshold</th><th>URI</th></tr>"
            )
            for ds in warnings:
                email_lines.append(
                    f"<tr>"
                    f"<td>{ds['name']}</td>"
                    f"<td>{ds['hours_old']:.1f} hours</td>"
                    f"<td>{ds['max_age_hours']} hours</td>"
                    f"<td><code>{ds['uri']}</code></td>"
                    f"</tr>"
                )
            email_lines.append("</table>")

        email_lines.extend(
            [
                "<h3>Recommended Actions</h3>",
                "<ul>",
                "<li>Check if upstream data sources are running</li>",
                "<li>Verify DAG execution status</li>",
                "<li>Review Airflow logs for errors</li>",
                "<li>Check MinIO bucket for data presence</li>",
                "</ul>",
                "<p><strong>Airflow UI:</strong> <a href='http://localhost:8081'>http://localhost:8081</a></p>",  # host port 8081 maps to container 8080
            ]
        )

        email_content = "\n".join(email_lines)

        # Send email
        try:
            send_email(
                to=ALERT_EMAILS,
                subject=f"[AIRFLOW ALERT] {len(critical)} Critical Dataset(s) Stale",
                html_content=email_content,
            )
            logger.info(f"Stale data alert email sent to {', '.join(ALERT_EMAILS)}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e!s}")
            # Don't fail the task if email fails
            return f"Email failed: {e!s}"

        return f"Alert sent for {len(stale_datasets)} stale datasets"

    @task()
    def generate_daily_report(freshness_results: dict):
        """Generate comprehensive daily freshness report.

        Args:
            freshness_results: Results from check_dataset_freshness

        Returns:
            Report summary
        """
        monitor = create_monitor()

        # Generate text report
        report = monitor.generate_freshness_report(max_age_hours=24)

        # Log the report
        logger.info("\n" + report)

        # Save to file
        report_file = (
            f"/opt/airflow/data/dataset_metrics/freshness_report_"
            f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        try:
            with open(report_file, "w") as f:
                f.write(report)
            logger.info(f"Report saved to {report_file}")
        except Exception as e:
            logger.warning(f"Could not save report: {e!s}")

        # Generate statistics for each dataset
        stats = {}
        for name, result in freshness_results.items():
            uri = result["uri"]
            ds_stats = monitor.get_dataset_statistics(uri)
            stats[name] = ds_stats

        logger.info(f"Generated statistics for {len(stats)} datasets")

        return {
            "report_file": report_file,
            "total_datasets": len(freshness_results),
            "fresh_datasets": sum(
                1 for r in freshness_results.values() if r["is_fresh"]
            ),
        }

    @task()
    def export_metrics() -> str | None:
        """Export dataset metrics to CSV for analysis.

        Returns:
            Export status
        """
        monitor = create_monitor()

        timestamp = datetime.utcnow().strftime("%Y%m%d")
        csv_file = f"/opt/airflow/data/dataset_metrics/dataset_events_{timestamp}.csv"

        try:
            monitor.export_metrics_to_csv(csv_file)
            logger.info(f"Metrics exported to {csv_file}")
            return f"Exported to {csv_file}"
        except Exception as e:
            logger.error(f"Failed to export metrics: {e!s}")
            return f"Export failed: {e!s}"

    @task.branch()
    def should_send_daily_report() -> str:
        """Decide if we should send daily report (only at 8 AM UTC).

        Returns:
            Task ID to execute next
        """
        current_hour = datetime.utcnow().hour

        # Send daily report at 8 AM UTC
        if current_hour == 8:
            return "send_daily_summary_email"
        return "skip_daily_report"

    @task()
    def send_daily_summary_email(report_summary: dict) -> str:
        """Send daily summary email with all dataset statistics.

        Args:
            report_summary: Summary from generate_daily_report
        """
        monitor = create_monitor()

        email_lines = [
            "<h2>📊 Daily Dataset Health Report</h2>",
            f"<p><strong>Date:</strong> {datetime.utcnow().strftime('%Y-%m-%d')}</p>",
            f"<p><strong>Total Datasets Monitored:</strong> {report_summary['total_datasets']}</p>",
            f"<p><strong>Fresh Datasets:</strong> {report_summary['fresh_datasets']}/{report_summary['total_datasets']}</p>",
            "<h3>Dataset Statistics</h3>",
            "<table border='1' cellpadding='5' cellspacing='0'>",
            "<tr><th>Dataset</th><th>Status</th><th>Last Update</th><th>Total Updates</th></tr>",
        ]

        for name, config in MONITORED_DATASETS.items():
            stats = monitor.get_dataset_statistics(config["uri"])
            last_update = stats.get("last_update", "N/A")
            update_count = stats.get("update_count", 0)
            is_fresh = check_freshness(config["uri"], config["max_age_hours"])
            status = "✅ Fresh" if is_fresh else "⚠️  Stale"

            email_lines.append(
                f"<tr>"
                f"<td>{name}</td>"
                f"<td>{status}</td>"
                f"<td>{last_update}</td>"
                f"<td>{update_count}</td>"
                f"</tr>"
            )

        email_lines.append("</table>")
        email_lines.append(
            "<p><em>Full report available in Airflow logs and /opt/airflow/data/dataset_metrics/</em></p>"
        )

        email_content = "\n".join(email_lines)

        # Only send email if ALERT_EMAILS is configured
        if ALERT_EMAILS:
            try:
                send_email(
                    to=ALERT_EMAILS,
                    subject=f"[AIRFLOW] Daily Dataset Health Report - {datetime.utcnow().strftime('%Y-%m-%d')}",
                    html_content=email_content,
                )
                logger.info(f"Daily summary email sent to {ALERT_EMAILS}")
            except Exception as e:
                logger.error(f"Failed to send daily summary: {e!s}")
        else:
            logger.warning(
                "Skipping daily report email - AIRFLOW_ALERT_EMAIL not configured"
            )

        return "Daily report sent"

    @task()
    def skip_daily_report() -> str:
        """Placeholder task when daily report should be skipped."""
        logger.info("Skipping daily report (not scheduled time)")
        return "Skipped"

    # Define task dependencies
    freshness = check_dataset_freshness()
    stale = identify_stale_datasets(freshness)
    alerts = send_stale_data_alerts(stale)
    report = generate_daily_report(freshness)
    export = export_metrics()

    # Branch for daily report
    branch = should_send_daily_report()
    daily_email = send_daily_summary_email(report)
    skip = skip_daily_report()

    # Task flow
    freshness >> stale >> alerts
    freshness >> report >> branch >> [daily_email, skip]
    freshness >> export


# Instantiate the DAG
monitoring_dag = dataset_monitoring_dag()
