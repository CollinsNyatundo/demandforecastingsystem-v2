"""Automated data profiling and quality monitoring utilities."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from pandas_profiling import ProfileReport

logger = logging.getLogger(__name__)

# Data quality threshold constants
HIGH_MISSING_VALUES_THRESHOLD = 5
SMALL_DATASET_THRESHOLD = 1000
OUTLIER_THRESHOLD = 10
MAX_PROFILES_PER_DATASET = 10
DATAFRAME_DIMENSIONS = 2


class DataProfiler:
    """Automated data profiling and quality monitoring inspired by EDA notebook.

    Generates comprehensive data quality reports and tracks changes over time.
    """

    def __init__(self, profile_dir: str = "/opt/airflow/data/profiles"):
        """Initialize data profiler.

        Args:
            profile_dir: Directory to store profile reports and metrics
        """
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.profile_dir / "data_quality_metrics.json"

    def generate_profile_report(self, df: pd.DataFrame, dataset_name: str) -> str:
        """Generate comprehensive data profile report similar to EDA notebook.

        Args:
            df: DataFrame to profile
            dataset_name: Name of the dataset for file naming

        Returns:
            Path to generated HTML profile report
        """
        if len(df) == 0:
            raise ValueError("Cannot profile empty DataFrame")

        # Generate ydata-profiling report
        profile = ProfileReport(
            df, title=f"Data Profile Report - {dataset_name}", explorative=True
        )

        # Save HTML report
        report_path = (
            self.profile_dir
            / f"{dataset_name}_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        profile.to_file(str(report_path))

        # Generate summary statistics
        summary_stats = self._generate_summary_stats(df, dataset_name)

        # Save metrics
        self._save_metrics(summary_stats, dataset_name)

        logger.info(f"Generated profile report for {dataset_name}: {report_path}")
        return str(report_path)

    def _generate_summary_stats(
        self, df: pd.DataFrame, dataset_name: str
    ) -> dict[str, Any]:
        """Generate summary statistics similar to EDA notebook analysis.

        Args:
            df: DataFrame to analyze
            dataset_name: Name of the dataset

        Returns:
            Dictionary with summary statistics
        """
        quality_flags: list[str] = []
        stats: dict[str, Any] = {
            "dataset_name": dataset_name,
            "timestamp": datetime.now().isoformat(),
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
            "numeric_summary": {},
            "categorical_summary": {},
            "correlations": {},
            "quality_flags": quality_flags,
        }

        # Numeric columns analysis
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            stats["numeric_summary"] = df[numeric_cols].describe().to_dict()

            # Correlations (only if enough columns)
            if len(numeric_cols) > 1:
                correlation_matrix = df[numeric_cols].corr()
                stats["correlations"] = correlation_matrix.to_dict()

        # Categorical columns analysis
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns
        if len(categorical_cols) > 0:
            for col in categorical_cols:
                stats["categorical_summary"][col] = {
                    "unique_count": df[col].nunique(),
                    "most_frequent": (
                        df[col].mode().iloc[0] if not df[col].mode().empty else None
                    ),
                    "frequency": df[col].value_counts().head().to_dict(),
                }

        # Data quality flags
        total_missing = df.isnull().sum().sum()
        missing_percentage = (total_missing / (len(df) * len(df.columns))) * 100

        if missing_percentage > HIGH_MISSING_VALUES_THRESHOLD:
            stats["quality_flags"].append("HIGH_MISSING_VALUES")

        if len(df) < SMALL_DATASET_THRESHOLD:
            stats["quality_flags"].append("SMALL_DATASET")

        # Check for potential target column (cnt)
        if "cnt" in df.columns:
            cnt_stats = {
                "mean": df["cnt"].mean(),
                "std": df["cnt"].std(),
                "skewness": df["cnt"].skew(),
                "zeros": (df["cnt"] == 0).sum(),
                "zero_percentage": ((df["cnt"] == 0).sum() / len(df)) * 100,
            }
            stats["target_analysis"] = cnt_stats

            try:
                zero_percentage = float(cnt_stats["zero_percentage"])  # type: ignore[arg-type]
            except (ValueError, TypeError):
                zero_percentage = 0.0

            if zero_percentage > OUTLIER_THRESHOLD:
                stats["quality_flags"].append("HIGH_ZERO_COUNT")

        return stats

    def _save_metrics(self, metrics: dict[str, Any], dataset_name: str) -> None:
        """Save metrics to JSON file for tracking over time.

        Args:
            metrics: Metrics dictionary
            dataset_name: Name of the dataset
        """
        # Load existing metrics
        existing_metrics = {}
        if self.metrics_file.exists():
            try:
                with self.metrics_file.open() as f:
                    existing_metrics = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("Could not load existing metrics file, starting fresh")

        # Add new metrics
        if dataset_name not in existing_metrics:
            existing_metrics[dataset_name] = []

        existing_metrics[dataset_name].append(metrics)

        # Keep only last MAX_PROFILES_PER_DATASET profiles per dataset
        if len(existing_metrics[dataset_name]) > MAX_PROFILES_PER_DATASET:
            existing_metrics[dataset_name] = existing_metrics[dataset_name][-MAX_PROFILES_PER_DATASET:]

        # Save updated metrics
        with self.metrics_file.open("w") as f:
            json.dump(existing_metrics, f, indent=2, default=str)

    def get_quality_summary(self, dataset_name: str | None = None) -> dict[str, Any]:
        """Get quality summary for a specific dataset or all datasets.

        Args:
            dataset_name: Specific dataset name, or None for all datasets

        Returns:
            Quality summary dictionary
        """
        if not self.metrics_file.exists():
            return {"error": "No metrics file found"}

        with self.metrics_file.open() as f:
            all_metrics = cast(dict[str, Any], json.load(f))

        if dataset_name:
            dataset_result: dict[str, Any] = all_metrics.get(
                dataset_name, {"error": f"Dataset {dataset_name} not found"}
            )
            return dataset_result

        all_result: dict[str, Any] = all_metrics
        return all_result

    def _compare_shape_drift(
        self, current_shape: tuple[int, int], baseline_shape: tuple[int, int], threshold: float
    ) -> dict[str, float]:
        """Compare shape drift between current and baseline shapes.

        Args:
            current_shape: Current dataframe shape (rows, cols)
            baseline_shape: Baseline dataframe shape (rows, cols)
            threshold: Drift detection threshold

        Returns:
            Dictionary with drift details for rows and columns
        """
        if len(current_shape) != DATAFRAME_DIMENSIONS or len(baseline_shape) != DATAFRAME_DIMENSIONS:
            return {}

        row_change = abs(current_shape[0] - baseline_shape[0]) / baseline_shape[0]
        col_change = abs(current_shape[1] - baseline_shape[1]) / baseline_shape[1]

        return {
            "shape_rows": row_change,
            "shape_cols": col_change
        }

    def _compare_missing_values_drift(
        self, current_missing: dict[str, Any], baseline_missing: dict[str, Any], threshold: float
    ) -> dict[str, float]:
        """Compare missing values drift between current and baseline.

        Args:
            current_missing: Current missing values dictionary
            baseline_missing: Baseline missing values dictionary
            threshold: Drift detection threshold

        Returns:
            Dictionary with drift details for missing values
        """
        drift_details = {}

        for col, current_val in current_missing.items():
            if col in baseline_missing:
                baseline_val = baseline_missing[col]

                if isinstance(current_val, (int, float)) and isinstance(baseline_val, (int, float)):
                    change = abs(current_val - baseline_val) / max(baseline_val, 1)
                    drift_details[f"missing_{col}"] = change

        return drift_details

    def detect_data_drift(
        self,
        current_metrics: dict[str, Any],
        historical_metrics: list[dict[str, Any]],
        threshold: float = 0.1,
    ) -> dict[str, Any]:
        """Detect data drift between current and historical metrics.

        Args:
            current_metrics: Current dataset metrics
            historical_metrics: List of historical metrics
            threshold: Drift detection threshold

        Returns:
            Drift detection results
        """
        if not historical_metrics:
            return {
                "status": "no_baseline",
                "message": "No historical data for comparison",
            }

        # Use most recent historical metrics as baseline
        baseline = historical_metrics[-1]

        drift_results: dict[str, Any] = {
            "status": "no_drift",
            "drift_detected": False,
            "drift_score": 0.0,
            "drift_details": {},
        }

        # Compare key metrics
        key_metrics = ["shape", "missing_percentage"]

        for metric in key_metrics:
            if metric in current_metrics and metric in baseline:
                if metric == "shape":
                    # Compare shape (rows, columns)
                    shape_drift = self._compare_shape_drift(
                        current_metrics[metric], baseline[metric], threshold
                    )
                    drift_results["drift_details"].update(shape_drift)

                    if any(change > threshold for change in shape_drift.values()):
                        drift_results["drift_detected"] = True

                elif isinstance(current_metrics[metric], dict) and isinstance(baseline[metric], dict):
                    # Compare missing values percentage
                    missing_drift = self._compare_missing_values_drift(
                        current_metrics[metric], baseline[metric], threshold
                    )
                    drift_results["drift_details"].update(missing_drift)

                    if any(change > threshold for change in missing_drift.values()):
                        drift_results["drift_detected"] = True

        # Calculate overall drift score
        if drift_results["drift_details"]:
            drift_results["drift_score"] = np.mean(
                list(drift_results["drift_details"].values())
            )

        if drift_results["drift_detected"]:
            drift_results["status"] = "drift_detected"

        return drift_results


def profile_dataset(
    df: pd.DataFrame, dataset_name: str, profile_dir: str = "/opt/airflow/data/profiles"
) -> str:
    """Convenience function to profile a dataset.

    Args:
        df: DataFrame to profile
        dataset_name: Name of the dataset
        profile_dir: Directory to store profiles

    Returns:
        Path to generated profile report
    """
    profiler = DataProfiler(profile_dir)
    return profiler.generate_profile_report(df, dataset_name)
