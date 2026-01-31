# Advanced Features Scripts

**Version:** 2.1.0  
**Last Updated:** January 3, 2025  
**Status:** Production Ready

---

## 📋 Overview

This directory contains production-ready scripts for advanced ML operations:
- **Parallel Optuna Optimization** - Monitor distributed optimization across workers
- **MLflow Model Promotion** - Promote models to production with validation
- **Study Analysis** - Analyze, visualize, and manage Optuna studies
- **Custom Metrics** - Track domain-specific KPIs in MLflow

---

## 📁 Scripts Overview

### 1. `monitor_parallel_optimization.py`

**Purpose:** Real-time monitoring of distributed Optuna optimization

**Features:**
- Live progress tracking (trials, RMSE, throughput)
- Multi-worker coordination monitoring
- Beautiful terminal UI with progress bars
- Automatic statistics calculation

**Usage:**
```bash
# Basic monitoring
python scripts/advanced_features/monitor_parallel_optimization.py

# Custom study and update interval
python scripts/advanced_features/monitor_parallel_optimization.py \
  --study-name my_study \
  --interval 2

# Monitor for 5 minutes then show summary
python scripts/advanced_features/monitor_parallel_optimization.py \
  --duration 300

# Just show summary (no monitoring)
python scripts/advanced_features/monitor_parallel_optimization.py --summary
```

**Output Example:**
```
[14:32:15] Study: demand_forecasting_study

Progress: [████████████░░░░░░░░░░░░░░░░░░] 42.0%

Trials:    Total:  150  |  Completed:   63  |  Running:  5
Status:    Failed:   0  |  Pruned:      2  |  Waiting:  0

Best RMSE: 51.2341  (Trial #42)
Throughput: 18.75 trials/min

Best Parameters:
  learning_rate: 0.0524
  depth: 6
  l2_leaf_reg: 2.3451
```

---

### 2. `promote_model_to_production.py`

**Purpose:** Promote ML models to production with validation and approval

**Features:**
- Automatic validation (RMSE threshold, improvement check)
- Side-by-side model comparison
- Approval workflow with user confirmation
- Dry-run mode for testing
- Archive old production versions

**Usage:**
```bash
# Promote latest model (with validation)
python scripts/advanced_features/promote_model_to_production.py

# Promote specific version
python scripts/advanced_features/promote_model_to_production.py --version 5

# Skip validation (force promotion)
python scripts/advanced_features/promote_model_to_production.py --force

# Dry run (show what would happen)
python scripts/advanced_features/promote_model_to_production.py --dry-run

# Auto-approve (no confirmation prompt)
python scripts/advanced_features/promote_model_to_production.py --auto-approve

# Custom thresholds
python scripts/advanced_features/promote_model_to_production.py \
  --rmse-threshold 53.0 \
  --improvement-threshold 0.5
```

**Validation Checks:**
1. **Absolute Threshold:** RMSE must be ≤ 52.0 (configurable)
2. **Improvement Threshold:** Must be ≥1.0% better than current production (configurable)
3. **Metrics Available:** Model must have tracked metrics

**Output Example:**
```
================================================================================
MODEL COMPARISON
================================================================================

📦 Candidate Model (Version 8):
   Run ID: abc123def456
   RMSE: 51.2341
   MAE: 30.1234
   MAPE: 22.15%
   Training Time: 1234.56s
   Model Size: 12.34 MB

🏭 Current Production Model (Version 5):
   Run ID: xyz789uvw012
   RMSE: 52.1234
   MAE: 31.5678
   MAPE: 23.45%

📊 Improvements:
   RMSE: +1.71%
   MAE: +4.58%

================================================================================

🔍 Validating candidate model...
✅ Validation passed: All validation checks passed

❓ Promote demand_forecasting_catboost v8 to Production?
   Type 'yes' to confirm: yes

✅ Successfully promoted demand_forecasting_catboost v8 to Production
   Existing production versions archived

🎉 Model promotion complete!

   Model: demand_forecasting_catboost
   Version: 8
   Stage: Production

   Load with:
   model = mlflow.pyfunc.load_model('models:/demand_forecasting_catboost/Production')
```

---

### 3. `analyze_study.py`

**Purpose:** Comprehensive Optuna study analysis and management

**Features:**
- Statistical analysis (mean, std, min, max, median)
- Interactive visualizations (optimization history, parameter importance)
- CSV export for external analysis
- Multi-study comparison
- Failed trial cleanup
- Study listing

