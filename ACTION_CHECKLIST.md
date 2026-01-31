# Action Checklist - Demand Forecasting System Setup

**Date:** December 31, 2025  
**Status:** Implementation Complete - User Action Required  
**Contact:** cnyagakan@gmail.com

---

## Overview

All code and configuration changes are complete. You now need to perform these actions to activate the new features.

**Estimated Time:** 20-30 minutes

---

## ✅ Immediate Actions (Required)

### 1. Configure Email Alerts (5 minutes)

**Why:** Enable failure notifications to cnyagakan@gmail.com

**Steps:**

```bash
# Step 1: Create Gmail App Password
# 1. Go to: https://myaccount.google.com/apppasswords
# 2. Sign in to cnyagakan@gmail.com
# 3. Select "Mail" and "Other (Custom name)"
# 4. Name it: "Airflow Demand Forecasting"
# 5. Click "Generate"
# 6. Copy the 16-character password (example: abcd efgh ijkl mnop)
```

```bash
# Step 2: Edit .env file
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"
notepad .env

# Replace this line:
# AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password-here
# With your actual password (remove spaces):
# AIRFLOW__SMTP__SMTP_PASSWORD=abcdefghijklmnop
```

```bash
# Step 3: Restart services
docker-compose restart

# Step 4: Test email (wait 30 seconds after restart)
docker-compose exec airflow-scheduler python -c "
from airflow.utils.email import send_email
send_email(
    to=['cnyagakan@gmail.com'],
    subject='[TEST] Airflow Email Setup Complete',
    html_content='<h3>Success!</h3><p>Email alerts are working correctly. ✅</p><p>You will receive notifications when:</p><ul><li>Tasks fail</li><li>Tasks retry</li><li>Data validation fails</li></ul>'
)
print('✅ Test email sent to cnyagakan@gmail.com')
"
```

**Expected Result:** You should receive an email within 1-2 minutes

**Troubleshooting:**
- If no email received, check spam folder
- If error "Authentication failed", verify App Password (not regular password)
- See `SETUP_INSTRUCTIONS.md` for detailed troubleshooting

---

### 2. Set Up Airflow Connections (2 minutes)

**Why:** Enable remote logging to MinIO S3

**Steps:**

```bash
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Run the setup script
docker-compose exec airflow-scheduler bash /opt/airflow/scripts/setup_connections.sh
```

**Expected Output:**
```
✅ MinIO S3 connection created: minio_s3
✅ airflow-logs bucket ready
Airflow Connections Setup Complete!
```

**Verify:**
```bash
# Check connection was created
docker-compose exec airflow-scheduler airflow connections list | grep minio_s3

# Check logs bucket exists
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc ls myminio/airflow-logs/"
```

---

### 3. Rebuild Docker Images (5 minutes)

**Why:** Install new packages (xgboost, lightgbm, great-expectations, mlflow)

**Steps:**

```bash
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Stop services
docker-compose down

# Rebuild with new packages (this will take a few minutes)
docker-compose build

# Start services
docker-compose up -d

# Wait for services to be healthy (check every 30 seconds)
docker-compose ps
```

**Expected Result:** All services show "healthy" status after 2-3 minutes

---

### 4. Test Full Pipeline with New Features (10 minutes)

**Why:** Verify data validation, email alerts, and metrics tracking work

**Steps:**

```bash
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Unpause DAG
docker-compose exec airflow-scheduler airflow dags unpause demand_forecasting_custom

# Trigger DAG run
docker-compose exec airflow-scheduler airflow dags trigger demand_forecasting_custom

# Monitor execution (Ctrl+C to exit)
docker-compose logs -f airflow-scheduler | grep -E "(demand_forecasting|validate|SUCCESS|FAILED)"
```

