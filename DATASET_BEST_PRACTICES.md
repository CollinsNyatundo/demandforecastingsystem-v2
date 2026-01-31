# Dataset Best Practices Guide - Demand Forecasting System

**Last Updated:** December 31, 2025  
**Status:** Production Guidelines  
**Contact:** cnyagakan@gmail.com

---

## Table of Contents

1. [Overview](#overview)
2. [URI Naming Conventions](#uri-naming-conventions)
3. [Dataset Documentation](#dataset-documentation)
4. [Versioning Strategy](#versioning-strategy)
5. [Monitoring & Alerting](#monitoring--alerting)
6. [Data-Driven DAGs](#data-driven-dags)
7. [Quality Checks](#quality-checks)
8. [Implementation Examples](#implementation-examples)
9. [Common Anti-Patterns](#common-anti-patterns)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Airflow Datasets enable data-aware orchestration, allowing DAGs to trigger based on data availability rather than time schedules. Following these best practices ensures maintainable, reliable, and observable data pipelines.

### Key Principles

1. **Meaningful URIs** - Use descriptive, domain-specific naming
2. **Stable URIs** - Version data content, not URIs
3. **Comprehensive Documentation** - Document purpose, schema, and lineage
4. **Active Monitoring** - Track freshness and quality metrics
5. **Event-Driven Architecture** - Prefer data triggers over time schedules

---

## URI Naming Conventions

### ✅ Best Practice: Domain/Stage/Purpose Structure

```python
# Good: Descriptive with clear purpose
Dataset("s3://bucket-name/domain/stage/purpose.format")

# Examples from our pipeline:
Dataset("s3://demand-forecasting/01_raw/raw_data_full.parquet")
Dataset("s3://demand-forecasting/02_intermediate/preprocessed_data.parquet")
Dataset("s3://demand-forecasting/03_primary/model_input.parquet")
Dataset("s3://demand-forecasting/06_models/regressor.pickle")
```

### ❌ Anti-Pattern: Generic Names

```python
# Bad: Non-descriptive
Dataset("s3://bucket/data.parquet")
Dataset("s3://bucket/output.csv")
Dataset("s3://bucket/file123.json")
```

### URI Structure Guidelines

**Format:** `s3://bucket/domain/stage/descriptive-name.format`

- **bucket:** Project or team bucket name
- **domain:** Business domain (e.g., demand-forecasting, inventory, sales)
- **stage:** Data processing stage (raw, intermediate, primary, models)
- **descriptive-name:** Clear indication of content
- **format:** File extension (parquet, csv, json, pickle)

### Staging Conventions

| Stage | Purpose | Example |
|-------|---------|---------|
| `01_raw` | Unprocessed source data | `raw_data_full.parquet` |
| `02_intermediate` | Cleaned/validated data | `preprocessed_data.parquet` |
| `03_primary` | Feature-engineered data | `model_input.parquet` |
| `04_feature` | Feature store outputs | `feature_vector.parquet` |
| `05_model_input` | ML-ready datasets | `training_data.parquet` |
| `06_models` | Trained model artifacts | `regressor.pickle` |
| `07_model_output` | Predictions | `predictions.parquet` |
| `08_reporting` | Business reports | `dashboard_data.parquet` |

---

## Dataset Documentation

### ✅ Best Practice: Comprehensive Inline Documentation

```python
# ==============================================================================
# Dataset Declarations - Demand Forecasting Pipeline
# ==============================================================================

# INPUT DATASET (DAG Trigger)
# Purpose: Raw bike demand data from external API
# Update Frequency: Daily at 6 AM UTC
# Schema: 
#   - dteday (date): Date of observation
#   - season (int): Season (1=spring, 2=summer, 3=fall, 4=winter)
#   - yr (int): Year (0=2011, 1=2012)
#   - mnth (int): Month (1-12)
#   - holiday (int): Whether day is holiday (0=no, 1=yes)
#   - weekday (int): Day of week (0-6)
#   - workingday (int): Whether day is working day (0=no, 1=yes)
#   - weathersit (int): Weather situation (1-4, 1=best, 4=worst)
#   - temp (float): Normalized temperature (0-1)
#   - atemp (float): Normalized feeling temperature (0-1)
#   - hum (float): Normalized humidity (0-1)
#   - windspeed (float): Normalized wind speed (0-1)
#   - cnt (int): Count of total bike rentals (target variable)
# Consumer: demand_forecasting_custom DAG (triggers on update)
# Producer: External data ingestion system
# Quality: Must have <50% missing values, >1000 rows
RAW_DATA_DATASET = Dataset("s3://demand-forecasting/01_raw/raw_data_full.parquet")

# INTERMEDIATE DATASET (Preprocessing Output)
# Purpose: Cleaned data after quality validation
# Producer: t_preprocess task
# Consumer: t_feature_eng task
# Transformations:
#   - Missing value imputation (mean for numeric, mode for categorical)
#   - Outlier capping (3-sigma rule)
#   - Type corrections (ensure int/float consistency)
# Quality: No missing values, all columns validated
PREPROCESSED_DATA_DATASET = Dataset(
    "s3://demand-forecasting/02_intermediate/preprocessed_data.parquet"
)
```

### Documentation Template

Use this template for all dataset declarations:

```python
# DATASET NAME (Role in Pipeline)
# Purpose: [What this dataset contains and why it exists]
# Producer: [Task or system that creates this dataset]
# Consumer: [Tasks or DAGs that use this dataset]
# Update Frequency: [How often this updates]
# Schema: [Key columns and their meanings]
# Transformations: [What processing has been applied]
# Quality Requirements: [Validation rules that must pass]
# Size: [Approximate size range]
# Retention: [How long to keep historical versions]
DATASET_NAME = Dataset("s3://bucket/domain/stage/name.format")
```

---

## Versioning Strategy

### ✅ Best Practice: Version Data Content, Not URIs

**Keep URIs Stable:**
```python
# Good: Stable URI, version inside data
Dataset("s3://demand-forecasting/03_primary/model_input.parquet")

# Data file contains version metadata:
# - schema_version: "2.1"
# - created_at: "2025-12-31T10:00:00Z"
# - data_version: "v20251231"
```

**Version Inside Files:**
```python
import pandas as pd
from datetime import datetime

def save_versioned_data(df, path):
    """Save data with embedded version metadata"""
    # Add metadata columns
    df['_data_version'] = 'v20251231'
    df['_schema_version'] = '2.1'
    df['_created_at'] = datetime.utcnow().isoformat()
    
    # Save to stable path
    df.to_parquet(path, index=False)
    
    return path
```

### ❌ Anti-Pattern: Versions in URIs

```python
# Bad: URI changes with each version
Dataset("s3://bucket/data_v1.parquet")
Dataset("s3://bucket/data_v2.parquet")
Dataset("s3://bucket/data_20251231.parquet")

# Problems:
# - Breaks downstream DAGs when version changes
# - Creates URI sprawl in Airflow metadata
# - Loses automatic lineage tracking
# - Requires code changes for each version
```

### Schema Evolution

When schema must change:

1. **Backward Compatible:** Add columns, don't remove
2. **Version Field:** Include `schema_version` in data
3. **Migration DAG:** Create separate DAG for schema migrations
4. **Documentation:** Update dataset comments with schema changes

```python
# Schema evolution example
def preprocess_with_schema_version(df):
    """Handle multiple schema versions"""
    # Detect schema version
    if 'schema_version' in df.columns:
        version = df['schema_version'].iloc[0]
    else:
        version = '1.0'  # Legacy data
    
    # Apply version-specific transformations
    if version == '1.0':
        # Add new columns for v2.0
        df['new_feature'] = 0
        df['schema_version'] = '2.0'
    
    return df
```

---

## Monitoring & Alerting

### ✅ Best Practice: Automated Freshness Monitoring

**Implement Monitoring DAG:**

```python
from demand_forecasting.utils import DatasetMonitor, check_freshness

@dag(schedule="@hourly")
def dataset_monitoring():
    @task()
    def check_all_datasets():
        """Check freshness of all datasets"""
        datasets = {
            'raw_data': {
                'uri': 's3://demand-forecasting/01_raw/raw_data_full.parquet',
                'max_age_hours': 24,
                'critical': True
            },
            'model': {
                'uri': 's3://demand-forecasting/06_models/regressor.pickle',
                'max_age_hours': 48,
                'critical': True
            }
        }
        
        monitor = DatasetMonitor()
        stale_datasets = []
        
        for name, config in datasets.items():
            is_fresh, hours_old = monitor.check_dataset_freshness(
                config['uri'], 
                config['max_age_hours']
            )
            
            if not is_fresh and config['critical']:
                stale_datasets.append({
                    'name': name,
                    'hours_old': hours_old,
                    'threshold': config['max_age_hours']
                })
        
        return stale_datasets
    
    @task()
    def alert_if_stale(stale_datasets):
        """Send alerts for stale datasets"""
        if stale_datasets:
            send_email(
                to=['cnyagakan@gmail.com'],
                subject='[ALERT] Stale Datasets Detected',
                html_content=f'<h3>Stale datasets: {len(stale_datasets)}</h3>'
            )
```

### Monitoring Checklist

- [ ] Freshness checks (hourly)
- [ ] Quality metrics tracking (per run)
- [ ] Email alerts for critical datasets
- [ ] Daily freshness reports
- [ ] Historical metrics export (CSV)
- [ ] Dashboard for dataset health

### Alert Thresholds

| Dataset Type | Max Age | Alert Level |
|--------------|---------|-------------|
| Raw data | 24 hours | Critical |
| Processed data | 24 hours | Warning |
| Models | 48 hours | Critical |
| Predictions | 2 hours | Critical |
| Reports | 24 hours | Warning |

---

## Data-Driven DAGs

### ✅ Best Practice: Dataset-Triggered DAGs

**Instead of time-based:**
```python
# Bad: Time-based schedule
@dag(schedule="@daily")  # Runs even if no new data
def ml_pipeline():
    ...
```

**Use dataset triggers:**
```python
# Good: Data-driven schedule
from airflow.datasets import Dataset

RAW_DATA = Dataset("s3://demand-forecasting/01_raw/raw_data_full.parquet")

@dag(schedule=[RAW_DATA])  # Runs when data arrives
def ml_pipeline():
    ...
```

### Multi-Dataset Dependencies

```python
# Trigger when multiple datasets are ready
RAW_DATA = Dataset("s3://bucket/raw/data.parquet")
FEATURES = Dataset("s3://bucket/features/features.parquet")

@dag(schedule=[RAW_DATA, FEATURES])  # AND condition
def training_pipeline():
    """Runs when BOTH datasets are updated"""
    ...
```

### Producer-Consumer Pattern

```python
# Producer DAG
@dag(schedule="@daily")
def data_ingestion():
    @task(outlets=[RAW_DATA])  # Marks dataset as updated
    def ingest():
        # Download and save data
        df = fetch_data()
        df.to_parquet("s3://bucket/raw/data.parquet")
        return "Success"

# Consumer DAG (triggers automatically)
@dag(schedule=[RAW_DATA])
def ml_pipeline():
    @task()
    def train():
        df = pd.read_parquet("s3://bucket/raw/data.parquet")
        # Train model
        ...
```

---

## Quality Checks

### ✅ Best Practice: Validate Before and After

**Pre-Processing Validation:**
```python
@task()
def validate_raw_data():
    """Validate raw data quality before processing"""
    df = load_data("s3://bucket/raw/data.parquet")
    
    # Check 1: Not empty
    assert len(df) > 0, "Dataset is empty"
    
    # Check 2: Missing values threshold
    missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns))
    assert missing_pct < 0.5, f"Too many missing values: {missing_pct:.2%}"
    
    # Check 3: Expected columns present
    required_cols = ['date', 'value', 'category']
    missing_cols = set(required_cols) - set(df.columns)
    assert not missing_cols, f"Missing columns: {missing_cols}"
    
    # Check 4: Data types
    assert pd.api.types.is_datetime64_any_dtype(df['date']), "date column must be datetime"
    
    # Check 5: Value ranges
    assert df['value'].min() >= 0, "Negative values found"
    
    return {"rows": len(df), "columns": len(df.columns), "validation": "passed"}
```

**Post-Processing Validation:**
```python
@task(outlets=[PROCESSED_DATA])
def process_and_validate():
    """Process data and validate output quality"""
    df = transform_data()
    
    # Validate output
    assert len(df) > 0, "Processing resulted in empty dataset"
    assert df.isnull().sum().sum() == 0, "Processed data has missing values"
    
    # Log metrics
    monitor = DatasetMonitor()
    monitor.log_dataset_metrics(
        dataset_uri="s3://bucket/processed/data.parquet",
        metrics={
            "rows": len(df),
            "columns": len(df.columns),
            "missing_pct": 0,
            "processing_time": "2.5s"
        }
    )
    
    # Save
    df.to_parquet("s3://bucket/processed/data.parquet")
    return "Success"
```

### Great Expectations Integration

```python
import great_expectations as gx

@task()
def validate_with_ge():
    """Use Great Expectations for comprehensive validation"""
    context = gx.get_context()
    
    # Load data
    df = pd.read_parquet("s3://bucket/data.parquet")
    
    # Create expectations
    batch = context.sources.add_or_update_pandas("my_source").read_dataframe(df)
    
    # Define expectations
    batch.expect_table_row_count_to_be_between(min_value=1000, max_value=1000000)
    batch.expect_column_values_to_not_be_null("id")
    batch.expect_column_values_to_be_between("value", min_value=0, max_value=100)
    batch.expect_column_values_to_be_in_set("category", ["A", "B", "C"])
    
    # Validate
    results = batch.validate()
    
    if not results.success:
        raise ValueError(f"Validation failed: {results}")
    
    return "Validation passed"
```

---

## Implementation Examples

### Example 1: Complete Dataset-Driven Pipeline

```python
from airflow.datasets import Dataset
from airflow.decorators import dag, task
import pendulum

# Dataset definitions
RAW_DATA = Dataset("s3://demand-forecasting/01_raw/data.parquet")
CLEAN_DATA = Dataset("s3://demand-forecasting/02_intermediate/clean.parquet")
MODEL = Dataset("s3://demand-forecasting/06_models/model.pickle")

# DAG 1: Data Ingestion (runs daily)
@dag(schedule="@daily", catchup=False)
def data_ingestion():
    @task(outlets=[RAW_DATA])
    def fetch_and_save():
        """Fetch data from API and save to S3"""
        data = fetch_from_api()
        save_to_s3(data, "s3://demand-forecasting/01_raw/data.parquet")
        
        # Log update
        from demand_forecasting.utils import log_update
        log_update(
            dataset_uri=str(RAW_DATA),
            task_id="fetch_and_save",
            dag_id="data_ingestion",
            run_id=get_current_context()['run_id'],
            metadata={"rows": len(data), "source": "api"}
        )
        return "Data ingested"

# DAG 2: Preprocessing (triggers on raw data update)
@dag(schedule=[RAW_DATA], catchup=False)
def preprocessing():
    @task(outlets=[CLEAN_DATA])
    def clean():
        """Clean and validate data"""
        df = pd.read_parquet("s3://demand-forecasting/01_raw/data.parquet")
        df_clean = clean_data(df)
        df_clean.to_parquet("s3://demand-forecasting/02_intermediate/clean.parquet")
        return "Data cleaned"

# DAG 3: Training (triggers on clean data update)
@dag(schedule=[CLEAN_DATA], catchup=False)
def model_training():
    @task(outlets=[MODEL])
    def train():
        """Train ML model"""
        df = pd.read_parquet("s3://demand-forecasting/02_intermediate/clean.parquet")
        model = train_model(df)
        save_model(model, "s3://demand-forecasting/06_models/model.pickle")
        return "Model trained"
```

### Example 2: Dataset Monitoring with Alerts

```python
@dag(schedule="@hourly", catchup=False)
def dataset_health_check():
    @task()
    def check_freshness():
        """Check all datasets for staleness"""
        from demand_forecasting.utils import get_stale_datasets
        
        stale = get_stale_datasets(max_age_hours=24)
        return stale
    
    @task()
    def alert_ops(stale_datasets):
        """Alert operations team if any dataset is stale"""
        if stale_datasets:
            send_email(
                to=['ops@company.com'],
                subject=f'[ALERT] {len(stale_datasets)} Stale Dataset(s)',
                html_content=format_alert(stale_datasets)
            )
```

### Example 3: Dataset Metrics Tracking

```python
@task(outlets=[OUTPUT_DATASET])
def process_with_metrics():
    """Process data and track quality metrics"""
    from demand_forecasting.utils import DatasetMonitor
    
    # Load and process
    df = load_data()
    df_processed = process_data(df)
    
    # Calculate metrics
    metrics = {
        "rows": len(df_processed),
        "columns": len(df_processed.columns),
        "missing_pct": df_processed.isnull().sum().sum() / df_processed.size * 100,
        "duplicate_rows": df_processed.duplicated().sum(),
        "memory_mb": df_processed.memory_usage(deep=True).sum() / 1024**2,
    }
    
    # Log metrics
    monitor = DatasetMonitor()
    monitor.log_dataset_metrics(
        dataset_uri=str(OUTPUT_DATASET),
        metrics=metrics,
        task_id=get_current_context()['task_instance'].task_id,
        dag_id=get_current_context()['dag'].dag_id
    )
    
    # Save
    save_data(df_processed)
    
    return metrics
```

---

## Common Anti-Patterns

### ❌ Anti-Pattern 1: Changing URIs

```python
# Bad: URI changes frequently
Dataset(f"s3://bucket/data_{datetime.now().strftime('%Y%m%d')}.parquet")
# Problem: Creates new dataset every day, breaks lineage

# Good: Stable URI
Dataset("s3://bucket/data.parquet")
# Version info inside the file
```

### ❌ Anti-Pattern 2: No Documentation

```python
# Bad: No context
DATASET_A = Dataset("s3://bucket/data.parquet")

# Good: Clear documentation
# RAW CUSTOMER DATA
# Purpose: Daily customer transaction records from payment API
# Schema: customer_id, transaction_date, amount, product_id
# Update: Daily at 2 AM UTC
CUSTOMER_TRANSACTIONS = Dataset("s3://bucket/customers/raw_transactions.parquet")
```

### ❌ Anti-Pattern 3: No Monitoring

```python
# Bad: Fire and forget
@task(outlets=[DATASET])
def process():
    df = transform()
    save(df)
    return "Done"

# Good: Monitor and alert
@task(outlets=[DATASET])
def process():
    df = transform()
    
    # Validate
    assert len(df) > 0, "Empty result"
    
    # Log metrics
    monitor.log_dataset_metrics(DATASET, {"rows": len(df)})
    
    # Check freshness of upstream
    assert check_freshness(UPSTREAM_DATASET), "Upstream data stale"
    
    save(df)
    return "Done"
```

### ❌ Anti-Pattern 4: Mixing Time and Data Triggers

```python
# Bad: Confusing mix
@dag(schedule="@daily")  # Time-based
def pipeline():
    @task(outlets=[DATASET])  # But produces dataset
    def process():
        ...

# Good: Pick one strategy
# Option 1: Pure time-based (legacy systems)
@dag(schedule="@daily")
def pipeline():
    ...

# Option 2: Pure data-driven (recommended)
@dag(schedule=[INPUT_DATASET])
def pipeline():
    @task(outlets=[OUTPUT_DATASET])
    def process():
        ...
```

---

## Troubleshooting

### Issue: Dataset Not Triggering DAG

**Symptoms:**
- Dataset is updated but consumer DAG doesn't trigger
- `dag_run_dataset_queue` table is empty

**Solutions:**

1. **Verify dataset URI matches exactly:**
```python
# In producer DAG
outlets=[Dataset("s3://bucket/data.parquet")]

# In consumer DAG  
schedule=[Dataset("s3://bucket/data.parquet")]  # Must match exactly!
```

2. **Check task completed successfully:**
```sql
SELECT * FROM task_instance 
WHERE task_id = 'producer_task' 
AND state = 'success'
ORDER BY execution_date DESC LIMIT 5;
```

3. **Verify dataset event created:**
```sql
SELECT * FROM dataset_event 
WHERE dataset_id = (SELECT id FROM dataset WHERE uri = 's3://bucket/data.parquet')
ORDER BY timestamp DESC LIMIT 5;
```

4. **Check DAG schedule reference:**
```sql
SELECT d.dag_id, ds.uri 
FROM dag_schedule_dataset_reference dsr
JOIN dataset ds ON dsr.dataset_id = ds.id;
```

### Issue: Dataset Not Showing in UI

**Symptoms:**
- Dataset registered in DB but not visible in Airflow UI

**Solutions:**

1. **Refresh DAG:**
```bash
docker-compose exec airflow-scheduler airflow dags reserialize demand_forecasting_custom
```

2. **Check for DAG errors:**
```bash
python /opt/airflow/dags/your_dag.py
```

3. **Restart scheduler:**
```bash
docker-compose restart airflow-scheduler
```

4. **Clear browser cache** (Ctrl+Shift+R)

### Issue: Stale Data Not Alerting

**Symptoms:**
- Dataset is old but no alerts received

**Solutions:**

1. **Verify monitoring DAG is running:**
```bash
docker-compose exec airflow-scheduler airflow dags list-runs -d dataset_monitoring
```

2. **Check email configuration:**
```bash
# Test email
docker-compose exec airflow-scheduler python -c "
from airflow.utils.email import send_email
send_email(to=['your@email.com'], subject='Test', html_content='Test')
"
```

3. **Verify freshness thresholds are appropriate:**
```python
# Check actual dataset age
monitor = DatasetMonitor()
stats = monitor.get_dataset_statistics("s3://bucket/data.parquet")
print(stats)
```

---

## Quick Reference

### Essential Commands

```bash
# List all datasets in database
docker-compose exec postgres psql -U airflow -c "SELECT id, uri FROM dataset;"

# Check dataset events
docker-compose exec postgres psql -U airflow -c "SELECT * FROM dataset_event ORDER BY timestamp DESC LIMIT 10;"

# Check dataset freshness
docker-compose exec airflow-scheduler python -c "
from demand_forecasting.utils import check_freshness
print(check_freshness('s3://bucket/data.parquet', max_age_hours=24))
"

# Generate freshness report
docker-compose exec airflow-scheduler python -c "
from demand_forecasting.utils import DatasetMonitor
monitor = DatasetMonitor()
print(monitor.generate_freshness_report(24))
"

# Export metrics to CSV
docker-compose exec airflow-scheduler python -c "
from demand_forecasting.utils import DatasetMonitor
monitor = DatasetMonitor()
monitor.export_metrics_to_csv('/tmp/metrics.csv')
"
```

### Python API Examples

```python
# Import utilities
from demand_forecasting.utils import (
    DatasetMonitor,
    check_freshness,
    log_update,
    get_stale_datasets
)

# Check if dataset is fresh
is_fresh = check_freshness('s3://bucket/data.parquet', max_age_hours=24)

# Log dataset update
log_update(
    dataset_uri='s3://bucket/data.parquet',
    task_id='my_task',
    dag_id='my_dag',
    run_id='manual__2025-12-31',
    metadata={'rows': 1000}
)

# Get stale datasets
stale = get_stale_datasets(max_age_hours=24)
for ds in stale:
    print(f"{ds['dataset_uri']}: {ds['hours_since_update']}h old")

# Monitor datasets
monitor = DatasetMonitor()
stats = monitor.get_dataset_statistics('s3://bucket/data.parquet')
report = monitor.generate_freshness_report(24)
```

---

## Summary Checklist

Use this checklist for every new dataset:

- [ ] **URI follows naming convention** (domain/stage/purpose)
- [ ] **Comprehensive documentation** added as comments
- [ ] **Version strategy** defined (version inside data)
- [ ] **Producer task** declares dataset in `outlets`
- [ ] **Consumer DAG/task** references dataset in `schedule` or reads it
- [ ] **Quality validation** added (pre and post processing)
- [ ] **Monitoring** configured (freshness checks, alerts)
- [ ] **Metrics tracking** implemented (rows, quality, size)
- [ ] **Alert thresholds** defined and documented
- [ ] **Tested** dataset triggers DAG correctly

---

## Additional Resources

- **Airflow Datasets Documentation:** https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/datasets.html
- **Our Implementation:**
  - `DATASET_REGISTRATION_COMPLETE.md` - Dataset registration details
  - `app-ml/dags/airflow_dag.py` - Main DAG with datasets
  - `app-ml/dags/dataset_monitoring_dag.py` - Monitoring implementation
  - `app-ml/src/demand_forecasting/utils/dataset_monitor.py` - Monitoring utility
- **Contact:** cnyagakan@gmail.com

---

**Document Version:** 1.0  
**Last Reviewed:** December 31, 2025  
**Next Review:** March 31, 2026