**Usage:**
```bash
# Analyze study and show summary
python scripts/advanced_features/analyze_study.py

# Create visualizations
python scripts/advanced_features/analyze_study.py --visualize

# Visualizations saved to custom directory
python scripts/advanced_features/analyze_study.py \
  --visualize \
  --output-dir ./my_analysis

# Export to CSV
python scripts/advanced_features/analyze_study.py \
  --export study_data.csv

# Clean up failed trials (dry run first!)
python scripts/advanced_features/analyze_study.py \
  --cleanup-failed \
  --dry-run

# Compare multiple studies
python scripts/advanced_features/analyze_study.py \
  --compare study1 study2 study3

# List all available studies
python scripts/advanced_features/analyze_study.py --list-studies
```

**Generated Visualizations:**
1. `optimization_history.html` - Trial RMSE and best RMSE over time
2. `param_importance.html` - Which parameters matter most
3. `parallel_coordinate.html` - Parameter relationships
4. `duration_analysis.html` - Trial duration trends
5. `study_comparison.html` - Multi-study comparison (when using --compare)

**Output Example:**
```
================================================================================
STUDY SUMMARY
================================================================================

Study Name: demand_forecasting_study
Direction: MINIMIZE
Sampler: TPESampler

Trial Statistics:
  Total Trials: 150
  Completed: 145
  Running: 0
  Failed: 3
  Pruned: 2

Best Trial:
  Trial #42
  Value (RMSE): 51.234567
  Parameters:
    learning_rate: 0.052341
    depth: 6
    l2_leaf_reg: 2.345678

Value Statistics:
  Mean: 53.456789
  Std: 1.234567
  Min: 51.234567
  Max: 58.901234
  Median: 53.123456

Duration Statistics:
  Mean: 82.34 seconds
  Min: 45.67 seconds
  Max: 120.45 seconds

================================================================================
```

---

## 🔧 Configuration

### Environment Variables

All scripts support these environment variables:

```bash
# Optuna Configuration
export OPTUNA_STORAGE_URL="postgresql://airflow:airflow@localhost:5432/optuna"
export OPTUNA_STUDY_NAME="demand_forecasting_study"

# MLflow Configuration
export MLFLOW_TRACKING_URI="http://localhost:5000"
export MLFLOW_MODEL_NAME="demand_forecasting_catboost"
```

### Connection Pooling (PostgreSQL)

Scripts use optimized connection pooling:
```python
engine_kwargs={
    "pool_size": 5,          # Keep 5 connections ready
    "max_overflow": 10,      # Allow up to 15 total connections
    "pool_pre_ping": True,   # Check connections before use
    "pool_recycle": 3600,    # Recycle connections after 1 hour
}
```

This ensures efficient resource usage with multiple workers.

---

## 🚀 Quick Start Guide

### Step 1: Install Dependencies

```bash
pip install optuna psycopg2-binary mlflow pandas plotly
```

### Step 2: Set Environment Variables

```bash
export OPTUNA_STORAGE_URL="postgresql://airflow:airflow@localhost:5432/optuna"
export MLFLOW_TRACKING_URI="http://localhost:5000"
```

### Step 3: Run Scripts

```bash
# Monitor optimization
python scripts/advanced_features/monitor_parallel_optimization.py

# In another terminal, promote best model
python scripts/advanced_features/promote_model_to_production.py

# Analyze study and create visualizations
python scripts/advanced_features/analyze_study.py --visualize
```

---

## 📊 Common Workflows

### Workflow 1: Monitor Training → Promote Model

```bash
# 1. Start monitoring in one terminal
python scripts/advanced_features/monitor_parallel_optimization.py

# 2. Wait for training to complete

# 3. In another terminal, analyze study
python scripts/advanced_features/analyze_study.py --visualize

# 4. Promote best model to production
python scripts/advanced_features/promote_model_to_production.py
```

### Workflow 2: Compare Multiple Training Runs

```bash
# 1. Export each study to CSV
python scripts/advanced_features/analyze_study.py \
  --study-name study_v1 \
  --export study_v1.csv

python scripts/advanced_features/analyze_study.py \
  --study-name study_v2 \
  --export study_v2.csv

# 2. Create comparison visualization
python scripts/advanced_features/analyze_study.py \
  --compare study_v1 study_v2 study_v3
```

### Workflow 3: Cleanup and Maintenance

```bash
# 1. List all studies
python scripts/advanced_features/analyze_study.py --list-studies

# 2. Analyze specific study
python scripts/advanced_features/analyze_study.py \
  --study-name old_study

# 3. Clean up failed trials (dry run first!)
python scripts/advanced_features/analyze_study.py \
  --study-name old_study \
  --cleanup-failed \
  --dry-run

# 4. Export data before cleanup
python scripts/advanced_features/analyze_study.py \
  --study-name old_study \
  --export old_study_backup.csv
```

---

## 🎓 Advanced Usage

### Parallel Monitoring with Custom Display

