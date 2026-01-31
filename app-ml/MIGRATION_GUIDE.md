# Migration Guide: Moving to Refactored DAG with Real Optuna

**Quick Start Guide for Developers**

---

## 🎯 What Changed?

### Before (Old DAG)
- ❌ Mock random sampling (not real Optuna)
- ❌ 50 random trials across 50 parallel tasks
- ❌ Hardcoded MinIO credentials
- ❌ Missing validation functions
- ❌ RandomForest as primary model
- ❌ RMSE: 56-58 (suboptimal)

### After (Refactored DAG)
- ✅ Real Optuna Bayesian optimization (TPESampler)
- ✅ 150 intelligent trials in single task
- ✅ Environment-based credentials
- ✅ Comprehensive validation
- ✅ CatBoost as primary model
- ✅ RMSE: 51-52 (10-15% better)

---

## 📋 Pre-Migration Checklist

- [ ] Read `docs/ENVIRONMENT_SETUP.md`
- [ ] Read `analysis_reports/IMPLEMENTATION_SUMMARY.md`
- [ ] Backup current `.env` file (if exists)
- [ ] Have MinIO credentials ready
- [ ] Have SMTP credentials ready (optional)
- [ ] Verify Python 3.9+ installed
- [ ] Verify Docker & Docker Compose installed

---

## 🚀 Migration Steps (30 minutes)

### Step 1: Set Up Environment Variables (10 min)

**Create `.env` file in project root:**

```bash
cd /path/to/app-ml
cp docs/ENVIRONMENT_SETUP.md .env.example  # Extract example from docs
nano .env  # or vim, code, etc.
```

**Minimum required variables:**

```bash
# MinIO Configuration
MINIO_ENDPOINT=http://host.docker.internal:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
S3_BUCKET=demand-forecasting

# Email Configuration (Optional - skip if not using email alerts)
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password

# Airflow Configuration
AIRFLOW__CORE__FERNET_KEY=GENERATE_WITH_PYTHON_CRYPTOGRAPHY
KEDRO_ENV=local
PYTHONPATH=/opt/airflow/src
```

**Generate Fernet Key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Test MinIO connection:**
```bash
python check_minio_data.py
```

---

### Step 2: Update Docker Configuration (5 min)

**Verify `docker-compose.yaml` loads `.env`:**

```yaml
services:
  airflow-scheduler:
    env_file:
      - .env
  
  airflow-worker:
    env_file:
      - .env
```

**Restart services to load environment:**
```bash
docker-compose down
docker-compose up -d
```

---

### Step 3: Switch to Refactored DAG (5 min)

**Option A: Rename files (Recommended for new deployments)**
```bash
cd dags/
mv airflow_dag.py airflow_dag_old.py
mv airflow_dag_refactored.py airflow_dag.py
```

**Option B: Update DAG ID (Recommended for existing deployments)**
- Keep both DAGs
- Pause old DAG: `demand_forecasting_custom`
- Unpause new DAG: `demand_forecasting_refactored`
- Old DAG remains as fallback

---

### Step 4: Verify Installation (5 min)

**Check DAG appears in Airflow:**
```bash
# View Airflow logs
docker-compose logs -f airflow-scheduler | grep -i "demand_forecasting"

# Expected output:
# "DAG demand_forecasting_refactored loaded successfully"
```

**Access Airflow UI:**
- Navigate to: http://localhost:8080
- Login with admin credentials
- Verify DAG `demand_forecasting_refactored` appears
- Check that DAG has 4 tasks (not 7)

---

### Step 5: Test Run (5 min)

**Trigger manual DAG run:**
1. Open Airflow UI
2. Find `demand_forecasting_refactored` DAG
3. Click "Trigger DAG" button
4. Monitor task execution

**Expected task sequence:**
```
1. t_validate_raw_data (30 sec)
2. t_preprocess (1 min)
3. t_feature_eng (2 min)
4. t_train_optimized_model (15-25 min with 150 trials)
```

