# Security Hardening Script
# Run this to generate secure values for production

import base64
import os
import secrets


def generate_fernet_key():
    """Generate a secure Fernet key for Airflow."""
    # Generate 32-byte key and base64 encode it
    key = base64.urlsafe_b64encode(os.urandom(32))
    return key.decode()


def generate_secret_key(length=32):
    """Generate a secure secret key."""
    return secrets.token_urlsafe(length)


def generate_minio_credentials():
    """Generate secure MinIO credentials."""
    return {
        "root_user": f"admin-{secrets.token_hex(8)}",
        "root_password": secrets.token_urlsafe(32),
    }


if __name__ == "__main__":
    creds = generate_minio_credentials()
