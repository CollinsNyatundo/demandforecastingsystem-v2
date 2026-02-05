#!/bin/bash
# =============================================================================
# MULTIPLE DATABASES INITIALIZATION SCRIPT
# =============================================================================
# Creates airflow, mlflow, and optuna databases with proper permissions
#
# Required environment variables:
#   - POSTGRES_USER: PostgreSQL admin user
#   - POSTGRES_DB: PostgreSQL default database
#   - MLFLOW_DB_PASSWORD: Password for mlflow_user (required)
#   - OPTUNA_DB_PASSWORD: Password for optuna_user (required)
# =============================================================================

set -e

# Validate required environment variables
if [ -z "$MLFLOW_DB_PASSWORD" ]; then
    echo "ERROR: MLFLOW_DB_PASSWORD environment variable is not set"
    exit 1
fi

if [ -z "$OPTUNA_DB_PASSWORD" ]; then
    echo "ERROR: OPTUNA_DB_PASSWORD environment variable is not set"
    exit 1
fi

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER"; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "PostgreSQL is ready - creating databases..."

# Create databases
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create MLflow database
    CREATE DATABASE mlflow;
    
    -- Create Optuna database  
    CREATE DATABASE optuna;
    
    -- Create users for each service with passwords from environment
    CREATE USER mlflow_user WITH PASSWORD '$MLFLOW_DB_PASSWORD';
    CREATE USER optuna_user WITH PASSWORD '$OPTUNA_DB_PASSWORD';
    
    -- Grant permissions
    GRANT ALL PRIVILEGES ON DATABASE mlflow TO mlflow_user;
    GRANT ALL PRIVILEGES ON DATABASE optuna TO optuna_user;
    
    -- Grant airflow user access to all databases
    GRANT ALL PRIVILEGES ON DATABASE mlflow TO airflow;
    GRANT ALL PRIVILEGES ON DATABASE optuna TO airflow;
    
    -- Create schemas for better organization
    \c mlflow;
    CREATE SCHEMA IF NOT EXISTS mlflow_schema;
    GRANT ALL ON SCHEMA mlflow_schema TO mlflow_user;
    GRANT ALL ON SCHEMA mlflow_schema TO airflow;
    
    \c optuna;
    CREATE SCHEMA IF NOT EXISTS optuna_schema;
    GRANT ALL ON SCHEMA optuna_schema TO optuna_user;
    GRANT ALL ON SCHEMA optuna_schema TO airflow;
    
    \c airflow;
    CREATE SCHEMA IF NOT EXISTS airflow_schema;
    GRANT ALL ON SCHEMA airflow_schema TO airflow;
    
    -- Set default schemas for users
    ALTER USER mlflow_user SET search_path TO mlflow_schema, public;
    ALTER USER optuna_user SET search_path TO optuna_schema, public;
    ALTER USER airflow SET search_path TO airflow_schema, public;
    
    -- Display created databases
    \c postgres;
    \l
EOSQL

echo "Multiple databases created successfully!"
echo "Databases created:"
echo "  - airflow (for Airflow metadata)"
echo "  - mlflow (for MLflow tracking)"  
echo "  - optuna (for Optuna study persistence)"
echo ""
echo "Users created:"
echo "  - mlflow_user (password set from MLFLOW_DB_PASSWORD)"
echo "  - optuna_user (password set from OPTUNA_DB_PASSWORD)"
echo "  - airflow (password from POSTGRES_PASSWORD)"
echo ""
echo "Schemas created for better isolation:"
