"""Shared theme configuration for the UrbanFlow Intelligence dashboard.

Centralizes color tokens, Plotly defaults, and data loading utilities
so that all pages and components import from one location.
"""

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

# Setup paths — use PROJECT_ROOT env var when running inside Docker
project_root = Path(
    os.environ.get("PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))
)
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app-ml" / "src"))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
THEME = {
    "bg": "#09090b",
    "paper": "rgba(24, 24, 27, 0.65)",
    "text": "#fafafa",
    "text_secondary": "#b4b4be",  # WCAG-AA contrast on dark bg
    "blue": "#3b82f6",
    "cyan": "#06b6d4",
    "green": "#10b981",
    "purple": "#8b5cf6",
    "amber": "#f59e0b",
    "rose": "#f43f5e",
    "grid": "rgba(255, 255, 255, 0.04)",
}

# Plotly template shared across all charts
PLOTLY_DEFAULTS = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {
        "family": "Inter, system-ui, sans-serif",
        "color": THEME["text"],
        "size": 12,
    },
    "margin": {"l": 40, "r": 20, "t": 20, "b": 20},
    "hovermode": "x unified",
}

# ---------------------------------------------------------------------------
# Application state (shared across pages)
# ---------------------------------------------------------------------------
app_state = {
    "data_loaded": False,
    "startup_time": datetime.now(UTC).isoformat(),
    "error": None,
    "row_count": 0,
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
df = pd.DataFrame()


def load_data() -> pd.DataFrame:
    """Load bike-sharing demand dataset from various locations."""
    global df
    search_paths = [
        project_root / "app-ml" / "data" / "01_raw" / "raw_data_full.parquet",
        project_root / "data" / "raw_data_full.parquet",
        Path("/project/app-ml/data/01_raw/raw_data_full.parquet"),
        Path("/project/data/raw_data_full.parquet"),
        Path(__file__).parent / "data" / "raw_data_full.parquet",
    ]
    for p in search_paths:
        if p.exists():
            logger.info(f"Loading data from {p}")
            try:
                df = pd.read_parquet(p)
            except Exception as e:
                logger.error(f"Failed to read {p}: {e}")
                continue
            break

    if df.empty:
        logger.warning("No data found — using empty DataFrame")
        app_state["data_loaded"] = False
        return df

    try:
        # Add helper columns
        if "dteday" in df.columns:
            df["datetime"] = pd.to_datetime(df["dteday"], errors="coerce")
        elif "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        else:
            df["datetime"] = pd.to_datetime(df.index, errors="coerce")

        if "date" not in df.columns:
            df["date"] = df["datetime"].dt.date

        season_map = {1: "spring", 2: "summer", 3: "fall", 4: "winter"}
        if "season" in df.columns and "season_label" not in df.columns:
            df["season_label"] = df["season"].map(season_map).fillna("unknown")
        elif "season_label" not in df.columns:
            df["season_label"] = "unknown"
    except Exception as e:
        logger.warning(f"Data column setup failed: {e}. Using raw data.")

    app_state["data_loaded"] = True
    app_state["row_count"] = len(df)
    logger.info(f"Data loaded: {len(df)} rows")
    return df


# Load on import
try:
    from common.utils import read_config

    config_path = project_root / "config" / "config.yaml"
    config = read_config(config_path) if config_path.exists() else {}
except Exception:
    config = {}

try:
    load_data()
except Exception as e:
    logger.warning(f"Initial data load failed: {e}")
