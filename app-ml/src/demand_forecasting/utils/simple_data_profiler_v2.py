"""Simplified data profiling and quality monitoring utilities.

Uses basic pandas profiling instead of pandas-profiling to avoid dependency issues.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Data quality threshold constants
MISSING_VALUES_THRESHOLD = 5
SMALL_DATASET_THRESHOLD = 1000
OUTLIER_THRESHOLD = 10


def profile_dataset(  # noqa: C901
    df: pd.DataFrame, dataset_name: str, profile_dir: str = "/opt/airflow/data/profiles"
) -> str:
    """Simple profiling function that generates basic statistics.

    Args:
        df: DataFrame to profile
        dataset_name: Name of the dataset
        profile_dir: Directory to store profiles

    Returns:
        Path to generated profile report
    """
    if len(df) == 0:
        raise ValueError("Cannot profile empty DataFrame")

    # Create profile directory
    profile_path = Path(profile_dir)
    profile_path.mkdir(parents=True, exist_ok=True)

    # Generate basic statistics
    quality_flags: list[str] = []
    stats: dict[str, Any] = {
        "dataset_name": dataset_name,
        "timestamp": datetime.now().isoformat(),
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "numeric_summary": {},
        "quality_flags": quality_flags,
    }

    # Numeric columns analysis
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        stats["numeric_summary"] = df[numeric_cols].describe().to_dict()

    # Data quality flags
    total_missing = df.isnull().sum().sum()
    missing_percentage = (total_missing / (len(df) * len(df.columns))) * 100

    if missing_percentage > MISSING_VALUES_THRESHOLD:
        stats["quality_flags"].append("HIGH_MISSING_VALUES")

    if len(df) < SMALL_DATASET_THRESHOLD:
        stats["quality_flags"].append("SMALL_DATASET")

    # Check for potential target column (cnt)
    if "cnt" in df.columns:
        cnt_stats = {
            "mean": df["cnt"].mean(),
            "std": df["cnt"].std(),
            "zeros": (df["cnt"] == 0).sum(),
            "zero_percentage": ((df["cnt"] == 0).sum() / len(df)) * 100,
        }
        stats["target_analysis"] = cnt_stats

        if cnt_stats["zero_percentage"] > OUTLIER_THRESHOLD:
            stats["quality_flags"].append("HIGH_ZERO_COUNT")

    # Save metrics to JSON
    metrics_file = (
        profile_path
        / f"{dataset_name}_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with metrics_file.open("w") as f:
        json.dump(stats, f, indent=2, default=str)

    # Generate simple text report
    report_file = (
        profile_path
        / f"{dataset_name}_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    with report_file.open("w") as f:
        f.write(f"Data Profile Report - {dataset_name}\n")
        f.write(f"Generated: {stats['timestamp']}\n")
        f.write(f"Shape: {stats['shape']}\n")
        f.write(f"Columns: {len(stats['columns'])}\n")
        f.write(
            f"Quality Flags: {', '.join(stats['quality_flags']) if stats['quality_flags'] else 'None'}\n\n"
        )

        if stats.get("target_analysis"):
            f.write("Target Analysis (cnt):\n")
            for key, value in stats["target_analysis"].items():
                f.write(f"  {key}: {value:.2f}\n")
            f.write("\n")

        if stats["numeric_summary"]:
            f.write("Numeric Summary:\n")
            for col, col_stats in stats["numeric_summary"].items():
                f.write(f"\n{col}:\n")
                for stat, value in col_stats.items():
                    f.write(f"  {stat}: {value:.2f}\n")

    logger.info(f"Generated profile report for {dataset_name}: {report_file}")
    return str(report_file)
