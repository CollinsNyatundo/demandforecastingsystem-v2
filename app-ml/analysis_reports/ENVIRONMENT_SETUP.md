# Environment Configuration Guide

This document describes all required environment variables for the Demand Forecasting ML system.

## Quick Setup

1. Copy the example configuration below to a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```

2. Update the values with your actual credentials

3. The `.env` file is automatically loaded by Docker Compose

---

## Required Environment Variables

### 1. MinIO / S3 Configuration

**Purpose:** Connect to MinIO object storage for data and model artifacts.

```bash
# MinIO Endpoint (default for local development)
MINIO_ENDPOINT=http://host.docker.internal:9000

# MinIO Access Credentials
# ⚠️ CHANGE THESE IN PRODUCTION!
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# S3 Bucket Configuration
S3_BUCKET=demand-forecasting
```

**Security Notes:**
- Never commit actual credentials to version control
- Use strong, unique passwords in production
- Consider using AWS Secrets Manager or HashiCorp Vault for production

---

### 2. Email / SMTP Configuration

**Purpose:** Send email notifications for DAG failures and alerts.

```bash
# SMTP Server Configuration
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_STARTTLS=True
AIRFLOW__SMTP__SMTP_SSL=False

# SMTP Authentication
# ⚠️ For Gmail, use an App Password, not your regular password
# Generate at: https://myaccount.google.com/apppasswords
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password

# Email Notification Settings
AIRFLOW__SMTP__SMTP_MAIL_FROM=airflow@demand-forecasting.local
```

**Gmail Setup:**
1. Enable 2-Factor Authentication on your Google account
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Use the App Password (16 characters, no spaces) as `SMTP_PASSWORD`

**Other Providers:**
- **Outlook/Office365:** `smtp.office365.com:587`
- **SendGrid:** `smtp.sendgrid.net:587`
- **AWS SES:** `email-smtp.us-east-1.amazonaws.com:587`

---

### 3. Airflow Configuration

**Purpose:** Configure Airflow runtime behavior and authentication.

```bash
# Airflow Core Settings
AIRFLOW__CORE__FERNET_KEY=<generate-with-python-cryptography>
AIRFLOW__CORE__EXECUTOR=CeleryExecutor
AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
AIRFLOW__CORE__LOAD_EXAMPLES=False

# Airflow Webserver
AIRFLOW__WEBSERVER__SECRET_KEY=<generate-random-string>
AIRFLOW__WEBSERVER__EXPOSE_CONFIG=False

# Airflow Admin User
AIRFLOW_ADMIN_USERNAME=admin
AIRFLOW_ADMIN_PASSWORD=<change-in-production>
AIRFLOW_ADMIN_EMAIL=admin@demand-forecasting.local
```

**Generate Fernet Key:**
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

**Generate Secret Key:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

---

### 4. Kedro Configuration

**Purpose:** Configure Kedro environment and runtime settings.

```bash
# Kedro Environment (local, dev, staging, prod)
KEDRO_ENV=local

# Kedro Project Path (inside container)
KEDRO_PROJECT_PATH=/opt/airflow

# Kedro Configuration Source
KEDRO_CONF_SOURCE=conf
```

---

### 5. Database Configuration (PostgreSQL)

**Purpose:** Airflow metadata database configuration.

```bash
# PostgreSQL Connection
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=airflow
POSTGRES_USER=airflow
POSTGRES_PASSWORD=<change-in-production>
```

---

### 6. Redis Configuration (Celery Backend)

**Purpose:** Message broker for distributed task execution.

```bash
# Redis Connection
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<optional-set-in-production>

# Celery Broker URL
AIRFLOW__CELERY__BROKER_URL=redis://redis:6379/0
AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres/airflow
```

---

### 7. Python / Application Settings

**Purpose:** Python path and application-specific settings.

```bash
# Python Path (for custom modules)
PYTHONPATH=/opt/airflow/src

# Application Settings
APP_ENV=development
LOG_LEVEL=INFO
ENABLE_DEBUG=False
```

---

## Complete .env.example File

Create a file named `.env.example` in the project root with the following content:

```bash
# ==============================================================================
# Demand Forecasting ML System - Environment Configuration
# ==============================================================================
# SECURITY WARNING: Never commit the actual .env file to version control!
# This is a template. Copy to .env and update with real credentials.
# ==============================================================================

# ------------------------------------------------------------------------------
# MinIO / S3 Configuration
# ------------------------------------------------------------------------------
MINIO_ENDPOINT=http://host.docker.internal:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
S3_BUCKET=demand-forecasting

# ------------------------------------------------------------------------------
# Email / SMTP Configuration
# ------------------------------------------------------------------------------
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_STARTTLS=True
AIRFLOW__SMTP__SMTP_SSL=False
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password
AIRFLOW__SMTP__SMTP_MAIL_FROM=airflow@demand-forecasting.local

# ------------------------------------------------------------------------------
# Airflow Core Configuration
# ------------------------------------------------------------------------------
AIRFLOW__CORE__FERNET_KEY=GENERATE_WITH_CRYPTOGRAPHY_FERNET
AIRFLOW__CORE__EXECUTOR=CeleryExecutor
AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
AIRFLOW__CORE__LOAD_EXAMPLES=False

