"""Demand Forecasting file for ensuring the package is executable.

as `demand-forecasting` and `python -m demand_forecasting`.
"""

import sys
from pathlib import Path

from kedro.framework.cli.utils import find_run_command
from kedro.framework.project import configure_project


def main(*args: object, **kwargs: object) -> None:
    """Entry point for the demand forecasting package.

    Configures and runs the Kedro project with the package name.
    Supports both interactive and standalone execution modes.

    Args:
        *args: Additional positional arguments passed to Kedro
        **kwargs: Additional keyword arguments passed to Kedro
    """
    package_name = Path(__file__).parent.name
    configure_project(package_name)

    interactive = hasattr(sys, "ps1")
    kwargs["standalone_mode"] = not interactive

    run = find_run_command(package_name)
    return run(*args, **kwargs)


if __name__ == "__main__":
    main()
