#!/bin/bash
# Database Backup Script for Demand Forecasting System
# AUDIT-M5: Database backup procedures

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/opt/airflow/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-airflow}"
POSTGRES_DB="${POSTGRES_DB:-airflow}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "============================================"
echo "Database Backup - $TIMESTAMP"
echo "============================================"

# Backup Airflow database
echo "Backing up Airflow database..."
PGPASSWORD="${POSTGRES_PASSWORD:-airflow}" pg_dump \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -F c \
    -f "$BACKUP_DIR/airflow_db_$TIMESTAMP.dump"

if [ $? -eq 0 ]; then
    echo "✅ Airflow database backup successful"
else
    echo "❌ Airflow database backup failed"
    exit 1
fi

# Backup Optuna database if exists
OPTUNA_DB="${OPTUNA_DB:-optuna}"
if PGPASSWORD="${POSTGRES_PASSWORD:-airflow}" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$OPTUNA_DB"; then
    echo "Backing up Optuna database..."
    PGPASSWORD="${POSTGRES_PASSWORD:-airflow}" pg_dump \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$OPTUNA_DB" \
        -F c \
        -f "$BACKUP_DIR/optuna_db_$TIMESTAMP.dump"
    
    if [ $? -eq 0 ]; then
        echo "✅ Optuna database backup successful"
    else
        echo "⚠️ Optuna database backup failed (non-critical)"
    fi
else
    echo "ℹ️ Optuna database not found, skipping..."
fi

# Backup MLflow database if exists
MLFLOW_DB="${MLFLOW_DB:-mlflow}"
if PGPASSWORD="${POSTGRES_PASSWORD:-airflow}" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$MLFLOW_DB"; then
    echo "Backing up MLflow database..."
    PGPASSWORD="${POSTGRES_PASSWORD:-airflow}" pg_dump \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$MLFLOW_DB" \
        -F c \
        -f "$BACKUP_DIR/mlflow_db_$TIMESTAMP.dump"
    
    if [ $? -eq 0 ]; then
        echo "✅ MLflow database backup successful"
    else
        echo "⚠️ MLflow database backup failed (non-critical)"
    fi
else
    echo "ℹ️ MLflow database not found, skipping..."
fi

# Cleanup old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete
OLD_COUNT=$(find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)
echo "ℹ️ Removed $OLD_COUNT old backup files"

# List current backups
echo ""
echo "Current backups:"
ls -lh "$BACKUP_DIR"/*.dump 2>/dev/null || echo "No backups found"

# Calculate size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
echo ""
echo "Total backup size: $TOTAL_SIZE"

echo ""
echo "============================================"
echo "Backup completed at $(date)"
echo "============================================"
