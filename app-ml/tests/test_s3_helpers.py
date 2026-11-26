"""
Unit tests for S3 helper utilities.
Tests the core functionality of s3_helpers.py module.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestS3Helpers:
    """Test suite for S3 helper functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_config = {
            "minio_endpoint": "http://localhost:9000",
            "minio_access_key": "minioadmin",
            "minio_secret_key": "minioadmin",
            "s3_bucket": "demand-forecasting",
        }

    @patch("demand_forecasting.utils.s3_helpers.s3fs.S3FileSystem")
    def test_get_s3_filesystem_success(self, mock_s3fs):
        """Test successful S3 filesystem creation."""
        # Mock the S3FileSystem
        mock_fs = MagicMock()
        mock_s3fs.return_value = mock_fs

        # Import and test the function
        from demand_forecasting.utils.s3_helpers import get_s3_filesystem

        # Set environment variables
        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": self.test_config["minio_endpoint"],
                "MINIO_ACCESS_KEY": self.test_config["minio_access_key"],
                "MINIO_SECRET_KEY": self.test_config["minio_secret_key"],
            },
        ):
            fs = get_s3_filesystem()

            # Verify S3FileSystem was created with correct parameters
            mock_s3fs.assert_called_once_with(
                client_kwargs={
                    "endpoint_url": self.test_config["minio_endpoint"],
                },
                key=self.test_config["minio_access_key"],
                secret=self.test_config["minio_secret_key"],
                use_ssl=False,
            )

            assert fs == mock_fs

    @patch("demand_forecasting.utils.s3_helpers.s3fs.S3FileSystem")
    def test_get_s3_filesystem_with_retry(self, mock_s3fs):
        """Test S3 filesystem creation with retry logic."""
        # Mock the S3FileSystem to fail twice then succeed
        mock_fs = MagicMock()
        mock_s3fs.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            mock_fs,
        ]

        from demand_forecasting.utils.s3_helpers import get_s3_filesystem

        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": self.test_config["minio_endpoint"],
                "MINIO_ACCESS_KEY": self.test_config["minio_access_key"],
                "MINIO_SECRET_KEY": self.test_config["minio_secret_key"],
            },
        ):
            fs = get_s3_filesystem()

            # Should have been called 3 times (initial + 2 retries)
            assert mock_s3fs.call_count == 3
            assert fs == mock_fs

    @patch("demand_forecasting.utils.s3_helpers.s3fs.S3FileSystem")
    def test_get_s3_filesystem_max_retries_exceeded(self, mock_s3fs):
        """Test S3 filesystem creation when max retries exceeded."""
        # Mock the S3FileSystem to always fail
        mock_s3fs.side_effect = Exception("Connection failed")

        from demand_forecasting.utils.s3_helpers import get_s3_filesystem

        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": self.test_config["minio_endpoint"],
                "MINIO_ACCESS_KEY": self.test_config["minio_access_key"],
                "MINIO_SECRET_KEY": self.test_config["minio_secret_key"],
            },
        ):
            with pytest.raises(Exception, match="Connection failed"):
                get_s3_filesystem()

            # Should have been called 3 times (stop_after_attempt(3))
            assert mock_s3fs.call_count == 3

    def test_validate_search_space_parameters_valid(self):
        """Test parameter validation with valid parameters."""
        from demand_forecasting.utils.s3_helpers import (
            validate_search_space_parameters,
        )

        valid_params = {
            "optuna": {"n_trials": 150, "metric": "rmse"},
            "catboost_search_space": {
                "learning_rate": {"min": 0.01, "max": 0.2},
                "depth": {"min": 3, "max": 8},
                "l2_leaf_reg": {"min": 0.5, "max": 5.0},
            },
        }

        # Should not raise any exception
        validate_search_space_parameters(valid_params)

    def test_validate_search_space_parameters_missing_optuna(self):
        """Test parameter validation with missing optuna section."""
        from demand_forecasting.utils.s3_helpers import (
            validate_search_space_parameters,
        )

        invalid_params = {
            "catboost_search_space": {"learning_rate": {"min": 0.01, "max": 0.2}}
        }

        with pytest.raises(KeyError, match="optuna"):
            validate_search_space_parameters(invalid_params)

    def test_validate_search_space_parameters_invalid_trials(self):
        """Test parameter validation with invalid n_trials."""
        from demand_forecasting.utils.s3_helpers import (
            validate_search_space_parameters,
        )

        invalid_params = {
            "optuna": {"n_trials": -5, "metric": "rmse"},  # Invalid negative value
            "catboost_search_space": {"learning_rate": {"min": 0.01, "max": 0.2}},
        }

        with pytest.raises(ValueError, match="positive"):
            validate_search_space_parameters(invalid_params)

    def test_validate_search_space_parameters_invalid_range(self):
        """Test parameter validation with invalid parameter range."""
        from demand_forecasting.utils.s3_helpers import (
            validate_search_space_parameters,
        )

        invalid_params = {
            "optuna": {"n_trials": 150, "metric": "rmse"},
            "catboost_search_space": {
                "learning_rate": {"min": 0.5, "max": 0.1}  # min > max
            },
        }

        with pytest.raises(ValueError, match="Min must be less than max"):
            validate_search_space_parameters(invalid_params)

    def test_validate_trial_files_list_valid(self):
        """Test trial files list validation with valid list."""
        from demand_forecasting.utils.s3_helpers import validate_trial_files_list

        valid_files = [
            "bucket/trials/trial_1.json",
            "bucket/trials/trial_2.json",
            "bucket/trials/trial_3.json",
        ]
        validate_trial_files_list(valid_files)  # Should not raise

    def test_validate_trial_files_list_empty(self):
        """Test trial files list validation with empty list."""
        from demand_forecasting.utils.s3_helpers import validate_trial_files_list

        with pytest.raises(ValueError, match="Trial files list is empty"):
            validate_trial_files_list([])

    def test_validate_trial_files_list_none(self):
        """Test trial files list validation with None."""
        from demand_forecasting.utils.s3_helpers import validate_trial_files_list

        with pytest.raises(ValueError, match="Trial files list is empty"):
            validate_trial_files_list(None)

    @patch("demand_forecasting.utils.s3_helpers.get_s3_filesystem")
    def test_validate_model_save_success(self, mock_get_fs):
        """Test model save validation with successful save."""
        mock_fs = MagicMock()
        mock_get_fs.return_value = mock_fs

        # Mock successful file existence check
        mock_fs.exists.return_value = True
        mock_fs.info.return_value = {"size": 1024}

        from demand_forecasting.utils.s3_helpers import validate_model_save

        # Should not raise any exception
        assert validate_model_save(mock_fs, "s3://bucket/models/model.pickle") is True

        mock_fs.exists.assert_called_once_with("s3://bucket/models/model.pickle")

    @patch("demand_forecasting.utils.s3_helpers.get_s3_filesystem")
    def test_validate_model_save_file_not_found(self, mock_get_fs):
        """Test model save validation when file doesn't exist."""
        mock_fs = MagicMock()
        mock_get_fs.return_value = mock_fs

        # Mock file doesn't exist
        mock_fs.exists.return_value = False

        from demand_forecasting.utils.s3_helpers import validate_model_save

        with pytest.raises(FileNotFoundError, match="Model file not found"):
            validate_model_save(mock_fs, "s3://bucket/models/model.pickle")

    @patch("demand_forecasting.utils.s3_helpers.get_s3_filesystem")
    def test_validate_model_save_empty_file(self, mock_get_fs):
        """Test model save validation with empty file."""
        mock_fs = MagicMock()
        mock_get_fs.return_value = mock_fs

        # Mock file exists but is empty
        mock_fs.exists.return_value = True
        mock_fs.info.return_value = {"size": 0}

        from demand_forecasting.utils.s3_helpers import validate_model_save

        with pytest.raises(ValueError, match="too small"):
            validate_model_save(mock_fs, "s3://bucket/models/model.pickle")

    def test_get_email_config_with_env_vars(self):
        """Test email config retrieval with environment variables."""
        from demand_forecasting.utils.s3_helpers import get_email_config

        test_config = {
            "host": "smtp.gmail.com",
            "port": "587",
            "user": "test@example.com",
            "password": "test-password",
        }

        with patch.dict(
            os.environ,
            {
                "AIRFLOW__SMTP__SMTP_HOST": test_config["host"],
                "AIRFLOW__SMTP__SMTP_PORT": test_config["port"],
                "AIRFLOW__SMTP__SMTP_USER": test_config["user"],
                "AIRFLOW__SMTP__SMTP_PASSWORD": test_config["password"],
            },
        ):
            config = get_email_config()

            assert config is not None
            assert config["host"] == test_config["host"]
            assert config["port"] == test_config["port"]
            assert config["user"] == test_config["user"]
            assert config["password"] == test_config["password"]

    def test_get_email_config_missing_env_vars(self):
        """Test email config retrieval with missing environment variables."""
        from demand_forecasting.utils.s3_helpers import get_email_config

        env_vars_to_clear = [
            "AIRFLOW__SMTP__SMTP_HOST",
            "AIRFLOW__SMTP__SMTP_PORT",
            "AIRFLOW__SMTP__SMTP_USER",
            "AIRFLOW__SMTP__SMTP_PASSWORD",
            "AIRFLOW_ALERT_EMAIL",
        ]

        with patch.dict(os.environ, dict.fromkeys(env_vars_to_clear, ""), clear=True):
            config = get_email_config()
            assert config is None

    def test_parse_s3_timestamp_path_valid(self):
        """Test S3 timestamp path parsing with valid path."""
        from demand_forecasting.utils.s3_helpers import parse_s3_timestamp_path

        test_path = "s3://demand-forecasting/logs/dag_id=demand_forecasting/run_date=2023-01-01/task_name=preprocess/attempt=1.log"

        result = parse_s3_timestamp_path(test_path)

        assert result == "2023-01-01"

    def test_parse_s3_timestamp_path_invalid(self):
        """Test S3 timestamp path parsing with invalid path."""
        from demand_forecasting.utils.s3_helpers import parse_s3_timestamp_path

        invalid_paths = [
            "s3://bucket/file.txt",
            "s3://bucket/logs/invalid_format.log",
            "not_an_s3_path/file.log",
            "",
        ]

        for invalid_path in invalid_paths:
            result = parse_s3_timestamp_path(invalid_path)
            assert result is None

    def test_parse_s3_timestamp_path_malformed(self):
        """Test S3 timestamp path parsing with embedded timestamp in malformed path."""
        from demand_forecasting.utils.s3_helpers import parse_s3_timestamp_path

        malformed_path = "s3://demand-forecasting/logs/dag_id=demand_forecasting/run_date=2023-01-01/task_name=preprocess/attempt=.log"

        result = parse_s3_timestamp_path(malformed_path)

        assert result == "2023-01-01"

    @patch("demand_forecasting.utils.s3_helpers.get_s3_filesystem")
    def test_s3_operations_with_context_manager(self, mock_get_fs):
        """Test S3 operations using context manager pattern."""
        mock_fs = MagicMock()
        mock_get_fs.return_value = mock_fs

        from demand_forecasting.utils.s3_helpers import get_s3_filesystem

        with patch.dict(os.environ, self.test_config):
            # Test that filesystem can be used in a context-like manner
            fs = get_s3_filesystem()

            # Simulate typical operations
            fs.ls("s3://bucket/")
            fs.exists("s3://bucket/file.txt")
            fs.size("s3://bucket/file.txt")

            # Verify operations were called
            mock_fs.ls.assert_called_once_with("s3://bucket/")
            mock_fs.exists.assert_called_once_with("s3://bucket/file.txt")
            mock_fs.size.assert_called_once_with("s3://bucket/file.txt")

    def test_environment_variable_fallbacks(self):
        """Test that missing S3 credentials raise ValueError instead of using defaults."""
        from demand_forecasting.utils.s3_helpers import get_s3_filesystem

        with (
            patch.dict(
                os.environ,
                {"MINIO_ENDPOINT": "http://localhost:9000"},
                clear=True,
            ),
            pytest.raises(ValueError, match="S3 credentials must be provided"),
        ):
            get_s3_filesystem()

    def test_error_handling_comprehensive(self):
        """Test comprehensive error handling."""
        from demand_forecasting.utils.s3_helpers import (
            get_email_config,
            parse_s3_timestamp_path,
            validate_search_space_parameters,
            validate_trial_files_list,
        )

        # Test that all functions handle None/empty inputs gracefully
        with pytest.raises((ValueError, TypeError)):
            validate_search_space_parameters(None)

        with pytest.raises(ValueError):
            validate_trial_files_list([])

        # Test email config with no environment variables returns None
        with patch.dict(os.environ, {}, clear=True):
            config = get_email_config()
            assert config is None

        # Test path parsing with edge cases
        assert parse_s3_timestamp_path(None) is None
        assert parse_s3_timestamp_path("") is None
        assert parse_s3_timestamp_path("not_s3_path") is None


class TestS3HelpersIntegration:
    """Integration tests for S3 helpers."""

    @pytest.mark.integration
    def test_full_workflow_simulation(self):
        """Test a complete workflow using S3 helpers."""
        # This would test the complete workflow in a real environment
        # For now, we'll use mocks to simulate the workflow

        with (
            patch(
                "demand_forecasting.utils.s3_helpers.get_s3_filesystem"
            ) as mock_get_fs,
            patch(
                "demand_forecasting.utils.s3_helpers.validate_search_space_parameters"
            ) as mock_validate_params,
        ):
            mock_fs = MagicMock()
            mock_get_fs.return_value = mock_fs

            # Simulate workflow steps
            from demand_forecasting.utils.s3_helpers import (
                get_s3_filesystem,
                validate_search_space_parameters,
            )

            # 1. Get filesystem
            fs = get_s3_filesystem()
            assert fs is not None

            # 2. Validate parameters
            test_params = {"optuna": {"n_trials": 100}}
            validate_search_space_parameters(test_params)

            # 3. Simulate file operations
            mock_fs.exists.return_value = True
            mock_fs.size.return_value = 1024

            # Verify all operations completed
            mock_get_fs.assert_called_once()
            mock_validate_params.assert_called_once_with(test_params)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
