#!/usr/bin/env python3
"""Input Validation Test Suite for Model Server.

Tests comprehensive input validation including range checking,
NaN/Inf protection, and injection prevention.
"""

import os
import sys

import pytest

sys.path.append('src')

# Set test environment variables
os.environ['VALID_API_KEYS'] = 'test_key_123,test_key_456'

def test_valid_input():
    """Test that valid input passes validation."""
    from demand_forecasting.serving.model_server import PredictionRequest

    valid_input = {
        "features": {
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        }
    }

    request = PredictionRequest(**valid_input)
    assert request.features == valid_input["features"]

def test_missing_features():
    """Test validation of missing required features."""
    from pydantic import ValidationError

    from demand_forecasting.serving.model_server import PredictionRequest

    # Test missing temp
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    assert "Missing required features" in str(exc_info.value)
    assert "temp" in str(exc_info.value)

    # Test multiple missing features
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65
        })
    assert "Missing required features" in str(exc_info.value)
    assert "wind_speed" in str(exc_info.value)
    assert "hour" in str(exc_info.value)
    assert "day_of_week" in str(exc_info.value)

def test_extra_features():
    """Test validation of unexpected features (injection protection)."""
    from pydantic import ValidationError

    from demand_forecasting.serving.model_server import PredictionRequest

    # Test with extra field
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3,
            "malicious_field": "hack_attempt"
        })
    error_str = str(exc_info.value)
    # Pydantic v2 handles extra fields differently - it may show as type error or extra field error
    assert "malicious_field" in error_str or "extra" in error_str.lower()

    # Test with multiple extra fields
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3,
            "extra1": 1,
            "extra2": 2,
            "__proto__": "hack"
        })
    error_str = str(exc_info.value)
    assert "extra1" in error_str or "extra2" in error_str or "__proto__" in error_str

def test_range_validation():
    """Test range validation for all features."""
    from pydantic import ValidationError

    from demand_forecasting.serving.model_server import PredictionRequest

    # Test temperature out of range
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 999.0,  # Way out of range
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "temp" in error_str
    assert "out of range" in error_str
    assert "0.0" in error_str
    assert "1.0" in error_str

    # Test negative temperature
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": -1.0,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "temp" in error_str
    assert "out of range" in error_str

    # Test humidity out of range
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": -1.0,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "humidity" in error_str
    assert "out of range" in error_str

    # Test wind speed out of range
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 2.0,
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "wind_speed" in error_str
    assert "out of range" in error_str

    # Test hour out of range
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 25,  # Invalid hour
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "hour" in error_str
    assert "out of range" in error_str
    assert "0" in error_str
    assert "23" in error_str

    # Test day_of_week out of range
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 7  # Invalid day (0-6)
        })
    error_str = str(exc_info.value)
    assert "day_of_week" in error_str
    assert "out of range" in error_str
    assert "0" in error_str
    assert "6" in error_str

def test_nan_inf_validation():
    """Test NaN and Infinity validation."""
    from pydantic import ValidationError

    from demand_forecasting.serving.model_server import PredictionRequest

    # Test NaN values
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": float('nan'),
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "temp" in error_str
    assert ("NaN" in error_str or "invalid value" in error_str)

    # Test Infinity values
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": float('inf'),
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "humidity" in error_str
    assert ("Inf" in error_str or "invalid value" in error_str)

    # Test negative infinity
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 0.5,
            "humidity": 0.65,
            "wind_speed": float('-inf'),
            "hour": 14,
            "day_of_week": 3
        })
    error_str = str(exc_info.value)
    assert "wind_speed" in error_str
    assert ("inf" in error_str or "invalid value" in error_str)

def test_type_validation():
    """Test type validation for features."""
    from pydantic import ValidationError

    from demand_forecasting.serving.model_server import PredictionRequest

    # Test string values
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": "not_a_number",
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    # Pydantic should catch this at the field level
    assert "temp" in str(exc_info.value)

    # Test None values
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": None,
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    assert "temp" in str(exc_info.value)

    # Test list values
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": [0.5],
            "humidity": 0.65,
            "wind_speed": 0.15,
            "hour": 14,
            "day_of_week": 3
        })
    assert "temp" in str(exc_info.value)