```bash
# Monitor with 2-second updates for 30 minutes
python scripts/advanced_features/monitor_parallel_optimization.py \
  --interval 2 \
  --duration 1800 \
  > optimization_log.txt
```

### Automated Model Promotion (CI/CD)

```bash
# For use in automated pipelines
python scripts/advanced_features/promote_model_to_production.py \
  --auto-approve \
  --rmse-threshold 52.0 \
  --improvement-threshold 1.0 \
  || echo "Model promotion failed validation"
```

### Batch Study Analysis

```bash
# Analyze and visualize all studies
for study in $(python scripts/advanced_features/analyze_study.py --list-studies | grep "📚" | awk '{print $2}'); do
  echo "Analyzing $study..."
  python scripts/advanced_features/analyze_study.py \
    --study-name "$study" \
    --visualize \
    --output-dir "./analysis/$study"
done
```

---

## 🔍 Troubleshooting

### Issue: "Connection refused" to PostgreSQL

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql -h localhost -p 5432 -U airflow -d optuna -c "SELECT 1;"

# Check database exists
psql -h localhost -p 5432 -U airflow -l | grep optuna
```

### Issue: "Study not found"

**Solution:**
```bash
# List all available studies
python scripts/advanced_features/analyze_study.py --list-studies

# Check spelling of study name
export OPTUNA_STUDY_NAME="correct_study_name"
```

### Issue: "MLflow server not responding"

**Solution:**
```bash
# Check MLflow is running
docker-compose ps mlflow

# Test connection
curl http://localhost:5000/api/2.0/mlflow/experiments/list

# Restart if needed
docker-compose restart mlflow
```

### Issue: Visualizations not created

**Solution:**
```bash
# Install plotly
pip install plotly kaleido

# Check permissions
ls -la ./study_analysis/
```

---

## 📝 Script Output Reference

### Monitor Output Format
```
[HH:MM:SS] Study: <study_name>

Progress: [████████░░░░] XX.X%

Trials:    Total: XXXX  |  Completed: XXXX  |  Running: XX
Status:    Failed: XXX  |  Pruned: XXXX  |  Waiting: XX

Best RMSE: XX.XXXX  (Trial #XX)
Throughput: XX.XX trials/min

Best Parameters:
  param1: value1
  param2: value2
  ...
```

### Promotion Output Format
```
================================================================================
MODEL COMPARISON
================================================================================

📦 Candidate Model (Version X):
   [Metrics]

🏭 Current Production Model (Version Y):
   [Metrics]

📊 Improvements:
   [Comparison]

================================================================================

🔍 Validating candidate model...
[Validation Results]

❓ Promote <model> vX to Production?
   Type 'yes' to confirm: 

[Promotion Result]
```

### Analysis Output Format
```
================================================================================
STUDY SUMMARY
================================================================================

Study Name: <name>
[Study Info]

Trial Statistics:
[Trial Counts]

Best Trial:
[Best Trial Info]

Value Statistics:
[Statistical Measures]

Duration Statistics:
[Timing Info]

================================================================================
```

---

## 🔗 Related Documentation

- [ADVANCED_FEATURES_GUIDE.md](../../docs/ADVANCED_FEATURES_GUIDE.md) - Complete feature documentation
- [PRIORITY2_ENHANCEMENTS.md](../../docs/PRIORITY2_ENHANCEMENTS.md) - MLflow & Optuna setup
- [ENVIRONMENT_SETUP.md](../../docs/ENVIRONMENT_SETUP.md) - Environment configuration
- [QUICK_REFERENCE.md](../../QUICK_REFERENCE.md) - Quick developer reference

---

## 💡 Tips & Best Practices

### Performance Optimization

1. **Use connection pooling** - Already configured in scripts
2. **Monitor during off-hours** - Less resource contention
3. **Export large studies to CSV** - Faster analysis offline
4. **Clean up old studies** - Keep database lean

### Security

1. **Never commit credentials** - Use environment variables
2. **Use read-only users** - For monitoring scripts
3. **Audit model promotions** - Log all promotions
4. **Validate before promoting** - Use validation thresholds

### Operational

1. **Monitor first run** - Understand normal behavior
2. **Set alerts** - Notify on failures or degradation
3. **Keep logs** - Redirect output to files for history
4. **Test dry-run first** - Always test with --dry-run

---

## 🆘 Support

**Questions?**
- Email: cnyagakan@gmail.com
- Documentation: See links above
- Issues: Check troubleshooting section

**Contributing:**
- Follow existing code style
- Add docstrings to new functions
- Test with --dry-run first
- Update this README

---

**Version:** 2.1.0  
**Last Updated:** January 3, 2025  
**Status:** ✅ Production Ready  
**Maintained By:** MLOps Team