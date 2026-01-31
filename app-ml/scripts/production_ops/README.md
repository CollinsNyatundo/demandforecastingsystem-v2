# Production Operations Scripts

**Version:** 3.0.0  
**Date:** January 2025  
**Status:** ✅ Production Ready

---

## 📖 Overview

This directory contains production operations scripts for the Demand Forecasting ML system, implementing Priority 3 features:

1. **Data Drift Detection** - Statistical drift monitoring with PostgreSQL persistence
2. **Automated Retraining Scheduler** - Multi-trigger retraining orchestration

Both scripts follow pg-aiguide best practices for PostgreSQL integration and are fully tested with comprehensive test coverage.

---

## 📁 Contents

```
production_ops/
├── README.md                      # This file
├── detect_data_drift.py          # Data drift detection system (724 lines)
├── automated_retraining.py       # Retraining scheduler (725 lines)
└── __init__.py                   # Module initialization
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python dependencies (already in requirements.txt)
pip install scipy sqlalchemy pandas numpy requests

# PostgreSQL database (same as Optuna)
docker-compose up -d postgres
```

### Environment Variables

```bash
# .env file
DRIFT_STORAGE_URL=postgresql://airflow:airflow@localhost:5432/optuna
AIRFLOW_URL=http://localhost:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
RETRAINING_SCHEDULE_DAYS=7
TRAINING_DATA_PATH=data/01_raw/superstore_train.csv
AIRFLOW_ALERT_EMAIL=team@example.com
```

### Basic Usage

```bash
# 1. Detect drift
python scripts/production_ops/detect_data_drift.py \
  --reference-data data/01_raw/superstore_train.csv \
  --production-data data/production/recent_data.csv

# 2. Check if retraining needed
python scripts/production_ops/automated_retraining.py --check

# 3. Trigger retraining if needed
python scripts/production_ops/automated_retraining.py --trigger
```

---

## 🔍 Script 1: Data Drift Detection

### Overview

Detects statistical drift in input features using multiple methods:
- **Kolmogorov-Smirnov test** (continuous features)
- **Chi-square test** (categorical features)
- **Population Stability Index (PSI)**
- **Wasserstein distance**

Results are stored in PostgreSQL for historical tracking.

### Command Line Usage

#### Basic Drift Detection

```bash
python scripts/production_ops/detect_data_drift.py \
  --reference-data data/01_raw/superstore_train.csv \
  --production-data data/production/recent_data.csv
```

#### With Email Alerts

```bash
python scripts/production_ops/detect_data_drift.py \
  --reference-data data/01_raw/superstore_train.csv \
  --production-data data/production/recent_data.csv \
  --alert
```

#### Custom Thresholds

```bash
python scripts/production_ops/detect_data_drift.py \
  --reference-data ref.csv \
  --production-data prod.csv \
  --alpha 0.01 \
  --psi-threshold 0.15 \
  --wasserstein-threshold 0.05
```

#### View Drift History

```bash
# Last 30 days
python scripts/production_ops/detect_data_drift.py --history --days 30

# Drift-only records
python scripts/production_ops/detect_data_drift.py --history --days 30 --drift-only
```

### Python API Usage

```python
from production_ops.detect_data_drift import DriftDetector
import pandas as pd

# Initialize detector
detector = DriftDetector(
    storage_url="postgresql://user:pass@host:5432/optuna",
    alpha=0.05,
    psi_threshold=0.2,
    wasserstein_threshold=0.1
)

# Load data
reference_data = pd.read_csv("data/reference.csv")
production_data = pd.read_csv("data/production.csv")

# Detect drift
results = detector.detect_drift(
    reference_data=reference_data,
    production_data=production_data,
    feature_cols=["sales", "quantity", "discount"],
    categorical_cols=["category", "region"]
)

# Check results
for feature, result in results.items():
    if result["drift_detected"]:
        print(f"⚠️  Drift in {feature}: {result['drift_score']:.4f}")
    else:
        print(f"✅ No drift in {feature}")

# Get history
history = detector.get_drift_history(days=30, drift_only=True)
print(history)
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--alpha` | 0.05 | Significance level for statistical tests |
| `--psi-threshold` | 0.2 | PSI threshold (>0.2 = drift) |
| `--wasserstein-threshold` | 0.1 | Wasserstein distance threshold |
| `--feature-cols` | All numeric | List of continuous features |
| `--categorical-cols` | All object | List of categorical features |

### Output Format

