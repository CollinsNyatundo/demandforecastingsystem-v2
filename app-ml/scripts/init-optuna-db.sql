-- Initialize Optuna database for study persistence
-- This script creates the optuna database and user for the Enhanced DAG

-- Create optuna database
CREATE DATABASE optuna;

-- Create optuna user (optional - you can use airflow user)
-- CREATE USER optuna_user WITH PASSWORD 'optuna_password';

-- Grant permissions
-- GRANT ALL PRIVILEGES ON DATABASE optuna TO optuna_user;

-- For simplicity, we'll use the airflow user for optuna
-- Grant permissions to airflow user
GRANT ALL PRIVILEGES ON DATABASE optuna TO airflow;

-- Create MLflow database
CREATE DATABASE mlflow;

-- Grant permissions to airflow user for MLflow
GRANT ALL PRIVILEGES ON DATABASE mlflow TO airflow;
