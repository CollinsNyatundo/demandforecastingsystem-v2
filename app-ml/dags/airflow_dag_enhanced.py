"""Enhanced Demand Forecasting DAG with MLflow & Optuna Persistence.

This DAG extends the refactored version with:
- Optuna study persistence to PostgreSQL
- MLflow experiment tracking
- Model versioning with timestamps
- Parallel Optuna optimization (optional)
- Comprehensive metrics logging

Version: 2.1.0
"""

import logging
import os
from datetime import datetime, timedelta

import pendulum
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
from demand_forecasting.pipelines.feature_engineering.nodes import (
    create_feature_interactions,
    extract_temporal_features,
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

# ClearML Integration (complements MLflow)
try:
    from clearml import Task as ClearMLTask
    CLEARML_AVAILABLE = True
except ImportError:
    CLEARML_AVAILABLE = False
    ClearMLTask = None  # type: ignore[misc, assignment]
    logging.warning("ClearML not installed. ClearML experiment tracking disabled.")

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
    """Bootstrap Kedro Context and return DataCatalog and config loader."""
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


def setup_mlflow() -> str | None:
    """Set up MLflow experiment tracking.

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
                mlflow.create_experiment(MLFLOW_EXPERIMENT_NAME)
                logger.info(f"Created MLflow experiment: {MLFLOW_EXPERIMENT_NAME}")
            else:
                pass
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
    """Get Optuna storage backend for study persistence.

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

    **Contact:** Set AIRFLOW_ALERT_EMAIL environment variable for alerts
    **Data Source:** MinIO S3 (demand-forecasting bucket)
    **Model Output:** s3://demand-forecasting/06_models/regressor_YYYYMMDD_HHMMSS.pickle
    """,
)
def demand_forecasting_dag():
    @task()
    def t_validate_raw_data() -> dict:
        """Validate raw data quality before processing.

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
            logger.error(f"❌ Data validation failed: {e!s}")
            if MLFLOW_AVAILABLE and mlflow_run_id:
                mlflow.log_param("validation_status", "failed")
            raise

    @task(outlets=[PREPROCESSED_DATA_DATASET])
    def t_preprocess() -> str | None:
        """Preprocess and clean raw bike demand data.

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
            logger.error(f"❌ Preprocessing failed: {e!s}")
            raise

    @task(outlets=[MODEL_INPUT_DATASET])
    def t_feature_eng() -> str | None:
        """Generate ML-ready features from preprocessed data.

        Produces: MODEL_INPUT_DATASET
        """
        try:
            catalog, _ = get_catalog()

            # Load preprocessed data
            logger.info("Loading preprocessed data...")
            df = catalog.load("preprocessed_bike_data")

            # Load parameters for feature engineering (use same conf source as get_catalog)
            _, conf_loader = get_catalog()
            params = conf_loader["parameters"]
            logger.info("✅ Parameters loaded from configuration")

            # Generate features
            logger.info("Creating temporal features...")
            df_with_temporal = extract_temporal_features(df)

            logger.info("Creating feature interactions with lag features...")
            # IMPORTANT: Pass feature_lags parameters from config to enable lag features
            # Using 'demand_lags' (matching notebook's cnt_lag) for current demand lags
            derived_df = create_feature_interactions(
                df_with_temporal,
                lags=params.get("feature_engineering", {}).get(
                    "demand_lags", [1, 2, 22, 23]
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
            logger.error(f"❌ Feature engineering failed: {e!s}")
            raise

    @task(outlets=[TRAINED_MODEL_DATASET])
    def t_train_optimized_model():
        """Train CatBoost model with persistent Optuna optimization and MLflow tracking.

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

            # Initialize ClearML task (complements MLflow)
            clearml_task = None
            if CLEARML_AVAILABLE:
                try:
                    clearml_task = ClearMLTask.init(
                        project_name="demand_forecasting",
                        task_name="catboost_training_dag",
                        task_type="training",
                        auto_connect_frameworks=True,  # Auto-capture CatBoost, Optuna
                    )
                    logger.info(f"✅ ClearML task initialized: {clearml_task.id}")
                except Exception as e:
                    logger.warning(f"ClearML init failed (non-fatal): {e}")
                    clearml_task = None

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
                logger.info("Storage: PostgreSQL (study will persist)")
                logger.info(f"Study name: {OPTUNA_STUDY_NAME}")
            else:
                logger.info("Storage: In-memory (study will not persist)")

            # Import and use catboost optimization
            # CRITICAL: Split data into train/test sets BEFORE optimization
            # This ensures hyperparameters are tuned on training data and evaluated on unseen test data
            # Matches the notebook strategy: 80% train, 20% test
            from sklearn.model_selection import (
                train_test_split as sklearn_train_test_split,
            )

            from demand_forecasting.pipelines.demand_modeling.catboost_nodes import (
                optimize_catboost_params,
                train_catboost_model,
            )

            train_fraction = params.get("train_fraction", 0.8)
            random_state = params.get("data_processing", {}).get("random_state", 42)

            logger.info(
                f"Splitting data: {train_fraction*100:.0f}% train, {(1-train_fraction)*100:.0f}% test"
            )

            # Split the data using SEQUENTIAL split (NO shuffle!)
            # This is CRITICAL for time series - we must not leak future data into training
            # Matching notebook: x_train, x_test = x[:train_size], x[train_size:]
            X_full = df.drop("target", axis=1)
            y_full = df["target"]

            train_size = int(train_fraction * len(X_full))
            X_train = X_full.iloc[:train_size]
            X_test = X_full.iloc[train_size:]
            y_train = y_full.iloc[:train_size]
            y_test = y_full.iloc[train_size:]

            logger.info("✅ Data split complete (sequential, no shuffle):")
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
                n_trials=params.get("optuna", {}).get("n_trials", 150),
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

            # Save versioned model directly to S3 (catalog doesn't support dynamic names)
            import pickle

            try:
                fs = get_s3_filesystem()
                versioned_model_path = f"{S3_BUCKET}/06_models/regressor_{timestamp}.pickle"
                logger.info(f"Saving versioned model to: {versioned_model_path}")

                with fs.open(versioned_model_path, "wb") as f:
                    pickle.dump(catboost_model, f)
                logger.info("✅ Versioned model saved to S3")
            except Exception as e:
                logger.error(f"❌ Failed to save timestamped model: {e}")
                raise

            # Also save as latest using catalog (for backward compatibility)
            try:
                logger.info("Saving model as latest (regressor_model)")
                catalog.save("regressor_model", catboost_model)
                logger.info("✅ Model saved as latest")
            except Exception as e:
                logger.error(f"❌ Failed to save latest model: {e}")
                raise

            # Verify versioned model was saved successfully
            try:
                logger.info("Verifying versioned model save...")
                validate_model_save(fs, versioned_model_path)
                logger.info("✅ Versioned model verification completed")
            except Exception as e:
                logger.error(f"❌ Model verification failed: {e}")
                raise

            logger.info(f"✅ Model saved and verified: regressor_{timestamp}.pickle")
            logger.info("✅ Model also saved as: regressor.pickle (latest)")

            # Log model path to MLflow
            if MLFLOW_AVAILABLE:
                mlflow.set_tag("model_version", timestamp)
                mlflow.set_tag("model_path", versioned_model_path)
                mlflow.log_param("model_timestamp", timestamp)

            # End MLflow run
            if MLFLOW_AVAILABLE:
                mlflow.end_run()

            # Close ClearML task
            if clearml_task:
                clearml_task.close()
                logger.info("✅ ClearML task closed")

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
            logger.error(f"❌ Model training failed: {e!s}")
            if MLFLOW_AVAILABLE:
                mlflow.log_param("training_status", "failed")
                mlflow.end_run(status="FAILED")
            if clearml_task:
                clearml_task.mark_failed(status_reason=str(e))
            raise

    @task
    def t_train_multi_objective():
        """Train model using multi-objective optimization.

        Multi-objective optimization finds Pareto-optimal solutions
        balancing multiple metrics (RMSE, MAE, training time).

        Enable via parameters.yml: advanced_features.enable_multi_objective: true
        """
        try:
            logger.info("🚀 Starting multi-objective optimization...")
            catalog, conf_loader = get_catalog()
            params = conf_loader["parameters"]

            # Check if multi-objective is enabled
            if not params.get("advanced_features", {}).get("enable_multi_objective", False):
                logger.info("Multi-objective optimization disabled. Skipping...")
                return {"status": "skipped", "reason": "disabled_in_config"}

            # Load data
            df = catalog.load("model_input_table")
            if len(df) == 0:
                raise ValueError("Model input data is empty")

            # Import multi-objective optimizer
            from demand_forecasting.optimization.multi_objective import (
                MultiObjectiveOptimizer,
            )

            # Sequential split for time series
            train_fraction = params.get("train_fraction", 0.8)
            X_full = df.drop("target", axis=1)
            y_full = df["target"]

            train_size = int(train_fraction * len(X_full))
            X_train = X_full.iloc[:train_size]
            X_test = X_full.iloc[train_size:]
            y_train = y_full.iloc[:train_size]
            y_test = y_full.iloc[train_size:]

            # Configure objectives
            objectives = params.get("advanced_features", {}).get(
                "multi_objective_targets", ["rmse", "mae", "training_time"]
            )
            directions = ["minimize"] * len(objectives)

            # Create and run optimizer
            optimizer = MultiObjectiveOptimizer(objectives, directions)
            optimizer.create_study(
                study_name="demand_forecasting_multi_objective",
                storage=get_optuna_storage(),
            )

            n_trials = params.get("advanced_features", {}).get("multi_objective_trials", 50)
            results = optimizer.optimize(X_train, X_test, y_train, y_test, n_trials=n_trials)

            # Get recommended solution
            preference_weights = params.get("advanced_features", {}).get(
                "objective_weights", {"rmse": 0.5, "mae": 0.3, "training_time": 0.2}
            )
            recommendation = optimizer.recommend_solution(preference_weights)

            logger.info(f"✅ Multi-objective optimization complete")
            logger.info(f"Pareto-optimal solutions found: {results['n_pareto_trials']}")
            logger.info(f"Recommended trial: {recommendation}")

            # Log to MLflow
            if MLFLOW_AVAILABLE:
                with mlflow.start_run(run_name="multi_objective_optimization"):
                    mlflow.log_params({
                        "objectives": ",".join(objectives),
                        "n_trials": n_trials,
                        "pareto_solutions": results["n_pareto_trials"],
                    })

            return {
                "status": "success",
                "pareto_solutions": results["n_pareto_trials"],
                "recommended_params": recommendation.get("recommended_trial", {}).get("params", {}),
                "objectives": objectives,
            }

        except Exception as e:
            logger.error(f"❌ Multi-objective optimization failed: {e}")
            return {"status": "failed", "error": str(e)}

    @task
    def t_train_ensemble():
        """Train ensemble model combining multiple algorithms.

        Ensemble methods (stacking/voting) can improve prediction robustness
        by combining CatBoost, XGBoost, LightGBM, and RandomForest.

        Enable via parameters.yml: advanced_features.enable_ensemble: true
        """
        try:
            logger.info("🚀 Starting ensemble training...")
            catalog, conf_loader = get_catalog()
            params = conf_loader["parameters"]

            # Check if ensemble is enabled
            if not params.get("advanced_features", {}).get("enable_ensemble", False):
                logger.info("Ensemble training disabled. Skipping...")
                return {"status": "skipped", "reason": "disabled_in_config"}

            # Load data
            df = catalog.load("model_input_table")
            if len(df) == 0:
                raise ValueError("Model input data is empty")

            # Import ensemble manager
            from demand_forecasting.optimization.ensemble import EnsembleManager

            # Sequential split for time series
            train_fraction = params.get("train_fraction", 0.8)
            X_full = df.drop("target", axis=1)
            y_full = df["target"]

            train_size = int(train_fraction * len(X_full))
            X_train = X_full.iloc[:train_size]
            X_test = X_full.iloc[train_size:]
            y_train = y_full.iloc[:train_size]
            y_test = y_full.iloc[train_size:]

            # Create ensemble manager
            ensemble_manager = EnsembleManager()

            # Get ensemble type from config
            ensemble_type = params.get("advanced_features", {}).get("ensemble_type", "stacking")

            if ensemble_type == "stacking":
                # Create stacking ensemble
                catboost_params = params.get("model_training", {}).get("catboost", {})
                ensemble_manager.create_stacking_ensemble(catboost_params=catboost_params)
            else:
                # Create voting ensemble with default models
                from catboost import CatBoostRegressor
                from sklearn.ensemble import RandomForestRegressor

                models = [
                    ("catboost", CatBoostRegressor(iterations=500, verbose=False, random_seed=42)),
                    ("rf", RandomForestRegressor(n_estimators=100, random_state=42)),
                ]
                ensemble_manager.create_voting_ensemble(models)

            # Train ensemble
            logger.info(f"Training {ensemble_type} ensemble...")
            train_results = ensemble_manager.train_ensemble(X_train, y_train, X_test, y_test)

            # Evaluate on test set
            eval_results = ensemble_manager.evaluate_ensemble(X_test, y_test)

            logger.info(f"✅ Ensemble training complete")
            logger.info(f"Ensemble RMSE: {eval_results['ensemble_metrics']['rmse']:.4f}")
            logger.info(f"Improvement over best base: {eval_results['improvements']['rmse_improvement_percent']:.2f}%")

            # Save ensemble model
            fs = get_s3_filesystem()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ensemble_path = f"{S3_BUCKET}/06_models/ensemble_{timestamp}.joblib"
            
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
                ensemble_manager.save_ensemble(tmp.name)
                with open(tmp.name, "rb") as f:
                    with fs.open(ensemble_path, "wb") as s3_f:
                        s3_f.write(f.read())
            
            logger.info(f"Ensemble saved to: {ensemble_path}")

            # Log to MLflow
            if MLFLOW_AVAILABLE:
                with mlflow.start_run(run_name="ensemble_training"):
                    mlflow.log_params({
                        "ensemble_type": ensemble_type,
                        "base_models": list(ensemble_manager.base_models.keys()),
                    })
                    mlflow.log_metrics({
                        "ensemble_rmse": eval_results["ensemble_metrics"]["rmse"],
                        "ensemble_mae": eval_results["ensemble_metrics"]["mae"],
                        "rmse_improvement": eval_results["improvements"]["rmse_improvement_percent"],
                    })

            return {
                "status": "success",
                "ensemble_type": ensemble_type,
                "rmse": eval_results["ensemble_metrics"]["rmse"],
                "mae": eval_results["ensemble_metrics"]["mae"],
                "improvement": eval_results["improvements"]["rmse_improvement_percent"],
                "model_path": ensemble_path,
            }

        except Exception as e:
            logger.error(f"❌ Ensemble training failed: {e}")
            return {"status": "failed", "error": str(e)}

    # Orchestration - Pipeline with optional advanced features
    validation = t_validate_raw_data()
    prep = t_preprocess()
    feat = t_feature_eng()
    model = t_train_optimized_model()

    # Advanced features (run in parallel with main model if enabled)
    multi_obj = t_train_multi_objective()
    ensemble = t_train_ensemble()

    # Define dependencies
    # Main pipeline
    validation >> prep >> feat >> model

    # Advanced features branch from feature engineering (parallel to main model)
    feat >> [multi_obj, ensemble]


# Instantiate the DAG
dag_instance = demand_forecasting_dag()