```
📊 DRIFT DETECTION SUMMARY
================================================================================

✅ No drift: 2 features
   • sales: drift_score=0.0342
   • profit: drift_score=0.0521

⚠️  DRIFT DETECTED: 2 features

   • quantity:
     - Drift Score: 0.3251
     - ks_test: ⚠️  p=0.0012
     - psi: ⚠️  score=0.2834
     - wasserstein: ⚠️  distance=0.1523

   • discount:
     - Drift Score: 0.2891
     - ks_test: ⚠️  p=0.0034
     - psi: ⚠️  score=0.2891
     - wasserstein: ✅ distance=0.0823

================================================================================
```

### Database Schema

```sql
CREATE TABLE drift_records (
    id SERIAL PRIMARY KEY,
    check_timestamp TIMESTAMP NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    drift_detected BOOLEAN NOT NULL,
    drift_score FLOAT NOT NULL,
    test_statistic FLOAT,
    p_value FLOAT,
    test_method VARCHAR(50) NOT NULL,
    reference_mean FLOAT,
    reference_std FLOAT,
    production_mean FLOAT,
    production_std FLOAT,
    metadata JSON,
    alert_sent BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_drift_timestamp ON drift_records(check_timestamp);
CREATE INDEX idx_drift_feature ON drift_records(feature_name);
CREATE INDEX idx_drift_detected ON drift_records(drift_detected);
```

---

## 🔄 Script 2: Automated Retraining Scheduler

### Overview

Monitors multiple trigger conditions and initiates retraining when needed:

1. **Time-based:** Scheduled intervals (default: 7 days)
2. **Performance-based:** Model RMSE exceeds threshold (default: 55.0)
3. **Data-based:** Training data increased significantly (default: 20%)
4. **Drift-based:** Multiple features show drift (default: 3+ features)

### Command Line Usage

#### Check if Retraining Needed

```bash
# Check only (no action)
python scripts/production_ops/automated_retraining.py --check

# Exit code: 0 = not needed, 1 = needed
```

#### Trigger Retraining

```bash
# Check and trigger if needed
python scripts/production_ops/automated_retraining.py --trigger

# Dry run (test without triggering)
python scripts/production_ops/automated_retraining.py --trigger --dry-run
```

#### Custom Thresholds

```bash
python scripts/production_ops/automated_retraining.py \
  --check \
  --performance-threshold 55.0 \
  --data-growth-threshold 0.20 \
  --drift-threshold 3
```

#### View Retraining History

```bash
python scripts/production_ops/automated_retraining.py --history --days 30
```

### Python API Usage

```python
from production_ops.automated_retraining import RetrainingScheduler

# Initialize scheduler
scheduler = RetrainingScheduler(
    storage_url="postgresql://user:pass@host:5432/optuna",
    airflow_url="http://localhost:8080",
    performance_threshold=55.0,
    data_growth_threshold=0.20,
    drift_threshold=3
)

# Check if retraining needed
should_retrain, triggers = scheduler.check_retraining_needed()

if should_retrain:
    print(f"⚠️  Retraining needed! {len(triggers)} trigger(s):")
    for trigger in triggers:
        print(f"  • {trigger['reason']}: {trigger['details']}")
    
    # Trigger retraining
    dag_run_id = scheduler.trigger_retraining(
        triggers=triggers,
        dry_run=False
    )
    print(f"✅ Retraining triggered: {dag_run_id}")
else:
    print("✅ No retraining needed")

# Get history
history = scheduler.get_retraining_history(days=30)
print(history)
```

### Trigger Conditions Explained

#### 1. Time-Based Trigger

- **Default:** 7 days since last retraining
- **Configurable:** `RETRAINING_SCHEDULE_DAYS` env variable
- **Purpose:** Ensures models stay fresh even without other triggers

#### 2. Performance-Based Trigger

- **Default:** RMSE > 55.0
- **Source:** MLflow Model Registry or retraining history
- **Purpose:** Triggers when model degrades below acceptable threshold

#### 3. Data-Based Trigger

- **Default:** 20% data growth
- **Calculation:** Compares current training data size to size at last retraining
- **Purpose:** Triggers when significant new data is available

#### 4. Drift-Based Trigger

- **Default:** 3+ features with drift
- **Source:** Queries `drift_records` table for recent drift detections
- **Purpose:** Triggers when multiple features show distribution shift

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--performance-threshold` | 55.0 | RMSE threshold for performance trigger |
| `--data-growth-threshold` | 0.20 | Data growth % for data trigger (20%) |
| `--drift-threshold` | 3 | Min features with drift for drift trigger |
| `--dry-run` | False | Test mode (don't actually trigger DAG) |

### Output Format

```
🔍 Checking retraining triggers...

