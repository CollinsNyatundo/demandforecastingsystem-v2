"""Seed raw bike data for local/Docker runs.

Creates data/01_raw/raw_bike_data.parquet with minimal valid rows matching
RawBikeDataSchema so the Airflow DAG and Kedro pipeline can run.

Usage:
  From app-ml: python scripts/seed_raw_data.py
  From repo root: python app-ml/scripts/seed_raw_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    raw_dir = project_root / "data" / "01_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / "raw_bike_data.parquet"

    # Minimal valid rows matching RawBikeDataSchema (strict)
    n = 500  # enough for train/test split and feature lags
    np.random.seed(42)
    df = pd.DataFrame({
        "datetime": pd.date_range("2011-01-01", periods=n, freq="h").astype(str),
        "season": np.random.randint(1, 5, size=n),
        "yr": np.random.randint(0, 2, size=n),
        "mnth": np.random.randint(1, 13, size=n),
        "hr": np.random.randint(0, 24, size=n),
        "holiday": np.random.randint(0, 2, size=n),
        "weekday": np.random.randint(0, 7, size=n),
        "workingday": np.random.randint(0, 2, size=n),
        "weathersit": np.random.randint(1, 5, size=n),
        "temp": np.clip(np.random.randn(n) * 0.15 + 0.5, 0.0, 1.0),
        "atemp": np.clip(np.random.randn(n) * 0.15 + 0.48, 0.0, 1.0),
        "hum": np.clip(np.random.randn(n) * 0.15 + 0.6, 0.0, 1.0),
        "windspeed": np.clip(np.random.randn(n) * 0.1 + 0.2, 0.0, 1.0),
        "casual": np.random.poisson(35, size=n),
        "registered": np.random.poisson(120, size=n),
    })
    df["cnt"] = df["casual"] + df["registered"]

    df.to_parquet(out_path, index=False)
    print(f"Created {out_path} with {len(df)} rows.")


if __name__ == "__main__":
    main()
