"""Secrets management utility for demand forecasting system.

This module provides a lightweight secrets management solution for free-tier
deployments, with hooks for upgrading to enterprise solutions like HashiCorp Vault
or AWS Secrets Manager.

Usage:
    from demand_forecasting.utils.secrets_manager import get_secret, validate_secrets

    # Get a secret (checks env vars, then .env file, then Vault if configured)
    api_key = get_secret("API_KEY")

    # Validate all required secrets at startup
    validate_secrets(["POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "REDIS_PASSWORD"])
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SecretsConfig:
    """Configuration for secrets management."""

    # Environment variable prefix for secrets
    env_prefix: str = ""

    # Path to .env file (for local development)
    env_file: Path | None = None

    # Vault configuration (for production)
    vault_enabled: bool = False
    vault_addr: str = ""
    vault_token: str = ""
    vault_path: str = "secret/data/demand_forecasting"

    # AWS Secrets Manager configuration (alternative)
    aws_secrets_enabled: bool = False
    aws_secret_name: str = "demand_forecasting"  # noqa: S105
    aws_region: str = "us-east-1"


# Default configuration
_config = SecretsConfig(
    vault_enabled=os.environ.get("VAULT_ENABLED", "false").lower() == "true",
    vault_addr=os.environ.get("VAULT_ADDR", ""),
    vault_token=os.environ.get("VAULT_TOKEN", ""),
    aws_secrets_enabled=os.environ.get("AWS_SECRETS_ENABLED", "false").lower()
    == "true",
)


# =============================================================================
# Secret Retrieval Functions
# =============================================================================


def get_secret(key: str, default: str | None = None) -> str | None:
    """Get a secret value with fallback chain.

    Order of precedence:
    1. Environment variable
    2. .env file (if configured)
    3. HashiCorp Vault (if enabled)
    4. AWS Secrets Manager (if enabled)
    5. Default value

    Args:
        key: Secret key name
        default: Default value if secret not found

    Returns:
        Secret value or default
    """
    # Check environment variable
    env_key = f"{_config.env_prefix}{key}" if _config.env_prefix else key
    value = os.environ.get(env_key)
    if value:
        return value

    # Check .env file
    if _config.env_file and _config.env_file.exists():
        value = _get_from_env_file(key)
        if value:
            return value

    # Check Vault (if enabled)
    if _config.vault_enabled:
        value = _get_from_vault(key)
        if value:
            return value

    # Check AWS Secrets Manager (if enabled)
    if _config.aws_secrets_enabled:
        value = _get_from_aws_secrets(key)
        if value:
            return value

    # Return default
    return default


def get_secret_required(key: str) -> str:
    """Get a required secret, raising error if not found.

    Args:
        key: Secret key name

    Returns:
        Secret value

    Raises:
        ValueError: If secret is not found
    """
    value = get_secret(key)
    if value is None:
        raise ValueError(
            f"Required secret '{key}' not found. "
            f"Set it via environment variable or configure secrets backend. "
            f"For production, consider using VAULT_ENABLED=true or AWS_SECRETS_ENABLED=true."
        )
    return value


def validate_secrets(required_keys: list[str]) -> dict[str, bool]:
    """Validate that all required secrets are available.

    Args:
        required_keys: List of secret keys that must be present

    Returns:
        Dictionary mapping key -> is_present

    Raises:
        ValueError: If any required secrets are missing
    """
    results = {}
    missing = []

    for key in required_keys:
        value = get_secret(key)
        is_present = value is not None and len(value) > 0
        results[key] = is_present
        if not is_present:
            missing.append(key)

    if missing:
        _LOGGER.error(f"Missing required secrets: {missing}")
        raise ValueError(
            f"Missing required secrets: {missing}. "
            f"Configure these via environment variables or secrets backend."
        )

    _LOGGER.info(f"✅ All {len(required_keys)} required secrets validated")
    return results


# =============================================================================
# Backend-Specific Functions
# =============================================================================


def _get_from_env_file(key: str) -> str | None:
    """Read secret from .env file."""
    if not _config.env_file:
        return None

    try:
        with _config.env_file.open() as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
    except Exception as e:
        _LOGGER.warning(f"Failed to read .env file: {e}")

    return None


def _get_from_vault(key: str) -> str | None:
    """Read secret from HashiCorp Vault.

    Requires: hvac package (pip install hvac)
    """
    try:
        import hvac  # noqa: PLC0415

        client = hvac.Client(url=_config.vault_addr, token=_config.vault_token)

        if not client.is_authenticated():
            _LOGGER.warning("Vault authentication failed")
            return None

        # Read from KV v2 secrets engine
        response = client.secrets.kv.v2.read_secret_version(
            path=_config.vault_path.replace("secret/data/", ""),
            mount_point="secret",
        )

        data = response.get("data", {}).get("data", {})
        return data.get(key)

    except ImportError:
        _LOGGER.debug("hvac package not installed, skipping Vault lookup")
        return None
    except Exception as e:
        _LOGGER.warning(f"Failed to read from Vault: {e}")
        return None


def _get_from_aws_secrets(key: str) -> str | None:
    """Read secret from AWS Secrets Manager.

    Requires: boto3 package (pip install boto3)
    """
    try:
        import boto3  # noqa: PLC0415

        client = boto3.client("secretsmanager", region_name=_config.aws_region)

        response = client.get_secret_value(SecretId=_config.aws_secret_name)
        secret_string = response.get("SecretString", "{}")
        secrets = json.loads(secret_string)

        return secrets.get(key)

    except ImportError:
        _LOGGER.debug(
            "boto3 package not installed, skipping AWS Secrets Manager lookup"
        )
        return None
    except Exception as e:
        _LOGGER.warning(f"Failed to read from AWS Secrets Manager: {e}")
        return None


# =============================================================================
# Helper Functions
# =============================================================================


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret for safe logging.

    Args:
        value: Secret value to mask
        visible_chars: Number of characters to show at end

    Returns:
        Masked string like "****xyz"
    """
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def list_available_backends() -> list[str]:
    """List configured and available secrets backends.

    Returns:
        List of available backend names
    """
    backends = ["environment"]

    if _config.env_file and _config.env_file.exists():
        backends.append("env_file")

    if _config.vault_enabled:
        try:
            import hvac  # noqa: F401, PLC0415

            backends.append("vault")
        except ImportError:
            pass

    if _config.aws_secrets_enabled:
        try:
            import boto3  # noqa: F401, PLC0415

            backends.append("aws_secrets_manager")
        except ImportError:
            pass

    return backends