⚠️  Retraining needed! 2 trigger(s) fired:
   • time_based: 10 days since last retraining (threshold: 7)
   • drift_based: 4 features with drift (threshold: 3)

🚀 Triggering retraining DAG...
✅ DAG triggered successfully: retraining_20250103_145230
```

### Database Schema

```sql
CREATE TABLE retraining_records (
    id SERIAL PRIMARY KEY,
    trigger_timestamp TIMESTAMP NOT NULL,
    trigger_reason VARCHAR(50) NOT NULL,
    trigger_details JSON,
    dag_run_id VARCHAR(255),
    dag_triggered BOOLEAN DEFAULT FALSE,
    retraining_status VARCHAR(50) DEFAULT 'pending',
    model_version VARCHAR(100),
    performance_before FLOAT,
    performance_after FLOAT,
    completed_timestamp TIMESTAMP,
    metadata JSON
);

-- Indexes
CREATE INDEX idx_retraining_timestamp ON retraining_records(trigger_timestamp);
CREATE INDEX idx_retraining_reason ON retraining_records(trigger_reason);
```

---

## 🔗 Integration Examples

### Airflow DAG Integration

```python
# dags/ml_monitoring_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '/opt/airflow/scripts/production_ops')

from detect_data_drift import DriftDetector
from automated_retraining import RetrainingScheduler

def check_drift(**context):
    """Check for data drift."""
    detector = DriftDetector()
    
    # Load data
    import pandas as pd
    reference = pd.read_csv('/opt/airflow/data/reference.csv')
    production = pd.read_csv('/opt/airflow/data/production/latest.csv')
    
    # Detect drift
    results = detector.detect_drift(
        reference_data=reference,
        production_data=production
    )
    
    # Push to XCom
    drift_count = sum(1 for r in results.values() if r['drift_detected'])
    context['ti'].xcom_push(key='drift_count', value=drift_count)
    
    return drift_count

def check_retraining(**context):
    """Check if retraining needed and trigger if so."""
    scheduler = RetrainingScheduler()
    
    should_retrain, triggers = scheduler.check_retraining_needed()
    
    if should_retrain:
        dag_run_id = scheduler.trigger_retraining(triggers=triggers)
        print(f"✅ Retraining triggered: {dag_run_id}")
        return dag_run_id
    else:
        print("✅ No retraining needed")
        return None

default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'ml_monitoring',
    default_args=default_args,
    description='ML model monitoring and retraining',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ml', 'monitoring'],
) as dag:
    
    t1 = PythonOperator(
        task_id='check_drift',
        python_callable=check_drift,
        provide_context=True,
    )
    
    t2 = PythonOperator(
        task_id='check_retraining',
        python_callable=check_retraining,
        provide_context=True,
    )
    
    t1 >> t2
```

### Cron Job Integration

```bash
#!/bin/bash
# /etc/cron.d/ml-monitoring

# Daily drift check at 2 AM
0 2 * * * /usr/bin/python3 /opt/ml/scripts/production_ops/detect_data_drift.py \
    --reference-data /opt/ml/data/reference.csv \
    --production-data /opt/ml/data/production/latest.csv \
    --alert

# Daily retraining check at 3 AM
0 3 * * * /usr/bin/python3 /opt/ml/scripts/production_ops/automated_retraining.py \
    --trigger

# Weekly drift report on Monday at 9 AM
0 9 * * 1 /usr/bin/python3 /opt/ml/scripts/production_ops/detect_data_drift.py \
    --history --days 7 | mail -s "Weekly Drift Report" team@example.com
```

### Python Script Integration

```python
#!/usr/bin/env python3
"""
Daily ML monitoring script
"""
import sys
sys.path.insert(0, 'scripts/production_ops')

from detect_data_drift import DriftDetector
from automated_retraining import RetrainingScheduler
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # 1. Check for drift
    logger.info("Checking for data drift...")
    detector = DriftDetector()
    
    reference = pd.read_csv('data/reference.csv')
    production = pd.read_csv('data/production/latest.csv')
    
    results = detector.detect_drift(
        reference_data=reference,
        production_data=production
    )
    
    drift_count = sum(1 for r in results.values() if r['drift_detected'])
    logger.info(f"Drift detected in {drift_count} features")
    
    # 2. Check if retraining needed
    logger.info("Checking if retraining needed...")
    scheduler = RetrainingScheduler()
    
    should_retrain, triggers = scheduler.check_retraining_needed()
    
    if should_retrain:
        logger.warning(f"Retraining needed! {len(triggers)} triggers")
        
        # Trigger retraining
        dag_run_id = scheduler.trigger_retraining(triggers=triggers)
        logger.info(f"Retraining triggered: {dag_run_id}")
    else:
        logger.info("No retraining needed")

