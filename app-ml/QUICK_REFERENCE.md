# Quick Reference Card: Demand Forecasting ML System

**Version:** 2.1.0  
**Last Updated:** January 3, 2025  
**Quick Start:** 5 minutes

---

## 🚀 Quick Start (30 seconds)

```bash
# 1. Set up environment
cp .env.example .env && nano .env

# 2. Start services
docker-compose up -d

# 3. Access UIs
open http://localhost:8080  # Airflow
open http://localhost:5000  # MLflow
```

---

## 📊 System Versions

| Version | Status | Description | Performance |
|---------|--------|-------------|-------------|
| **v1.0** | ❌ Deprecated | Mock Optuna, RandomForest | RMSE: 56-58 |
| **v2.0** | ✅ Stable | Real Optuna, CatBoost | RMSE: 51-52 |
| **v2.1** | ✅ Current | + MLflow + Persistence | RMSE: 51-52 |
| **v2.2** | 🔄 Planned | + A/B Testing + Drift | TBD |

**Use v2.1 for production**

---

## 🎯 Key Metrics (Target)

```
RMSE:  ≤ 52.0  (currently: 51-52)
MAE:   ≤ 31.0  (currently: 30-31)
MAPE:  ≤ 22.5% (currently: 22-22.5%)
Time:  ~20 min (150 trials)
```

---

## 📁 Important Files

### **Start Here**
- `COMPLETE_SUMMARY.md` - Full system overview
- `MIGRATION_GUIDE.md` - 30-min deployment

### **Configuration**
- `.env` - Credentials (CREATE THIS!)
- `conf/base/parameters.yml` - Model config

### **DAGs** (Pick ONE)
- `dags/airflow_dag.py` - Original (deprecated)
- `dags/airflow_dag_refactored.py` - v2.0 (stable)
- `dags/airflow_dag_enhanced.py` - v2.1 (recommended)

### **Documentation**
- `docs/ENVIRONMENT_SETUP.md` - Env variables
- `docs/PRIORITY2_ENHANCEMENTS.md` - MLflow + Optuna
- `docs/FUTURE_ROADMAP.md` - Priority 3 & 4
- `docs/ADVANCED_FEATURES_GUIDE.md` - Pro tips

---

## ⚙️ Environment Variables (Required)

```bash
# MinIO (REQUIRED)
MINIO_ENDPOINT=http://host.docker.internal:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Optuna (v2.1 only)
OPTUNA_STORAGE_URL=postgresql://airflow:airflow@postgres:5432/optuna
OPTUNA_STUDY_NAME=demand_forecasting_study

# MLflow (v2.1 only)
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_EXPERIMENT_NAME=demand_forecasting

# Email (optional)
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password
```

---

## 🔧 Common Commands

### **Start/Stop**
```bash
docker-compose up -d           # Start all services
docker-compose down            # Stop all services
docker-compose restart         # Restart services
docker-compose ps              # Check status
```

### **Logs**
```bash
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-worker
docker-compose logs -f mlflow
docker-compose logs -f postgres
```

### **Database**
```bash
# Create Optuna database
docker-compose exec postgres psql -U airflow -c "CREATE DATABASE optuna;"

# Create MLflow database
docker-compose exec postgres psql -U airflow -c "CREATE DATABASE mlflow;"

# Check studies
docker-compose exec postgres psql -U airflow optuna -c "SELECT * FROM studies;"
```

### **Trigger DAG**
```bash
# Via Airflow UI
open http://localhost:8080
# Click DAG → Trigger

# Via CLI (inside container)
docker-compose exec airflow-scheduler airflow dags trigger demand_forecasting_enhanced
```

---

## 🐛 Troubleshooting

### **Issue: DAG not appearing**
```bash
# Check for syntax errors
docker-compose exec airflow-scheduler python -m py_compile /opt/airflow/dags/airflow_dag_enhanced.py

# Restart scheduler
docker-compose restart airflow-scheduler

# Check logs
docker-compose logs airflow-scheduler | tail -50
```

