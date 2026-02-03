"""Great Expectations data profiling and validation utilities.

Production-compatible alternative to pandas-profiling.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Data quality threshold constants
ZERO_PERCENTAGE_THRESHOLD = 20

# Great Expectations imports with graceful fallback
try:
    from great_expectations.data_context import EphemeralDataContext
    from great_expectations.expectations.core import (
        ExpectColumnMaxToBeBetween,
        ExpectColumnMeanToBeBetween,
        ExpectColumnMinToBeBetween,
        ExpectColumnValuesToBeOfType,
        ExpectColumnValuesToNotBeNull,
        ExpectColumnValueZScoresToBeLessThan,
        ExpectTableColumnsToMatchOrderedList,
    )

    GX_AVAILABLE = True
except ImportError:
    logger.warning("Great Expectations not available. Data profiling will be disabled.")
    GX_AVAILABLE = False

logger = logging.getLogger(__name__)


def create_gx_data_docs(  # noqa: C901, PLR0915
    df: pd.DataFrame, dataset_name: str, docs_dir: str = "/opt/airflow/data/docs"
) -> str:
    """Generate Great Expectations Data Docs for a dataset.

    Args:
        df: DataFrame to profile
        dataset_name: Name of the dataset
        docs_dir: Directory to store Data Docs

    Returns:
        Path to generated Data Docs index
    """
    if not GX_AVAILABLE:
        raise ImportError(
            "Great Expectations is not installed. Install with: pip install great-expectations"
        )

    if len(df) == 0:
        raise ValueError("Cannot profile empty DataFrame")

    # Create docs directory
    docs_path = Path(docs_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    # Create ephemeral context with proper configuration
    from great_expectations.data_context.types.base import DataContextConfig, InMemoryStoreBackendDefaults
    
    data_context_config = DataContextConfig(
        store_backend_defaults=InMemoryStoreBackendDefaults()
    )
    context = EphemeralDataContext(project_config=data_context_config)

    # Create expectation suite name
    suite_name = f"{dataset_name}_suite"
    
    # Add expectations based on data characteristics
    validator = context.get_validator(
        batch_data=df,
        create_expectation_suite_with_name=suite_name
    )

    # Basic structure expectations
    validator.expect_table_columns_to_match_ordered_list(column_list=list(df.columns))

    # Column type expectations
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        if "int" in dtype_str:
            validator.expect_column_values_to_be_of_type(column=col, type_="int")
        elif "float" in dtype_str:
            validator.expect_column_values_to_be_of_type(column=col, type_="float")
        elif "object" in dtype_str:
            validator.expect_column_values_to_be_of_type(column=col, type_="str")

        # Outlier detection - use correct parameter name
        if "int" in dtype_str or "float" in dtype_str:
            validator.expect_column_z_scores_to_be_less_than(
                column=col, threshold=3.0  # Correct parameter name
            )

    # Numeric column expectations
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        # Non-null expectation
        if df[col].isnull().sum() == 0:
            validator.expect_column_values_to_not_be_null(column=col)

        # Range expectations
        col_min = df[col].min()
        col_max = df[col].max()
        col_mean = df[col].mean()

        # Add reasonable range expectations
        validator.expect_column_min_to_be_between(
            column=col, min_value=col_min * 0.9, max_value=col_min * 1.1
        )

        validator.expect_column_max_to_be_between(
            column=col, min_value=col_max * 0.9, max_value=col_max * 1.1
        )

        validator.expect_column_mean_to_be_between(
            column=col, min_value=col_mean * 0.9, max_value=col_mean * 1.1
        )

    # Special handling for target column (cnt)
    if "cnt" in df.columns:
        cnt_col = df["cnt"]

        # Non-negative values
        validator.expect_column_min_to_be_between(column="cnt", min_value=0, max_value=0)

        # Reasonable range for bike counts
        validator.expect_column_max_to_be_between(
            column="cnt",
            min_value=cnt_col.max() * 0.9,
            max_value=cnt_col.max() * 1.1,
        )

        # Check for excessive zeros
        zero_percentage = (cnt_col == 0).sum() / len(cnt_col) * 100
        if zero_percentage > ZERO_PERCENTAGE_THRESHOLD:
            logger.warning(
                f"High zero percentage in cnt column: {zero_percentage:.1f}%"
            )

    # Validate expectations
    validation_result = validator.validate()

    # Generate summary statistics
    summary_stats = {
        "dataset_name": dataset_name,
        "timestamp": datetime.now().isoformat(),
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
        "numeric_summary": {},
        "validation_results": {
            "success": validation_result.success,
            "statistics": getattr(validation_result, 'statistics', {}),
            "expectations_count": len(getattr(validation_result, 'results', [])),
            "failed_expectations": len(
                [r for r in getattr(validation_result, 'results', []) if not getattr(r, 'success', True)]
            ),
        },
    }

    # Numeric columns analysis
    if len(numeric_cols) > 0:
        summary_stats["numeric_summary"] = df[numeric_cols].describe().to_dict()

    # Save summary statistics
    stats_file = (
        docs_path
        / f"{dataset_name}_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with stats_file.open("w") as f:
        json.dump(summary_stats, f, indent=2, default=str)

    # Build Data Docs
    context.build_data_docs()

    # Get the Data Docs index path
    data_docs_index = docs_path / "index.html"

    logger.info(f"Generated Great Expectations Data Docs for {dataset_name}")
    logger.info(f"Data Docs index: {data_docs_index}")
    logger.info(f"Summary statistics: {stats_file}")

    return str(data_docs_index)


def profile_dataset_gx(
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

    try:
        return create_gx_data_docs(df, dataset_name, docs_dir)
    except Exception as e:
        logger.error(f"Failed to generate Data Docs for {dataset_name}: {e!s}")
        raise