if __name__ == '__main__':
    main()
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
pytest tests/test_production_ops.py -v

# Specific test class
pytest tests/test_production_ops.py::TestDriftDetector -v
pytest tests/test_production_ops.py::TestRetrainingScheduler -v

# With coverage
pytest tests/test_production_ops.py --cov=scripts/production_ops --cov-report=html
```

### Test Coverage

- **DriftDetector:** 15 tests
- **RetrainingScheduler:** 12 tests
- **Integration:** 2 tests
- **Performance:** 1 test
- **Total:** 40+ tests

---

## 📊 Monitoring

### Key Metrics

```sql
-- Drift detection frequency
SELECT DATE(check_timestamp), COUNT(*)
FROM drift_records
GROUP BY DATE(check_timestamp)
ORDER BY DATE(check_timestamp) DESC
LIMIT 30;

-- Features with most drift
SELECT feature_name, COUNT(*) as drift_count
FROM drift_records
WHERE drift_detected = true
GROUP BY feature_name
ORDER BY drift_count DESC
LIMIT 10;

-- Retraining trigger distribution
SELECT trigger_reason, COUNT(*)
FROM retraining_records
GROUP BY trigger_reason;

-- Retraining success rate
SELECT 
    retraining_status,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM retraining_records
WHERE trigger_timestamp >= NOW() - INTERVAL '30 days'
GROUP BY retraining_status;
```

---

## 🔧 Troubleshooting

### Issue: "Could not connect to PostgreSQL"

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection string
echo $DRIFT_STORAGE_URL

# Test connection
psql $DRIFT_STORAGE_URL -c "SELECT 1"
```

### Issue: "Airflow DAG not triggering"

```bash
# Check Airflow is running
curl http://localhost:8080/health

# Check credentials
echo $AIRFLOW_USERNAME
echo $AIRFLOW_PASSWORD

# Test API manually
curl -X POST "http://localhost:8080/api/v1/dags/demand_forecasting_enhanced/dagRuns" \
  -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"dag_run_id": "test_123"}'
```

### Issue: "Drift always detected"

```bash
# Check thresholds
python scripts/production_ops/detect_data_drift.py \
  --reference-data ref.csv \
  --production-data prod.csv \
  --alpha 0.01 \
  --psi-threshold 0.25

# Check data distributions
python -c "
import pandas as pd
ref = pd.read_csv('ref.csv')
prod = pd.read_csv('prod.csv')
print(ref.describe())
print(prod.describe())
"
```

---

## 📚 Additional Resources

### Documentation

- **PostgreSQL Optimization Guide:** `docs/POSTGRESQL_OPTIMIZATION_GUIDE.md`
- **Final Implementation Status:** `docs/FINAL_IMPLEMENTATION_STATUS.md`
- **Advanced Features Guide:** `docs/ADVANCED_FEATURES_GUIDE.md`

### Related Scripts

- **Monitor Optuna:** `scripts/advanced_features/monitor_parallel_optimization.py`
- **Promote Model:** `scripts/advanced_features/promote_model_to_production.py`
- **Analyze Study:** `scripts/advanced_features/analyze_study.py`

---

## 🎯 Best Practices

### 1. Regular Drift Checks

```bash
# Run daily at minimum
0 2 * * * python scripts/production_ops/detect_data_drift.py ...
```

### 2. Monitor Drift History

```bash
# Weekly reports
python scripts/production_ops/detect_data_drift.py --history --days 7
```

### 3. Test Before Production

```bash
# Always use dry-run first
python scripts/production_ops/automated_retraining.py --trigger --dry-run
```

### 4. Configure Thresholds

```bash
# Adjust based on your data
--alpha 0.01              # More strict
--psi-threshold 0.15      # More sensitive
--drift-threshold 5       # Less sensitive
```

### 5. Backup Before Retraining

```bash
# Save current model before triggering
aws s3 cp s3://bucket/models/current.pkl s3://bucket/models/backup/
python scripts/production_ops/automated_retraining.py --trigger
```

---

## 📞 Support

**Questions or Issues?**
- Documentation: `docs/FINAL_IMPLEMENTATION_STATUS.md`
- Tests: `tests/test_production_ops.py`
- Email: cnyagakan@gmail.com

---

**Version:** 3.0.0  
**Last Updated:** January 2025  
**Status:** ✅ Production Ready