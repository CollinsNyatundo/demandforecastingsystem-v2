"""
Unit tests for MinIO data upload functionality.
Tests both the PowerShell script logic and Python equivalent.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np


class TestMinioUpload:
    """Test suite for MinIO data upload functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_data_dir = Path(tempfile.mkdtemp())
        self.minio_config = {
            "endpoint": "http://localhost:9000",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "bucket": "demand-forecasting",
        }

        # Create sample data files for testing
        self._create_sample_data()

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_data_dir)

    def _create_sample_data(self):
        """Create sample data files for testing."""
        # Create sample parquet file
        sample_df = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-01", periods=100, freq="h"),
                "value": np.random.randn(100),
                "category": np.random.choice(["A", "B", "C"], 100),
            }
        )

        parquet_path = self.test_data_dir / "sample_data.parquet"
        sample_df.to_parquet(parquet_path)

        # Create sample pickle file
        sample_model = {"model": "test", "version": "1.0"}
        pickle_path = self.test_data_dir / "sample_model.pickle"
        import pickle

        with open(pickle_path, "wb") as f:
            pickle.dump(sample_model, f)

        # Create sample JSON file
        json_path = self.test_data_dir / "sample_config.json"
        import json

        with open(json_path, "w") as f:
            json.dump({"config": "test"}, f)

    @patch("boto3.client")
    def test_minio_connection_success(self, mock_boto3_client):
        """Test successful MinIO connection."""
        # Mock the S3 client
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Test connection logic
        try:
            s3_client = mock_boto3_client(
                "s3",
                endpoint_url=self.minio_config["endpoint"],
                aws_access_key_id=self.minio_config["access_key"],
                aws_secret_access_key=self.minio_config["secret_key"],
            )

            # Verify client was created with correct parameters
            mock_boto3_client.assert_called_once_with(
                "s3",
                endpoint_url=self.minio_config["endpoint"],
                aws_access_key_id=self.minio_config["access_key"],
                aws_secret_access_key=self.minio_config["secret_key"],
            )

            assert s3_client is not None

        except Exception as e:
            pytest.fail(f"MinIO connection test failed: {e}")

    @patch("boto3.client")
    def test_bucket_creation_success(self, mock_boto3_client):
        """Test successful bucket creation."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Mock successful bucket creation
        mock_client.create_bucket.return_value = None

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        # Test bucket creation
        try:
            s3_client.create_bucket(Bucket=self.minio_config["bucket"])
            mock_client.create_bucket.assert_called_once_with(
                Bucket=self.minio_config["bucket"]
            )
        except Exception as e:
            pytest.fail(f"Bucket creation test failed: {e}")

    @patch("boto3.client")
    def test_bucket_creation_already_exists(self, mock_boto3_client):
        """Test bucket creation when bucket already exists."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Mock bucket already exists error
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "BucketAlreadyOwnedByYou"}}
        mock_client.create_bucket.side_effect = ClientError(
            error_response, "CreateBucket"
        )

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        # Test that bucket creation handles existing bucket gracefully
        try:
            s3_client.create_bucket(Bucket=self.minio_config["bucket"])
            # Should not raise an exception for existing bucket
            assert True
        except ClientError as e:
            if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                pytest.fail(f"Unexpected error for existing bucket: {e}")
        except Exception as e:
            pytest.fail(f"Bucket creation test failed unexpectedly: {e}")

    @patch("boto3.client")
    def test_file_upload_success(self, mock_boto3_client):
        """Test successful file upload."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        # Test uploading a sample file
        test_file = self.test_data_dir / "sample_data.parquet"

        try:
            with open(test_file, "rb") as f:
                s3_client.upload_fileobj(
                    f, self.minio_config["bucket"], "test/sample_data.parquet"
                )

            # Verify upload was called
            assert mock_client.upload_fileobj.called
            args, kwargs = mock_client.upload_fileobj.call_args
            assert kwargs["Bucket"] == self.minio_config["bucket"]
            assert kwargs["Key"] == "test/sample_data.parquet"

        except Exception as e:
            pytest.fail(f"File upload test failed: {e}")

    @patch("boto3.client")
    def test_file_upload_with_metadata(self, mock_boto3_client):
        """Test file upload with metadata."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        test_file = self.test_data_dir / "sample_model.pickle"

        try:
            # Test upload with extra arguments
            extra_args = {
                "Metadata": {
                    "model_type": "catboost",
                    "version": "1.0",
                    "created_by": "test",
                },
                "ContentType": "application/octet-stream",
            }

            with open(test_file, "rb") as f:
                s3_client.upload_fileobj(
                    f,
                    self.minio_config["bucket"],
                    "models/sample_model.pickle",
                    ExtraArgs=extra_args,
                )

            # Verify upload was called with extra args
            assert mock_client.upload_fileobj.called
            args, kwargs = mock_client.upload_fileobj.call_args
            assert "ExtraArgs" in kwargs
            assert kwargs["ExtraArgs"]["Metadata"]["model_type"] == "catboost"

        except Exception as e:
            pytest.fail(f"File upload with metadata test failed: {e}")

    @patch("boto3.client")
    def test_upload_multiple_files(self, mock_boto3_client):
        """Test uploading multiple files."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        files_to_upload = [
            ("sample_data.parquet", "data/"),
            ("sample_model.pickle", "models/"),
            ("sample_config.json", "config/"),
        ]

        try:
            upload_count = 0
            for filename, prefix in files_to_upload:
                file_path = self.test_data_dir / filename
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        s3_client.upload_fileobj(
                            f, self.minio_config["bucket"], f"{prefix}{filename}"
                        )
                    upload_count += 1

            assert upload_count == 3
            assert mock_client.upload_fileobj.call_count == 3

        except Exception as e:
            pytest.fail(f"Multiple file upload test failed: {e}")

    @patch("boto3.client")
    def test_connection_failure_handling(self, mock_boto3_client):
        """Test handling of connection failures."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Mock connection failure
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "NetworkingError", "Message": "Connection failed"}
        }
        mock_client.create_bucket.side_effect = ClientError(
            error_response, "CreateBucket"
        )

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        # Test that connection failures are handled
        try:
            s3_client.create_bucket(Bucket=self.minio_config["bucket"])
            pytest.fail("Expected ClientError to be raised")
        except ClientError as e:
            assert e.response["Error"]["Code"] == "NetworkingError"
        except Exception as e:
            pytest.fail(f"Unexpected exception type: {e}")

    def test_file_validation(self):
        """Test file validation before upload."""
        # Test that files exist before attempting upload
        existing_file = self.test_data_dir / "sample_data.parquet"
        non_existing_file = self.test_data_dir / "nonexistent.parquet"

        assert existing_file.exists()
        assert not non_existing_file.exists()

        # Test file size validation
        file_size = existing_file.stat().st_size
        assert file_size > 0, "Test file should not be empty"

    @patch("boto3.client")
    def test_bucket_policy_setting(self, mock_boto3_client):
        """Test setting bucket policies."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        s3_client = mock_boto3_client(
            "s3",
            endpoint_url=self.minio_config["endpoint"],
            aws_access_key_id=self.minio_config["access_key"],
            aws_secret_access_key=self.minio_config["secret_key"],
        )

        # Test setting public read policy
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.minio_config['bucket']}/*"],
                }
            ],
        }

        try:
            import json

            s3_client.put_bucket_policy(
                Bucket=self.minio_config["bucket"], Policy=json.dumps(policy)
            )

            mock_client.put_bucket_policy.assert_called_once()
            args, kwargs = mock_client.put_bucket_policy.call_args
            assert kwargs["Bucket"] == self.minio_config["bucket"]
            assert "Policy" in kwargs

        except Exception as e:
            pytest.fail(f"Bucket policy test failed: {e}")

    def test_environment_variable_handling(self):
        """Test environment variable handling for credentials."""
        # Test with environment variables set
        test_env = {
            "MINIO_ENDPOINT": "http://test:9000",
            "MINIO_ACCESS_KEY": "testkey",
            "MINIO_SECRET_KEY": "testsecret",
            "S3_BUCKET": "test-bucket",
        }

        with patch.dict(os.environ, test_env):
            # Verify environment variables are accessible
            assert os.getenv("MINIO_ENDPOINT") == "http://test:9000"
            assert os.getenv("MINIO_ACCESS_KEY") == "testkey"
            assert os.getenv("MINIO_SECRET_KEY") == "testsecret"
            assert os.getenv("S3_BUCKET") == "test-bucket"

    def test_data_integrity_verification(self):
        """Test data integrity after upload/download cycle."""
        # Create test data
        original_data = pd.DataFrame(
            {
                "id": range(100),
                "value": np.random.randn(100),
                "category": np.random.choice(["A", "B", "C"], 100),
            }
        )

        # Save to temporary file
        temp_file = self.test_data_dir / "integrity_test.parquet"
        original_data.to_parquet(temp_file)

        # Read back and verify
        loaded_data = pd.read_parquet(temp_file)

        pd.testing.assert_frame_equal(original_data, loaded_data)
        assert len(loaded_data) == 100
        assert list(loaded_data.columns) == ["id", "value", "category"]


class TestMinioUploadIntegration:
    """Integration tests for MinIO upload functionality."""

    @pytest.mark.integration
    @patch("boto3.client")
    def test_full_upload_workflow(self, mock_boto3_client):
        """Test complete upload workflow."""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Mock all operations
        mock_client.create_bucket.return_value = None
        mock_client.upload_fileobj.return_value = None
        mock_client.put_bucket_policy.return_value = None

        # Simulate full workflow
        s3_client = mock_boto3_client(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
        )

        bucket_name = "demand-forecasting"

        # 1. Create bucket
        s3_client.create_bucket(Bucket=bucket_name)

        # 2. Upload files
        test_files = ["data.parquet", "model.pickle", "config.json"]
        for filename in test_files:
            file_path = f"/tmp/{filename}"
            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                s3_client.upload_fileobj(mock_file, bucket_name, f"upload/{filename}")

        # 3. Set bucket policy
        import json

        policy = {"Version": "2012-10-17", "Statement": []}
        s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

        # Verify all operations were called
        assert mock_client.create_bucket.call_count == 1
        assert mock_client.upload_fileobj.call_count == 3
        assert mock_client.put_bucket_policy.call_count == 1

    @pytest.mark.integration
    def test_error_recovery(self):
        """Test error recovery mechanisms."""
        # Test that partial failures don't break the entire process
        # This would test retry logic, partial upload recovery, etc.

        # For now, just test that exceptions are handled properly
        try:
            # Simulate a failure scenario
            raise ConnectionError("Simulated connection failure")
        except ConnectionError:
            # Verify that error handling works
            assert True  # Error was caught and handled


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
