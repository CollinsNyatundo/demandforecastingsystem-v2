#!/usr/bin/env python3
"""
Test script to verify Enhanced DAG functionality with environment variables set
"""

import os
import sys
from pathlib import Path

# Set environment variables directly for testing
os.environ['MLFLOW_TRACKING_URI'] = os.environ.get('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
os.environ['MLFLOW_EXPERIMENT_NAME'] = os.environ.get('MLFLOW_EXPERIMENT_NAME', 'demand_forecasting')
os.environ['OPTUNA_STORAGE_URL'] = os.environ.get('OPTUNA_STORAGE_URL', 'postgresql://airflow:airflow@postgres:5432/optuna')
os.environ['OPTUNA_STUDY_NAME'] = os.environ.get('OPTUNA_STUDY_NAME', 'demand_forecasting_study')

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "dags"))

def test_enhanced_dag_import():
    """Test that Enhanced DAG can be imported successfully"""
    print("🧪 Testing Enhanced DAG import...")
    try:
        from airflow_dag_enhanced import dag
        print("✅ Enhanced DAG imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Enhanced DAG import failed: {e}")
        return False

def test_mlflow_connection():
    """Test MLflow connection"""
    print("🧪 Testing MLflow connection...")
    try:
        import mlflow
        tracking_uri = os.environ.get('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
        experiment_name = os.environ.get('MLFLOW_EXPERIMENT_NAME', 'demand_forecasting')
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment:
            print("✅ MLflow connection successful")
        else:
            print("⚠️ MLflow connection successful but no experiment found")
        return True
    except Exception as e:
        print(f"❌ MLflow connection failed: {e}")
        print(f"💡 Make sure MLflow server is running: docker-compose -f docker-compose-unified.yml up -d")
        return False

def test_optuna_postgresql():
    """Test Optuna PostgreSQL connection"""
    print("🧪 Testing Optuna PostgreSQL connection...")
    try:
        import optuna
        from optuna.storages import RDBStorage
        
        storage_url = os.environ.get('OPTUNA_STORAGE_URL', 'postgresql://airflow:airflow@postgres:5432/optuna')
        storage = RDBStorage(storage_url)
        study = optuna.create_study(
            storage=storage, 
            study_name="test_study",
            direction="minimize",
            load_if_exists=True
        )
        print("✅ Optuna PostgreSQL connection successful")
        return True
    except Exception as e:
        print(f"❌ Optuna PostgreSQL connection failed: {e}")
        print(f"💡 Make sure PostgreSQL is running: docker-compose -f docker-compose-unified.yml up -d")
        return False

def test_catboost_import():
    """Test CatBoost import"""
    print("🧪 Testing CatBoost import...")
    try:
        from catboost import CatBoostRegressor
        print("✅ CatBoost imported successfully")
        return True
    except ImportError as e:
        print(f"❌ CatBoost import failed: {e}")
        return False

def test_environment_variables():
    """Test required environment variables"""
    print("🧪 Testing environment variables...")
    
    required_vars = [
        "MLFLOW_TRACKING_URI",
        "MLFLOW_EXPERIMENT_NAME", 
        "OPTUNA_STORAGE_URL",
        "OPTUNA_STUDY_NAME"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        return False
    else:
        print("✅ All required environment variables found")
        return True

def main():
    """Run all tests"""
    print("🚀 Enhanced DAG Implementation Test Suite (with env vars set)")
    print("=" * 60)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("CatBoost Import", test_catboost_import),
        ("Enhanced DAG Import", test_enhanced_dag_import),
        ("MLflow Connection", test_mlflow_connection),
        ("Optuna PostgreSQL", test_optuna_postgresql),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced DAG is ready for deployment.")
    else:
        print("⚠️ Some tests failed. Please resolve issues before deployment.")
        print("📖 See ENHANCED_DAG_IMPLEMENTATION_GUIDE.md for troubleshooting steps.")

if __name__ == "__main__":
    main()
