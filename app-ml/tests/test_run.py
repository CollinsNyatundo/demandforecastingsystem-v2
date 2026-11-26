"""
This module contains example tests for a Kedro project.
Tests should be placed in ``src/tests``, in modules that mirror your
project's structure, and in files named test_*.py.
"""

from pathlib import Path

import pytest
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project

# The tests below are here for the demonstration purpose
# and should be replaced with the ones testing the project
# functionality


class TestKedroRun:
    def test_kedro_run_no_pipeline(self):
        # Verify the Kedro project bootstraps and registers pipelines properly.
        metadata = bootstrap_project(Path.cwd())
        assert metadata.package_name == "demand_forecasting"

        from demand_forecasting.pipeline_registry import register_pipelines

        pipelines = register_pipelines()
        assert "__default__" in pipelines
        assert len(pipelines["__default__"].nodes) > 0
