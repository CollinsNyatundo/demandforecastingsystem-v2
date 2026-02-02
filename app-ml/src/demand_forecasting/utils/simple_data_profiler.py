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
MAX_PROFILES_PER_DATASET = 10


class SimpleDataProfiler:
    """Simple data profiling and quality monitoring inspired by EDA notebook.

    Uses basic pandas operations instead of pandas-profiling to avoid dependency issues.
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

        # Generate summary statistics
        summary_stats = self._generate_summary_stats(df, dataset_name)

        # Save metrics
        self._save_metrics(summary_stats, dataset_name)

        # Generate simple HTML report
        report_path = self._generate_html_report(df, summary_stats, dataset_name)

        logger.info(f"Generated profile report for {dataset_name}: {report_path}")
        return str(report_path)

    def _generate_summary_stats(self, df: pd.DataFrame, dataset_name: str) -> dict[str, Any]:
        """Generate summary statistics similar to EDA notebook analysis.

        Args:
            df: DataFrame to analyze
            dataset_name: Name of the dataset

        Returns:
            Dictionary with summary statistics
        """
        stats = {
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
            "quality_flags": []
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
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        if len(categorical_cols) > 0:
            for col in categorical_cols:
                stats["categorical_summary"][col] = {
                    "unique_count": df[col].nunique(),
                    "most_frequent": df[col].mode().iloc[0] if not df[col].mode().empty else None,
                    "frequency": df[col].value_counts().head().to_dict()
                }

        # Data quality flags
        total_missing = df.isnull().sum().sum()
        missing_percentage = (total_missing / (len(df) * len(df.columns))) * 100

        if missing_percentage > MISSING_VALUES_THRESHOLD:
            stats["quality_flags"].append("HIGH_MISSING_VALUES")

        if len(df) < SMALL_DATASET_THRESHOLD:
            stats["quality_flags"].append("SMALL_DATASET")

        # Check for potential target column (cnt)
        if 'cnt' in df.columns:
            cnt_stats = {
                "mean": df['cnt'].mean(),
                "std": df['cnt'].std(),
                "skewness": df['cnt'].skew(),
                "zeros": (df['cnt'] == 0).sum(),
                "zero_percentage": ((df['cnt'] == 0).sum() / len(df)) * 100
            }
            stats["target_analysis"] = cnt_stats

            if cnt_stats["zero_percentage"] > OUTLIER_THRESHOLD:
                stats["quality_flags"].append("HIGH_ZERO_COUNT")

        return stats

    def _format_number(self, value: object) -> str:
        """Helper function to format numbers safely."""
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)

    def _generate_html_report(self, df: pd.DataFrame, stats: dict[str, Any], dataset_name: str) -> str:
        """Generate a simple HTML report.

        Args:
            df: DataFrame being profiled
            stats: Summary statistics
            dataset_name: Name of the dataset

        Returns:
            Path to generated HTML report
        """
        report_path = self.profile_dir / f"{dataset_name}_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

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
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Data Profile Report</h1>
                <h2>{dataset_name}</h2>
                <p>Generated: {stats['timestamp']}</p>
            </div>

            <div class="section">
                <h3>Dataset Overview</h3>
                <table class="stats-table">
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Shape</td><td>{stats['shape']}</td></tr>
                    <tr><td>Columns</td><td>{len(stats['columns'])}</td></tr>
                    <tr><td>Total Missing Values</td><td>{sum(stats['missing_values'].values())}</td></tr>
                </table>
            </div>

            <div class="section">
                <h3>Quality Flags</h3>
                {"".join([f'<p class="quality-flag">⚠️ {flag}</p>' for flag in stats.get('quality_flags', [])]) or '<p>No quality issues detected ✅</p>'}
            </div>

            <div class="section">
                <h3>Numeric Summary</h3>
                <table class="stats-table">
                    <tr><th>Column</th><th>Count</th><th>Mean</th><th>Std</th><th>Min</th><th>Max</th></tr>
                    {"".join([f'''
                    <tr>
                        <td>{col}</td>
                        <td>{stats['numeric_summary'][col].get('count', 'N/A')}</td>
                        <td>{stats['numeric_summary'][col].get('mean', 'N/A'):.2f if isinstance(stats['numeric_summary'][col].get('mean'), (int, float)) else stats['numeric_summary'][col].get('mean', 'N/A')}</td>
                        <td>{stats['numeric_summary'][col].get('std', 'N/A'):.2f if isinstance(stats['numeric_summary'][col].get('std'), (int, float)) else stats['numeric_summary'][col].get('std', 'N/A')}</td>
                        <td>{stats['numeric_summary'][col].get('min', 'N/A')}</td>
                        <td>{stats['numeric_summary'][col].get('max', 'N/A')}</td>
                    </tr>
                    ''' for col in stats.get('numeric_summary', {})])}
                </table>
            </div>

            <div class="section">
                <h3>Missing Values</h3>
                <table class="stats-table">
                    <tr><th>Column</th><th>Missing Count</th><th>Missing %</th></tr>
                    {"".join([f'''
                    <tr>
                        <td>{col}</td>
                        <td>{stats['missing_values'][col]}</td>
                        <td>{stats['missing_percentage'][col]:.2f}%</td>
                    </tr>
                    ''' for col in stats['missing_values'] if stats['missing_values'][col] > 0])}
                </table>
            </div>
        </body>
        </html>
        """

        with report_path.open('w', encoding='utf-8') as f:
            f.write(html_content)

        return str(report_path)

    def _save_metrics(self, metrics: dict[str, Any], dataset_name: str):
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
        with self.metrics_file.open('w') as f:
            json.dump(existing_metrics, f, indent=2, default=str)

    def get_quality_summary(self, dataset_name: str = None) -> dict[str, Any]:
        """Get quality summary for a specific dataset or all datasets.

        Args:
            dataset_name: Specific dataset name, or None for all datasets

        Returns:
            Quality summary dictionary
        """
        if not self.metrics_file.exists():
            return {"error": "No metrics file found"}

        with self.metrics_file.open() as f:
            all_metrics = json.load(f)

        if dataset_name:
            return all_metrics.get(dataset_name, {"error": f"Dataset {dataset_name} not found"})

        return all_metrics


def profile_dataset(df: pd.DataFrame, dataset_name: str, profile_dir: str = "/opt/airflow/data/profiles") -> str:
    """Convenience function to profile a dataset.

    Args:
        df: DataFrame to profile
        dataset_name: Name of the dataset
        profile_dir: Directory to store profiles

    Returns:
        Path to generated profile report
    """
    profiler = SimpleDataProfiler(profile_dir)
    return profiler.generate_profile_report(df, dataset_name)