**Watch For:**
- ✅ `t_validate_raw_data` task completes successfully
- ✅ Validation statistics logged (rows, columns, missing values)
- ✅ Pipeline completes end-to-end
- ✅ No error emails received (unless there's a genuine issue)

**Alternative Monitoring:**
- Open Airflow UI: http://localhost:8080
- Username: Cole, Password: admin
- Click on "demand_forecasting_custom" DAG
- Watch the Graph view for task progress

---

## 📋 Optional Enhancements (Recommended)

### 5. Set Up Monitoring Dashboard (30 minutes)

**Why:** Track system performance with Prometheus + Grafana

**Steps:** See `SETUP_INSTRUCTIONS.md` → "Monitoring & Alerting" section

**Benefits:**
- Visual dashboards for DAG performance
- CPU, memory, task duration metrics
- Alerting for resource issues

---

### 6. Configure CI/CD Pipeline (60 minutes)

**Why:** Automate testing and deployment

**Steps:** See `SETUP_INSTRUCTIONS.md` → "CI/CD Pipeline" section

**Benefits:**
- Automated testing on code changes
- Lint checks before deployment
- Consistent deployment process

---

### 7. Set Up Automated Backups (15 minutes)

**Why:** Protect data and metadata

**Steps:**

```bash
# Create backup script
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"

# Create scripts directory if it doesn't exist
mkdir -p scripts

# Create backup script
cat > scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/airflow/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U airflow > "$BACKUP_DIR/postgres_backup.sql"

# Backup MinIO data
docker-compose exec -T minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc mirror myminio/demand-forecasting /tmp/backup"
docker cp app-ml-minio-1:/tmp/backup "$BACKUP_DIR/minio_backup"

echo "✅ Backup complete: $BACKUP_DIR"
EOF

chmod +x scripts/backup.sh
```

**Schedule with Windows Task Scheduler:**
- Open Task Scheduler
- Create Basic Task
- Name: "Airflow Backup"
- Trigger: Daily at 2 AM
- Action: Start a program
- Program: `bash`
- Arguments: `scripts/backup.sh`
- Start in: `D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml`

---

## 🔍 Verification Checklist

After completing the immediate actions, verify everything works:

### System Health
```bash
cd app-ml
docker-compose ps
# All services should show "Up (healthy)"
```

- [ ] ✅ airflow-scheduler: healthy
- [ ] ✅ airflow-worker: healthy
- [ ] ✅ airflow-webserver: healthy
- [ ] ✅ airflow-triggerer: healthy
- [ ] ✅ postgres: healthy
- [ ] ✅ redis: healthy
- [ ] ✅ minio: healthy

### Email Alerts
- [ ] ✅ Test email received at cnyagakan@gmail.com
- [ ] ✅ Email contains proper formatting and HTML
- [ ] ✅ Subject line is correct

### Remote Logging
- [ ] ✅ `minio_s3` connection exists
- [ ] ✅ `airflow-logs` bucket created
- [ ] ✅ Logs appear in bucket after DAG run

### Data Validation
- [ ] ✅ `t_validate_raw_data` task appears in DAG graph
- [ ] ✅ Validation task runs before preprocessing
- [ ] ✅ Validation logs show data statistics

### Full Pipeline
- [ ] ✅ DAG completes successfully
- [ ] ✅ All tasks green in UI
- [ ] ✅ Final model saved to MinIO (101 MiB)

---

## 📚 Documentation Reference

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **ACTION_CHECKLIST.md** | This file - step-by-step actions | Right now |
| **SETUP_INSTRUCTIONS.md** | Detailed setup for all features | When configuring advanced features |
| **QUICK_REFERENCE.md** | Common commands and troubleshooting | Daily operations |
| **IMPLEMENTATION_COMPLETE.md** | Summary of what was implemented | Understanding changes |
| **AIRFLOW_INTEGRATION_COMPLETE.md** | Architecture and design decisions | System design questions |

---

## 🚨 Troubleshooting Quick Guide

### Email Not Working

**Problem:** Test email not received

**Solutions:**
```bash
# 1. Verify SMTP configuration
docker-compose exec airflow-scheduler python -c "
import os
print('SMTP Host:', os.getenv('AIRFLOW__SMTP__SMTP_HOST'))
print('SMTP User:', os.getenv('AIRFLOW__SMTP__SMTP_USER'))
print('SMTP Port:', os.getenv('AIRFLOW__SMTP__SMTP_PORT'))
"

# 2. Check .env file is loaded
docker-compose exec airflow-scheduler env | grep SMTP

# 3. Test SMTP connection
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
- Using regular password instead of App Password
- App Password has spaces (remove them)
- 2-Step Verification not enabled on Gmail
- .env file not loaded (restart services)

---

### Remote Logging Not Working

**Problem:** Logs not appearing in MinIO

**Solutions:**
```bash
# 1. Verify connection
docker-compose exec airflow-scheduler airflow connections get minio_s3

# 2. Recreate bucket
docker-compose exec minio sh -c "
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc mb myminio/airflow-logs --ignore-existing
mc ls myminio/
"

# 3. Test S3 access
docker-compose exec airflow-scheduler python -c "
import s3fs
fs = s3fs.S3FileSystem(
    client_kwargs={'endpoint_url': 'http://minio:9000'},
    key='minioadmin',
    secret='minioadmin'
)
print('Buckets:', fs.ls(''))
"
```

---

### Data Validation Failing

**Problem:** Validation task fails unexpectedly

**Solutions:**
```bash
# Check raw data
docker-compose exec airflow-scheduler python -c "
from kedro.config import OmegaConfigLoader
from kedro.io import DataCatalog

loader = OmegaConfigLoader(conf_source='/opt/airflow/conf', env='local')
catalog = DataCatalog.from_config(loader['catalog'], loader['credentials'])
df = catalog.load('raw_bike_data')
print(f'✅ Data loaded: {len(df)} rows, {len(df.columns)} columns')
print(f'Missing values: {df.isnull().sum().sum()}')
"
```

---

### Packages Not Found

**Problem:** `ModuleNotFoundError` after rebuild

**Solutions:**
```bash
# 1. Verify rebuild completed
docker images | grep app-ml

# 2. Force rebuild without cache
docker-compose build --no-cache

# 3. Verify packages installed
docker-compose exec airflow-scheduler pip list | grep -E "(xgboost|lightgbm|great-expectations|mlflow)"
```

---

## 🎯 Success Criteria

You'll know everything is working when:

1. ✅ **Email test succeeds** - Received email at cnyagakan@gmail.com
2. ✅ **Connections configured** - `airflow connections list` shows `minio_s3`
3. ✅ **Services healthy** - `docker-compose ps` shows all healthy
4. ✅ **Pipeline completes** - DAG run finishes successfully with validation
5. ✅ **No errors** - Logs show no critical errors

---

## 📞 Getting Help

**Stuck? Need assistance?**

1. **Check logs:**
   ```bash
   docker-compose logs -f airflow-scheduler
   docker-compose logs -f airflow-worker
   ```

2. **Review documentation:**
   - Start with `QUICK_REFERENCE.md`
   - Check `SETUP_INSTRUCTIONS.md` troubleshooting section

3. **Contact:**
   - Email: cnyagakan@gmail.com
   - Include: error message, logs, steps to reproduce

---

## ✅ Completion Sign-Off

Once you've completed all immediate actions:

- [ ] Email alerts tested and working
- [ ] Airflow connections configured
- [ ] Docker images rebuilt with new packages
- [ ] Full pipeline tested successfully
- [ ] Documentation reviewed
- [ ] System is production ready

**Date Completed:** _______________  
**Completed By:** _______________  
**Notes:** _______________

---

**Next Steps After Completion:**
- Monitor daily DAG runs
- Review email alerts
- Set up optional monitoring (Prometheus/Grafana)
- Configure automated backups
- Plan CI/CD pipeline implementation

**System Status:** 🚀 Ready for Production Use

---

**END OF ACTION CHECKLIST**