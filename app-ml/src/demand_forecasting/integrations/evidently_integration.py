"""Evidently Integration Module.

Data drift and model performance monitoring for production.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

_LOGGER = logging.getLogger(__name__)

try:
    from evidently import ColumnMapping
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    from evidently.metrics import DataDriftTable, DatasetDriftMetric
    from evidently.report import Report

    EVIDENTLY_AVAILABLE = True
except ImportError:
    EVIDENTLY_AVAILABLE = False
    _LOGGER.warning("Evidently not installed. Drift monitoring disabled.")


def generate_drift_report(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
    output_path: Path | str,
    column_mapping: dict[str, Any] | None = None,
    numerical_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> dict[str, Any]:
    """Generate Evidently data drift report.

    Args:
        reference_data: Historical/training data
        current_data: Current production data
        output_path: Path to save HTML report
        column_mapping: Optional explicit column type mapping
        numerical_features: List of numerical feature names
        categorical_features: List of categorical feature names

    Returns:
        Dictionary with drift metrics and report path
    """
    if not EVIDENTLY_AVAILABLE:
        return {"error": "Evidently not available", "drift_detected": False}

    # Build column mapping
    mapping_kwargs = column_mapping or {}
    if numerical_features:
        mapping_kwargs["numerical_features"] = numerical_features
    if categorical_features:
        mapping_kwargs["categorical_features"] = categorical_features

    mapping = ColumnMapping(**mapping_kwargs) if mapping_kwargs else None

    # Create report with drift metrics
    report = Report(
        metrics=[
            DatasetDriftMetric(),
            DataDriftPreset(),
            DataQualityPreset(),
        ]
    )

    report.run(
        reference_data=reference_data,
        current_data=current_data,
        column_mapping=mapping,
    )

    # Save HTML report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(output_path))
    _LOGGER.info(f"Drift report saved to {output_path}")

    # Extract metrics
    result_dict = report.as_dict()
    metrics = result_dict.get("metrics", [])

    dataset_drift = False
    drift_share = 0.0
    drifted_columns: list[str] = []

    for metric in metrics:
        metric_result = metric.get("result", {})
        if "dataset_drift" in metric_result:
            dataset_drift = metric_result.get("dataset_drift", False)
            drift_share = metric_result.get("drift_share", 0.0)
            drifted_columns = [
                col
                for col, info in metric_result.get("drift_by_columns", {}).items()
                if info.get("drift_detected", False)
            ]
            break

    return {
        "drift_detected": dataset_drift,
        "drift_share": drift_share,
        "drifted_columns": drifted_columns,
        "report_path": str(output_path),
        "generated_at": datetime.utcnow().isoformat(),
    }


def get_drift_metrics_for_prometheus(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
) -> dict[str, float]:
    """Get drift metrics formatted for Prometheus exposition.

    Returns dict of metric_name -> value for Prometheus gauges.

    Args:
        reference_data: Reference/training data
        current_data: Current production data

    Returns:
        Dictionary of Prometheus-compatible metrics
    """
    if not EVIDENTLY_AVAILABLE:
        return {}

    report = Report(metrics=[DatasetDriftMetric()])
    report.run(reference_data=reference_data, current_data=current_data)

    result = report.as_dict()
    metrics = result.get("metrics", [{}])[0].get("result", {})

    return {
        "evidently_dataset_drift": 1.0 if metrics.get("dataset_drift") else 0.0,
        "evidently_drift_share": metrics.get("drift_share", 0.0),
        "evidently_columns_total": float(metrics.get("number_of_columns", 0)),
        "evidently_columns_drifted": float(metrics.get("number_of_drifted_columns", 0)),
    }


def check_drift_threshold(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
    threshold: float = 0.1,
) -> tuple[bool, dict[str, Any]]:
    """Check if data drift exceeds threshold.

    Args:
        reference_data: Reference/training data
        current_data: Current production data
        threshold: Drift share threshold (0.0 to 1.0)

    Returns:
        Tuple of (drift_exceeds_threshold, metrics_dict)
    """
    if not EVIDENTLY_AVAILABLE:
        return False, {"error": "Evidently not available"}

    report = Report(metrics=[DatasetDriftMetric()])
    report.run(reference_data=reference_data, current_data=current_data)

    result = report.as_dict()
    metrics = result.get("metrics", [{}])[0].get("result", {})

    drift_share = metrics.get("drift_share", 0.0)
    exceeds_threshold = drift_share > threshold

    return exceeds_threshold, {
        "drift_share": drift_share,
        "threshold": threshold,
        "exceeds_threshold": exceeds_threshold,
        "dataset_drift": metrics.get("dataset_drift", False),
    }
