import pandas as pd
from pathlib import Path

# Path to the data file
file_path = Path(r"d:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\data\raw_data\raw_data_full.parquet")

try:
    df = pd.read_parquet(file_path)
    print("Columns:")
    print(df.columns.tolist())
    print("\nFirst 5 rows:")
    print(df.head())
    print("\nData Types:")
    print(df.dtypes)
except Exception as e:
    print(f"Error reading file: {e}")
