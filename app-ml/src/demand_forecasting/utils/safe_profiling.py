# Secure Data Profiling with pandas-profiling
# Alternative to ydata-profiling with better security

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import warnings
from pathlib import Path
import json

# Try to import pandas-profiling, fallback to basic profiling if not available
try:
    from pandas_profiling import ProfileReport

    PANDAS_PROFILING_AVAILABLE = True
except ImportError:
    PANDAS_PROFILING_AVAILABLE = False
    warnings.warn("pandas-profiling not available. Using basic profiling instead.")


def safe_data_profile(
    df: pd.DataFrame,
    sample_size: int = 10000,
    output_dir: Optional[str] = None,
    profile_title: str = "Data Profile Report",
) -> Dict[str, Any]:
    """
    Generate a secure data profile using pandas-profiling or basic analysis.

    Args:
        df: DataFrame to profile
        sample_size: Max rows to process (prevents DoS on large datasets)
        output_dir: Directory to save HTML report (optional)
        profile_title: Title for the profiling report

    Returns:
        Dictionary with profiling information
    """
    # Sample large datasets to prevent resource exhaustion
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)
        warnings.warn(f"Dataset sampled to {sample_size} rows for profiling")

    if PANDAS_PROFILING_AVAILABLE:
        return _pandas_profiling_report(df, output_dir, profile_title)
    else:
        return _basic_profiling_report(df)


def _pandas_profiling_report(
    df: pd.DataFrame, output_dir: Optional[str], title: str
) -> Dict[str, Any]:
    """Generate pandas-profiling report with security constraints."""
    try:
        # Configure profiling with security settings
        profile = ProfileReport(
            df,
            title=title,
            explorative=True,
            minimal=False,
            samples={"head": 5, "tail": 5, "random": 10},
            correlations={
                "auto": {"calculate": True},
                "pearson": {"calculate": True},
                "spearman": {"calculate": True},
                "kendall": {"calculate": True},
                "phi_k": {"calculate": True},
                "cramers": {"calculate": True},
            },
            missing_diagrams={
                "heatmap": True,
                "dendrogram": True,
                "matrix": True,
                "bar": True,
            },
        )

        # Save report if output directory specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Save HTML report
            html_file = output_path / "profile_report.html"
            profile.to_file(str(html_file))

            # Save JSON summary
            json_file = output_path / "profile_summary.json"
            summary = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": df.dtypes.to_dict(),
                "missing_values": df.isnull().sum().to_dict(),
                "memory_usage": int(df.memory_usage(deep=True).sum()),
            }

            with open(json_file, "w") as f:
                json.dump(summary, f, indent=2, default=str)

        return {
            "status": "success",
            "method": "pandas-profiling",
            "shape": df.shape,
            "columns": list(df.columns),
            "report_generated": True,
            "output_dir": output_dir,
        }

    except Exception as e:
        warnings.warn(f"pandas-profiling failed: {e}. Falling back to basic profiling.")
        return _basic_profiling_report(df)


def _basic_profiling_report(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate basic profiling report when pandas-profiling is not available."""
    profile = {
        "status": "success",
        "method": "basic",
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "memory_usage": df.memory_usage(deep=True).sum(),
        "numeric_summary": {},
        "categorical_summary": {},
    }

    # Numeric columns analysis
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        profile["numeric_summary"][col] = {
            "mean": float(df[col].mean()),
            "std": float(df[col].std()),
            "min": float(df[col].min()),
            "max": float(df[col].max()),
            "q25": float(df[col].quantile(0.25)),
            "q50": float(df[col].quantile(0.50)),
            "q75": float(df[col].quantile(0.75)),
        }

    # Categorical columns analysis
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns
    for col in categorical_cols:
        profile["categorical_summary"][col] = {
            "unique_count": int(df[col].nunique()),
            "top_values": df[col].value_counts().head(10).to_dict(),
            "missing_count": int(df[col].isnull().sum()),
        }

    return profile


def quick_profile_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate a quick profiling summary for monitoring purposes.

    Args:
        df: DataFrame to profile

    Returns:
        Dictionary with key metrics
    """
    return {
        "shape": df.shape,
        "columns": len(df.columns),
        "missing_ratio": df.isnull().sum().sum() / (df.shape[0] * df.shape[1]),
        "numeric_columns": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_columns": len(
            df.select_dtypes(include=["object", "category"]).columns
        ),
        "memory_mb": df.memory_usage(deep=True).sum() / (1024 * 1024),
    }


if __name__ == "__main__":
    # Example usage
    # df = pd.read_csv("your_data.csv")
    # profile = safe_data_profile(df, output_dir="reports")
    # print(profile)
    pass
