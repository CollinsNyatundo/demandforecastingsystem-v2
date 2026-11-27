"""ClearML Integration Module.

Unified ClearML integration for experiment tracking, hyperparameter
optimization visualization, and resource monitoring.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

_LOGGER = logging.getLogger(__name__)

try:
    from clearml import Task

    CLEARML_AVAILABLE = True
except ImportError:
    CLEARML_AVAILABLE = False
    Task = None  # type: ignore[misc, assignment]
    _LOGGER.warning("ClearML not installed. Experiment tracking disabled.")


def init_clearml_task(
    project_name: str = "demand_forecasting",
    task_name: str | None = None,
    task_type: str = "training",
    auto_connect_frameworks: bool = True,
    reuse_last_task_id: bool = False,
) -> "Task | None":
    """Initialize a ClearML task for experiment tracking.

    Args:
        project_name: ClearML project name
        task_name: Task name (auto-generated if None)
        task_type: Task type (training, testing, inference, optimizer, etc.)
        auto_connect_frameworks: Auto-capture from ML frameworks
        reuse_last_task_id: Reuse last task with same name if True

    Returns:
        ClearML Task object or None if unavailable
    """
    if not CLEARML_AVAILABLE:
        _LOGGER.debug("ClearML not available, skipping task init")
        return None

    try:
        task = Task.init(
            project_name=project_name,
            task_name=task_name,
            task_type=task_type,
            auto_connect_frameworks=auto_connect_frameworks,
            auto_connect_arg_parser=True,
            auto_connect_streams=True,
            reuse_last_task_id=reuse_last_task_id,
        )
        _LOGGER.info(f"ClearML task initialized: {task.name} (ID: {task.id})")
        return task
    except Exception as e:
        _LOGGER.warning(f"Failed to initialize ClearML task: {e}")
        return None


def log_optuna_study(task: "Task | None", study: object) -> None:
    """Log Optuna study visualizations to ClearML.

    ClearML auto-captures Optuna, but this adds explicit plots.

    Args:
        task: ClearML Task object
        study: Optuna study object
    """
    if task is None or not CLEARML_AVAILABLE:
        return

    try:
        import optuna.visualization as vis  # noqa: PLC0415

        logger = task.get_logger()

        # Parallel coordinates plot
        try:
            fig = vis.plot_parallel_coordinate(study)
            logger.report_plotly("Hyperparameters", "Parallel Coordinates", fig)
        except Exception as e:
            _LOGGER.debug(f"Could not create parallel coordinates: {e}")

        # Parameter importance
        try:
            fig = vis.plot_param_importances(study)
            logger.report_plotly("Hyperparameters", "Parameter Importance", fig)
        except Exception as e:
            _LOGGER.debug(f"Could not create parameter importances: {e}")

        # Optimization history
        try:
            fig = vis.plot_optimization_history(study)
            logger.report_plotly("Optimization", "History", fig)
        except Exception as e:
            _LOGGER.debug(f"Could not create optimization history: {e}")

        _LOGGER.info("Optuna study logged to ClearML")
    except Exception as e:
        _LOGGER.warning(f"Failed to log Optuna study: {e}")


def log_model_artifact(
    task: "Task | None",
    model: object,
    model_name: str = "model",
    framework: str = "catboost",
) -> None:
    """Explicitly log a model artifact to ClearML.

    Args:
        task: ClearML Task object
        model: Model object to log
        model_name: Name for the model artifact
        framework: ML framework name
    """
    if task is None or not CLEARML_AVAILABLE:
        return

    try:
        task.update_output_model(
            model_name=model_name,
            model_path=None,
            framework=framework,
        )
        _LOGGER.info(f"Model artifact logged: {model_name}")
    except Exception as e:
        _LOGGER.warning(f"Failed to log model artifact: {e}")


def log_metrics(
    task: "Task | None", metrics: dict[str, float], iteration: int = 0
) -> None:
    """Log metrics to ClearML.

    Args:
        task: ClearML Task object
        metrics: Dictionary of metric names to values
        iteration: Training iteration/epoch number
    """
    if task is None or not CLEARML_AVAILABLE:
        return

    try:
        logger = task.get_logger()
        for name, value in metrics.items():
            logger.report_scalar(
                title="Metrics", series=name, value=value, iteration=iteration
            )
    except Exception as e:
        _LOGGER.warning(f"Failed to log metrics: {e}")


def with_clearml_tracking(
    project_name: str = "demand_forecasting",
    task_name: str | None = None,
    task_type: str = "training",
) -> Callable:
    """Decorator to automatically track function execution in ClearML.

    Args:
        project_name: ClearML project name
        task_name: Task name (defaults to function name)
        task_type: Task type

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            task = init_clearml_task(
                project_name=project_name,
                task_name=task_name or func.__name__,
                task_type=task_type,
            )
            try:
                result = func(*args, **kwargs)
                if task:
                    task.close()
                return result
            except Exception as e:
                if task:
                    task.mark_failed(status_reason=str(e))
                raise

        return wrapper

    return decorator