**Monitor logs for validation messages:**
```bash
docker-compose logs -f airflow-worker | grep -i "validation\|optimization\|catboost"

# Expected messages:
# "✅ Raw data validated: 17379 rows, 17 columns"
# "✅ Preprocessing complete: 17379 rows"
# "✅ Feature engineering complete: 17356 rows, 32 features"
# "🚀 Starting CatBoost training with real Optuna optimization..."
# "Trials: 150"
# "Sampler: TPESampler (Bayesian optimization)"
# "✅ CatBoost training completed!"
# "RMSE: 51.34"
# "✅ Model saved and verified successfully"
```

---

## 🧪 Verification Checklist

After test run completes:

- [ ] All 4 tasks show green (success)
- [ ] No errors in Airflow logs
- [ ] RMSE ≤ 52 (check task logs)
- [ ] Model saved to S3: `s3://demand-forecasting/06_models/regressor.pickle`
- [ ] Model file size > 1 KB (not corrupted)
- [ ] Log shows "Real Optuna optimization" message
- [ ] Log shows "TPESampler (Bayesian optimization)"
- [ ] Log shows "150 trials" (or your configured value)
- [ ] No hardcoded credentials in logs
- [ ] Email alert received (if configured)

---

## 🔍 Troubleshooting

### Issue: DAG not appearing in Airflow UI

**Solution:**
```bash
# Check for Python syntax errors
docker-compose exec airflow-scheduler python -m py_compile /opt/airflow/dags/airflow_dag_refactored.py

# Check scheduler logs
docker-compose logs airflow-scheduler | tail -50

# Restart scheduler
docker-compose restart airflow-scheduler
```

---

### Issue: `ModuleNotFoundError: No module named 'demand_forecasting'`

**Solution:**
```bash
# Verify PYTHONPATH is set in .env
echo $PYTHONPATH  # Should be /opt/airflow/src

# Verify src/ directory exists in container
docker-compose exec airflow-worker ls -la /opt/airflow/src/demand_forecasting

# Rebuild Docker images
docker-compose build --no-cache
docker-compose up -d
```

---

### Issue: `Cannot connect to MinIO`

**Solution:**
```bash
# Check MinIO is running
docker-compose ps minio

# Test MinIO connectivity
curl http://localhost:9000/minio/health/live

# Verify credentials in .env
grep MINIO_ .env

# Test Python connection
python -c "
import s3fs
fs = s3fs.S3FileSystem(
    client_kwargs={'endpoint_url': 'http://host.docker.internal:9000'},
    key='minioadmin',
    secret='minioadmin'
)
print('✅ Connected to MinIO')
print('Buckets:', fs.ls(''))
"
```

---

### Issue: Email alerts not working

**Solution:**
```bash
# Verify SMTP configuration
grep AIRFLOW__SMTP .env

# For Gmail: Use App Password (not regular password)
# Generate at: https://myaccount.google.com/apppasswords

# Test email sending
docker-compose exec airflow-scheduler python -c "
from airflow.utils.email import send_email
send_email(
    to=['your-email@gmail.com'],
    subject='Test Email',
    html_content='<p>Test</p>'
)
print('✅ Email sent')
"
```

---

### Issue: Training takes too long

**Solution:**
```bash
# Reduce trials temporarily for testing
# Edit conf/base/parameters.yml:
# optuna:
#   n_trials: 20  # Instead of 150

# Or set environment variable
export OPTUNA_N_TRIALS=20

# Restart services
docker-compose restart airflow-scheduler airflow-worker
```

---

### Issue: `ValueError: Missing 'optuna' key in parameters`

**Solution:**
```bash
# Verify parameters.yml has optuna section
cat conf/base/parameters.yml | grep -A 10 "optuna:"

# Should see:
# optuna:
#   n_trials: 150
#   primary_model: "catboost"
#   catboost_search_space:
#     ...
```

---

## 🔄 Rollback Procedure

If critical issues arise:

**Immediate Rollback (< 5 minutes):**
```bash
cd dags/

# Restore old DAG
mv airflow_dag.py airflow_dag_refactored_backup.py
mv airflow_dag_old.py airflow_dag.py

# Restart services
docker-compose restart airflow-scheduler airflow-worker

# Verify old DAG loaded
docker-compose logs airflow-scheduler | grep "demand_forecasting_custom"
```

