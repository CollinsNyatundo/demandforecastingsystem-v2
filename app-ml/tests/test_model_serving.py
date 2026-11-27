"""
Comprehensive test suite for model serving components.

Tests FastAPI endpoints, model loading, prediction logic, A/B testing,
and edge cases including error handling and performance scenarios.
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from demand_forecasting.serving.model_router import ModelRouter


class TestModelServerEndpoints:
    """Test FastAPI model server endpoints."""

    def test_health_check_success(self, model_server_test_client: TestClient):
        """Test successful health check."""
        response = model_server_test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "models_loaded" in data
        assert "timestamp" in data

    def test_health_check_with_models(
        self, model_server_test_client: TestClient, sample_model
    ):
        """Test health check with loaded models."""
        with patch(
            "demand_forecasting.serving.model_server.ml_models",
            {"production": sample_model},
        ):
            response = model_server_test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["models_loaded"] == 1

    def test_predict_success(
        self, model_server_test_client: TestClient, sample_data
    ):
        """Test successful prediction request."""
        import os

        from demand_forecasting.serving import model_server as ms

        # Mock model loading and prediction
        mock_model = Mock()
        mock_model.predict.return_value = [45.5]

        # Prepare request data (normalized weather features)
        request_data = {
            "features": {
                "temp": 0.5,
                "humidity": 0.6,
                "wind_speed": 0.15,
                "hour": 14,
                "day_of_week": 3,
            }
        }

        with (
            patch.dict(ms.ml_models, {"production": mock_model}, clear=True),
            patch.dict(
                ms.feature_metadata,
                {"feature_names": ["temp", "humidity", "wind_speed", "hour", "day_of_week"]},
                clear=True,
            ),
            patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}),
        ):
            response = model_server_test_client.post(
                "/predict",
                json=request_data,
                headers={"X-API-Key": "test_serving_key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "prediction" in data
        assert "confidence" in data
        assert "model_version" in data
        assert "timestamp" in data
        assert "model_id" in data
        assert isinstance(data["prediction"], float)
        assert 0 <= data["confidence"] <= 1

    def test_predict_missing_features(self, model_server_test_client: TestClient):
        """Test prediction with missing required features."""
        import os

        request_data = {
            "features": {
                "temp": 0.5,
                "humidity": 0.6,
                # Missing wind_speed, hour, day_of_week
            }
        }

        with patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}):
            response = model_server_test_client.post(
                "/predict",
                json=request_data,
                headers={"X-API-Key": "test_serving_key"},
            )

        assert response.status_code == 422  # Validation error
        assert "Missing required core features" in response.text

    def test_predict_invalid_feature_types(self, model_server_test_client: TestClient):
        """Test prediction with invalid feature types."""
        import os

        request_data = {
            "features": {
                "temp": "not_a_number",
                "humidity": 0.6,
                "wind_speed": 0.15,
                "hour": 14,
                "day_of_week": 3,
            }
        }

        with patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}):
            response = model_server_test_client.post(
                "/predict",
                json=request_data,
                headers={"X-API-Key": "test_serving_key"},
            )

        assert response.status_code == 422  # Validation error

    def test_predict_empty_request(self, model_server_test_client: TestClient):
        """Test prediction with empty request."""
        import os

        with patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}):
            response = model_server_test_client.post(
                "/predict",
                json={},
                headers={"X-API-Key": "test_serving_key"},
            )

        assert response.status_code == 422  # Validation error

    def test_predict_model_loading_failure(
        self, model_server_test_client: TestClient
    ):
        """Test prediction when model is not loaded."""
        import os

        from demand_forecasting.serving import model_server as ms

        request_data = {
            "features": {
                "temp": 0.5,
                "humidity": 0.6,
                "wind_speed": 0.15,
                "hour": 14,
                "day_of_week": 3,
            }
        }

        with (
            patch.dict(ms.ml_models, {}, clear=True),
            patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}),
        ):
            response = model_server_test_client.post(
                "/predict",
                json=request_data,
                headers={"X-API-Key": "test_serving_key"},
            )

        assert response.status_code in [500, 503]

    def test_predict_fallback_model(
        self, model_server_test_client: TestClient
    ):
        """Test prediction using loaded fallback model."""
        import os

        from demand_forecasting.serving import model_server as ms

        mock_model = Mock()
        mock_model.predict.return_value = [42.0]

        request_data = {
            "features": {
                "temp": 0.5,
                "humidity": 0.6,
                "wind_speed": 0.15,
                "hour": 14,
                "day_of_week": 3,
            }
        }

        with (
            patch.dict(ms.ml_models, {"production": mock_model}, clear=True),
            patch.dict(
                ms.feature_metadata,
                {"feature_names": ["temp", "humidity", "wind_speed", "hour", "day_of_week"]},
                clear=True,
            ),
            patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}),
        ):
            response = model_server_test_client.post(
                "/predict",
                json=request_data,
                headers={"X-API-Key": "test_serving_key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["prediction"] == 42.0

    def test_model_info_success(
        self, model_server_test_client: TestClient, sample_model
    ):
        """Test model info endpoint."""
        with patch(
            "demand_forecasting.serving.model_server.ml_models",
            {"production": sample_model},
        ):
            response = model_server_test_client.get("/model/info")

            assert response.status_code == 200
            data = response.json()
            assert "model_version" in data
            assert "model_type" in data
            assert "features" in data
            assert "last_updated" in data
            assert "model_id" in data

    def test_metrics_endpoint(self, model_server_test_client: TestClient):
        """Test Prometheus metrics endpoint."""
        response = model_server_test_client.get("/metrics")

        assert response.status_code == 200
        assert "prediction_requests_total" in response.text
        assert "prediction_duration_seconds" in response.text
        assert "model_accuracy" in response.text


class TestModelRouter:
    """Test A/B testing model router."""

    @patch("mlflow.pyfunc.load_model")
    def test_router_initialization(self, mock_load_model):
        """Test router initialization with model loading."""
        mock_model_a = Mock()
        mock_model_b = Mock()
        mock_load_model.side_effect = [mock_model_a, mock_model_b]

        router = ModelRouter("model_a_uri", "model_b_uri", split=0.7)

        assert router.model_a_uri == "model_a_uri"
        assert router.model_b_uri == "model_b_uri"
        assert router.split == 0.7
        assert router.model_a == mock_model_a
        assert router.model_b == mock_model_b
        assert router.request_count == 0

    @patch("mlflow.pyfunc.load_model")
    def test_route_request_model_a(self, mock_load_model):
        """Test routing to model A based on split ratio."""
        mock_model_a = Mock()
        mock_model_b = Mock()
        mock_model_a.predict.return_value = [45.0]
        mock_model_b.predict.return_value = [55.0]
        mock_load_model.side_effect = [mock_model_a, mock_model_b]

        router = ModelRouter("model_a_uri", "model_b_uri", split=1.0)  # Always A

        data = {
            "temp": 20.0,
            "humidity": 60.0,
            "wind_speed": 5.0,
            "hour": 14,
            "day_of_week": 3,
        }
        result = router.route_request(data)

        assert result["model_id"] == "A"
        assert result["prediction"] == 45.0
        assert router.model_a_count == 1
        assert router.model_b_count == 0

    @patch("mlflow.pyfunc.load_model")
    def test_route_request_model_b(self, mock_load_model):
        """Test routing to model B based on split ratio."""
        mock_model_a = Mock()
        mock_model_b = Mock()
        mock_model_a.predict.return_value = [45.0]
        mock_model_b.predict.return_value = [55.0]
        mock_load_model.side_effect = [mock_model_a, mock_model_b]

        router = ModelRouter("model_a_uri", "model_b_uri", split=0.0)  # Always B

        data = {
            "temp": 20.0,
            "humidity": 60.0,
            "wind_speed": 5.0,
            "hour": 14,
            "day_of_week": 3,
        }
        result = router.route_request(data)

        assert result["model_id"] == "B"
        assert result["prediction"] == 55.0
        assert router.model_a_count == 0
        assert router.model_b_count == 1

    @patch("mlflow.pyfunc.load_model")
    def test_traffic_distribution(self, mock_load_model):
        """Test traffic distribution over multiple requests."""
        mock_model_a = Mock()
        mock_model_b = Mock()
        mock_model_a.predict.return_value = [45.0]
        mock_model_b.predict.return_value = [55.0]
        mock_load_model.side_effect = [mock_model_a, mock_model_b]

        router = ModelRouter("model_a_uri", "model_b_uri", split=0.7)

        data = {
            "temp": 20.0,
            "humidity": 60.0,
            "wind_speed": 5.0,
            "hour": 14,
            "day_of_week": 3,
        }

        # Make enough requests that 70/30 split tolerance (±10%) is >6.8 sigma wide
        n_requests = 1000
        for _ in range(n_requests):
            router.route_request(data)

        stats = router.get_statistics()

        assert stats["total_requests"] == n_requests
        assert stats["model_a_requests"] + stats["model_b_requests"] == n_requests
        # Allow wide variance around 70/30 split without stochastic flakes
        assert 600 <= stats["model_a_requests"] <= 800
        assert 200 <= stats["model_b_requests"] <= 400

    @patch("mlflow.pyfunc.load_model")
    def test_confidence_calculation(self, mock_load_model):
        """Test confidence calculation for predictions."""
        mock_model_a = Mock()
        mock_model_b = Mock()
        mock_model_a.predict.return_value = [50.0]
        mock_model_b.predict.return_value = [50.0]
        mock_load_model.side_effect = [mock_model_a, mock_model_b]

        router = ModelRouter("model_a_uri", "model_b_uri", split=0.5)

        data = {
            "temp": 20.0,
            "humidity": 60.0,
            "wind_speed": 5.0,
            "hour": 14,
            "day_of_week": 3,
        }
        result = router.route_request(data)

        assert "confidence" in result
        assert 0.7 <= result["confidence"] <= 0.95  # Expected range

    @patch("mlflow.pyfunc.load_model")
    def test_route_request_missing_features(self, mock_load_model):
        """Test routing with missing features."""
        mock_model_a = Mock()
        mock_model_b = Mock()
        mock_load_model.side_effect = [mock_model_a, mock_model_b]

        router = ModelRouter("model_a_uri", "model_b_uri", split=0.5)

        # Missing required features
        incomplete_data = {"temp": 20.0, "humidity": 60.0}

        with pytest.raises(KeyError):
            router.route_request(incomplete_data)

    @patch("mlflow.pyfunc.load_model")
    def test_model_loading_failure(self, mock_load_model):
        """Test router initialization when model loading fails."""
        mock_load_model.side_effect = Exception("Model loading failed")

        with pytest.raises(Exception):
            ModelRouter("model_a_uri", "model_b_uri", split=0.5)


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.parametrize("invalid_split", [-0.1, 1.1, 2.0, -1.0])
    @patch("mlflow.pyfunc.load_model")
    def test_invalid_traffic_split(self, mock_load_model, invalid_split):
        """Test router with invalid traffic split ratios."""
        mock_load_model.return_value = Mock()

        with pytest.raises((ValueError, AssertionError)):
            ModelRouter("model_a_uri", "model_b_uri", split=invalid_split)

    def test_concurrent_predictions(self, model_server_test_client: TestClient):
        """Test concurrent prediction requests."""
        import threading

        results = []
        errors = []

        import os

        def make_request():
            try:
                request_data = {
                    "features": {
                        "temp": 0.5,
                        "humidity": 0.6,
                        "wind_speed": 0.15,
                        "hour": 14,
                        "day_of_week": 3,
                    }
                }
                response = model_server_test_client.post(
                    "/predict",
                    json=request_data,
                    headers={"X-API-Key": "test_serving_key"},
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(e)

        # Make 10 concurrent requests
        with patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}):
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

        # All requests should succeed or fail gracefully
        assert len(errors) == 0
        assert len(results) == 10
        # All should be either 200 (success) or 5xx (server error)
        for status in results:
            assert status in [200, 500, 503]

    def test_large_request_payload(self, model_server_test_client: TestClient):
        """Test handling of large request payloads."""
        import os

        # Create request with many features
        request_data = {
            "features": {
                f"feature_{i}": np.random.random() for i in range(1000)  # 1000 features
            }
        }

        with patch.dict(os.environ, {"VALID_API_KEYS": "test_serving_key"}):
            response = model_server_test_client.post(
                "/predict",
                json=request_data,
                headers={"X-API-Key": "test_serving_key"},
            )

        # Should handle gracefully (either accept or reject with proper error)
        assert response.status_code in [200, 413, 422]

    def test_malformed_json(self, model_server_test_client: TestClient):
        """Test handling of malformed JSON."""
        malformed_json = (
            '{"features": {"temp": 20.5, "humidity": 60.0'  # Missing closing braces
        )

        response = model_server_test_client.post(
            "/predict",
            data=malformed_json,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422  # Unprocessable entity

    @pytest.mark.slow
    def test_memory_usage_under_load(self, model_server_test_client: TestClient):
        """Test memory usage under sustained load."""
        import gc
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        request_data = {
            "features": {
                "temp": 20.5,
                "humidity": 60.0,
                "wind_speed": 5.2,
                "hour": 14,
                "day_of_week": 3,
            }
        }

        # Make many requests
        for _ in range(1000):
            response = model_server_test_client.post("/predict", json=request_data)
            assert response.status_code in [200, 500]

        gc.collect()  # Force garbage collection
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
