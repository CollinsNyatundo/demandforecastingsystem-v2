"""MLOps Integrations Package.

Provides unified integrations for:
- ClearML: Experiment tracking and visualization
- Evidently: Production drift monitoring
"""

from .clearml_integration import (
    CLEARML_AVAILABLE,
    init_clearml_task,
    log_metrics,
    log_model_artifact,
    log_optuna_study,
    with_clearml_tracking,
)
from .evidently_integration import (
    EVIDENTLY_AVAILABLE,
    check_drift_threshold,
    generate_drift_report,
    get_drift_metrics_for_prometheus,
)

__all__ = [
    "CLEARML_AVAILABLE",
    "EVIDENTLY_AVAILABLE",
    "check_drift_threshold",
    "generate_drift_report",
    "get_drift_metrics_for_prometheus",
    "init_clearml_task",
    "log_metrics",
    "log_model_artifact",
    "log_optuna_study",
    "with_clearml_tracking",
]