### **Issue: Cannot connect to MinIO**
```bash
# Test connection
curl http://localhost:9000/minio/health/live

# Check MinIO logs
docker-compose logs minio

# Restart MinIO
docker-compose restart minio
```

### **Issue: Optuna connection error**
```bash
# Check PostgreSQL
docker-compose exec postgres psql -U airflow -c "SELECT 1;"

# Check database exists
docker-compose exec postgres psql -U airflow -c "\l" | grep optuna

# Create if missing
docker-compose exec postgres psql -U airflow -c "CREATE DATABASE optuna;"
```

### **Issue: MLflow UI not loading**
```bash
# Check MLflow service
docker-compose ps mlflow

# Test connection
curl http://localhost:5000

# Restart MLflow
docker-compose restart mlflow

# Check logs
docker-compose logs mlflow
```

### **Issue: RMSE > 55 (poor performance)**
```bash
# Check using correct DAG (v2.1, not v1.0)
# Check parameters.yml has n_trials: 150
# Check logs show "Real Optuna optimization"
# Verify CatBoost is being used (not RandomForest)
```

---

## 📊 Monitoring

### **Airflow UI**
```
URL: http://localhost:8080
User: admin
Pass: admin (change in production!)

Check:
- DAG success rate (target: >95%)
- Task duration trends
- Recent failures
```

### **MLflow UI**
```
URL: http://localhost:5000

Check:
- Experiment metrics
- Model versions
- Artifact storage
- Compare runs
```

### **Key Metrics to Watch**
```python
# Good indicators
✅ RMSE: 51-52
✅ Training time: 15-25 min
✅ Trials completed: 150
✅ Study persists across runs

# Warning signs
⚠️ RMSE > 55 (check if using v1.0 by mistake)
⚠️ Training time > 30 min (check workers)
⚠️ Trials < 150 (check parameters.yml)
⚠️ Study resets each run (check Optuna storage)
```

---

## 🎓 Key Concepts

### **Real Optuna vs Mock**
```python
# ❌ Mock (v1.0) - Random sampling
params = {
    "depth": random.randint(3, 8),
    "learning_rate": random.uniform(0.01, 0.2)
}

# ✅ Real (v2.0+) - Bayesian optimization
study = optuna.create_study(
    sampler=optuna.samplers.TPESampler(seed=42)
)
study.optimize(objective, n_trials=150)
```

### **Study Persistence**
```python
# Without persistence (v2.0)
# - Each DAG run starts from scratch
# - 150 trials per run
# - Previous trials lost

# With persistence (v2.1)
# - Studies saved to PostgreSQL
# - Resume from previous runs
# - Accumulates: 150 + 150 + 150... trials
# - Better optimization over time
```

### **Model Versioning**
```python
# v2.0: Only latest
s3://demand-forecasting/06_models/regressor.pickle

# v2.1: All versions
s3://demand-forecasting/06_models/
  ├── regressor.pickle              # Latest
  ├── regressor_20250103_141530.pickle
  ├── regressor_20250103_183245.pickle
  └── regressor_20250104_092115.pickle
```

---

## 💡 Pro Tips

### **Parallel Optimization (5x faster)**
```bash
# Scale to 5 workers
docker-compose up -d --scale airflow-worker=5

# All workers optimize same study in parallel
# No code changes needed!
```

### **Load Production Model**
```python
import mlflow
mlflow.set_tracking_uri("http://localhost:5000")

# Always loads current production model
model = mlflow.pyfunc.load_model(
    "models:/demand_forecasting_catboost/Production"
)
```

### **Monitor Optimization**
```python
import optuna
storage = optuna.storages.RDBStorage(
    "postgresql://airflow:airflow@postgres:5432/optuna"
)
study = optuna.load_study("demand_forecasting_study", storage=storage)

print(f"Trials: {len(study.trials)}")
print(f"Best RMSE: {study.best_value:.4f}")
```

### **Custom Metrics**
```python
# Add to DAG
if MLFLOW_AVAILABLE:
    mlflow.log_metric("peak_hour_rmse", peak_rmse)
    mlflow.log_metric("training_time_seconds", time)
    mlflow.log_metric("model_size_mb", size)
```

