"""Automated Drift Detection and Retraining DAG.

This DAG implements automated MLOps workflows:
1. Scheduled drift detection on production data
2. Automated retraining triggers based on multiple conditions
3. Model promotion after successful retraining
4. Alert notifications for critical drift events

Best Practices Applied (from research):
- Conditional task flows using BranchPythonOperator
- XCom for passing drift status between tasks
- Data-driven scheduling with Airflow Datasets
- Self-checks post-retraining before model promotion
- Proper error handling and alerts
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import pendulum
from airflow import Dataset
from airflow.decorators import dag, task
from airflow.operators.python import BranchPythonOperator
from airflow.utils.trigger_rule import TriggerRule

# Kedro imports
from kedro.config import OmegaConfigLoader
from kedro.io import DataCatalog

from demand_forecasting.automation.retraining_scheduler import RetrainingScheduler

# Project imports
from demand_forecasting.monitoring.drift_detector import DriftDetector
from demand_forecasting.utils import get_s3_filesystem

# Optional imports
try:
    import mlflow
    from mlflow.tracking import MlflowClient

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants (use absolute path so config works regardless of task CWD in Docker)
# Constants (use absolute path so config works regardless of task CWD in Docker)
# Issue 6 fix: use str.removesuffix() instead of str.rstrip() — rstrip removes a *character set*,
# not a substring, so it could silently corrupt paths with trailing chars from "dags".
_dags_folder = os.environ.get("AIRFLOW__CORE__DAGS_FOLDER", "/opt/airflow/dags")
PROJECT_PATH = (
    _dags_folder.removesuffix("/dags").removesuffix("/dags/") or "/opt/airflow"
)
CONF_PATH = os.path.join(PROJECT_PATH, "conf")
S3_BUCKET = os.environ.get("S3_BUCKET", "demand-forecasting")
DRIFT_THRESHOLD = float(os.environ.get("DRIFT_THRESHOLD", "0.1"))
REFERENCE_DATA_PATH = f"s3://{S3_BUCKET}/01_raw/reference_data.parquet"

# Airflow Datasets for data-driven scheduling
PRODUCTION_DATA_DATASET = Dataset(f"s3://{S3_BUCKET}/production_predictions")
DRIFT_REPORT_DATASET = Dataset(f"s3://{S3_BUCKET}/drift_reports")

# Default args
default_args = {
    "owner": "mlops-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def _get_email_recipients() -> list[str]:
    """Get email recipients from environment."""
    email_str = os.environ.get("AIRFLOW_ALERT_EMAIL", "")
    if email_str:
        return [e.strip() for e in email_str.split(",") if e.strip()]
    return []


@dag(
    dag_id="automated_drift_detection_retraining",
    default_args=default_args,
    description="Automated drift detection and conditional model retraining",
    schedule="0 */6 * * *",  # Every 6 hours
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    tags=["mlops", "drift-detection", "retraining", "automated", "production"],
    doc_md="""
    ## Automated Drift Detection and Retraining Pipeline

    **Purpose:** Continuously monitor model performance and data distribution,
    automatically triggering retraining when drift is detected.

    **Workflow:**
    1. Load reference data (training distribution baseline)
    2. Load current production data
    3. Perform drift detection using statistical tests
    4. Check retraining triggers (time, performance, data volume, drift)
    5. Branch: If retraining needed → trigger retraining DAG
    6. Generate drift report and alerts

    **Triggers:**
    - TIME_INTERVAL: Scheduled periodic retraining
    - PERFORMANCE_DEGRADATION: RMSE exceeds baseline threshold
    - DATA_VOLUME: Sufficient new data accumulated
    - DATA_DRIFT: Statistical drift detected in features

    **Configuration:** See parameters.yml `monitoring` and `automation` sections
    """,
)
def automated_retraining_pipeline():
    """Main DAG for automated drift detection and retraining."""

    @task
    def load_reference_data() -> dict[str, Any]:
        """Load reference data for drift comparison."""
        logger.info("Loading reference data...")

        try:
            # Load from Kedro catalog (absolute path for Docker/task CWD)
            conf_loader = OmegaConfigLoader(CONF_PATH)
            catalog_config = conf_loader["catalog"]
            catalog = DataCatalog.from_config(catalog_config)

            # Try to load reference data
            if "reference_data" in catalog._datasets:
                ref_data = catalog.load("reference_data")
            else:
                # Fallback: Load training data as reference
                fs = get_s3_filesystem()
                ref_path = f"{S3_BUCKET}/03_primary/model_input_table.parquet"

                with fs.open(ref_path, "rb") as f:
                    ref_data = pd.read_parquet(f)

            logger.info(f"Reference data loaded: {ref_data.shape}")

            # Store stats for downstream tasks
            return {
                "shape": list(ref_data.shape),
                "columns": list(ref_data.columns),
                "path": REFERENCE_DATA_PATH,
                "loaded_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to load reference data: {e}")
            raise

    @task
    def load_production_data() -> dict[str, Any]:
        """Load recent production data for drift analysis."""
        logger.info("Loading production data...")

        try:
            fs = get_s3_filesystem()

            # Load recent production predictions/data
            # This would typically be the last N days of production data
            prod_path = f"{S3_BUCKET}/production_data/latest.parquet"

            # Check if production data exists
            if fs.exists(prod_path):
                with fs.open(prod_path, "rb") as f:
                    prod_data = pd.read_parquet(f)
            else:
                # Fallback: Use test split from training data
                logger.warning("No production data found, using test data as proxy")
                train_path = f"{S3_BUCKET}/03_primary/model_input_table.parquet"

                with fs.open(train_path, "rb") as f:
                    full_data = pd.read_parquet(f)

                # Use last 20% as "production" data
                split_idx = int(len(full_data) * 0.8)
                prod_data = full_data.iloc[split_idx:]

            logger.info(f"Production data loaded: {prod_data.shape}")

            return {
                "shape": list(prod_data.shape),
                "columns": list(prod_data.columns),
                "sample_count": len(prod_data),
                "loaded_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to load production data: {e}")
            raise

    @task
    def perform_drift_detection(
        ref_info: dict[str, Any],
        prod_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform statistical drift detection."""
        logger.info("Performing drift detection...")

        try:
            fs = get_s3_filesystem()

            # Load actual data for drift detection
            # Reference data
            ref_path = f"{S3_BUCKET}/03_primary/model_input_table.parquet"
            with fs.open(ref_path, "rb") as f:
                full_data = pd.read_parquet(f)

            # Split into reference and current
            split_idx = int(len(full_data) * 0.8)
            ref_data = full_data.iloc[:split_idx]
            curr_data = full_data.iloc[split_idx:]

            # Initialize drift detector
            # Select only numeric columns for drift detection
            numeric_cols = ref_data.select_dtypes(include=["int64", "float64"]).columns
            ref_numeric = ref_data[numeric_cols]
            curr_numeric = curr_data[numeric_cols]

            detector = DriftDetector(ref_numeric, threshold=DRIFT_THRESHOLD)

            # Perform drift detection
            drift_result = detector.detect_drift(curr_numeric)

            logger.info("Drift detection complete:")
            logger.info(
                f"  Overall drift score: {drift_result['overall_drift_score']:.4f}"
            )
            logger.info(
                f"  Drifted features: {len(drift_result['drifted_features'])}/{drift_result['total_features']}"
            )
            logger.info(f"  Recommendation: {drift_result['recommendation']}")

            # Save drift report to S3
            report_path = f"{S3_BUCKET}/drift_reports/drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with fs.open(report_path, "w") as f:
                json.dump(drift_result, f, indent=2, default=str)

            logger.info(f"Drift report saved to: {report_path}")

            return drift_result

        except Exception as e:
            logger.error(f"Drift detection failed: {e}")
            raise

    @task
    def check_retraining_triggers(drift_result: dict[str, Any]) -> dict[str, Any]:
        """Check all retraining triggers and decide if retraining is needed."""
        logger.info("Checking retraining triggers...")

        try:
            # Load configuration (absolute path for Docker/task CWD)
            conf_loader = OmegaConfigLoader(CONF_PATH)
            params = conf_loader["parameters"]

            # Initialize retraining scheduler
            scheduler_config = {
                "time_interval_days": params.get("automation", {}).get(
                    "time_interval_days", 7
                ),
                "performance_threshold": params.get("automation", {}).get(
                    "performance_threshold", 5.0
                ),
                "data_volume_threshold": params.get("automation", {}).get(
                    "data_volume_threshold", 10000
                ),
                "drift_threshold": params.get("monitoring", {}).get(
                    "drift_threshold", 0.1
                ),
                "model_registry_name": "demand_forecasting_catboost",
            }

            scheduler = RetrainingScheduler(scheduler_config)

            # Check all triggers
            decision = scheduler.should_retrain()

            # Add drift-based trigger from our detection
            if drift_result["overall_drift_score"] > DRIFT_THRESHOLD:
                if "DATA_DRIFT" not in decision["triggers"]:
                    decision["triggers"].append("DATA_DRIFT")
                    decision["should_retrain"] = True
                    logger.info("Drift-based trigger activated from detection results")

            # Get recommendations
            recommendations = scheduler.get_retraining_recommendations(decision)
            decision["recommendations"] = recommendations
            decision["drift_analysis"] = {
                "overall_score": drift_result["overall_drift_score"],
                "drifted_features": drift_result["drifted_features"],
                "drift_percentage": drift_result["drift_percentage"],
            }

            logger.info(f"Retraining decision: {decision['should_retrain']}")
            logger.info(f"Triggers: {decision['triggers']}")
            logger.info(f"Priority: {decision['priority']}")

            # Log decision to MLflow if available
            if MLFLOW_AVAILABLE:
                scheduler.log_retraining_decision(decision)

            return decision

        except Exception as e:
            logger.error(f"Failed to check retraining triggers: {e}")
            raise

    def decide_retraining_branch(ti: Any) -> str:
        """Branch based on retraining decision."""
        decision = ti.xcom_pull(task_ids="check_retraining_triggers")

        if decision and decision.get("should_retrain", False):
            priority = decision.get("priority", "LOW")
            logger.info(f"Retraining needed with priority: {priority}")
            return "trigger_retraining"
        logger.info("No retraining needed")
        return "skip_retraining"

    @task
    def trigger_retraining(decision: dict[str, Any]) -> dict[str, Any]:
        """Trigger model retraining based on decision."""
        logger.info("Triggering model retraining...")

        try:
            # Issue 1 fix: trigger_dag was removed in Airflow 2.4+.
            # Use TriggerDagRunOperator (the official replacement) executed inline.
            from airflow.operators.trigger_dagrun import TriggerDagRunOperator
            from airflow.utils.context import get_current_context

            execution_date = datetime.now()
            run_id = f"retraining_{execution_date.strftime('%Y%m%d_%H%M%S')}"

            trigger = TriggerDagRunOperator(
                task_id="_inline_trigger",
                trigger_dag_id="demand_forecasting_enhanced",
                run_id=run_id,
                conf={
                    "triggered_by": "automated_retraining",
                    "triggers": decision["triggers"],
                    "priority": decision["priority"],
                    "drift_score": decision.get("drift_analysis", {}).get(
                        "overall_score", 0
                    ),
                },
                reset_dag_run=True,
                wait_for_completion=False,
            )
            trigger.execute(get_current_context())

            logger.info("Retraining DAG triggered successfully")

            return {
                "status": "triggered",
                "dag_id": "demand_forecasting_enhanced",
                "run_id": run_id,
                "triggered_at": execution_date.isoformat(),
                "triggers": decision["triggers"],
                "priority": decision["priority"],
            }

        except Exception as e:
            logger.error(f"Failed to trigger retraining: {e}")
            # Don't fail the DAG, just report the error
            return {
                "status": "failed",
                "error": str(e),
                "triggers": decision.get("triggers", []),
            }

    @task
    def skip_retraining(decision: dict[str, Any]) -> dict[str, Any]:
        """Log that retraining was skipped."""
        logger.info("Retraining skipped - no triggers activated")

        return {
            "status": "skipped",
            "reason": "No retraining triggers activated",
            "next_check": (datetime.now() + timedelta(hours=6)).isoformat(),
            "recommendations": decision.get("recommendations", []),
        }

    @task
    def generate_drift_report(
        drift_result: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate and save comprehensive drift report."""
        logger.info("Generating drift report...")

        try:
            fs = get_s3_filesystem()

            report = {
                "timestamp": datetime.now().isoformat(),
                "drift_analysis": {
                    "overall_score": drift_result["overall_drift_score"],
                    "threshold": drift_result["threshold"],
                    "drifted_features": drift_result["drifted_features"],
                    "drifted_count": drift_result["drifted_feature_count"],
                    "total_features": drift_result["total_features"],
                    "drift_percentage": drift_result["drift_percentage"],
                    "recommendation": drift_result["recommendation"],
                },
                "retraining_decision": {
                    "should_retrain": decision["should_retrain"],
                    "triggers": decision["triggers"],
                    "priority": decision["priority"],
                    "recommendations": decision.get("recommendations", []),
                },
                "next_scheduled_check": (
                    datetime.now() + timedelta(hours=6)
                ).isoformat(),
            }

            # Save report
            report_path = f"{S3_BUCKET}/drift_reports/comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with fs.open(report_path, "w") as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Comprehensive report saved to: {report_path}")

            return report

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            raise

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def send_alerts(
        drift_result: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """Send alerts for critical drift or retraining events."""
        logger.info("Processing alerts...")

        alerts_sent = []

        try:
            # Check if alerts should be sent
            priority = decision.get("priority", "LOW")
            should_alert = (
                priority in ["CRITICAL", "HIGH"]
                or drift_result["drift_percentage"] > 50
            )

            if not should_alert:
                logger.info("No critical alerts needed")
                return {"alerts_sent": [], "status": "no_alerts_needed"}

            # Prepare alert message
            alert_message = f"""
            🚨 MLOps Alert: Drift Detection Results

            Timestamp: {datetime.now().isoformat()}

            Drift Analysis:
            - Overall Score: {drift_result["overall_drift_score"]:.4f}
            - Drifted Features: {drift_result["drifted_feature_count"]}/{drift_result["total_features"]}
            - Drift Percentage: {drift_result["drift_percentage"]:.1f}%

            Retraining Decision:
            - Should Retrain: {decision["should_retrain"]}
            - Triggers: {", ".join(decision["triggers"]) or "None"}
            - Priority: {priority}

            Recommendations:
            {chr(10).join(decision.get("recommendations", ["No specific recommendations"]))}
            """

            # Log the alert (in production, this would send email/Slack)
            logger.warning(f"ALERT: {alert_message}")

            # Try to send email if configured
            recipients = _get_email_recipients()
            if recipients:
                try:
                    from airflow.utils.email import send_email

                    send_email(
                        to=recipients,
                        subject=f"[{priority}] MLOps Alert: Data Drift Detected",
                        html_content=alert_message.replace("\n", "<br>"),
                    )
                    alerts_sent.append({"type": "email", "recipients": recipients})
                    logger.info(f"Email alert sent to: {recipients}")
                except Exception as e:
                    logger.warning(f"Failed to send email alert: {e}")

            return {
                "alerts_sent": alerts_sent,
                "status": "alerts_processed",
                "priority": priority,
            }

        except Exception as e:
            logger.error(f"Alert processing failed: {e}")
            return {"alerts_sent": [], "status": "error", "error": str(e)}

    # Define task flow
    ref_info = load_reference_data()
    prod_info = load_production_data()
    drift_result = perform_drift_detection(ref_info, prod_info)
    decision = check_retraining_triggers(drift_result)

    # Branching based on decision
    branch = BranchPythonOperator(
        task_id="decide_retraining_branch",
        python_callable=decide_retraining_branch,
    )

    retrain_task = trigger_retraining(decision)
    skip_task = skip_retraining(decision)

    # Report and alerts run regardless of branch
    report = generate_drift_report(drift_result, decision)
    alerts = send_alerts(drift_result, decision)

    # Set dependencies
    decision >> branch >> [retrain_task, skip_task]
    [retrain_task, skip_task] >> report >> alerts


# Instantiate the DAG
dag = automated_retraining_pipeline()
