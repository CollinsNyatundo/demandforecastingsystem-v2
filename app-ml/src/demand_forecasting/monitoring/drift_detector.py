"""Data drift detection using statistical methods."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp

logger = logging.getLogger(__name__)

# Drift detection constants
HIGH_DRIFT_THRESHOLD = 0.8
MEDIUM_DRIFT_THRESHOLD = 0.6
LOW_DRIFT_THRESHOLD = 0.4


class DriftDetector:
    """Detect distribution drift in features using statistical tests."""

    def __init__(self, reference_data: pd.DataFrame, threshold: float = 0.05):
        """Initialize drift detector.

        Args:
            reference_data: Reference dataset for comparison
            threshold: P-value threshold for drift detection
        """
        self.reference_data = reference_data.copy()
        self.reference_stats = self._compute_statistics(reference_data)
        self.threshold = threshold
        self.drift_history = []

    def detect_drift(
        self, current_data: pd.DataFrame, threshold: float | None = None
    ) -> dict[str, Any]:
        """Detect drift between reference and current data.

        Args:
            current_data: Current dataset to compare
            threshold: Override default threshold

        Returns:
            Dictionary with drift detection results
        """
        if threshold is None:
            threshold = self.threshold

        drift_results = {}

        # Test each column for drift
        for column in self.reference_data.columns:
            if column in current_data.columns:
                drift_results[column] = self._test_column_drift(
                    column, current_data, threshold
                )
            else:
                drift_results[column] = {
                    "drift_score": 1.0,
                    "p_value": 0.0,
                    "is_drifted": True,
                    "method": "MISSING_COLUMN",
                    "error": f"Column {column} not found in current data",
                }

        # Calculate overall drift score
        valid_results = [r for r in drift_results.values() if "error" not in r]
        if valid_results:
            overall_drift_score = np.mean([r["drift_score"] for r in valid_results])
            drifted_features = [
                col
                for col, res in drift_results.items()
                if res.get("is_drifted", False)
            ]
        else:
            overall_drift_score = 1.0
            drifted_features = list(drift_results.keys())

        # Create summary
        result = {
            "overall_drift_score": overall_drift_score,
            "drifted_features": drifted_features,
            "total_features": len(self.reference_data.columns),
            "drifted_feature_count": len(drifted_features),
            "drift_percentage": len(drifted_features)
            / len(self.reference_data.columns)
            * 100,
            "details": drift_results,
            "recommendation": self._get_recommendation(overall_drift_score, threshold),
            "threshold": threshold,
            "timestamp": pd.Timestamp.now().isoformat(),
        }

        # Store in history
        self.drift_history.append(result)

        return result

    def _test_column_drift(
        self, column: str, current_data: pd.DataFrame, threshold: float
    ) -> dict[str, Any]:
        """Test drift for a single column."""
        ref_values = self.reference_data[column].dropna()
        curr_values = current_data[column].dropna()

        # Check if we have enough data
        min_samples = 30
        if len(ref_values) < min_samples or len(curr_values) < min_samples:
            return {
                "drift_score": 0.0,
                "p_value": 1.0,
                "is_drifted": False,
                "method": "INSUFFICIENT_DATA",
                "error": f"Insufficient samples: ref={len(ref_values)}, curr={len(curr_values)}",
            }

        try:
            # Numerical: Kolmogorov-Smirnov test
            if pd.api.types.is_numeric_dtype(ref_values):
                statistic, p_value = ks_2samp(ref_values, curr_values)
                drift_score = statistic
                is_drifted = p_value < threshold
                method = "KS_TEST"

                # Additional statistics for numerical features
                ref_mean, curr_mean = np.mean(ref_values), np.mean(curr_values)
                ref_std, curr_std = np.std(ref_values), np.std(curr_values)

                result = {
                    "drift_score": drift_score,
                    "p_value": p_value,
                    "is_drifted": is_drifted,
                    "method": method,
                    "ref_mean": ref_mean,
                    "curr_mean": curr_mean,
                    "mean_diff": abs(ref_mean - curr_mean),
                    "ref_std": ref_std,
                    "curr_std": curr_std,
                    "std_diff": abs(ref_std - curr_std),
                }

            # Categorical: Chi-square test
            else:
                # Create contingency table
                ref_counts = ref_values.value_counts()
                curr_counts = curr_values.value_counts()

                # Align categories
                all_categories = set(ref_counts.index) | set(curr_counts.index)
                for cat in all_categories:
                    if cat not in ref_counts:
                        ref_counts[cat] = 0
                    if cat not in curr_counts:
                        curr_counts[cat] = 0

                # Create contingency table
                contingency_table = pd.DataFrame(
                    {"reference": ref_counts, "current": curr_counts}
                ).T

                chi2, p_value, _, _expected = chi2_contingency(contingency_table)
                drift_score = chi2 / len(ref_values)  # Normalized chi-square
                is_drifted = p_value < threshold
                method = "CHI_SQUARE"

                result = {
                    "drift_score": drift_score,
                    "p_value": p_value,
                    "is_drifted": is_drifted,
                    "method": method,
                    "chi2_statistic": chi2,
                    "ref_categories": len(ref_counts),
                    "curr_categories": len(curr_counts),
                    "category_overlap": len(
                        set(ref_counts.index) & set(curr_counts.index)
                    ),
                }

            return result

        except Exception as e:
            logger.error(f"Error testing drift for column {column}: {e}")
            return {
                "drift_score": 0.0,
                "p_value": 1.0,
                "is_drifted": False,
                "method": "ERROR",
                "error": str(e),
            }

    def _compute_statistics(self, data: pd.DataFrame) -> dict[str, Any]:
        """Compute reference statistics for all columns."""
        stats = {}

        for column in data.columns:
            col_data = data[column].dropna()

            if pd.api.types.is_numeric_dtype(col_data):
                stats[column] = {
                    "mean": np.mean(col_data),
                    "std": np.std(col_data),
                    "min": np.min(col_data),
                    "max": np.max(col_data),
                    "q25": np.percentile(col_data, 25),
                    "q50": np.percentile(col_data, 50),
                    "q75": np.percentile(col_data, 75),
                    "count": len(col_data),
                    "missing_rate": data[column].isna().sum() / len(data),
                }
            else:
                value_counts = col_data.value_counts()
                stats[column] = {
                    "unique_count": len(value_counts),
                    "most_frequent": (
                        value_counts.index[0] if len(value_counts) > 0 else None
                    ),
                    "most_frequent_count": (
                        value_counts.iloc[0] if len(value_counts) > 0 else 0
                    ),
                    "count": len(col_data),
                    "missing_rate": data[column].isna().sum() / len(data),
                }

        return stats

    def _get_recommendation(self, drift_score: float, threshold: float) -> str:
        """Generate recommendation based on drift score."""
        if drift_score > HIGH_DRIFT_THRESHOLD:
            return "URGENT_RETRAIN"
        if drift_score > MEDIUM_DRIFT_THRESHOLD:
            return "CONSIDER_RETRAIN"
        if drift_score > LOW_DRIFT_THRESHOLD:
            return "MONITOR_CLOSELY"
        return "NO_ACTION"

    def get_drift_trend(self, window_size: int = 10) -> dict[str, Any]:
        """Analyze drift trend over recent runs."""
        if len(self.drift_history) < window_size:
            return {
                "trend": "insufficient_data",
                "recent_scores": [
                    h.get("overall_drift_score", 0) for h in self.drift_history
                ],
                "message": f"Need at least {window_size} drift detection runs",
            }

        recent_history = self.drift_history[-window_size:]
        recent_scores = [h.get("overall_drift_score", 0) for h in recent_history]

        # Calculate trend
        if len(recent_scores) >= 2:
            slope = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]
            if slope > 0.01:
                trend = "increasing"
            elif slope < -0.01:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        return {
            "trend": trend,
            "slope": slope if len(recent_scores) >= 2 else 0,
            "recent_scores": recent_scores,
            "avg_score": np.mean(recent_scores),
            "max_score": np.max(recent_scores),
            "min_score": np.min(recent_scores),
            "window_size": window_size,
        }

    def update_reference(self, new_reference: pd.DataFrame):
        """Update reference data with new dataset."""
        self.reference_data = new_reference.copy()
        self.reference_stats = self._compute_statistics(new_reference)
        logger.info(f"Reference data updated with {len(new_reference)} samples")

    def get_feature_drift_summary(self) -> pd.DataFrame:
        """Get summary of drift for all features."""
        if not self.drift_history:
            return pd.DataFrame()

        # Collect drift scores for each feature over time
        feature_scores = {}
        for run in self.drift_history:
            for feature, details in run.get("details", {}).items():
                if feature not in feature_scores:
                    feature_scores[feature] = []
                feature_scores[feature].append(details.get("drift_score", 0))

        # Create summary statistics
        summary_data = []
        for feature, scores in feature_scores.items():
            if scores:
                summary_data.append(
                    {
                        "feature": feature,
                        "avg_drift_score": np.mean(scores),
                        "max_drift_score": np.max(scores),
                        "min_drift_score": np.min(scores),
                        "std_drift_score": np.std(scores),
                        "latest_drift_score": scores[-1],
                        "drift_runs": len(scores),
                    }
                )

        return pd.DataFrame(summary_data).sort_values(
            "avg_drift_score", ascending=False
        )


class PopulationStabilityIndex:
    """Calculate Population Stability Index (PSI) for drift detection."""

    @staticmethod
    def calculate_psi(
        expected: pd.Series, actual: pd.Series, buckets: int = 10
    ) -> dict[str, Any]:
        """Calculate PSI between two distributions.

        Args:
            expected: Expected/Reference distribution
            actual: Actual/Current distribution
            buckets: Number of buckets for binning

        Returns:
            Dictionary with PSI calculation results
        """
        try:
            # Create bins
            if pd.api.types.is_numeric_dtype(expected):
                # For numerical data, use quantile-based binning
                _, bin_edges = pd.qcut(
                    expected, q=buckets, retbins=True, duplicates="drop"
                )
                expected_binned = pd.cut(expected, bins=bin_edges, include_lowest=True)
                actual_binned = pd.cut(actual, bins=bin_edges, include_lowest=True)
            else:
                # For categorical data, use unique values as bins
                all_categories = set(expected.unique()) | set(actual.unique())
                expected_binned = pd.Categorical(expected, categories=all_categories)
                actual_binned = pd.Categorical(actual, categories=all_categories)

            # Calculate percentages
            expected_counts = expected_binned.value_counts(normalize=True, sort=False)
            actual_counts = actual_binned.value_counts(normalize=True, sort=False)

            # Align and calculate PSI
            all_bins = set(expected_counts.index) | set(actual_counts.index)
            psi_components = []

            for bin_label in all_bins:
                exp_pct = expected_counts.get(bin_label, 0)
                act_pct = actual_counts.get(bin_label, 0)

                # Avoid division by zero
                if exp_pct == 0:
                    exp_pct = 0.0001
                if act_pct == 0:
                    act_pct = 0.0001

                psi_component = (act_pct - exp_pct) * np.log(act_pct / exp_pct)
                psi_components.append(psi_component)

            psi_total = sum(psi_components)

            # Interpret PSI
            if psi_total < 0.1:
                psi_interpretation = "no_significant_change"
            elif psi_total < 0.25:
                psi_interpretation = "moderate_change"
            else:
                psi_interpretation = "significant_change"

            return {
                "psi_value": psi_total,
                "interpretation": psi_interpretation,
                "expected_counts": expected_counts.to_dict(),
                "actual_counts": actual_counts.to_dict(),
                "psi_components": dict(zip(all_bins, psi_components, strict=False)),
                "buckets_used": len(all_bins),
            }

        except Exception as e:
            logger.error(f"Error calculating PSI: {e}")
            return {
                "psi_value": float("inf"),
                "interpretation": "error",
                "error": str(e),
            }
