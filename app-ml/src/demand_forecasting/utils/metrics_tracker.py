"""Metrics Tracker for Model Performance Monitoring

Tracks model training metrics, validation results, and production performance.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class MetricsTracker:
    """Track and log model performance metrics."""

    def __init__(self, run_id: str | None = None):
        """Initialize metrics tracker.

        Args:
            run_id: Unique identifier for this run (defaults to timestamp)
        """
        self.run_id = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.metrics: dict[str, Any] = {
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "training_metrics": {},
            "validation_metrics": {},
            "test_metrics": {},
            "metadata": {},
        }

    def log_training_metrics(
        self,
        model_name: str,
        metrics: dict[str, float],
        hyperparameters: dict[str, Any] | None = None,
    ):
        """Log training metrics for a model.

        Args:
            model_name: Name of the model
            metrics: Dictionary of metric names and values
            hyperparameters: Optional hyperparameters used
        """
        self.metrics["training_metrics"][model_name] = {
            "metrics": metrics,
            "hyperparameters": hyperparameters or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info(f"Logged training metrics for {model_name}: {metrics}")

    def log_validation_metrics(
        self,
        model_name: str,
        metrics: dict[str, float],
        dataset_info: dict[str, Any] | None = None,
    ):
        """Log validation metrics for a model.

        Args:
            model_name: Name of the model
            metrics: Dictionary of metric names and values
            dataset_info: Optional information about validation dataset
        """
        self.metrics["validation_metrics"][model_name] = {
            "metrics": metrics,
            "dataset_info": dataset_info or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info(f"Logged validation metrics for {model_name}: {metrics}")

    def log_test_metrics(
        self,
        model_name: str,
        metrics: dict[str, float],
        predictions_summary: dict[str, Any] | None = None,
    ):
        """Log test/production metrics for a model.

        Args:
            model_name: Name of the model
            metrics: Dictionary of metric names and values
            predictions_summary: Optional summary of predictions
        """
        self.metrics["test_metrics"][model_name] = {
            "metrics": metrics,
            "predictions_summary": predictions_summary or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info(f"Logged test metrics for {model_name}: {metrics}")

    def log_metadata(self, key: str, value: Any):
        """Log arbitrary metadata.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metrics["metadata"][key] = value
        logger.debug(f"Logged metadata: {key} = {value}")

    def get_best_model(
        self, metric_name: str = "rmse", higher_is_better: bool = False
    ) -> str | None:
        """Get the best performing model based on validation metrics.

        Args:
            metric_name: Metric to compare (e.g., 'rmse', 'mae', 'r2')
            higher_is_better: If True, higher values are better

        Returns:
            Name of the best model or None if no validation metrics
        """
        if not self.metrics["validation_metrics"]:
            logger.warning("No validation metrics available")
            return None

        best_model = None
        best_value = float("-inf") if higher_is_better else float("inf")

        for model_name, data in self.metrics["validation_metrics"].items():
            if metric_name not in data["metrics"]:
                continue

            value = data["metrics"][metric_name]
            if higher_is_better:
                if value > best_value:
                    best_value = value
                    best_model = model_name
            elif value < best_value:
                best_value = value
                best_model = model_name

        logger.info(f"Best model: {best_model} with {metric_name}={best_value:.4f}")
        return best_model

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of all tracked metrics.

        Returns:
            Dictionary with metrics summary
        """
        summary = {
            "run_id": self.run_id,
            "timestamp": self.metrics["timestamp"],
            "num_models_trained": len(self.metrics["training_metrics"]),
            "num_models_validated": len(self.metrics["validation_metrics"]),
            "num_models_tested": len(self.metrics["test_metrics"]),
        }

        # Add best model info if available
        if self.metrics["validation_metrics"]:
            best_model = self.get_best_model()
            if best_model:
                summary["best_model"] = {
                    "name": best_model,
                    "metrics": self.metrics["validation_metrics"][best_model][
                        "metrics"
                    ],
                }

        return summary

    def save_to_json(self, filepath: str):
        """Save metrics to JSON file.

        Args:
            filepath: Path to save the JSON file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with filepath.open("w") as f:
            json.dump(self.metrics, f, indent=2, default=str)

        logger.info(f"Metrics saved to {filepath}")

    def save_to_csv(self, filepath: str, metrics_type: str = "validation"):
        """Save metrics to CSV file for easy analysis.

        Args:
            filepath: Path to save the CSV file
            metrics_type: Type of metrics to save ('training', 'validation', 'test')
        """
        if metrics_type not in ["training", "validation", "test"]:
            raise ValueError(
                f"Invalid metrics_type: {metrics_type}. "
                "Must be 'training', 'validation', or 'test'"
            )

        metrics_key = f"{metrics_type}_metrics"
        if not self.metrics[metrics_key]:
            logger.warning(f"No {metrics_type} metrics to save")
            return

        # Flatten metrics for CSV
        rows = []
        for model_name, data in self.metrics[metrics_key].items():
            row = {
                "run_id": self.run_id,
                "model_name": model_name,
                "timestamp": data["timestamp"],
            }
            # Add all metrics
            for metric_name, value in data["metrics"].items():
                row[metric_name] = value
            # Add hyperparameters if available
            if "hyperparameters" in data:
                for param_name, value in data["hyperparameters"].items():
                    row[f"hp_{param_name}"] = value
            rows.append(row)

        df = pd.DataFrame(rows)
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False)

        logger.info(f"{metrics_type.capitalize()} metrics saved to {filepath}")

    def load_from_json(self, filepath: str):
        """Load metrics from JSON file.

        Args:
            filepath: Path to the JSON file
        """
        filepath = Path(filepath)
        with filepath.open() as f:
            self.metrics = json.load(f)

        self.run_id = self.metrics.get("run_id", self.run_id)
        logger.info(f"Metrics loaded from {filepath}")

    def compare_models(self, metric_names: list[str] | None = None) -> pd.DataFrame:
        """Compare all models across multiple metrics.

        Args:
            metric_names: List of metrics to compare (None = all metrics)

        Returns:
            DataFrame with models as rows and metrics as columns
        """
        if not self.metrics["validation_metrics"]:
            logger.warning("No validation metrics available for comparison")
            return pd.DataFrame()

        data = {}
        for model_name, model_data in self.metrics["validation_metrics"].items():
            metrics = model_data["metrics"]
            if metric_names:
                metrics = {k: v for k, v in metrics.items() if k in metric_names}
            data[model_name] = metrics

        df = pd.DataFrame(data).T
        df.index.name = "model"
        return df.sort_values(by=df.columns[0])

    def __repr__(self) -> str:
        summary = self.get_metrics_summary()
        return (
            f"MetricsTracker(run_id='{self.run_id}', "
            f"models_trained={summary['num_models_trained']}, "
            f"models_validated={summary['num_models_validated']})"
        )


def create_tracker(run_id: str | None = None) -> MetricsTracker:
    """Factory function to create a MetricsTracker.

    Args:
        run_id: Optional run identifier

    Returns:
        MetricsTracker instance
    """
    return MetricsTracker(run_id=run_id)
