"""Great Expectations data profiling and validation utilities.

Production-compatible alternative to pandas-profiling.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Data quality threshold constants
OUTLIER_PERCENTAGE_THRESHOLD = 5
MISSING_VALUES_THRESHOLD = 20
ZERO_COUNT_THRESHOLD = 5
SMALL_DATASET_THRESHOLD = 1000
HIGH_VARIANCE_THRESHOLD = 10


def profile_dataset_gx(  # noqa: C901, PLR0912, PLR0915
    df: pd.DataFrame,
    dataset_name: str,
    docs_dir: str = "/opt/airflow/data/docs",
    enable_data_docs: bool = True,
) -> str | None:
    """Profile dataset using Great Expectations.

    Args:
        df: DataFrame to profile
        dataset_name: Name of the dataset
        docs_dir: Directory to store Data Docs
        enable_data_docs: Whether to generate Data Docs

    Returns:
        Path to generated Data Docs index, or None if disabled
    """
    if not enable_data_docs:
        logger.info(f"Data Docs generation disabled for {dataset_name}")
        return None

    if len(df) == 0:
        raise ValueError("Cannot profile empty DataFrame")

    # Create docs directory
    docs_path = Path(docs_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    # Generate comprehensive profiling report
    quality_flags: List[str] = []
    data_quality_checks: List[str] = []
    profile_data: Dict[str, Any] = {
        "dataset_name": dataset_name,
        "timestamp": datetime.now().isoformat(),
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
        "numeric_summary": {},
        "categorical_summary": {},
        "quality_flags": quality_flags,
        "data_quality_checks": data_quality_checks,
    }

    # Numeric columns analysis
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        profile_data["numeric_summary"] = df[numeric_cols].describe().to_dict()

        # Data quality checks for numeric columns
        for col in numeric_cols:
            col_data = df[col]

            # Check for outliers using IQR method
            Q1 = col_data.quantile(0.25)
            Q3 = col_data.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outliers = col_data[(col_data < lower_bound) | (col_data > upper_bound)]

            if len(outliers) > 0:
                outlier_percentage = (len(outliers) / len(col_data)) * 100
                profile_data["data_quality_checks"].append(
                    {
                        "column": col,
                        "check": "outliers",
                        "status": "warning" if outlier_percentage > OUTLIER_PERCENTAGE_THRESHOLD else "info",
                        "message": f"{len(outliers)} outliers detected ({outlier_percentage:.1f}%)",
                    }
                )

            # Check for zero values
            zero_count = (col_data == 0).sum()
            if zero_count > 0:
                zero_percentage = (zero_count / len(col_data)) * 100
                profile_data["data_quality_checks"].append(
                    {
                        "column": col,
                        "check": "zero_values",
                        "status": "warning" if zero_percentage > MISSING_VALUES_THRESHOLD else "info",
                        "message": f"{zero_count} zero values ({zero_percentage:.1f}%)",
                    }
                )

    # Categorical columns analysis
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns
    if len(categorical_cols) > 0:
        for col in categorical_cols:
            col_data = df[col]
            profile_data["categorical_summary"][col] = {
                "unique_count": col_data.nunique(),
                "most_frequent": (
                    col_data.mode().iloc[0] if not col_data.mode().empty else None
                ),
                "frequency": col_data.value_counts().head().to_dict(),
            }

            # Check for high cardinality
            if col_data.nunique() > len(col_data) * 0.5:
                profile_data["data_quality_checks"].append(
                    {
                        "column": col,
                        "check": "high_cardinality",
                        "status": "warning",
                        "message": f"High cardinality: {col_data.nunique()} unique values",
                    }
                )

    # Overall data quality flags
    total_missing = df.isnull().sum().sum()
    missing_percentage = (total_missing / (len(df) * len(df.columns))) * 100

    if missing_percentage > ZERO_COUNT_THRESHOLD:
        profile_data["quality_flags"].append("HIGH_MISSING_VALUES")

    if len(df) < SMALL_DATASET_THRESHOLD:
        profile_data["quality_flags"].append("SMALL_DATASET")

    # Special handling for target column (cnt)
    if "cnt" in df.columns:
        cnt_stats = {
            "mean": df["cnt"].mean(),
            "std": df["cnt"].std(),
            "skewness": df["cnt"].skew(),
            "zeros": (df["cnt"] == 0).sum(),
            "zero_percentage": ((df["cnt"] == 0).sum() / len(df)) * 100,
        }
        profile_data["target_analysis"] = cnt_stats

        if float(cnt_stats["zero_percentage"]) > HIGH_VARIANCE_THRESHOLD:
            profile_data["quality_flags"].append("HIGH_ZERO_COUNT")

        # Check for negative values (shouldn't exist for bike counts)
        negative_count = (df["cnt"] < 0).sum()
        if negative_count > 0:
            profile_data["data_quality_checks"].append(
                {
                    "column": "cnt",
                    "check": "negative_values",
                    "status": "error",
                    "message": f"{negative_count} negative values detected",
                }
            )

    # Save profiling data
    profile_file = (
        docs_path
        / f"{dataset_name}_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with profile_file.open("w") as f:
        json.dump(profile_data, f, indent=2, default=str)

    # Generate HTML report
    html_file = (
        docs_path
        / f"{dataset_name}_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Data Profile Report - {dataset_name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .stats-table {{ width: 100%; border-collapse: collapse; }}
            .stats-table th, .stats-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .stats-table th {{ background-color: #f2f2f2; }}
            .quality-flag {{ color: #d9534f; font-weight: bold; }}
            .quality-check {{ margin: 5px 0; padding: 5px; border-radius: 3px; }}
            .error {{ background-color: #f8d7da; border: 1px solid #f5c6cb; }}
            .warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; }}
            .info {{ background-color: #d1ecf1; border: 1px solid #bee5eb; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Data Profile Report</h1>
            <h2>{dataset_name}</h2>
            <p>Generated: {profile_data['timestamp']}</p>
        </div>

        <div class="section">
            <h3>Dataset Overview</h3>
            <table class="stats-table">
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Shape</td><td>{profile_data['shape']}</td></tr>
                <tr><td>Columns</td><td>{len(profile_data['columns'])}</td></tr>
                <tr><td>Total Missing Values</td><td>{sum(profile_data['missing_values'].values())}</td></tr>
            </table>
        </div>

        <div class="section">
            <h3>Quality Flags</h3>
            {"".join([f'<p class="quality-flag">⚠️ {flag}</p>' for flag in profile_data.get('quality_flags', [])]) or '<p>No quality issues detected ✅</p>'}
        </div>

        <div class="section">
            <h3>Data Quality Checks</h3>
            {"".join([f'''
            <div class="quality-check {check['status']}">
                <strong>{check['column']} - {check['check']}:</strong> {check['message']}
            </div>
            ''' for check in profile_data.get('data_quality_checks', [])])}
        </div>

        <div class="section">
            <h3>Numeric Summary</h3>
            <table class="stats-table">
                <tr><th>Column</th><th>Count</th><th>Mean</th><th>Std</th><th>Min</th><th>Max</th></tr>
                {"".join([f'''
                <tr>
                    <td>{col}</td>
                    <td>{profile_data['numeric_summary'][col].get('count', 'N/A')}</td>
                    <td>{profile_data['numeric_summary'][col].get('mean', 'N/A'):.2f}</td>
                    <td>{profile_data['numeric_summary'][col].get('std', 'N/A'):.2f}</td>
                    <td>{profile_data['numeric_summary'][col].get('min', 'N/A')}</td>
                    <td>{profile_data['numeric_summary'][col].get('max', 'N/A')}</td>
                </tr>
                ''' for col in profile_data.get('numeric_summary', {})])}
            </table>
        </div>

        <div class="section">
            <h3>Missing Values</h3>
            <table class="stats-table">
                <tr><th>Column</th><th>Missing Count</th><th>Missing %</th></tr>
                {"".join([f'''
                <tr>
                    <td>{col}</td>
                    <td>{profile_data['missing_values'][col]}</td>
                    <td>{profile_data['missing_percentage'][col]:.2f}%</td>
                </tr>
                ''' for col in profile_data['missing_values'] if profile_data['missing_values'][col] > 0])}
            </table>
        </div>
    </body>
    </html>
    """

    with html_file.open("w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Generated data profile report for {dataset_name}")
    logger.info(f"HTML report: {html_file}")
    logger.info(f"JSON data: {profile_file}")

    return str(html_file)
