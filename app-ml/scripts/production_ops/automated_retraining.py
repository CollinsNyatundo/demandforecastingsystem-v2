#!/usr/bin/env python3
"""Automated Retraining Scheduler for Demand Forecasting.

Monitors multiple trigger conditions and initiates retraining when needed:
- Time-based: Scheduled intervals (daily, weekly, monthly)
- Performance-based: Model performance degradation
- Data-based: Significant data volume increase
- Drift-based: Data drift detection

Based on Priority 3 requirements and pg-aiguide best practices.

Usage:
    python scripts/production_ops/automated_retraining.py --check
    python scripts/production_ops/automated_retraining.py --schedule weekly
    python scripts/production_ops/automated_retraining.py --trigger-dag
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

# Optional MLflow import (graceful degradation)
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

Base = declarative_base()


class RetrainingRecord(Base):
    """SQLAlchemy model for retraining history."""

    __tablename__ = "retraining_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_timestamp = Column(DateTime, nullable=False, index=True)
    trigger_reason = Column(String(50), nullable=False, index=True)
    trigger_details = Column(JSON, nullable=True)
    dag_run_id = Column(String(255), nullable=True)
    dag_triggered = Column(Boolean, default=False)
    retraining_status = Column(String(50), default="pending")
    model_version = Column(String(100), nullable=True)
    performance_before = Column(Float, nullable=True)
    performance_after = Column(Float, nullable=True)
    completed_timestamp = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)


class RetrainingScheduler:
    """Automated retraining scheduler with multiple trigger conditions.

    Trigger Conditions:
    1. Time-based: Fixed schedule (daily, weekly, monthly)
    2. Performance-based: Model RMSE exceeds threshold
    3. Data-based: Training data size increased significantly
    4. Drift-based: Data drift detected in key features

    Attributes:
        storage_url: PostgreSQL connection string
        airflow_url: Airflow API base URL
        performance_threshold: RMSE threshold for performance trigger
        data_growth_threshold: % data increase for data trigger
        drift_threshold: Number of features with drift for drift trigger
    """

    def __init__(
        self,
        storage_url: str | None = None,
        airflow_url: str | None = None,
        performance_threshold: float = 55.0,
        data_growth_threshold: float = 0.20,
        drift_threshold: int = 3,
    ):
        """Initialize retraining scheduler.

        Args:
            storage_url: PostgreSQL URL (default: from env)
            airflow_url: Airflow API URL (default: from env)
            performance_threshold: RMSE threshold (default: 55.0)
            data_growth_threshold: Data growth % for trigger (default: 20%)
            drift_threshold: Min features with drift (default: 3)
        """
        self.performance_threshold = performance_threshold
        self.data_growth_threshold = data_growth_threshold
        self.drift_threshold = drift_threshold

        # Get storage URL from environment or parameter
        self.storage_url = storage_url or os.getenv(
            "DRIFT_STORAGE_URL", "postgresql://airflow:airflow@localhost:5432/optuna"
        )

        # Get Airflow URL
        self.airflow_url = airflow_url or os.getenv(
            "AIRFLOW_URL", "http://localhost:8080"
        )
        self.airflow_user = os.getenv("AIRFLOW_USERNAME", "admin")
        self.airflow_password = os.getenv("AIRFLOW_PASSWORD", "admin")

        # Create engine with connection pooling (PostgreSQL) or lightweight engine (SQLite)
        if self.storage_url.startswith("sqlite"):
            self.engine = create_engine(self.storage_url)
        else:
            self.engine = create_engine(
                self.storage_url,
                poolclass=QueuePool,
                pool_size=3,
                max_overflow=5,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "connect_timeout": 10,
                    "options": "-c statement_timeout=30000",
                },
            )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.Session = sessionmaker(bind=self.engine)

        logger.info("RetrainingScheduler initialized")
        logger.info(f"  Storage: {self.storage_url}")
        logger.info(f"  Airflow: {self.airflow_url}")
        logger.info(f"  Performance threshold: {self.performance_threshold}")
        logger.info(f"  Data growth threshold: {self.data_growth_threshold * 100}%")
        logger.info(f"  Drift threshold: {self.drift_threshold} features")

    def check_retraining_needed(self) -> tuple[bool, list[dict[str, Any]]]:
        """Check all trigger conditions and determine if retraining is needed.

        Returns:
            Tuple of (should_retrain, list of trigger reasons)
        """
        logger.info("🔍 Checking retraining triggers...")

        triggers = []

        # Check time-based trigger
        time_trigger = self._check_time_trigger()
        if time_trigger["should_trigger"]:
            triggers.append(time_trigger)

        # Check performance-based trigger
        performance_trigger = self._check_performance_trigger()
        if performance_trigger["should_trigger"]:
            triggers.append(performance_trigger)

        # Check data-based trigger
        data_trigger = self._check_data_trigger()
        if data_trigger["should_trigger"]:
            triggers.append(data_trigger)

        # Check drift-based trigger
        drift_trigger = self._check_drift_trigger()
        if drift_trigger["should_trigger"]:
            triggers.append(drift_trigger)

        should_retrain = len(triggers) > 0

        if should_retrain:
            logger.warning(f"⚠️  Retraining needed! {len(triggers)} trigger(s) fired:")
            for trigger in triggers:
                logger.warning(f"   • {trigger['reason']}: {trigger['details']}")
        else:
            logger.info("✅ No retraining needed at this time")

        return should_retrain, triggers

    def _check_time_trigger(self) -> dict[str, Any]:
        """Check if retraining is due based on time schedule.

        Looks for last retraining timestamp and compares to schedule.
        Default schedule: weekly (7 days)
        """
        session = self.Session()
        try:
            # Get last successful retraining
            last_retraining = (
                session.query(RetrainingRecord)
                .filter(RetrainingRecord.retraining_status == "completed")
                .order_by(RetrainingRecord.completed_timestamp.desc())
                .first()
            )

            if last_retraining is None:
                # Never retrained before
                return {
                    "should_trigger": True,
                    "reason": "time_based",
                    "details": "No previous retraining found",
                    "days_since_last": None,
                }

            days_since = (datetime.now() - last_retraining.completed_timestamp).days

            # Default schedule: 7 days
            schedule_days = int(os.getenv("RETRAINING_SCHEDULE_DAYS", "7"))

            should_trigger = days_since >= schedule_days

            return {
                "should_trigger": should_trigger,
                "reason": "time_based",
                "details": f"{days_since} days since last retraining (threshold: {schedule_days})",
                "days_since_last": days_since,
                "schedule_days": schedule_days,
            }

        finally:
            session.close()

    def _check_performance_trigger(self) -> dict[str, Any]:
        """Check if model performance has degraded below threshold.

        Queries MLflow or production metrics to get current RMSE.
        """
        try:
            # Try to get current production model performance
            # Option 1: Query MLflow (if available)
            mlflow_url = os.getenv("MLFLOW_TRACKING_URI")
            if mlflow_url:
                # TODO: Query MLflow for production model metrics
                current_rmse = self._get_mlflow_production_rmse()
            else:
                # Option 2: Query from retraining records
                current_rmse = self._get_latest_model_rmse()

            if current_rmse is None:
                return {
                    "should_trigger": False,
                    "reason": "performance_based",
                    "details": "No performance metrics available",
                    "current_rmse": None,
                }

            should_trigger = current_rmse > self.performance_threshold

            return {
                "should_trigger": should_trigger,
                "reason": "performance_based",
                "details": f"RMSE {current_rmse:.2f} {'>' if should_trigger else '<='} threshold {self.performance_threshold:.2f}",
                "current_rmse": current_rmse,
                "threshold": self.performance_threshold,
            }

        except Exception as e:
            logger.error(f"Error checking performance trigger: {e}")
            return {
                "should_trigger": False,
                "reason": "performance_based",
                "details": f"Error: {e!s}",
                "error": str(e),
            }

    def _check_data_trigger(self) -> dict[str, Any]:
        """Check if training data has grown significantly.

        Compares current data size to size at last retraining.
        """
        try:
            # Get current data size
            data_path = os.getenv(
                "TRAINING_DATA_PATH", "data/01_raw/superstore_train.csv"
            )

            if not os.path.exists(data_path):
                return {
                    "should_trigger": False,
                    "reason": "data_based",
                    "details": f"Training data not found: {data_path}",
                }

            current_size = len(pd.read_csv(data_path))

            # Get size at last retraining
            session = self.Session()
            try:
                last_retraining = (
                    session.query(RetrainingRecord)
                    .filter(RetrainingRecord.retraining_status == "completed")
                    .order_by(RetrainingRecord.completed_timestamp.desc())
                    .first()
                )

                if last_retraining is None:
                    # No previous retraining, can't compare
                    return {
                        "should_trigger": False,
                        "reason": "data_based",
                        "details": "No previous retraining to compare data size",
                        "current_size": current_size,
                    }

                metadata = last_retraining.metadata or {}
                previous_size = metadata.get("training_data_size")

                if previous_size is None:
                    return {
                        "should_trigger": False,
                        "reason": "data_based",
                        "details": "Previous data size not recorded",
                        "current_size": current_size,
                    }

                growth_rate = (current_size - previous_size) / previous_size
                should_trigger = growth_rate >= self.data_growth_threshold

                return {
                    "should_trigger": should_trigger,
                    "reason": "data_based",
                    "details": f"Data grew from {previous_size} to {current_size} rows ({growth_rate * 100:.1f}% growth)",
                    "current_size": current_size,
                    "previous_size": previous_size,
                    "growth_rate": growth_rate,
                    "threshold": self.data_growth_threshold,
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error checking data trigger: {e}")
            return {
                "should_trigger": False,
                "reason": "data_based",
                "details": f"Error: {e!s}",
                "error": str(e),
            }

    def _check_drift_trigger(self) -> dict[str, Any]:
        """Check if data drift has been detected in multiple features.

        Queries drift_records table for recent drift detections.
        """
        session = self.Session()
        try:
            # Check for drift in the last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)

            # Query for features with drift
            from detect_data_drift import DriftRecord

            recent_drift = (
                session.query(DriftRecord)
                .filter(DriftRecord.check_timestamp >= cutoff)
                .filter(DriftRecord.drift_detected)
                .all()
            )

            # Get unique features with drift
            features_with_drift = {r.feature_name for r in recent_drift}
            n_features_with_drift = len(features_with_drift)

            should_trigger = n_features_with_drift >= self.drift_threshold

            return {
                "should_trigger": should_trigger,
                "reason": "drift_based",
                "details": f"{n_features_with_drift} features with drift (threshold: {self.drift_threshold})",
                "features_with_drift": list(features_with_drift),
                "n_features": n_features_with_drift,
                "threshold": self.drift_threshold,
            }

        except Exception as e:
            logger.error(f"Error checking drift trigger: {e}")
            return {
                "should_trigger": False,
                "reason": "drift_based",
                "details": f"Error: {e!s}",
                "features_with_drift": [],
                "n_features": 0,
                "threshold": self.drift_threshold,
                "error": str(e),
            }
        finally:
            session.close()

    def trigger_retraining(
        self, triggers: list[dict[str, Any]], dry_run: bool = False
    ) -> str | None:
        """Trigger Airflow DAG for retraining.

        Args:
            triggers: List of trigger reasons
            dry_run: If True, don't actually trigger DAG

        Returns:
            DAG run ID if triggered, None otherwise
        """
        if dry_run:
            logger.info("🔵 DRY RUN: Would trigger retraining DAG")
            logger.info(f"   Triggers: {[t['reason'] for t in triggers]}")
            return None

        logger.info("🚀 Triggering retraining DAG...")

        # Prepare trigger details
        trigger_reason = ", ".join([t["reason"] for t in triggers])
        trigger_details = {
            "triggers": triggers,
            "timestamp": datetime.now().isoformat(),
        }

        # Record in database
        session = self.Session()
        record = None
        try:
            record = RetrainingRecord(
                trigger_timestamp=datetime.now(),
                trigger_reason=trigger_reason,
                trigger_details=trigger_details,
                dag_triggered=False,
                retraining_status="pending",
            )
            session.add(record)
            session.commit()

            # Get record ID
            record_id = record.id

        except Exception as e:
            session.rollback()
            logger.error(f"Error recording retraining trigger: {e}")
            raise
        finally:
            session.close()

        # Trigger Airflow DAG
        try:
            dag_run_id = self._trigger_airflow_dag(
                dag_id="demand_forecasting_enhanced",
                conf={"retraining_record_id": record_id, "triggers": trigger_details},
            )

            # Update record with DAG run ID
            session = self.Session()
            try:
                record = session.query(RetrainingRecord).get(record_id)
                record.dag_run_id = dag_run_id
                record.dag_triggered = True
                session.commit()
            finally:
                session.close()

            logger.info(f"✅ DAG triggered successfully: {dag_run_id}")
            return dag_run_id

        except Exception as e:
            logger.error(f"❌ Failed to trigger DAG: {e}")

            # Update record with error
            session = self.Session()
            try:
                record = session.query(RetrainingRecord).get(record_id)
                record.retraining_status = "failed"
                record.metadata = {"error": str(e)}
                session.commit()
            finally:
                session.close()

            raise

    def _trigger_airflow_dag(
        self, dag_id: str, conf: dict[str, Any] | None = None
    ) -> str:
        """Trigger Airflow DAG via REST API.

        Args:
            dag_id: DAG ID to trigger
            conf: Configuration dict to pass to DAG

        Returns:
            DAG run ID
        """
        url = f"{self.airflow_url}/api/v1/dags/{dag_id}/dagRuns"

        payload = {
            "conf": conf or {},
            "dag_run_id": f"retraining_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        }

        response = requests.post(
            url,
            json=payload,
            auth=(self.airflow_user, self.airflow_password),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code in [200, 201]:
            data = response.json()
            return data["dag_run_id"]
        logger.error(f"Airflow API error: {response.status_code}")
        logger.error(f"Response: {response.text}")
        raise Exception(f"Failed to trigger DAG: {response.text}")

    def _get_mlflow_production_rmse(self) -> float | None:
        """Query MLflow for production model RMSE."""
        if not MLFLOW_AVAILABLE:
            logger.warning(
                "MLflow not available. Cannot query production model metrics."
            )
            return None

        try:
            # Get MLflow configuration
            mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
            if not mlflow_tracking_uri:
                logger.warning("MLFLOW_TRACKING_URI not configured.")
                return None

            # Set tracking URI
            mlflow.set_tracking_uri(mlflow_tracking_uri)

            # Get experiment name
            experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "demand_forecasting")

            # Get experiment
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if not experiment:
                logger.warning(f"MLflow experiment '{experiment_name}' not found.")
                return None

            # Search for runs in the experiment
            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                filter_string="tags.model_type = 'CatBoost'",
                order_by=["attributes.start_time DESC"],
                max_results=10,
            )

            if runs.empty:
                logger.warning("No CatBoost model runs found in MLflow.")
                return None

            # Get the most recent successful run with RMSE metric
            for _, run in runs.iterrows():
                if "metrics.rmse" in run:
                    rmse = run["metrics.rmse"]
                    logger.info(f"Found production model RMSE from MLflow: {rmse:.4f}")
                    return rmse

            logger.warning("No RMSE metric found in recent MLflow runs.")
            return None

        except Exception as e:
            logger.error(f"Failed to query MLflow for production model RMSE: {e}")
            return None

    def _get_latest_model_rmse(self) -> float | None:
        """Get RMSE from latest retraining record."""
        session = self.Session()
        try:
            last_retraining = (
                session.query(RetrainingRecord)
                .filter(RetrainingRecord.retraining_status == "completed")
                .order_by(RetrainingRecord.completed_timestamp.desc())
                .first()
            )

            if last_retraining and last_retraining.performance_after:
                return last_retraining.performance_after

            return None

        finally:
            session.close()

    def get_retraining_history(self, days: int = 30) -> pd.DataFrame:
        """Retrieve retraining history from PostgreSQL.

        Args:
            days: Number of days to look back

        Returns:
            DataFrame with retraining history
        """
        session = self.Session()
        try:
            cutoff = datetime.now() - timedelta(days=days)

            records = (
                session.query(RetrainingRecord)
                .filter(RetrainingRecord.trigger_timestamp >= cutoff)
                .order_by(RetrainingRecord.trigger_timestamp.desc())
                .all()
            )

            if not records:
                logger.info("No retraining history found")
                return pd.DataFrame()

            data = [
                {
                    "timestamp": r.trigger_timestamp,
                    "reason": r.trigger_reason,
                    "dag_triggered": r.dag_triggered,
                    "dag_run_id": r.dag_run_id,
                    "status": r.retraining_status,
                    "model_version": r.model_version,
                    "performance_before": r.performance_before,
                    "performance_after": r.performance_after,
                    "completed": r.completed_timestamp,
                }
                for r in records
            ]

            df = pd.DataFrame(data)
            logger.info(f"Retrieved {len(df)} retraining records")

            return df

        finally:
            session.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Automated retraining scheduler for demand forecasting"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if retraining is needed (no action)",
    )
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="Check and trigger retraining if needed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't actually trigger DAG)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show retraining history",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days for history (default: 30)",
    )
    parser.add_argument(
        "--performance-threshold",
        type=float,
        default=55.0,
        help="RMSE threshold for performance trigger (default: 55.0)",
    )
    parser.add_argument(
        "--data-growth-threshold",
        type=float,
        default=0.20,
        help="Data growth threshold for data trigger (default: 0.20 = 20%%)",
    )
    parser.add_argument(
        "--drift-threshold",
        type=int,
        default=3,
        help="Min features with drift for drift trigger (default: 3)",
    )

    args = parser.parse_args()

    # Initialize scheduler
    scheduler = RetrainingScheduler(
        performance_threshold=args.performance_threshold,
        data_growth_threshold=args.data_growth_threshold,
        drift_threshold=args.drift_threshold,
    )

    # Show history if requested
    if args.history:
        history = scheduler.get_retraining_history(days=args.days)
        if not history.empty:

            # Summary
            (history["status"] == "completed").sum()
            (history["status"] == "failed").sum()
            (history["status"] == "pending").sum()

        else:
            pass
        return

    # Check if retraining needed
    should_retrain, triggers = scheduler.check_retraining_needed()

    if args.check:
        # Just check, don't trigger
        if should_retrain:
            for _trigger in triggers:
                pass
            sys.exit(1)  # Exit with error code to signal retraining needed
        else:
            sys.exit(0)

    elif args.trigger:
        # Trigger retraining if needed
        if should_retrain:
            try:
                dag_run_id = scheduler.trigger_retraining(
                    triggers=triggers, dry_run=args.dry_run
                )

                if dag_run_id:
                    pass
                elif args.dry_run:
                    for _trigger in triggers:
                        pass

                sys.exit(0)

            except Exception:
                sys.exit(1)
        else:
            sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
