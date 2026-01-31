# Security Hardening Script
# Run this to generate secure values for production

import secrets
import base64
import os

def generate_fernet_key():
    """Generate a secure Fernet key for Airflow"""
    # Generate 32-byte key and base64 encode it
    key = base64.urlsafe_b64encode(os.urandom(32))
    return key.decode()

def generate_secret_key(length=32):
    """Generate a secure secret key"""
    return secrets.token_urlsafe(length)

def generate_minio_credentials():
    """Generate secure MinIO credentials"""
    return {
        "root_user": f"admin-{secrets.token_hex(8)}",
        "root_password": secrets.token_urlsafe(32)
    }

if __name__ == "__main__":
    print("=== Security Configuration Generator ===")
    print()
    print("1. Airflow Fernet Key:")
    print(f'   AIRFLOW__CORE__FERNET_KEY: "{generate_fernet_key()}"')
    print()
    print("2. Airflow Webserver Secret Key:")
    print(f'   AIRFLOW__WEBSERVER__SECRET_KEY: "{generate_secret_key()}"')
    print()
    print("3. MinIO Credentials:")
    creds = generate_minio_credentials()
    print(f'   MINIO_ROOT_USER: {creds["root_user"]}')
    print(f'   MINIO_ROOT_PASSWORD: {creds["root_password"]}')
    print()
    print("4. Postgres Password:")
    print(f'   POSTGRES_PASSWORD: {secrets.token_urlsafe(24)}')
    print()
    print("=== Add these to your .env file ===")
