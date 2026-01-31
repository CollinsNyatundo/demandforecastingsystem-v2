import os
import ast

baseDir = r"D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Check each critical file
files = {
    "Feature Engineering": "src/demand_forecasting/pipelines/feature_engineering/nodes.py",
    "Demand Modeling": "src/demand_forecasting/pipelines/demand_modeling/nodes.py",
    "CatBoost": "src/demand_forecasting/pipelines/demand_modeling/catboost_nodes.py",
}

for name, rel_path in files.items():
    full_path = os.path.join(baseDir, rel_path.replace("/", "\\"))
    with open(full_path, "r") as f:
        first_line = f.readline()
    
    if first_line.startswith("#"):
        print(f"[OK] {name}: starts with docstring/comment")
    elif first_line.startswith("import"):
        print(f"[OK] {name}: starts with import")
    else:
        print(f"[CHECK] {name}: first line is '{first_line[:50]}'")
