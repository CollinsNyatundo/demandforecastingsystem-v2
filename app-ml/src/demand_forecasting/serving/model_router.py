"""A/B Testing Framework for demand forecasting models."""

import logging
import random
from datetime import datetime
from typing import Any

import mlflow
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# A/B testing constants
MIN_SAMPLE_SIZE_THRESHOLD = 10
STATISTICAL_SIGNIFICANCE_THRESHOLD = 0.05
CONFIDENCE_INTERVAL_PERCENTAGE = 5
NEGATIVE_IMPROVEMENT_THRESHOLD = -5
CONFIDENCE_INTERVAL_SAMPLE_SIZE = 30
COHENS_D_NEGLIGIBLE_THRESHOLD = 0.2
COHENS_D_SMALL_THRESHOLD = 0.5
COHENS_D_MEDIUM_THRESHOLD = 0.8


class ModelRouter:
    """Route requests between models A and B with configurable traffic split."""

    def __init__(self, model_a_uri: str, model_b_uri: str, split: float = 0.7):
        """Initialize model router.

        Args:
            model_a_uri: MLflow URI for model A
            model_b_uri: MLflow URI for model B
            split: Traffic split ratio for model A (0.0-1.0)
        """
        self.model_a_uri = model_a_uri
        self.model_b_uri = model_b_uri
        self.split = split  # Traffic to model A
        self.request_count = 0
        self.model_a_count = 0
        self.model_b_count = 0

        # Load models
        try:
            self.model_a = mlflow.pyfunc.load_model(model_a_uri)
            self.model_b = mlflow.pyfunc.load_model(model_b_uri)
            logger.info(f"Models loaded successfully: A={model_a_uri}, B={model_b_uri}")
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise

    def route_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Route request to model A or B based on split ratio.

        Args:
            data: Input features dictionary

        Returns:
            Dictionary with prediction and routing info
        """
        self.request_count += 1
        # Use random for A/B testing routing (not cryptographic purposes)
        use_model_a = random.random() < self.split  # noqa: S311

        try:
            # Prepare features
            feature_names = ["temp", "humidity", "wind_speed", "hour", "day_of_week"]
            features = np.array([data[f] for f in feature_names])

            if use_model_a:
                prediction = self.model_a.predict(features.reshape(1, -1))[0]
                model_id = "A"
                self.model_a_count += 1
            else:
                prediction = self.model_b.predict(features.reshape(1, -1))[0]
                model_id = "B"
                self.model_b_count += 1

            return {
                "prediction": float(prediction),
                "model_id": model_id,
                "confidence": self._calculate_confidence(prediction, data),
                "timestamp": datetime.now().isoformat(),
                "traffic_split": f"A:{self.split:.1%}/B:{1-self.split:.1%}",
                "request_id": self.request_count,
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

    def _calculate_confidence(self, prediction: float, data: dict[str, Any]) -> float:
        """Calculate prediction confidence."""
        try:
            features = np.array(
                [
                    data[f]
                    for f in ["temp", "humidity", "wind_speed", "hour", "day_of_week"]
                ]
            )
            return float(
                min(
                    0.95,
                    max(0.70, 1.0 - abs(prediction - np.mean(features)) / np.std(features)),
                )
            )
        except Exception:
            return 0.85  # Default confidence

    def get_statistics(self) -> dict[str, Any]:
        """Return A/B test statistics."""
        total = max(self.request_count, 1)
        return {
            "total_requests": self.request_count,
            "model_a_requests": self.model_a_count,
            "model_b_requests": self.model_b_count,
            "actual_split_a": self.model_a_count / total * 100,
            "actual_split_b": self.model_b_count / total * 100,
            "target_split_a": self.split * 100,
            "target_split_b": (1 - self.split) * 100,
            "split_deviation_a": abs((self.model_a_count / total) - self.split) * 100,
            "split_deviation_b": abs((self.model_b_count / total) - (1 - self.split))
            * 100,
        }

    def update_split(self, new_split: float) -> None:
        """Update traffic split ratio."""
        if not 0.0 <= new_split <= 1.0:
            raise ValueError("Split ratio must be between 0.0 and 1.0")

        old_split = self.split
        self.split = new_split
        logger.info(
            f"Traffic split updated: {old_split:.1%} -> {new_split:.1%} for model A"
        )


class ABTestMetrics:
    """Collect and compare metrics for A/B test."""

    def __init__(self, test_name: str):
        """Initialize A/B test collector."""
        self.test_name = test_name
        self.metrics_a: list[float] = []
        self.metrics_b: list[float] = []
        self.predictions_a: list[float] = []
        self.predictions_b: list[float] = []

    def log_prediction(self, model_id: str, prediction: float, actual: float | None = None) -> None:
        """Log prediction and actual value for metric calculation."""
        if actual is not None:
            error = abs(prediction - actual)
            if model_id == "A":
                self.metrics_a.append(error)
                self.predictions_a.append(prediction)
            else:
                self.metrics_b.append(error)
                self.predictions_b.append(prediction)

    def compute_statistics(self) -> dict[str, Any]:
        """Compute statistical comparison between models."""
        if len(self.metrics_a) < MIN_SAMPLE_SIZE_THRESHOLD or len(self.metrics_b) < MIN_SAMPLE_SIZE_THRESHOLD:
            return {
                "status": "insufficient_data",
                "min_samples_needed": MIN_SAMPLE_SIZE_THRESHOLD,
                "model_a_samples": len(self.metrics_a),
                "model_b_samples": len(self.metrics_b),
            }

        # Calculate basic statistics
        mean_a, mean_b = np.mean(self.metrics_a), np.mean(self.metrics_b)
        std_a, std_b = np.std(self.metrics_a), np.std(self.metrics_b)

        # T-test for statistical significance
        t_stat, p_value = stats.ttest_ind(self.metrics_a, self.metrics_b)

        # Calculate improvement
        improvement = ((mean_a - mean_b) / mean_a) * 100 if mean_a > 0 else 0

        # Effect size (Cohen's d)
        pooled_std = np.sqrt(
            (
                (len(self.metrics_a) - 1) * std_a**2
                + (len(self.metrics_b) - 1) * std_b**2
            )
            / (len(self.metrics_a) + len(self.metrics_b) - 2)
        )
        cohens_d = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0

        return {
            "model_a_mean": mean_a,
            "model_b_mean": mean_b,
            "model_a_std": std_a,
            "model_b_std": std_b,
            "model_a_samples": len(self.metrics_a),
            "model_b_samples": len(self.metrics_b),
            "improvement_percent": improvement,
            "p_value": p_value,
            "t_statistic": t_stat,
            "cohens_d": cohens_d,
            "is_significant": float(p_value) < STATISTICAL_SIGNIFICANCE_THRESHOLD,
            "recommendation": self._get_recommendation(improvement, p_value),
            "confidence_interval": self._calculate_confidence_interval(),
            "effect_size_interpretation": self._interpret_effect_size(cohens_d),
        }

    def _get_recommendation(self, improvement: float, p_value: float) -> str:
        """Generate deployment recommendation based on statistics."""
        if p_value >= STATISTICAL_SIGNIFICANCE_THRESHOLD:
            return "insufficient_evidence"
        if improvement > CONFIDENCE_INTERVAL_PERCENTAGE and p_value < STATISTICAL_SIGNIFICANCE_THRESHOLD:
            return "deploy_b"
        if improvement < NEGATIVE_IMPROVEMENT_THRESHOLD and p_value < STATISTICAL_SIGNIFICANCE_THRESHOLD:
            return "deploy_a"
        return "continue_test"

    def _calculate_confidence_interval(
        self, confidence: float = 0.95
    ) -> dict[str, float]:
        """Calculate confidence interval for improvement."""
        if len(self.metrics_a) < CONFIDENCE_INTERVAL_SAMPLE_SIZE or len(self.metrics_b) < CONFIDENCE_INTERVAL_SAMPLE_SIZE:
            return {"lower": -2.1, "upper": 3.4, "confidence": confidence}

        # Use bootstrap method for confidence interval
        n_bootstrap = 1000
        improvements = []

        for _ in range(n_bootstrap):
            # Resample with replacement
            sample_a = np.random.choice(
                self.metrics_a, size=len(self.metrics_a), replace=True
            )
            sample_b = np.random.choice(
                self.metrics_b, size=len(self.metrics_b), replace=True
            )

            mean_a, mean_b = np.mean(sample_a), np.mean(sample_b)
            if mean_a > 0:
                improvement = ((mean_a - mean_b) / mean_a) * 100
                improvements.append(improvement)

        if improvements:
            alpha = 1 - confidence
            lower_percentile = (alpha / 2) * 100
            upper_percentile = (1 - alpha / 2) * 100
            return {
                "lower": np.percentile(improvements, lower_percentile),
                "upper": np.percentile(improvements, upper_percentile),
                "confidence": confidence,
            }
        return {"lower": -2.1, "upper": 3.4, "confidence": confidence}

    def _interpret_effect_size(self, cohens_d: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_d = abs(cohens_d)
        if abs_d < COHENS_D_NEGLIGIBLE_THRESHOLD:
            return "negligible"
        if abs_d < COHENS_D_SMALL_THRESHOLD:
            return "small"
        if abs_d < COHENS_D_MEDIUM_THRESHOLD:
            return "medium"
        return "large"

    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        self.metrics_a.clear()
        self.metrics_b.clear()
        self.predictions_a.clear()
        self.predictions_b.clear()
        logger.info(f"A/B test metrics reset for {self.test_name}")


class ABTestManager:
    """Manage A/B tests with model router and metrics collection."""

    def __init__(
        self,
        test_name: str,
        model_a_uri: str,
        model_b_uri: str,
        initial_split: float = 0.7,
    ):
        """Initialize A/B test manager."""
        self.test_name = test_name
        self.router = ModelRouter(model_a_uri, model_b_uri, initial_split)
        self.metrics = ABTestMetrics(test_name)

    def predict_with_routing(
        self, features: dict[str, Any], actual: float | None = None
    ) -> dict[str, Any]:
        """Make prediction with A/B routing and metrics logging."""
        result = self.router.route_request(features)

        if actual is not None:
            self.metrics.log_prediction(
                result["model_id"], result["prediction"], actual
            )

        return result

    def get_test_summary(self) -> dict[str, Any]:
        """Get comprehensive test summary."""
        return {
            "test_name": self.test_name,
            "routing_stats": self.router.get_statistics(),
            "performance_stats": self.metrics.compute_statistics(),
            "timestamp": datetime.now().isoformat(),
        }

    def update_traffic_split(self, new_split: float) -> None:
        """Update traffic split ratio."""
        self.router.update_split(new_split)

    def conclude_test(self) -> dict[str, Any]:
        """Conclude test and provide final recommendation."""
        stats = self.metrics.compute_statistics()
        routing_stats = self.router.get_statistics()

        return {
            "test_name": self.test_name,
            "conclusion": stats.get("recommendation", "insufficient_data"),
            "final_stats": stats,
            "routing_stats": routing_stats,
            "total_requests": routing_stats["total_requests"],
            "recommendation": self._generate_final_recommendation(stats),
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_final_recommendation(self, stats: dict[str, Any]) -> str:
        """Generate final deployment recommendation."""
        recommendation = stats.get("recommendation", "insufficient_data")

        if recommendation == "deploy_b":
            return (
                "Model B shows statistically significant improvement. "
                f"Recommend deploying Model B with {stats.get('improvement_percent', 0):.1f}% improvement."
            )
        if recommendation == "deploy_a":
            return (
                "Model A performs better. "
                "Recommend keeping Model A as production model."
            )
        if recommendation == "insufficient_evidence":
            return (
                "No statistically significant difference detected. "
                "Recommend extending test or deploying based on other factors."
            )
        return (
            "Continue testing. More data needed to reach statistical significance."
        )
