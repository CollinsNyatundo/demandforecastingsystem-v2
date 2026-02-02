"""Automated retraining scheduler with multiple trigger types."""

import logging
from datetime import datetime, timedelta
from typing import Any

import mlflow
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Constants for magic values
DEFAULT_DAYS_INTERVAL = 2
DEFAULT_HOURS_INTERVAL = 4
MIN_PERFORMANCE_THRESHOLD = 0.05
DEFAULT_PERFORMANCE_THRESHOLD = 0.5
DEFAULT_DATA_VOLUME_THRESHOLD = 10000


class RetrainingScheduler:
    """Automated retraining with multiple trigger types."""

    def __init__(self, config: dict[str, Any]):
        self.time_interval_days = config.get("time_interval_days", 7)
        self.performance_threshold = config.get("performance_threshold", 5.0)
        self.data_volume_threshold = config.get("data_volume_threshold", 10000)
        self.drift_threshold = config.get("drift_threshold", 0.1)
        self.model_registry_name = config.get(
            "model_registry_name", "demand_forecasting"
        )

    def should_retrain(self) -> dict[str, Any]:
        """Check all triggers and decide if retraining needed."""
        triggers = []

        # 1. Time-based trigger
        if self._check_time_trigger():
            triggers.append("TIME_INTERVAL")

        # 2. Performance-based trigger
        if self._check_performance_trigger():
            triggers.append("PERFORMANCE_DEGRADATION")

        # 3. Data-based trigger
        if self._check_data_trigger():
            triggers.append("DATA_VOLUME")

        # 4. Drift-based trigger
        if self._check_drift_trigger():
            triggers.append("DATA_DRIFT")

        return {
            "should_retrain": len(triggers) > 0,
            "triggers": triggers,
            "priority": self._calculate_priority(triggers),
            "timestamp": datetime.now().isoformat(),
            "trigger_details": self._get_trigger_details(),
        }

    def _check_time_trigger(self) -> bool:
        """Check if time interval reached."""
        try:
            # Get last training time from MLflow
            client = mlflow.tracking.MlflowClient()
            latest_versions = client.get_latest_versions(
                self.model_registry_name, stages=["Production"]
            )

            if not latest_versions:
                logger.info(
                    "No production model found, triggering time-based retraining"
                )
                return True

            last_version = latest_versions[0]
            last_training_time = last_version.creation_timestamp

            # Calculate days since last training
            days_since = (datetime.now() - last_training_time).days

            should_trigger = days_since >= self.time_interval_days

            if should_trigger:
                logger.info(
                    f"Time-based trigger activated: {days_since} days since last training"
                )
            else:
                logger.info(
                    f"Time-based trigger not activated: {days_since} days since last training (threshold: {self.time_interval_days})"
                )

            return should_trigger

        except Exception as e:
            logger.error(f"Error checking time trigger: {e}")
            return False

    def _check_performance_trigger(self) -> bool:
        """Check if performance degraded."""
        try:
            # Get production model metrics from MLflow
            client = mlflow.tracking.MlflowClient()
            latest_versions = client.get_latest_versions(
                self.model_registry_name, stages=["Production"]
            )

            if not latest_versions:
                logger.info("No production model found for performance check")
                return False

            model_version = latest_versions[0]
            run_id = model_version.run_id

            # Get run metrics
            run = client.get_run(run_id)
            current_rmse = run.data.metrics.get("rmse")

            if current_rmse is None:
                logger.warning("No RMSE metric found for production model")
                return False

            # Get baseline RMSE (best historical performance)
            baseline_rmse = self._get_baseline_rmse()

            if baseline_rmse is None:
                logger.warning("No baseline RMSE available, using default threshold")
                return False

            # Calculate performance degradation
            degradation_pct = ((current_rmse - baseline_rmse) / baseline_rmse) * 100
            should_trigger = degradation_pct > self.performance_threshold

            if should_trigger:
                logger.info(
                    f"Performance trigger activated: {degradation_pct:.2f}% degradation (current: {current_rmse:.4f}, baseline: {baseline_rmse:.4f})"
                )
            else:
                logger.info(
                    f"Performance trigger not activated: {degradation_pct:.2f}% degradation (threshold: {self.performance_threshold}%)"
                )

            return should_trigger

        except Exception as e:
            logger.error(f"Error checking performance trigger: {e}")
            return False

    def _check_data_trigger(self) -> bool:
        """Check if enough new data accumulated."""
        try:
            # This would typically connect to your data source
            # For now, we'll simulate with MLflow run data
            client = mlflow.tracking.MlflowClient()

            # Get recent runs to estimate data volume
            experiments = client.search_experiments(
                filter_string=f"name = '{self.model_registry_name}'"
            )

            if not experiments:
                logger.info("No experiments found for data volume check")
                return False

            experiment_id = experiments[0].experiment_id

            # Get runs from last time interval
            since_date = datetime.now() - timedelta(days=self.time_interval_days)
            runs = client.search_runs(
                experiment_ids=[experiment_id],
                filter_string=f"attributes.start_time > '{since_date.isoformat()}'",
            )

            # Estimate new data volume (this is a simplified approach)
            # In practice, you'd query your actual data source
            estimated_new_data = len(runs) * 1000  # Rough estimate

            should_trigger = estimated_new_data >= self.data_volume_threshold

            if should_trigger:
                logger.info(
                    f"Data volume trigger activated: ~{estimated_new_data} new samples (threshold: {self.data_volume_threshold})"
                )
            else:
                logger.info(
                    f"Data volume trigger not activated: ~{estimated_new_data} new samples (threshold: {self.data_volume_threshold})"
                )

            return should_trigger

        except Exception as e:
            logger.error(f"Error checking data trigger: {e}")
            return False

    def _check_drift_trigger(self) -> bool:
        """Check if data drift detected."""
        try:
            # This would typically use your drift detection implementation
            # For now, we'll simulate with statistical tests on recent data

            client = mlflow.tracking.MlflowClient()
            experiments = client.search_experiments(
                filter_string=f"name = '{self.model_registry_name}'"
            )

            if not experiments:
                return False

            experiment_id = experiments[0].experiment_id

            # Get recent runs for drift analysis
            recent_runs = client.search_runs(
                experiment_ids=[experiment_id],
                max_results=10,
                order_by=["start_time DESC"],
            )

            if len(recent_runs) < DEFAULT_DAYS_INTERVAL:
                logger.info("Insufficient runs for drift analysis")
                return False

            # Compare recent model performance
            recent_rmse_values = []
            for run in recent_runs:
                rmse = run.data.metrics.get("rmse")
                if rmse is not None:
                    recent_rmse_values.append(rmse)

            if len(recent_rmse_values) < DEFAULT_DAYS_INTERVAL:
                return False

            # Statistical test for performance drift
            older_rmse = recent_rmse_values[-2:]  # Older runs
            newer_rmse = recent_rmse_values[:2]  # Recent runs

            if len(older_rmse) == 0 or len(newer_rmse) == 0:
                return False

            # Perform t-test
            _t_stat, p_value = stats.ttest_ind(older_rmse, newer_rmse)

            # Calculate effect size (Cohen's d)
            pooled_std = (
                (len(older_rmse) - 1) * pd.Series(older_rmse).var()
                + (len(newer_rmse) - 1) * pd.Series(newer_rmse).var()
            ) / (len(older_rmse) + len(newer_rmse) - 2)

            if pooled_std > 0:
                cohens_d = (
                    pd.Series(newer_rmse).mean() - pd.Series(older_rmse).mean()
                ) / pooled_std
            else:
                cohens_d = 0

            should_trigger = (
                p_value < MIN_PERFORMANCE_THRESHOLD and cohens_d > DEFAULT_PERFORMANCE_THRESHOLD
            )  # Significant degradation

            if should_trigger:
                logger.info(
                    f"Drift trigger activated: p-value={p_value:.4f}, Cohen's d={cohens_d:.2f}"
                )
            else:
                logger.info(
                    f"Drift trigger not activated: p-value={p_value:.4f}, Cohen's d={cohens_d:.2f}"
                )

            return should_trigger

        except Exception as e:
            logger.error(f"Error checking drift trigger: {e}")
            return False

    def _get_baseline_rmse(self) -> float:
        """Get baseline RMSE from best historical performance."""
        try:
            client = mlflow.tracking.MlflowClient()
            experiments = client.search_experiments(
                filter_string=f"name = '{self.model_registry_name}'"
            )

            if not experiments:
                return None

            experiment_id = experiments[0].experiment_id

            # Get best run by RMSE
            best_runs = client.search_runs(
                experiment_ids=[experiment_id],
                filter_string="metrics.rmse IS NOT NULL",
                max_results=1,
                order_by=["metrics.rmse ASC"],
            )

            if best_runs:
                return best_runs[0].data.metrics.get("rmse")

            return None

        except Exception as e:
            logger.error(f"Error getting baseline RMSE: {e}")
            return None

    def _calculate_priority(self, triggers: list[str]) -> str:
        """Calculate retraining priority based on trigger types."""
        priority_scores = {
            "TIME_INTERVAL": 1,
            "DATA_VOLUME": DEFAULT_HOURS_INTERVAL,
            "PERFORMANCE_DEGRADATION": 3,
            "DATA_DRIFT": DEFAULT_DAYS_INTERVAL,
        }

        max_score = max([priority_scores.get(trigger, 0) for trigger in triggers])

        if max_score >= 4:
            return "CRITICAL"
        if max_score >= 3:
            return "HIGH"
        if max_score >= 2:
            return "MEDIUM"
        return "LOW"

    def _get_trigger_details(self) -> dict[str, Any]:
        """Get detailed information about each trigger."""
        return {
            "time_interval": {
                "threshold_days": self.time_interval_days,
                "description": f"Retrain every {self.time_interval_days} days",
            },
            "performance": {
                "threshold_percent": self.performance_threshold,
                "description": f"Retrain if RMSE degrades by >{self.performance_threshold}%",
            },
            "data_volume": {
                "threshold_samples": self.data_volume_threshold,
                "description": f"Retrain if >{self.data_volume_threshold} new samples available",
            },
            "drift": {
                "threshold_p_value": 0.05,
                "threshold_effect_size": 0.5,
                "description": "Retrain if significant performance drift detected",
            },
        }

    def log_retraining_decision(self, decision: dict[str, Any]):
        """Log retraining decision to MLflow."""
        try:
            mlflow.tracking.MlflowClient()

            with mlflow.start_run(
                run_name=f"retraining_decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ):
                # Log decision
                mlflow.log_param("should_retrain", decision["should_retrain"])
                mlflow.log_param("triggers", ",".join(decision["triggers"]))
                mlflow.log_param("priority", decision["priority"])

                # Log trigger details
                for trigger in decision["triggers"]:
                    mlflow.log_param(f"trigger_{trigger.lower()}", True)

                # Log timestamp
                mlflow.log_param("decision_timestamp", decision["timestamp"])

                logger.info(f"Retraining decision logged to MLflow: {decision}")

        except Exception as e:
            logger.error(f"Failed to log retraining decision to MLflow: {e}")

    def get_retraining_recommendations(self, decision: dict[str, Any]) -> list[str]:
        """Get recommendations based on retraining decision."""
        recommendations = []

        if not decision["should_retrain"]:
            recommendations.append("No retraining needed at this time.")
            return recommendations

        priority = decision["priority"]
        triggers = decision["triggers"]

        if priority == "CRITICAL":
            recommendations.append(
                "🚨 URGENT: Immediate retraining required due to data drift or performance degradation."
            )
            recommendations.append(
                "Consider investigating data quality and model assumptions."
            )
        elif priority == "HIGH":
            recommendations.append(
                "⚠️ HIGH PRIORITY: Retraining recommended due to performance issues."
            )
            recommendations.append("Monitor model closely until retraining completes.")
        elif priority == "MEDIUM":
            recommendations.append(
                "📊 MEDIUM PRIORITY: Retraining recommended for optimal performance."
            )
            recommendations.append(
                "Schedule retraining during next maintenance window."
            )
        else:
            recommendations.append("📅 LOW PRIORITY: Routine retraining due.")
            recommendations.append("Can be scheduled during regular maintenance.")

        # Trigger-specific recommendations
        if "DATA_DRIFT" in triggers:
            recommendations.append(
                "🔍 Investigate potential data distribution changes."
            )
            recommendations.append("Consider updating feature engineering pipeline.")

        if "PERFORMANCE_DEGRADATION" in triggers:
            recommendations.append("📈 Review recent model performance trends.")
            recommendations.append("Consider hyperparameter re-optimization.")

        if "DATA_VOLUME" in triggers:
            recommendations.append("📊 Validate data quality before retraining.")
            recommendations.append("Consider incremental training if available.")

        return recommendations