**The old DAG will:**
- Use mock random sampling (functional but suboptimal)
- Return to 7-task architecture
- Continue working with existing data/models
- No data loss

---

## 📊 Performance Comparison

After successful migration, compare metrics:

**Before Migration:**
```python
# Old DAG metrics (mock Optuna)
{
    "rmse": 56-58,
    "mae": 33-35,
    "mape": 23-24%,
    "training_time": "~10 min (50 parallel trials)"
}
```

**After Migration:**
```python
# New DAG metrics (real Optuna)
{
    "rmse": 51-52,      # ✅ 10-13% better
    "mae": 30-31,        # ✅ 9-11% better
    "mape": 22-22.5%,    # ✅ 4-8% better
    "training_time": "~20 min (150 intelligent trials)"
}
```

---

## 🎓 Key Concepts

### What is Bayesian Optimization?

**Old Approach (Random):**
```python
# Each trial is independent - no learning
for i in range(50):
    params = {
        "depth": random.randint(3, 8),
        "learning_rate": random.uniform(0.01, 0.2)
    }
    train_model(params)  # No connection between trials
```

**New Approach (Bayesian):**
```python
# Each trial learns from previous trials
study = optuna.create_study(sampler=TPESampler())
study.optimize(objective, n_trials=150)
# Trial 150 is much smarter than Trial 1
# Converges to optimal parameters efficiently
```

### Why 150 Trials?

- Notebook reference used 150 trials
- Achieved RMSE ~51.34
- Balance between exploration and exploitation
- More trials = better results (diminishing returns after ~200)

### Why CatBoost?

- Best performer in notebook experiments
- Handles categorical features automatically
- Built-in regularization (L2 leaf reg)
- Faster training than RandomForest
- Better generalization

---

## 📚 Additional Resources

**Documentation:**
- `docs/ENVIRONMENT_SETUP.md` - Complete environment guide
- `analysis_reports/IMPLEMENTATION_SUMMARY.md` - Technical details
- `analysis_reports/ERROR_ANALYSIS_REPORT.md` - All issues fixed
- `analysis_reports/NOTEBOOK_GAP_ANALYSIS_SUMMARY.md` - Notebook comparison

**Code Reference:**
- `src/demand_forecasting/utils/s3_helpers.py` - New utility functions
- `dags/airflow_dag_refactored.py` - New DAG implementation
- `src/demand_forecasting/pipelines/demand_modeling/catboost_nodes.py` - Optuna logic

**External Resources:**
- [Optuna Documentation](https://optuna.readthedocs.io/)
- [CatBoost Documentation](https://catboost.ai/docs/)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)

---

## 🤝 Support

**Questions or Issues?**
- Email: cnyagakan@gmail.com
- Check existing issues in analysis reports
- Review troubleshooting section above
- Consult documentation files

**Common Questions:**

**Q: Can I keep both DAGs running?**
A: Yes! Keep both and unpause the one you want to use.

**Q: Will this affect existing models?**
A: No. Models are versioned by timestamp. Old models remain unchanged.

**Q: How long does training take?**
A: 15-25 minutes with 150 trials (vs. 10 min with 50 random trials).

**Q: Can I reduce trials for testing?**
A: Yes. Edit `conf/base/parameters.yml` and set `n_trials: 20`.

**Q: What if I don't have email configured?**
A: System works fine without email. Just won't send alerts.

**Q: Is this production-ready?**
A: Yes, after verification testing. Follow the verification checklist.

---

## ✅ Success Criteria

You've successfully migrated when:

1. ✅ Refactored DAG appears in Airflow UI
2. ✅ All 4 tasks execute without errors
3. ✅ RMSE ≤ 52 (10-15% better than before)
4. ✅ Log shows "Real Optuna optimization"
5. ✅ Model saved and verified in S3
6. ✅ No hardcoded credentials in logs
7. ✅ System can run multiple times consistently

---

**Migration Time:** ~30 minutes  
**Complexity:** Low (mostly configuration)  
**Risk:** Low (old DAG preserved as fallback)  
**Impact:** High (10-15% performance improvement)

**Ready to migrate? Follow the steps above and you'll be running with real Optuna optimization in 30 minutes!** 🚀