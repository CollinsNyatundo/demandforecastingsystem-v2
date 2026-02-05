"""Project settings. There is no need to edit this file unless you want to change values
from Kedro defaults.

For further information, including these default values, see
https://docs.kedro.org/en/stable/kedro_project_setup/settings.html.
"""  # noqa: D205

# Instantiated project hooks.
# NOTE: MLflow integration is handled at the Airflow DAG level (airflow_dag_enhanced.py)
# rather than through Kedro hooks. This provides better control when running via Airflow.
# Enable these hooks ONLY if running Kedro directly without Airflow:
# from kedro_mlflow import MLflowHooks
# HOOKS = (MLflowHooks(),)

# Hooks are executed in a Last-In-First-Out (LIFO) order.
HOOKS = ()

# Installed plugins for which to disable hook auto-registration.
# Disabling kedro-pandera due to hook compatibility issue with Kedro 1.1.1
DISABLE_HOOKS_FOR_PLUGINS = ("kedro-pandera",)

# Class that manages storing KedroSession data.
# from kedro.framework.session.store import BaseSessionStore
# SESSION_STORE_CLASS = BaseSessionStore
# Keyword arguments to pass to the `SESSION_STORE_CLASS` constructor.
# SESSION_STORE_ARGS = {
#     "path": "./sessions"
# }

# Directory that holds configuration.
# CONF_SOURCE = "conf"

# Class that manages how configuration is loaded.
# from kedro.config import OmegaConfigLoader

# CONFIG_LOADER_CLASS = OmegaConfigLoader

# Keyword arguments to pass to the `CONFIG_LOADER_CLASS` constructor.
CONFIG_LOADER_ARGS = {
    "base_env": "base",
    "default_run_env": "local",
    # "config_patterns": {
    #     "spark" : ["spark*/"],
    #     "parameters": ["parameters*", "parameters*/**", "**/parameters*"],
    # }
}

# Class that manages Kedro's library components.
# from kedro.framework.context import KedroContext
# CONTEXT_CLASS = KedroContext

# Class that manages the Data Catalog.
# from kedro.io import DataCatalog
# DATA_CATALOG_CLASS = DataCatalog