# ------------------------------------------------------------------------------
# Airflow Webserver Configuration
# ------------------------------------------------------------------------------
AIRFLOW__WEBSERVER__SECRET_KEY=GENERATE_RANDOM_SECRET_KEY
AIRFLOW__WEBSERVER__EXPOSE_CONFIG=False

# ------------------------------------------------------------------------------
# Airflow Admin User
# ------------------------------------------------------------------------------
AIRFLOW_ADMIN_USERNAME=admin
AIRFLOW_ADMIN_PASSWORD=CHANGE_IN_PRODUCTION
AIRFLOW_ADMIN_EMAIL=admin@demand-forecasting.local

# ------------------------------------------------------------------------------
# Kedro Configuration
# ------------------------------------------------------------------------------
KEDRO_ENV=local
KEDRO_PROJECT_PATH=/opt/airflow
KEDRO_CONF_SOURCE=conf

# ------------------------------------------------------------------------------
# Database Configuration (PostgreSQL)
# ------------------------------------------------------------------------------
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=airflow
POSTGRES_USER=airflow
POSTGRES_PASSWORD=CHANGE_IN_PRODUCTION

# ------------------------------------------------------------------------------
# Redis Configuration (Celery Backend)
# ------------------------------------------------------------------------------
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
AIRFLOW__CELERY__BROKER_URL=redis://redis:6379/0
AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres/airflow

# ------------------------------------------------------------------------------
# Python / Application Settings
# ------------------------------------------------------------------------------
PYTHONPATH=/opt/airflow/src
APP_ENV=development
LOG_LEVEL=INFO
ENABLE_DEBUG=False

# ------------------------------------------------------------------------------
# Security Settings
# ------------------------------------------------------------------------------
# Set to 'production' to enforce stricter security
ENVIRONMENT=development

# Disable email in development if not configured
DISABLE_EMAIL_ALERTS=False
```

---

## Environment-Specific Configurations

### Local Development

```bash
KEDRO_ENV=local
MINIO_ENDPOINT=http://host.docker.internal:9000
LOG_LEVEL=DEBUG
ENABLE_DEBUG=True
DISABLE_EMAIL_ALERTS=True  # Skip email in local dev
```

### Staging

```bash
KEDRO_ENV=staging
MINIO_ENDPOINT=https://minio-staging.example.com
LOG_LEVEL=INFO
ENABLE_DEBUG=False
DISABLE_EMAIL_ALERTS=False
```

### Production

```bash
KEDRO_ENV=prod
MINIO_ENDPOINT=https://s3.amazonaws.com
LOG_LEVEL=WARNING
ENABLE_DEBUG=False
DISABLE_EMAIL_ALERTS=False
# ⚠️ Use AWS Secrets Manager or Vault for production credentials
```

---

## Validation

To validate your environment configuration:

```bash
# Check that .env file exists
test -f .env && echo "✅ .env file found" || echo "❌ .env file missing"

# Verify environment variables are loaded
docker-compose config | grep MINIO_ENDPOINT

# Test MinIO connection
python scripts/test_minio_connection.py

# Test email configuration
python scripts/test_email_config.py
```

---

## Security Best Practices

### 1. Credential Rotation

- Rotate credentials every 90 days in production
- Use different credentials for each environment
- Never reuse credentials across systems

### 2. Access Control

- Use IAM roles and policies in cloud environments
- Implement least-privilege access
- Audit access logs regularly

### 3. Secrets Management

**Development:**
- Use `.env` file (excluded from git)
- Store template in `.env.example`

**Production:**
- Use AWS Secrets Manager
- Use HashiCorp Vault
- Use Kubernetes Secrets
- Never use `.env` files in production

### 4. Encryption

- Enable SSL/TLS for all external connections
- Encrypt data at rest in S3
- Use encrypted environment variables in CI/CD

---

## Troubleshooting

### Issue: Email notifications not working

**Solution:**
1. Check SMTP credentials are correct
2. Verify firewall allows outbound port 587
3. For Gmail, ensure App Password is used (not regular password)
4. Check Airflow logs: `docker-compose logs airflow-scheduler | grep -i smtp`

### Issue: Cannot connect to MinIO

**Solution:**
1. Verify MinIO is running: `docker-compose ps minio`
2. Check MinIO endpoint is reachable: `curl http://localhost:9000/minio/health/live`
3. Verify credentials match MinIO configuration
4. Check network settings in docker-compose.yaml

### Issue: Airflow tasks fail with import errors

**Solution:**
1. Verify PYTHONPATH is set correctly: `echo $PYTHONPATH`
2. Check that `/opt/airflow/src` contains your Python packages
3. Rebuild Docker image: `docker-compose build`

---

## Additional Resources

- [Airflow Configuration Reference](https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html)
- [MinIO Configuration Guide](https://docs.min.io/docs/minio-server-configuration-guide.html)
- [Kedro Configuration](https://kedro.readthedocs.io/en/stable/04_kedro_project_setup/02_configuration.html)
- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)

---

**Last Updated:** 2025-01-XX  
**Version:** 1.0.0  
**Status:** Production Ready ✅