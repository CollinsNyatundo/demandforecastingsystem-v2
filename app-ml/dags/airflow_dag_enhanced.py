"""
Enhanced Demand Forecasting DAG with MLflow & Optuna Persistence

This DAG extends the refactored version with:
- Optuna study persistence to PostgreSQL
- MLflow experiment tracking
- Model versioning with timestamps
- Parallel Optuna optimization (optional)
- Comprehensive metrics logging

Version: 2.1.0
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import pendulum
from airflow import DAG
from airflow.datasets import Dataset
from airflow.decorators import dag, task
from airflow.utils.email import send_email

# Kedro Imports
from kedro.config import OmegaConfigLoader
from kedro.framework.project import configure_project
from kedro.framework.startup import bootstrap_project
from kedro.io import DataCatalog

# Project Imports
from demand_forecasting.pipelines.data_processing.nodes import preprocess_data
from demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
    optimize_catboost_params,
    train_catboost_model,
)
from demand_forecasting.pipelines.feature_engineering.nodes import (
    extract_temporal_features,
    create_feature_interactions,
)
from demand_forecasting.utils import (
    get_email_config,
    get_s3_filesystem,
    validate_model_save,
    validate_search_space_parameters,
)

# Optional imports (graceful degradation if not installed)
try:
    import mlflow
    import mlflow.catboost

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logging.warning("MLflow not installed. Experiment tracking disabled.")

try:
    import optuna
    from optuna.storages import RDBStorage

    OPTUNA_PERSISTENCE_AVAILABLE = True
except ImportError:
    OPTUNA_PERSISTENCE_AVAILABLE = False
    logging.warning("Optuna RDBStorage not available. Study persistence disabled.")

# CONSTANTS
PROJECT_PATH = "/opt/airflow"
CONF_SOURCE = "conf"
PACKAGE_NAME = "demand_forecasting"
S3_BUCKET = os.environ.get("S3_BUCKET", "demand-forecasting")

# MLflow Configuration
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "demand_forecasting")

# Optuna Persistence Configuration
OPTUNA_STORAGE_URL = os.environ.get(
    "OPTUNA_STORAGE_URL", "postgresql://airflow:airflow@postgres:5432/optuna"
)
OPTUNA_STUDY_NAME = os.environ.get("OPTUNA_STUDY_NAME", "demand_forecasting_study")

# Dataset Declarations
RAW_DATA_DATASET = Dataset("s3://demand-forecasting/01_raw/raw_data_full.parquet")
PREPROCESSED_DATA_DATASET = Dataset(
    "s3://demand-forecasting/02_intermediate/preprocessed_data.parquet"
)
MODEL_INPUT_DATASET = Dataset("s3://demand-forecasting/03_primary/model_input.parquet")
TRAINED_MODEL_DATASET = Dataset("s3://demand-forecasting/06_models/regressor.pickle")

# Email configuration - MUST come from environment variable, no hardcoded defaults
EMAIL_RECIPIENTS = (
    os.environ.get("AIRFLOW_ALERT_EMAIL", "").split(",")
    if os.environ.get("AIRFLOW_ALERT_EMAIL")
    else []
)

default_args = {
    "owner": "kedro",
    "start_date": pendulum.datetime(2024, 1, 1, tz="UTC"),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "email": EMAIL_RECIPIENTS,
    "email_on_failure": False,
    "email_on_retry": False,
}

logger = logging.getLogger(__name__)


def get_catalog():
    """Bootstrap Kedro Context and return DataCatalog and config loader"""
    configure_project(PACKAGE_NAME)
    project_path = PROJECT_PATH
    bootstrap_project(project_path)

    # Load configuration
    env = os.environ.get("KEDRO_ENV", "local")
    conf_loader = OmegaConfigLoader(
        conf_source=f"{project_path}/{CONF_SOURCE}", env=env
    )
    conf_catalog = conf_loader["catalog"]
    conf_creds = conf_loader["credentials"]

    # Create Catalog
    catalog = DataCatalog.from_config(conf_catalog, conf_creds)
    return catalog, conf_loader


def setup_mlflow() -> Optional[str]:
    """
    Set up MLflow experiment tracking.

    Returns:
        Run ID if MLflow is available, None otherwise
    """
    if not MLFLOW_AVAILABLE:
        logger.warning("MLflow not available. Skipping experiment tracking.")
        return None

    try:
        # Set tracking URI
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

        # Set or create experiment
        try:
            experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT_NAME)
            if experiment is None:
                experiment_id = mlflow.create_experiment(MLFLOW_EXPERIMENT_NAME)
                logger.info(f"Created MLflow experiment: {MLFLOW_EXPERIMENT_NAME}")
            else:
                experiment_id = experiment.experiment_id
        except Exception as e:
            logger.warning(f"Could not set up MLflow experiment: {e}")
            return None

        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

        # Start MLflow run
        run = mlflow.start_run(
            run_name=f"demand_forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Log system information
        mlflow.set_tag("pipeline_version", "2.1.0")
        mlflow.set_tag("model_type", "CatBoost")
        mlflow.set_tag("optimization", "Optuna_TPESampler")

        logger.info(f"✅ MLflow tracking enabled. Run ID: {run.info.run_id}")
        return run.info.run_id

    except Exception as e:
        logger.error(f"Failed to set up MLflow: {e}")
        return None


def get_optuna_storage():
    """
    Get Optuna storage backend for study persistence.

    Returns:
        RDBStorage instance or None if not available
    """
    if not OPTUNA_PERSISTENCE_AVAILABLE:
        logger.warning("Optuna persistence not available. Studies will not be saved.")
        return None

    try:
        storage = RDBStorage(
            url=OPTUNA_STORAGE_URL,
            engine_kwargs={
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,
            },
        )
        logger.info(f"✅ Optuna persistence enabled. Storage: {OPTUNA_STORAGE_URL}")
        return storage
    except Exception as e:
        logger.error(f"Failed to set up Optuna storage: {e}")
        logger.warning("Falling back to in-memory storage (studies will not persist)")
        return None


def send_failure_notification(context: dict, error_message: str):
    """Send email notification on task failure."""
    email_config = get_email_config()
    if not email_config:
        logger.warning("Email not configured. Skipping failure notification.")
        return

    try:
        task_instance = context.get("task_instance")
        dag_id = context.get("dag").dag_id
        task_id = task_instance.task_id
        execution_date = context.get("execution_date")

        send_email(
            to=EMAIL_RECIPIENTS,
            subject=f"[AIRFLOW] Task Failed - {dag_id}.{task_id}",
            html_content=f"""
            <h3>Airflow Task Failure</h3>
            <p><strong>DAG:</strong> {dag_id}</p>
            <p><strong>Task:</strong> {task_id}</p>
            <p><strong>Execution Date:</strong> {execution_date}</p>
            <p><strong>Error:</strong></p>
            <pre>{error_message}</pre>
            <p>Please check the Airflow logs for more details.</p>
            """,
        )
    except Exception as e:
        logger.error(f"Failed to send failure notification: {e}")


@dag(
    dag_id="demand_forecasting_enhanced",
    default_args=default_args,
    schedule="@daily",
    catchup=False,
    tags=["kedro", "ml", "production", "catboost", "optuna", "mlflow", "enhanced"],
    doc_md="""
    ## Demand Forecasting ML Pipeline (Enhanced v2.1)

    **Purpose:** Production ML pipeline with MLflow tracking and Optuna persistence

    **Enhancements over v2.0:**
    - ✅ MLflow experiment tracking (metrics, parameters, models)
    - ✅ Optuna study persistence to PostgreSQL (resume optimization)
    - ✅ Model versioning with timestamps
    - ✅ Comprehensive metrics logging
    - ✅ Graceful degradation if MLflow/Optuna not available

    **Pipeline Steps:**
    1. Data validation and preprocessing
    2. Feature engineering (lag features, temporal features)
    3. Model training with persistent Optuna optimization
    4. Model evaluation and registration (MLflow + S3)

    **Performance Targets:**
    - RMSE: ~51-52 (matching notebook baseline)
    - MAE: ~30-31
    - MAPE: ~22-22.5%

    **New Features:**
    - 📊 MLflow tracking: http://mlflow:5000
    - 💾 Optuna persistence: PostgreSQL database
    - 🏷️ Model versioning: Timestamp-based versions
    - 📈 Rich metrics logging

    **Contact:** cnyagakan@gmail.com
    **Data Source:** MinIO S3 (demand-forecasting bucket)
    **Model Output:** s3://demand-forecasting/06_models/regressor_YYYYMMDD_HHMMSS.pickle
    """,
)
def demand_forecasting_dag():
    @task()
    def t_validate_raw_data() -> dict:
        """
        Validate raw data quality before processing.

        Returns:
            Dictionary with data statistics
        """
        # Set up MLflow (if available)
        mlflow_run_id = setup_mlflow()

        try:
            catalog, _ = get_catalog()
            df = catalog.load("raw_bike_data")

            # Basic validations
            if len(df) == 0:
                raise ValueError("Raw data is empty")

            missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
            if missing_pct > 50:
                raise ValueError(f"Too many missing values: {missing_pct:.2f}%")

            # Collect statistics
            stats = {
                "rows": len(df),
                "columns": len(df.columns),
                "missing_pct": float(missing_pct),
            }

            # Log to MLflow
            if MLFLOW_AVAILABLE and mlflow_run_id:
                mlflow.log_metrics(
                    {
                        "data_rows": stats["rows"],
                        "data_columns": stats["columns"],
                        "data_missing_pct": stats["missing_pct"],
                    }
                )

            logger.info(
                f"✅ Raw data validated: {len(df)} rows, {len(df.columns)} columns"
            )
            logger.info(f"Missing values: {missing_pct:.2f}%")

            if "dteday" in df.columns:
                logger.info(f"Date range: {df['dteday'].min()} to {df['dteday'].max()}")

            return stats

        except Exception as e:
            logger.error(f"❌ Data validation failed: {str(e)}")
            if MLFLOW_AVAILABLE and mlflow_run_id:
                mlflow.log_param("validation_status", "failed")
            raise

    @task(outlets=[PREPROCESSED_DATA_DATASET])
    def t_preprocess():
        """
        Preprocess and clean raw bike demand data.

        Produces: PREPROCESSED_DATA_DATASET
        """
        try:
            catalog, _ = get_catalog()

            # Load raw data
            logger.info("Loading raw data...")
            df = catalog.load("raw_bike_data")

            # Run preprocessing
            logger.info("Running preprocessing...")
            cleaned_df = preprocess_data(df)

            # Validate preprocessed data
            if len(cleaned_df) == 0:
                raise ValueError("Preprocessing resulted in empty DataFrame")

            # Log to MLflow
            if MLFLOW_AVAILABLE:
                mlflow.log_metrics(
                    {
                        "preprocessed_rows": len(cleaned_df),
                        "preprocessed_columns": len(cleaned_df.columns),
                    }
                )

            # Save intermediate data
            catalog.save("preprocessed_bike_data", cleaned_df)

            logger.info(f"✅ Preprocessing complete: {len(cleaned_df)} rows")
            return "Success"

        except Exception as e:
            logger.error(f"❌ Preprocessing failed: {str(e)}")
            raise

    @task(outlets=[MODEL_INPUT_DATASET])
    def t_feature_eng():
        """
        Generate ML-ready features from preprocessed data.

        Produces: MODEL_INPUT_DATASET
        """
        try:
            catalog, _ = get_catalog()

            # Load preprocessed data
            logger.info("Loading preprocessed data...")
            df = catalog.load("preprocessed_bike_data")

            # Load parameters for feature engineering
            # Parameters must be loaded from configuration (parameters.yml)
            from kedro.config import OmegaConfigLoader

            conf_loader = OmegaConfigLoader("conf")
            params = conf_loader["parameters"]
            logger.info("✅ Parameters loaded from configuration")

            # Generate features
            logger.info("Creating temporal features...")
            df_with_temporal = extract_temporal_features(df)

            logger.info("Creating feature interactions with lag features...")
            # IMPORTANT: Pass feature_lags parameters from config to enable lag features
            derived_df = create_feature_interactions(
                df_with_temporal,
                lags=params.get("feature_engineering", {}).get(
                    "target_lags", [1, 2, 22, 23]
                ),
                feature_lags=params.get("feature_engineering", {}).get(
                    "feature_lags", {}
                ),
            )
            logger.info(f"✅ Feature engineering complete. Shape: {derived_df.shape}")

            # Validate feature engineering output
            if len(derived_df) == 0:
                raise ValueError("Feature engineering resulted in empty DataFrame")

            if "target" not in derived_df.columns:
                raise ValueError("Target column missing after feature engineering")

            # Log to MLflow
            if MLFLOW_AVAILABLE:
                mlflow.log_metrics(
                    {
                        "feature_rows": len(derived_df),
                        "feature_columns": len(derived_df.columns),
                        "num_features": len(
                            [c for c in derived_df.columns if c != "target"]
                        ),
                    }
                )

            # Save model input
            catalog.save("model_input_table", derived_df)

            logger.info(
                f"✅ Feature engineering complete: {len(derived_df)} rows, {len(derived_df.columns)} features"
            )
            return "Success"

        except Exception as e:
            logger.error(f"❌ Feature engineering failed: {str(e)}")
            raise

    @task(outlets=[TRAINED_MODEL_DATASET])
    def t_train_optimized_model():
        """
        Train CatBoost model with persistent Optuna optimization and MLflow tracking.

        This task implements:
        - Real Optuna TPESampler Bayesian optimization
        - Study persistence to PostgreSQL (resume between runs)
        - MLflow experiment tracking (metrics, parameters, model)
        - Model versioning with timestamps

        Expected Performance:
        - RMSE: ~51-52 (10-15% better than mock random sampling)
        - MAE: ~30-31
        - MAPE: ~22-22.5%

        Produces: TRAINED_MODEL_DATASET (with timestamp)
        """
        try:
            logger.info("🚀 Starting training task...")
            catalog, conf_loader = get_catalog()
            logger.info("✅ Catalog loaded")

            params = conf_loader["parameters"]
            logger.info("✅ Parameters loaded")

            # Validate search space parameters
            logger.info("Validating search space parameters...")
            validate_search_space_parameters(params)
            logger.info("✅ Parameters validated")

            # Load model input data
            logger.info("Loading model input data...")
            df = catalog.load("model_input_table")

            if len(df) == 0:
                raise ValueError("Model input data is empty")

            logger.info(f"Training data loaded: {len(df)} rows")

            # Set up Optuna storage (if available)
            optuna_storage = get_optuna_storage()

            # Set up MLflow (if available)
            if MLFLOW_AVAILABLE:
                # Set AWS credentials for MLflow S3 artifact storage FROM ENVIRONMENT VARIABLES
                # NEVER hardcode credentials - must come from environment
                minio_access_key = os.environ.get("MINIO_ACCESS_KEY", "")
                minio_secret_key = os.environ.get("MINIO_SECRET_KEY", "")

                if not minio_access_key or not minio_secret_key:
                    logger.warning(
                        "MINIO_ACCESS_KEY or MINIO_SECRET_KEY not set. MLflow S3 storage may fail."
                    )
                    logger.warning(
                        "Please set environment variables: MINIO_ACCESS_KEY, MINIO_SECRET_KEY"
                    )

                os.environ["AWS_ACCESS_KEY_ID"] = minio_access_key
                os.environ["AWS_SECRET_ACCESS_KEY"] = minio_secret_key
                os.environ["AWS_DEFAULT_REGION"] = os.environ.get(
                    "AWS_REGION", "us-east-1"
                )
                logger.info(
                    "✅ AWS credentials set from environment variables for MLflow S3 storage"
                )

                # Start MLflow run
                mlflow_run = mlflow.start_run()
                logger.info(f"✅ MLflow run started: {mlflow_run.info.run_id}")

                # Log parameters
                mlflow.log_params(
                    {
                        "n_trials": params.get("optuna", {}).get("n_trials", 150),
                        "primary_model": params.get("optuna", {}).get(
                            "primary_model", "catboost"
                        ),
                        "train_fraction": params.get("train_fraction", 0.8),
                    }
                )

            # Train CatBoost with Optuna optimization
            logger.info("🚀 Starting CatBoost training with Optuna optimization...")
            logger.info(f"Trials: {params.get('optuna', {}).get('n_trials', 150)}")
            logger.info("Sampler: TPESampler (Bayesian optimization)")

            if optuna_storage:
                logger.info(f"Storage: PostgreSQL (study will persist)")
                logger.info(f"Study name: {OPTUNA_STUDY_NAME}")
            else:
                logger.info("Storage: In-memory (study will not persist)")

            # Import and use catboost optimization
            from demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
                optimize_catboost_params,
                train_catboost_model,
            )

            # CRITICAL: Split data into train/test sets BEFORE optimization
            # This ensures hyperparameters are tuned on training data and evaluated on unseen test data
            # Matches the notebook strategy: 80% train, 20% test
            from sklearn.model_selection import (
                train_test_split as sklearn_train_test_split,
            )

            train_fraction = params.get("train_fraction", 0.8)
            random_state = params.get("data_processing", {}).get("random_state", 42)

            logger.info(
                f"Splitting data: {train_fraction*100:.0f}% train, {(1-train_fraction)*100:.0f}% test"
            )

            # Split the data
            X_full = derived_df.drop("target", axis=1)
            y_full = derived_df["target"]

            X_train, X_test, y_train, y_test = sklearn_train_test_split(
                X_full,
                y_full,
                train_size=train_fraction,
                test_size=1 - train_fraction,
                random_state=random_state,
                shuffle=True,
            )

            logger.info(f"✅ Data split complete:")
            logger.info(f"   Training: {len(X_train)} samples")
            logger.info(f"   Testing: {len(X_test)} samples")
            logger.info(f"   Total: {len(X_full)} samples")

            # Prepare data for training
            # NOTE: optimize_catboost_params will further split X_train internally (80/20)
            # for its own hyperparameter optimization validation set
            # X_test is held completely separate for final evaluation

            # Optimize parameters with persistence
            # NOTE: optimize_catboost_params receives TRAINING data only
            # It will create its own 80/20 split for hyperparameter optimization
            logger.info("🚀 Starting Optuna hyperparameter optimization...")
            optimization_result = optimize_catboost_params(
                X_train,
                y_train,
                n_trials=params.get("optimization", {}).get("n_trials", 150),
                storage=optuna_storage,
                study_name=OPTUNA_STUDY_NAME,
            )
            logger.info("✅ Optuna optimization complete")

            # Extract parameters and metrics
            if (
                isinstance(optimization_result, dict)
                and "best_params" in optimization_result
            ):
                optimized_params = optimization_result["best_params"]
                optuna_metrics = {
                    "rmse": optimization_result["best_value"],
                    "n_trials": optimization_result["n_trials"],
                    "storage_used": optimization_result["storage_used"],
                    "study_name": optimization_result["study_name"],
                }
            else:
                # Backward compatibility
                optimized_params = optimization_result
                optuna_metrics = {"rmse": 0.0, "n_trials": 0, "storage_used": False}

            # Train model with optimized parameters
            # CRITICAL: Now pass both training AND test sets
            # Training set: Used to train the final model on 100% of data
            # Test set: Used to compute final metrics on held-out unseen data
            logger.info("🚀 Starting final CatBoost model training...")
            catboost_model, catboost_metrics = train_catboost_model(
                X_train,
                y_train,  # Full training set
                optimized_params,
                X_test=X_test,  # Held-out test set for evaluation
                y_test=y_test,
            )
            logger.info("✅ Final model training complete")

            # Merge metrics
            catboost_metrics.update(optuna_metrics)

            logger.info("✅ CatBoost training completed!")
            logger.info(f"RMSE: {catboost_metrics['rmse']:.4f}")
            logger.info(f"MAE: {catboost_metrics['mae']:.4f}")
            logger.info(f"MAPE: {catboost_metrics['mape']:.4f}%")
            logger.info(f"Best trial: {catboost_metrics.get('best_trial', 'N/A')}")

            # Log metrics to MLflow
            if MLFLOW_AVAILABLE:
                mlflow.log_metrics(
                    {
                        "rmse": catboost_metrics["rmse"],
                        "mae": catboost_metrics["mae"],
                        "mape": catboost_metrics["mape"],
                        "best_trial": catboost_metrics.get("best_trial", 0),
                    }
                )

                # Log model to MLflow
                try:
                    mlflow.catboost.log_model(
                        catboost_model,
                        "model",
                        registered_model_name="demand_forecasting_catboost",
                    )
                    logger.info("✅ Model logged to MLflow")
                except Exception as e:
                    logger.error(f"❌ Failed to log model to MLflow: {e}")
                    raise

            # Generate timestamp for model versioning
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info(f"Model timestamp: {timestamp}")

            # Save model to S3 with timestamp
            try:
                versioned_model_name = f"regressor_{timestamp}"
                logger.info(f"Saving model as: {versioned_model_name}")
                catalog.save(versioned_model_name, catboost_model)
                logger.info("✅ Model saved with timestamp")
            except Exception as e:
                logger.error(f"❌ Failed to save timestamped model: {e}")
                raise

            # Also save as latest (for backward compatibility)
            try:
                logger.info("Saving model as latest (regressor_model)")
                catalog.save("regressor_model", catboost_model)
                logger.info("✅ Model saved as latest")
            except Exception as e:
                logger.error(f"❌ Failed to save latest model: {e}")
                raise

            # Verify model was saved successfully
            try:
                logger.info("Verifying model save...")
                fs = get_s3_filesystem()
                model_path = f"{S3_BUCKET}/06_models/regressor_{timestamp}.pickle"
                logger.info(f"Verifying path: {model_path}")
                validate_model_save(fs, model_path)
                logger.info("✅ Model verification completed")
            except Exception as e:
                logger.error(f"❌ Model verification failed: {e}")
                raise

            logger.info(f"✅ Model saved and verified: regressor_{timestamp}.pickle")
            logger.info("✅ Model also saved as: regressor.pickle (latest)")

            # Log model path to MLflow
            if MLFLOW_AVAILABLE:
                mlflow.set_tag("model_version", timestamp)
                mlflow.set_tag("model_path", model_path)
                mlflow.log_param("model_timestamp", timestamp)

            # End MLflow run
            if MLFLOW_AVAILABLE:
                mlflow.end_run()

            # Return summary
            return {
                "model_type": "CatBoost",
                "rmse": catboost_metrics["rmse"],
                "mae": catboost_metrics["mae"],
                "mape": catboost_metrics["mape"],
                "best_trial": catboost_metrics.get("best_trial", "N/A"),
                "model_version": timestamp,
                "mlflow_tracking": MLFLOW_AVAILABLE,
                "optuna_persistence": optuna_storage is not None,
                "message": f"CatBoost model trained with RMSE: {catboost_metrics['rmse']:.4f}",
            }

        except Exception as e:
            logger.error(f"❌ Model training failed: {str(e)}")
            if MLFLOW_AVAILABLE:
                mlflow.log_param("training_status", "failed")
                mlflow.end_run(status="FAILED")
            raise

    # Orchestration - Simplified linear pipeline
    validation = t_validate_raw_data()
    prep = t_preprocess()
    feat = t_feature_eng()
    model = t_train_optimized_model()

    # Define dependencies
    validation >> prep >> feat >> model


# Instantiate the DAG
dag_instance = demand_forecasting_dag()
