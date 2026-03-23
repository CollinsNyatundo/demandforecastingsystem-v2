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
    # Evidently v0.7.x API (paths changed significantly from v0.4.x)
    from evidently import Report
    from evidently.presets import DataDriftPreset, DataSummaryPreset
    from evidently.metrics import ValueDrift, DriftedColumnsCount
    from evidently.legacy.pipeline.column_mapping import ColumnMapping

    # Compatibility aliases so rest of module keeps working unchanged
    DataDriftTable = ValueDrift
    DatasetDriftMetric = DriftedColumnsCount
    DataQualityPreset = DataSummaryPreset  # renamed in v0.7.x

    EVIDENTLY_AVAILABLE = True
except ImportError as e:
    EVIDENTLY_AVAILABLE = False
    _LOGGER.warning(f"Evidently not available - drift monitoring disabled: {e}")


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

    # Extract metrics via v0.7.x direct attribute access on metric objects
    dataset_drift = False
    drift_share = 0.0
    drifted_columns: list[str] = []

    for metric in report.items():
        drift_share_val = getattr(metric, 'drift_share', None)
        if drift_share_val is not None:
            drift_share = float(drift_share_val)
            dataset_drift = drift_share > 0.0
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
    Column counts are derived from the shared numeric columns between
    reference and current data (Evidently v0.7.x does not expose per-column
    drift counts via the public metric attribute API, so we compute them
    from the input DataFrames directly).

    Args:
        reference_data: Reference/training data
        current_data: Current production data

    Returns:
        Dictionary of Prometheus-compatible metrics
    """
    if not EVIDENTLY_AVAILABLE:
        return {}

    # Determine total monitored columns (numeric columns shared by both sets)
    shared_cols = set(reference_data.select_dtypes(include='number').columns) & \
                  set(current_data.select_dtypes(include='number').columns)
    n_total = len(shared_cols)

    report = Report(metrics=[DatasetDriftMetric()])
    report.run(reference_data=reference_data, current_data=current_data)

    drift_share = 0.0
    dataset_drift = False
    for metric in report.items():
        ds = getattr(metric, 'drift_share', None)
        if ds is not None:
            drift_share = float(ds)
            dataset_drift = drift_share > 0.0
            break

    # Estimate drifted column count from share × total
    n_drifted = round(drift_share * n_total) if n_total > 0 else 0

    return {
        "evidently_dataset_drift": 1.0 if dataset_drift else 0.0,
        "evidently_drift_share": drift_share,
        "evidently_columns_total": float(n_total),
        "evidently_columns_drifted": float(n_drifted),
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

    drift_share = 0.0
    for metric in report.items():
        ds = getattr(metric, 'drift_share', None)
        if ds is not None:
            drift_share = float(ds)
            break

    exceeds_threshold = drift_share > threshold

    return exceeds_threshold, {
        "drift_share": drift_share,
        "threshold": threshold,
        "exceeds_threshold": exceeds_threshold,
        "dataset_drift": drift_share > 0.0,
    }
