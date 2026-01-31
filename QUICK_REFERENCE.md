# Quick Reference Guide - Demand Forecasting Airflow System

**Last Updated:** December 31, 2025  
**Airflow Version:** 2.10.4  
**Status:** ✅ Production Ready

---

## Table of Contents
1. [Service Management](#service-management)
2. [DAG Operations](#dag-operations)
3. [Monitoring & Debugging](#monitoring--debugging)
4. [Data Management](#data-management)
5. [Common Issues](#common-issues)
6. [Useful Commands](#useful-commands)

---

## Service Management

### Start All Services
```bash
cd "D:\Projects\MLOPs\ml-systems\ml-systems\System 1 - demand_forecasting\app-ml"
docker-compose up -d
```

### Stop All Services
```bash
cd app-ml
docker-compose down
```

### Restart Services
```bash
cd app-ml
docker-compose restart
```

### Check Service Status
```bash
cd app-ml
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-worker
docker-compose logs -f airflow-webserver

# Last 100 lines
docker-compose logs --tail=100 airflow-worker
```

### Rebuild After Code Changes
```bash
cd app-ml
docker-compose down
docker-compose build
docker-compose up -d
```

---

## DAG Operations

### Access Airflow UI
```
http://localhost:8080
Username: admin
Password: admin
```

### List All DAGs
```bash
docker-compose exec airflow-scheduler airflow dags list
```

### Trigger DAG Manually
```bash
docker-compose exec airflow-scheduler airflow dags trigger demand_forecasting_custom
```

### Unpause/Pause DAG
```bash
# Unpause
docker-compose exec airflow-scheduler airflow dags unpause demand_forecasting_custom

# Pause
docker-compose exec airflow-scheduler airflow dags pause demand_forecasting_custom
```

### List DAG Runs
```bash
docker-compose exec airflow-scheduler airflow dags list-runs -d demand_forecasting_custom
```

### View DAG Run State
```bash
docker-compose exec airflow-scheduler airflow dags state demand_forecasting_custom <RUN_ID>
```

### Test Single Task
```bash
docker-compose exec airflow-scheduler airflow tasks test demand_forecasting_custom t_preprocess 2025-12-31
```

### Clear Failed Tasks
```bash
docker-compose exec airflow-scheduler airflow tasks clear demand_forecasting_custom -s 2025-12-31 -e 2025-12-31
```

---

## Monitoring & Debugging

### Check Celery Worker Status
```bash
docker-compose exec airflow-worker celery -A airflow.providers.celery.executors.celery_executor inspect active
```

### Monitor Task Execution
```bash
# Real-time worker logs
docker-compose logs -f airflow-worker | grep "succeeded\|failed\|ERROR"

# Real-time scheduler logs
docker-compose logs -f airflow-scheduler | grep "demand_forecasting"
```

### Check Redis Queue
```bash
docker-compose exec redis redis-cli
> KEYS *
> LLEN celery
> EXIT
```

### Database Connection
```bash
docker-compose exec postgres psql -U airflow
\dt  # List tables
\q   # Quit
```

### Check Airflow Configuration
```bash
docker-compose exec airflow-scheduler airflow config list
```

### View Task Instance Details
```bash
docker-compose exec airflow-scheduler airflow tasks state demand_forecasting_custom t_preprocess <RUN_ID>
```

---

## Data Management

### Access MinIO UI
```
http://localhost:9001
Username: minioadmin
Password: minioadmin
```

### List MinIO Buckets (CLI)
```bash
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc ls myminio/"
```

### List Files in Bucket
```bash
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc ls -r myminio/demand-forecasting/"
```

### Upload File to MinIO
```bash
# Copy to container
docker cp /path/to/local/file.parquet app-ml-minio-1:/tmp/file.parquet

# Move to bucket
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc cp /tmp/file.parquet myminio/demand-forecasting/01_raw/"
```

### Download File from MinIO
```bash
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc cp myminio/demand-forecasting/06_models/regressor.pickle /tmp/"
docker cp app-ml-minio-1:/tmp/regressor.pickle ./regressor.pickle
```

### Check File Size
```bash
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc ls --summarize myminio/demand-forecasting/"
```

---

## Common Issues

### Issue: DAG Not Appearing in UI
**Solution:**
```bash
# Check for syntax errors
docker-compose exec airflow-scheduler python /opt/airflow/dags/airflow_dag.py

# Restart scheduler
docker-compose restart airflow-scheduler

# Check logs
docker-compose logs airflow-scheduler | grep ERROR
```

### Issue: Tasks Stuck in Queued State
**Solution:**
```bash
# Check worker is running
docker-compose ps airflow-worker

# Check Celery connectivity
docker-compose logs airflow-worker | tail -50

# Restart worker
docker-compose restart airflow-worker
```

### Issue: "Duplicate keys found" Error
**Solution:**
- Ensure only ONE credentials file exists:
  - Keep: `app-ml/conf/docker/credentials.yml`
  - Remove: `app-ml/conf/local/credentials.yml` (if present)

### Issue: Out of Memory
**Solution:**
```bash
# Check resource usage
docker stats

# Reduce parallelism in docker-compose.yaml
# Change: AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=8

# Restart services
docker-compose restart
```

### Issue: MinIO Connection Failed
**Solution:**
```bash
# Check MinIO is running
docker-compose ps minio

# Check credentials in conf/docker/credentials.yml
# Should be: minioadmin / minioadmin

# Test connectivity
docker-compose exec airflow-worker curl http://minio:9000/minio/health/live
```

### Issue: PostgreSQL Connection Errors
**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Reinitialize database (CAUTION: Deletes all metadata!)
docker-compose down
docker volume rm app-ml_postgres-db-volume
docker-compose up -d airflow-init
docker-compose up -d
```

---

## Useful Commands

### Execute Python in Airflow Container
```bash
docker-compose exec airflow-scheduler python
```

### Access Airflow Container Shell
```bash
docker-compose exec airflow-scheduler bash
```

### Check Kedro Catalog
```bash
docker-compose exec airflow-scheduler python -c "
from kedro.config import OmegaConfigLoader
loader = OmegaConfigLoader(conf_source='/opt/airflow/conf')
print(loader['catalog'])
"
```

### Check Disk Space
```bash
# Container disk usage
docker system df

# Volume disk usage
docker volume ls
docker volume inspect app-ml_postgres-db-volume
```

### Clean Up Docker Resources
```bash
# Remove stopped containers
docker-compose down

# Remove volumes (CAUTION: Deletes data!)
docker-compose down -v

# Remove unused images
docker image prune -a
```

### Export DAG Run Results
```bash
docker-compose exec postgres psql -U airflow -c "COPY (SELECT * FROM dag_run WHERE dag_id='demand_forecasting_custom') TO STDOUT CSV HEADER" > dag_runs.csv
```

### Backup MinIO Data
```bash
docker-compose exec minio sh -c "mc alias set myminio http://localhost:9000 minioadmin minioadmin && mc mirror myminio/demand-forecasting /tmp/backup"
docker cp app-ml-minio-1:/tmp/backup ./minio_backup
```

---

## Performance Tuning

### Increase Worker Parallelism
Edit `docker-compose.yaml`:
```yaml
airflow-worker:
  environment:
    - AIRFLOW__CELERY__WORKER_CONCURRENCY=32  # Default: 16
```

### Adjust DAG Parallelism
Edit `app-ml/dags/airflow_dag.py`:
```python
@dag(
    max_active_tasks=32,  # Default: 16
    max_active_runs=3,    # Default: 1
)
```

### Enable Task Retries
```python
default_args = {
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}
```

---

## Maintenance

### Weekly Tasks
- [ ] Check disk space: `docker system df`
- [ ] Review failed DAG runs in UI
- [ ] Check worker logs for errors
- [ ] Verify MinIO data integrity

### Monthly Tasks
- [ ] Update Airflow to latest 2.10.x patch: `docker-compose build --pull`
- [ ] Backup PostgreSQL metadata: `pg_dump`
- [ ] Backup MinIO data: `mc mirror`
- [ ] Review and archive old DAG runs

### Quarterly Tasks
- [ ] Evaluate Airflow 3.x upgrade
- [ ] Review resource utilization trends
- [ ] Update dependencies in requirements.txt
- [ ] Security audit (credentials, network, access)

---

## Emergency Contacts & Resources

### Documentation
- Airflow 2.10.4: https://airflow.apache.org/docs/apache-airflow/2.10.4/
- Kedro: https://kedro.readthedocs.io/
- CeleryExecutor: https://airflow.apache.org/docs/apache-airflow/stable/executor/celery.html

### Key Files
- DAG: `app-ml/dags/airflow_dag.py`
- Docker Compose: `app-ml/docker-compose.yaml`
- Dockerfile: `app-ml/Dockerfile`
- Credentials: `app-ml/conf/docker/credentials.yml`
- Catalog: `app-ml/conf/base/catalog.yml`

### Troubleshooting Docs
- `app-ml/docs/fixes/AIRFLOW_2_10_4_SUCCESS.md`
- `AIRFLOW_INTEGRATION_COMPLETE.md`
- `app-ml/docs/fixes/CURRENT_STATUS.md`

---

## Quick Troubleshooting Decision Tree

```
Pipeline Not Running?
├─ DAG not visible in UI?
│  ├─ Check syntax: python /opt/airflow/dags/airflow_dag.py
│  └─ Restart scheduler: docker-compose restart airflow-scheduler
│
├─ Tasks stuck in "queued"?
│  ├─ Check worker: docker-compose ps airflow-worker
│  └─ Check Celery: docker-compose logs airflow-worker
│
├─ Tasks failing?
│  ├─ Check task logs in Airflow UI
│  ├─ Test task: airflow tasks test <dag> <task> <date>
│  └─ Check credentials: conf/docker/credentials.yml
│
└─ Data not accessible?
   ├─ Check MinIO: http://localhost:9001
   ├─ Verify bucket exists: mc ls myminio/demand-forecasting/
   └─ Check credentials in catalog.yml
```

---

**End of Quick Reference**

For detailed architecture and integration details, see:
- `AIRFLOW_INTEGRATION_COMPLETE.md`
- `app-ml/docs/fixes/AIRFLOW_2_10_4_SUCCESS.md`