---

## 🔗 Quick Links

### **Documentation**
- [Complete Summary](./COMPLETE_SUMMARY.md) - Executive overview
- [Migration Guide](./MIGRATION_GUIDE.md) - 30-min deployment
- [Environment Setup](./docs/ENVIRONMENT_SETUP.md) - Configuration
- [Advanced Features](./docs/ADVANCED_FEATURES_GUIDE.md) - Pro features
- [Future Roadmap](./docs/FUTURE_ROADMAP.md) - What's next

### **External Resources**
- [Optuna Docs](https://optuna.readthedocs.io/)
- [MLflow Docs](https://mlflow.org/docs/latest/)
- [CatBoost Docs](https://catboost.ai/docs/)
- [Airflow Docs](https://airflow.apache.org/docs/)

### **UIs**
- Airflow: http://localhost:8080
- MLflow: http://localhost:5000
- MinIO: http://localhost:9001

---

## 📞 Support

**Owner:** cnyagakan@gmail.com  
**Documentation:** See links above  
**Issues:** Check analysis_reports/ directory

---

## ✅ Pre-Deployment Checklist

### **Required**
- [ ] `.env` file created with credentials
- [ ] PostgreSQL databases created (optuna, mlflow)
- [ ] MinIO accessible
- [ ] Airflow UI accessible
- [ ] DAG appears in Airflow
- [ ] Test run succeeds

### **Validation**
- [ ] RMSE ≤ 52
- [ ] Training time ~20 min
- [ ] Log shows "Real Optuna optimization"
- [ ] Log shows "TPESampler (Bayesian optimization)"
- [ ] Model saved to S3
- [ ] MLflow tracking works
- [ ] Optuna study persists

### **Production**
- [ ] Change default passwords
- [ ] Configure email alerts
- [ ] Set up monitoring
- [ ] Document runbook
- [ ] Train team

---

## 🚨 Emergency Procedures

### **Rollback to v2.0**
```bash
cd dags/
mv airflow_dag.py airflow_dag_enhanced_backup.py
mv airflow_dag_refactored.py airflow_dag.py
docker-compose restart airflow-scheduler airflow-worker
```

### **Rollback Model**
```bash
# List versions
aws s3 ls s3://demand-forecasting/06_models/

# Copy old version as latest
aws s3 cp \
  s3://demand-forecasting/06_models/regressor_20250103_141530.pickle \
  s3://demand-forecasting/06_models/regressor.pickle
```

### **Reset Optuna Study**
```python
import optuna
storage = optuna.storages.RDBStorage(
    "postgresql://airflow:airflow@postgres:5432/optuna"
)
optuna.delete_study(study_name="demand_forecasting_study", storage=storage)
```

---

## 📊 Performance Benchmarks

| Configuration | RMSE | Time | Notes |
|--------------|------|------|-------|
| v1.0 (Mock) | 56-58 | 10 min | ❌ Don't use |
| v2.0 (1 worker) | 51-52 | 20 min | ✅ Stable |
| v2.1 (1 worker) | 51-52 | 20 min | ✅ + Tracking |
| v2.1 (5 workers) | 51-52 | 5 min | ✅ Faster |

---

## 🎯 Success Criteria

**System is healthy when:**
- ✅ DAG success rate > 95%
- ✅ RMSE consistently ≤ 52
- ✅ Training time < 25 min
- ✅ Optuna study accumulates trials
- ✅ MLflow tracks all runs
- ✅ Models versioned correctly

**Take action if:**
- ⚠️ RMSE > 55 (check DAG version)
- ⚠️ Training time > 30 min (scale workers)
- ⚠️ Study resets (check PostgreSQL)
- ⚠️ MLflow errors (check connection)

---

**Last Updated:** January 3, 2025  
**Version:** 2.1.0  
**Status:** Production Ready ✅  

**For detailed information, see [COMPLETE_SUMMARY.md](./COMPLETE_SUMMARY.md)**