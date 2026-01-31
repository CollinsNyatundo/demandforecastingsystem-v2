# Setup Instructions - Demand Forecasting System

**Last Updated:** December 31, 2025  
**Status:** Production Ready with Enhanced Monitoring

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Email Alerts Setup](#email-alerts-setup)
3. [Remote Logging Configuration](#remote-logging-configuration)
4. [Data Validation](#data-validation)
5. [Model Metrics Tracking](#model-metrics-tracking)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Gmail account for email alerts (or another SMTP provider)
- At least 8GB RAM and 20GB disk space

### Initial Setup

```bash
# Navigate to project directory
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Create .env file from template
copy .env.template .env

# Edit .env and add your email credentials (see Email Alerts Setup below)
notepad .env

# Start services
docker-compose up -d

# Wait for services to be healthy (~2 minutes)
docker-compose ps

# Run connection setup script
docker-compose exec airflow-scheduler bash /opt/airflow/scripts/setup_connections.sh

# Access Airflow UI
# http://localhost:8080
# Username: Cole
# Password: admin
```

---

## Email Alerts Setup

### Option 1: Gmail (Recommended for Testing)

**Step 1: Create Gmail App Password**

1. Go to your Google Account: https://myaccount.google.com/
2. Navigate to Security → 2-Step Verification (enable if not already)
3. Go to Security → App passwords
4. Select "Mail" and "Other (Custom name)" → Name it "Airflow Demand Forecasting"
5. Copy the 16-character password (example: `abcd efgh ijkl mnop`)

**Step 2: Configure .env File**

Edit `app-ml/.env`:

```bash
# Gmail Configuration
AIRFLOW__SMTP__SMTP_USER=cnyagakan@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=abcdefghijklmnop  # Your 16-char app password (no spaces)
```

**Step 3: Restart Services**

```bash
cd app-ml
docker-compose restart
```

**Step 4: Test Email**

```bash
docker-compose exec airflow-scheduler python -c "
from airflow.utils.email import send_email
send_email(
    to=['cnyagakan@gmail.com'],
    subject='[TEST] Airflow Email Setup',
    html_content='<p>Email alerts are working! ✅</p>'
)
print('✅ Test email sent!')
"
```

Check your inbox for the test email.

### Option 2: Other SMTP Providers

**For Outlook/Office365:**

Edit `app-ml/docker-compose.yaml`:

```yaml
AIRFLOW__SMTP__SMTP_HOST: "smtp.office365.com"
AIRFLOW__SMTP__SMTP_PORT: "587"
AIRFLOW__SMTP__SMTP_STARTTLS: "true"
AIRFLOW__SMTP__SMTP_SSL: "false"
```

Edit `.env`:
```bash
AIRFLOW__SMTP__SMTP_USER=your-email@outlook.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-password
```

**For AWS SES:**

Edit `app-ml/docker-compose.yaml`:

```yaml
AIRFLOW__SMTP__SMTP_HOST: "email-smtp.us-east-1.amazonaws.com"
AIRFLOW__SMTP__SMTP_PORT: "587"
AIRFLOW__SMTP__SMTP_STARTTLS: "true"
AIRFLOW__SMTP__SMTP_SSL: "false"
```

Edit `.env`:
```bash
AIRFLOW__SMTP__SMTP_USER=your-ses-smtp-username
AIRFLOW__SMTP__SMTP_PASSWORD=your-ses-smtp-password
```

### Email Alert Configuration in DAG

The DAG is already configured to send emails on:
- ✅ Task failures (`email_on_failure: true`)
- ✅ Task retries (`email_on_retry: true`)
- ✅ Data validation failures (custom alerts)

**Email Recipients:**
- Default: `cnyagakan@gmail.com`
- To add more recipients, edit `app-ml/dags/airflow_dag.py`:

```python
default_args = {
    "email": ["cnyagakan@gmail.com", "team@company.com"],
    "email_on_failure": True,
    "email_on_retry": True,
}
```

---

## Remote Logging Configuration

Remote logging to MinIO S3 is pre-configured. Logs are stored in the `airflow-logs` bucket.

### Verify Remote Logging

```bash
# Check if airflow-logs bucket exists
docker-compose exec minio sh -c "
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc ls myminio/airflow-logs/
"

# Trigger a DAG run
docker-compose exec airflow-scheduler airflow dags trigger demand_forecasting_custom

# Wait 30 seconds, then check logs
docker-compose exec minio sh -c "
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc ls -r myminio/airflow-logs/ | head -20
"
```

### Access Logs via MinIO UI

1. Open http://localhost:9001
2. Login: `minioadmin` / `minioadmin`
3. Navigate to `airflow-logs` bucket
4. Browse logs by DAG ID and execution date

---

## Data Validation

The pipeline now includes automatic data validation before preprocessing.

### What's Validated

1. **Data Presence:** Ensures raw data exists and is not empty
2. **Missing Values:** Checks that < 50% of data is missing
3. **Data Quality:** Logs data statistics (rows, columns, date ranges)

### Custom Validation Rules

Edit `app-ml/dags/airflow_dag.py` in the `t_validate_raw_data` task:

```python
@task()
def t_validate_raw_data():
    catalog, _ = get_catalog()
    df = catalog.load("raw_bike_data")
    
    # Add custom validations
    assert len(df) > 1000, "Need at least 1000 rows"
    assert 'cnt' in df.columns, "Missing target column 'cnt'"
    assert df['cnt'].min() >= 0, "Negative demand values found"
    
    return {"rows": len(df), "validation": "passed"}
```

### Using Great Expectations (Advanced)

For more sophisticated validation, use Great Expectations:

```python
import great_expectations as gx

@task()
def t_validate_with_ge():
    context = gx.get_context()
    
    # Define expectations
    suite = context.add_expectation_suite("raw_data_suite")
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name="raw_data_suite"
    )
    
    validator.expect_column_values_to_not_be_null("cnt")
    validator.expect_column_values_to_be_between("temp", 0, 1)
    
    results = validator.validate()
    assert results.success, "Data validation failed"
```

---

## Model Metrics Tracking

### Using the MetricsTracker

The system includes a built-in `MetricsTracker` for logging model performance.

**Example Usage in DAG:**

```python
from demand_forecasting.utils import create_tracker

@task()
def t_train_and_track_model():
    tracker = create_tracker(run_id="manual_run_20251231")
    
    # Log training metrics
    tracker.log_training_metrics(
        model_name="catboost_v1",
        metrics={"rmse": 45.2, "mae": 32.1, "r2": 0.89},
        hyperparameters={"iterations": 1000, "depth": 6}
    )
    
    # Log validation metrics
    tracker.log_validation_metrics(
        model_name="catboost_v1",
        metrics={"rmse": 48.5, "mae": 35.2, "r2": 0.87}
    )
    
    # Save metrics
    tracker.save_to_json("/opt/airflow/data/metrics/run_metrics.json")
    tracker.save_to_csv("/opt/airflow/data/metrics/validation.csv", "validation")
    
    # Get best model
    best_model = tracker.get_best_model(metric_name="rmse", higher_is_better=False)
    print(f"Best model: {best_model}")
    
    return tracker.get_metrics_summary()
```

### Viewing Metrics

```bash
# View JSON metrics
docker-compose exec airflow-scheduler cat /opt/airflow/data/metrics/run_metrics.json

# View CSV metrics
docker-compose exec airflow-scheduler cat /opt/airflow/data/metrics/validation.csv

# Copy to local machine
docker cp app-ml-airflow-scheduler-1:/opt/airflow/data/metrics ./metrics_export
```

### Integration with MLflow (Optional)

To track experiments with MLflow:

1. **Start MLflow Server:**

```yaml
# Add to docker-compose.yaml
mlflow:
  image: ghcr.io/mlflow/mlflow:v2.10.0
  ports:
    - "5000:5000"
  command: mlflow server --host 0.0.0.0 --backend-store-uri sqlite:///mlflow.db --default-artifact-root /mlflow/artifacts
  volumes:
    - mlflow-data:/mlflow
```

2. **Update DAG to Log to MLflow:**

```python
import mlflow

@task()
def t_train_with_mlflow():
    mlflow.set_tracking_uri("http://mlflow:5000")
    
    with mlflow.start_run():
        # Train model
        model = train_model(data)
        
        # Log parameters
        mlflow.log_params({"iterations": 1000, "depth": 6})
        
        # Log metrics
        mlflow.log_metrics({"rmse": 45.2, "mae": 32.1})
        
        # Log model
        mlflow.sklearn.log_model(model, "model")
```

---

## Monitoring & Alerting

### Health Check Dashboard

Create a simple monitoring script:

```python
# app-ml/scripts/health_check.py
import requests
from datetime import datetime

def check_airflow_health():
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_minio_health():
    try:
        response = requests.get("http://localhost:9000/minio/health/live", timeout=5)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print(f"[{datetime.now()}] Health Check")
    print(f"Airflow: {'✅' if check_airflow_health() else '❌'}")
    print(f"MinIO: {'✅' if check_minio_health() else '❌'}")
```

Run periodically:
```bash
# Windows Task Scheduler or cron
python app-ml/scripts/health_check.py
```

### Prometheus + Grafana (Production-Grade)

**Step 1: Add to docker-compose.yaml**

```yaml
prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus-data:/prometheus

grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana-data:/var/lib/grafana
```

**Step 2: Create prometheus.yml**

```yaml
# app-ml/monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'airflow'
    static_configs:
      - targets: ['airflow-webserver:8080']
```

**Step 3: Configure Airflow to Expose Metrics**

Add to docker-compose.yaml:
```yaml
AIRFLOW__METRICS__STATSD_ON: "true"
AIRFLOW__METRICS__STATSD_HOST: "prometheus"
AIRFLOW__METRICS__STATSD_PORT: "9125"
```

**Step 4: Access Dashboards**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

---

## CI/CD Pipeline

### GitHub Actions Setup

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Airflow DAG

on:
  push:
    branches: [ main ]
    paths:
      - 'app-ml/dags/**'
      - 'app-ml/src/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r app-ml/requirements.txt
          pip install pytest flake8
      
      - name: Lint
        run: flake8 app-ml/dags app-ml/src
      
      - name: Test DAG
        run: python app-ml/dags/airflow_dag.py
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Production
        run: |
          # SSH to production server and restart Airflow
          ssh user@production-server "cd /opt/airflow && docker-compose restart"
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
EOF

# Install hooks
pre-commit install
```

---

## Troubleshooting

### Email Not Sending

**Check SMTP Configuration:**
```bash
docker-compose exec airflow-scheduler python -c "
import os
print('SMTP Host:', os.getenv('AIRFLOW__SMTP__SMTP_HOST'))
print('SMTP User:', os.getenv('AIRFLOW__SMTP__SMTP_USER'))
print('SMTP Port:', os.getenv('AIRFLOW__SMTP__SMTP_PORT'))
"
```

**Test SMTP Connection:**
```bash
docker-compose exec airflow-scheduler python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('cnyagakan@gmail.com', 'your-app-password')
print('✅ SMTP connection successful')
server.quit()
"
```

**Common Issues:**
- ❌ "Authentication failed" → Check App Password (not regular password)
- ❌ "Connection refused" → Check firewall/network settings
- ❌ "SMTP not configured" → Verify .env file is loaded

### Data Validation Failing

```bash
# Check raw data
docker-compose exec airflow-scheduler python -c "
from kedro.config import OmegaConfigLoader
from kedro.io import DataCatalog

loader = OmegaConfigLoader(conf_source='/opt/airflow/conf', env='local')
catalog = DataCatalog.from_config(loader['catalog'], loader['credentials'])
df = catalog.load('raw_bike_data')
print(f'Rows: {len(df)}, Columns: {len(df.columns)}')
print(f'Missing: {df.isnull().sum().sum()}')
"
```

### Remote Logging Not Working

```bash
# Check MinIO connection
docker-compose exec airflow-scheduler python -c "
import s3fs
fs = s3fs.S3FileSystem(
    client_kwargs={'endpoint_url': 'http://minio:9000'},
    key='minioadmin',
    secret='minioadmin'
)
print('Buckets:', fs.ls(''))
"

# Recreate airflow-logs bucket
docker-compose exec minio sh -c "
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc mb myminio/airflow-logs --ignore-existing
mc ls myminio/
"
```

---

## Security Best Practices

### 1. Never Commit Secrets
```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore
echo "*.env" >> .gitignore
```

### 2. Use Airflow Connections for Credentials
```bash
# Store in Airflow (not in code)
docker-compose exec airflow-scheduler airflow connections add 'my_db' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-login 'user' \
    --conn-password 'password'
```

### 3. Enable HTTPS (Production)
Use nginx reverse proxy with Let's Encrypt SSL.

### 4. Rotate Passwords Regularly
Update SMTP passwords, database passwords every 90 days.

---

## Next Steps After Setup

- [ ] Configure email alerts with your Gmail App Password
- [ ] Test email sending
- [ ] Verify remote logging to MinIO
- [ ] Run a full DAG execution
- [ ] Set up Prometheus + Grafana (optional)
- [ ] Configure CI/CD pipeline
- [ ] Review and customize data validation rules
- [ ] Set up automated backups

---

## Support & Contact

**Email:** cnyagakan@gmail.com  
**Documentation:** See `AIRFLOW_INTEGRATION_COMPLETE.md` and `QUICK_REFERENCE.md`  
**Issues:** Check logs with `docker-compose logs -f <service-name>`

---

**End of Setup Instructions**