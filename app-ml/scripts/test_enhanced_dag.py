#!/usr/bin/env python3
"""
Test script to verify Enhanced DAG functionality
Tests imports, MLflow connection, and Optuna persistence
"""

import sys
import os
from pathlib import Path

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

        mlflow.set_tracking_uri("http://localhost:5000")
        experiment = mlflow.get_experiment_by_name("demand_forecasting")
        if experiment:
            print("✅ MLflow connection successful")
        else:
            print("⚠️ MLflow connection successful but no experiment found")
        return True
    except Exception as e:
        print(f"❌ MLflow connection failed: {e}")
        print(
            "💡 Make sure MLflow server is running: docker-compose -f docker-compose-enhanced.yml up -d"
        )
        return False


def test_optuna_postgresql():
    """Test Optuna PostgreSQL connection"""
    print("🧪 Testing Optuna PostgreSQL connection...")
    try:
        import optuna
        from optuna.storages import RDBStorage

        storage = RDBStorage("postgresql://airflow:airflow@localhost:5432/optuna")
        study = optuna.create_study(
            storage=storage,
            study_name="test_study",
            direction="minimize",
            load_if_exists=True,
        )
        print("✅ Optuna PostgreSQL connection successful")
        return True
    except Exception as e:
        print(f"❌ Optuna PostgreSQL connection failed: {e}")
        print(
            "💡 Make sure PostgreSQL is running: docker-compose -f docker-compose-enhanced.yml up -d"
        )
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
        "OPTUNA_STUDY_NAME",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        print("💡 Copy .env.example to .env and configure the variables")
        return False
    else:
        print("✅ All required environment variables found")
        return True


def main():
    """Run all tests"""
    print("🚀 Enhanced DAG Implementation Test Suite")
    print("=" * 50)

    tests = [
        ("Enhanced DAG Import", test_enhanced_dag_import),
        ("CatBoost Import", test_catboost_import),
        ("Environment Variables", test_environment_variables),
        ("MLflow Connection", test_mlflow_connection),
        ("Optuna PostgreSQL", test_optuna_postgresql),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        result = test_func()
        results.append((test_name, result))

    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)

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