def test_boundary_values():
    """Test boundary values (edge cases)."""
    from demand_forecasting.serving.model_server import PredictionRequest

    # Test valid boundary values
    boundary_cases = [
        # Temperature boundaries
        {"temp": 0.0, "humidity": 0.5, "wind_speed": 0.5, "hour": 12, "day_of_week": 3},
        {"temp": 1.0, "humidity": 0.5, "wind_speed": 0.5, "hour": 12, "day_of_week": 3},

        # Humidity boundaries
        {"temp": 0.5, "humidity": 0.0, "wind_speed": 0.5, "hour": 12, "day_of_week": 3},
        {"temp": 0.5, "humidity": 1.0, "wind_speed": 0.5, "hour": 12, "day_of_week": 3},

        # Wind speed boundaries
        {"temp": 0.5, "humidity": 0.5, "wind_speed": 0.0, "hour": 12, "day_of_week": 3},
        {"temp": 0.5, "humidity": 0.5, "wind_speed": 1.0, "hour": 12, "day_of_week": 3},

        # Hour boundaries
        {"temp": 0.5, "humidity": 0.5, "wind_speed": 0.5, "hour": 0, "day_of_week": 3},
        {"temp": 0.5, "humidity": 0.5, "wind_speed": 0.5, "hour": 23, "day_of_week": 3},

        # Day of week boundaries
        {"temp": 0.5, "humidity": 0.5, "wind_speed": 0.5, "hour": 12, "day_of_week": 0},
        {"temp": 0.5, "humidity": 0.5, "wind_speed": 0.5, "hour": 12, "day_of_week": 6},
    ]

    for _i, case in enumerate(boundary_cases):
        request = PredictionRequest(features=case)
        assert request.features == case

def test_edge_case_floats():
    """Test edge case float values."""
    from demand_forecasting.serving.model_server import PredictionRequest

    # Test very small positive numbers
    request = PredictionRequest(features={
        "temp": 1e-10,
        "humidity": 1e-10,
        "wind_speed": 1e-10,
        "hour": 0,
        "day_of_week": 0
    })
    assert request.features["temp"] == 1e-10

    # Test floating point precision
    request = PredictionRequest(features={
        "temp": 0.3333333333333333,
        "humidity": 0.6666666666666666,
        "wind_speed": 0.9999999999999999,
        "hour": 12,
        "day_of_week": 3
    })
    assert request.features["temp"] == 0.3333333333333333

def test_model_documentation():
    """Test that model documentation is properly set."""
    from demand_forecasting.serving.model_server import (
        PredictionRequest,
        PredictionResponse,
    )

    # Test field descriptions (use model_fields for Pydantic v2)
    try:
        request_fields = PredictionRequest.model_fields
        assert "features" in request_fields
        assert request_fields["features"].description is not None
    except AttributeError:
        # Fallback for older Pydantic versions
        request_fields = PredictionRequest.__fields__
        assert "features" in request_fields
        assert request_fields["features"].description is not None

    # Test that models have proper configuration
    assert hasattr(PredictionRequest, 'model_config')
    assert hasattr(PredictionResponse, 'model_config')

    # Test that models can be instantiated with valid data
    valid_request = PredictionRequest(features={
        "temp": 0.5,
        "humidity": 0.65,
        "wind_speed": 0.15,
        "hour": 14,
        "day_of_week": 3
    })
    assert valid_request.features["temp"] == 0.5

    # Test response model
    valid_response = PredictionResponse(
        prediction=142.5,
        confidence=0.87,
        model_version="v2.1.0",
        timestamp="2026-01-31T12:00:00Z",
        model_id="production"
    )
    assert valid_response.prediction == 142.5

def test_comprehensive_validation_errors():
    """Test multiple validation errors at once."""
    from pydantic import ValidationError

    from demand_forecasting.serving.model_server import PredictionRequest

    # Test multiple issues at once - extra field will be caught first in Pydantic v2
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 999.0,  # Out of range
            "humidity": float('nan'),  # NaN
            "wind_speed": -1.0,  # Out of range
            "hour": 25,  # Out of range
            "day_of_week": 7,  # Out of range
            "extra_field": "injection"  # Extra field
        })

    error_str = str(exc_info.value)

    # In Pydantic v2, extra field errors are caught first as type errors
    assert "extra_field" in error_str or "extra" in error_str.lower()

    # Test range validation errors separately (without extra fields)
    with pytest.raises(ValidationError) as exc_info:
        PredictionRequest(features={
            "temp": 999.0,  # Out of range
            "humidity": float('nan'),  # NaN
            "wind_speed": -1.0,  # Out of range
            "hour": 25,  # Out of range
            "day_of_week": 7  # Out of range
        })

    error_str = str(exc_info.value)

    # Should catch multiple validation errors
    assert "temp" in error_str  # Range error
    assert "humidity" in error_str  # NaN error
    assert "wind_speed" in error_str  # Range error
    assert "hour" in error_str  # Range error
    assert "day_of_week" in error_str  # Range error


def main() -> int | None:
    """Run all input validation tests."""
    try:
        test_valid_input()
        test_missing_features()
        test_extra_features()
        test_range_validation()
        test_nan_inf_validation()
        test_type_validation()
        test_boundary_values()
        test_edge_case_floats()
        test_model_documentation()
        test_comprehensive_validation_errors()


        return 0

    except Exception:
        return 1

if __name__ == "__main__":
    sys.exit(main())
