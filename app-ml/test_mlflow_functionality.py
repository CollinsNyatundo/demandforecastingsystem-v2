#!/usr/bin/env python3
"""
Test MLflow functionality by connecting to the tracking server
"""

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import sys
import requests
import time


def test_mlflow_connection():
    """Test connection to MLflow tracking server"""
    print("[INFO] Testing MLflow Connection")
    print("=" * 50)
    
    try:
        # Set tracking URI
        mlflow.set_tracking_uri("http://localhost:5000")
        
        # Test connection by getting experiments
        experiments = mlflow.search_experiments()
        print(f"[PASS] Connected to MLflow server")
        print(f"[INFO] Found {len(experiments)} existing experiments")
        
        for exp in experiments:
            print(f"  - {exp.name} (ID: {exp.experiment_id})")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to connect to MLflow: {str(e)}")
        return False


def test_mlflow_experiment_creation():
    """Test creating an MLflow experiment"""
    print("\n[INFO] Testing MLflow Experiment Creation")
    print("=" * 50)
    
    try:
        # Create experiment
        experiment_name = f"demand_forecasting_test_{int(time.time())}"
        experiment_id = mlflow.create_experiment(
            name=experiment_name,
            tags={"purpose": "system_test", "environment": "development"}
        )
        
        print(f"[PASS] Created experiment: {experiment_name} (ID: {experiment_id})")
        
        # Set experiment
        mlflow.set_experiment(experiment_name)
        
        return experiment_id
        
    except Exception as e:
        print(f"[FAIL] Failed to create experiment: {str(e)}")
        return None


def test_mlflow_run_and_model():
    """Test creating an MLflow run and logging a model"""
    print("\n[INFO] Testing MLflow Run and Model Logging")
    print("=" * 50)
    
    try:
        # Generate sample data
        np.random.seed(42)
        X = np.random.rand(100, 5)
        y = np.random.rand(100) * 100
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Start MLflow run
        with mlflow.start_run(run_name="demand_forecasting_test_run") as run:
            print(f"[INFO] Started run: {run.info.run_id}")
            
            # Train model
            model = RandomForestRegressor(n_estimators=10, random_state=42)
            model.fit(X_train, y_train)
            
            # Make predictions
            y_pred = model.predict(X_test)
            
            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # Log parameters
            mlflow.log_param("n_estimators", 10)
            mlflow.log_param("random_state", 42)
            mlflow.log_param("test_size", 0.2)
            
            # Log metrics
            mlflow.log_metric("mse", mse)
            mlflow.log_metric("r2", r2)
            mlflow.log_metric("training_samples", len(X_train))
            mlflow.log_metric("test_samples", len(X_test))
            
            # Log model
            mlflow.sklearn.log_model(
                model, 
                "random_forest_model",
                registered_model_name="demand_forecasting_test_model"
            )
            
            print(f"[PASS] Logged model and metrics")
            print(f"[INFO] MSE: {mse:.4f}")
            print(f"[INFO] R2: {r2:.4f}")
            
            return run.info.run_id
            
    except Exception as e:
        print(f"[FAIL] Failed to create run/log model: {str(e)}")
        return None


def test_mlflow_model_registry():
    """Test MLflow model registry functionality"""
    print("\n[INFO] Testing MLflow Model Registry")
    print("=" * 50)
    
    try:
        # Get registered models
        registered_models = mlflow.search_registered_models()
        
        print(f"[INFO] Found {len(registered_models)} registered models")
        
        for model in registered_models:
            print(f"  - {model.name}")
            print(f"    Latest versions: {len(model.latest_versions)}")
            
            for version in model.latest_versions:
                print(f"      Version {version.version}: {version.status}")
        
        # Test model serving prediction
        if registered_models:
            model_name = registered_models[0].name
            latest_version = registered_models[0].latest_versions[0].version
            
            print(f"[PASS] Model registry working with {model_name} v{latest_version}")
            return True
        else:
            print("[WARN] No registered models found")
            return False
            
    except Exception as e:
        print(f"[FAIL] Model registry test failed: {str(e)}")
        return False


def test_mlflow_ui_access():
    """Test MLflow UI accessibility"""
    print("\n[INFO] Testing MLflow UI Access")
    print("=" * 50)
    
    try:
        # Test UI endpoints
        endpoints = [
            "http://localhost:5000",
            "http://localhost:5000/experiments",
            "http://localhost:5000/models"
        ]
        
        for endpoint in endpoints:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                print(f"[PASS] {endpoint} accessible")
            else:
                print(f"[FAIL] {endpoint} returned {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] UI access test failed: {str(e)}")
        return False


def main():
    print("=" * 60)
    print("MLFLOW FUNCTIONALITY TEST")
    print("=" * 60)
    
    results = {}
    
    # Test connection
    results['connection'] = test_mlflow_connection()
    
    if results['connection']:
        # Test experiment creation
        experiment_id = test_mlflow_experiment_creation()
        results['experiment_creation'] = experiment_id is not None
        
        if results['experiment_creation']:
            # Test run and model logging
            run_id = test_mlflow_run_and_model()
            results['run_and_model'] = run_id is not None
            
            # Test model registry
            results['model_registry'] = test_mlflow_model_registry()
        else:
            results['run_and_model'] = False
            results['model_registry'] = False
    
    # Test UI access
    results['ui_access'] = test_mlflow_ui_access()
    
    # Summary
    print("\n" + "=" * 60)
    print("MLFLOW TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test, result in results.items():
        if result:
            print(f"[PASS] {test}")
            passed += 1
        else:
            print(f"[FAIL] {test}")
            failed += 1
    
    print(f"\nTotal Tests: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n[SUCCESS] All MLflow tests passed!")
        return 0
    else:
        print(f"\n[PARTIAL] {failed} MLflow test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