# =============================================================================
# Startup Validation
# =============================================================================

# Common secrets that should be validated at startup
REQUIRED_SECRETS = [
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "MINIO_ROOT_PASSWORD",
]

OPTIONAL_SECRETS = [
    "AIRFLOW__CORE__FERNET_KEY",
    "AIRFLOW__WEBSERVER__SECRET_KEY",
    "GRAFANA_ADMIN_PASSWORD",
]


def validate_startup_secrets(strict: bool = False) -> dict[str, Any]:
    """Validate secrets at application startup.

    Args:
        strict: If True, raise error on missing required secrets

    Returns:
        Validation report
    """
    report = {
        "backends": list_available_backends(),
        "required": {},
        "optional": {},
        "missing_required": [],
        "missing_optional": [],
    }

    for key in REQUIRED_SECRETS:
        value = get_secret(key)
        is_present = value is not None
        report["required"][key] = is_present
        if not is_present:
            report["missing_required"].append(key)

    for key in OPTIONAL_SECRETS:
        value = get_secret(key)
        is_present = value is not None
        report["optional"][key] = is_present
        if not is_present:
            report["missing_optional"].append(key)

    if report["missing_required"]:
        msg = f"Missing required secrets: {report['missing_required']}"
        _LOGGER.warning(msg)
        if strict:
            raise ValueError(msg)
    else:
        _LOGGER.info("✅ All required secrets are configured")

    if report["missing_optional"]:
        _LOGGER.info(f"Optional secrets not configured: {report['missing_optional']}")

    return report
