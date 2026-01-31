#!/usr/bin/env python3
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor

print("Testing MLflow Model Registry...")

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5000")

# Create experiment for registry test
mlflow.set_experiment("model_registry_test")

# Start run and register model
with mlflow.start_run(run_name="registry_test_run") as run:
    print(f"Started run: {run.info.run_id}")
    
    # Simple model
    X = np.random.rand(20, 2)
    y = np.random.rand(20)
    
    model = RandomForestRegressor(n_estimators=3, random_state=42)
    model.fit(X, y)
    
    # Register model
    mlflow.sklearn.log_model(
        model, 
        "model",
        registered_model_name="demand_forecasting_test_model"
    )
    
    print("Model registered successfully")

# Test model registry functionality
try:
    from mlflow.tracking import MlflowClient
    client = MlflowClient()
    
    # List registered models
    models = client.search_registered_models()
    print(f"Found {len(models)} registered models:")
    
    for model in models:
        print(f"  - {model.name}")
        print(f"    Latest versions: {len(model.latest_versions)}")
        
        for version in model.latest_versions:
            print(f"      Version {version.version}: {version.status}")
            print(f"      Run ID: {version.run_id}")
    
    print("Model registry test completed successfully!")
    
except Exception as e:
    print(f"Model registry error: {str(e)}")
