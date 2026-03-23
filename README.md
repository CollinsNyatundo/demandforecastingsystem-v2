# UrbanFlow Intelligence: Demand Forecasting System v2

[![CI/CD Pipeline](https://github.com/CollinsNyatundo/demandforecastingsystem-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/CollinsNyatundo/demandforecastingsystem-v2/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Powered by Kedro](https://img.shields.io/badge/powered_by-kedro-ffc900?logo=kedro)](https://kedro.org)

UrbanFlow Intelligence is a production-grade MLOps ecosystem designed for high-precision demand forecasting. It integrates advanced machine learning engineering with automated orchestration and real-time monitoring to provide a robust solution for urban mobility and logistics optimization.

## 🏛️ System Architecture & Deep Dive

The system is architected as a decoupled, multi-tier environment:

### 1. Data Engineering & ML Pipeline (`app-ml`)
Powered by **Kedro**, the pipeline implements a rigorous transformation process:
- **Data Ingestion & Validation**: Uses **Pandera** for schema enforcement and data quality checks (`data_processing/nodes.py`).
- **Feature Engineering**: Automated extraction of temporal features (hour, day of week, season) and creation of demand lags (1h, 2h, 22h, 23h) based on autocorrelation analysis.
- **Modeling Strategy**: A competitive ensemble approach comparing **CatBoost**, **XGBoost**, and **LightGBM**.
- **Optimization**: **Optuna** Bayesian optimization with persistence to a PostgreSQL backend, allowing trials to resume across pipeline runs.
- **Explainability**: SHAP integration provides per-prediction transparency.

### 2. Orchestration & MLOps Infrastructure
- **Apache Airflow**: Manages complex DAGs including `automated_drift_detection_retraining`. It features conditional branching to trigger retraining only when statistical drift (measured via **Evidently**) exceeds pre-defined thresholds.
- **Experiment Tracking**: **MLflow** logs over 15 metrics (RMSE, MAE, MAPE), 8 parameters, and 12 tags per run, providing a complete audit trail.
- **Object Storage**: **MinIO** serves as the unified data lake for raw inputs, intermediate artifacts, and model binaries.

### 3. Intelligence Dashboard (`app-ui`)
A sophisticated **Dash/Streamlit** interface (UrbanFlow Intelligence) featuring:
- **Multi-page Routing**: Dedicated views for forecast analysis, system health, and drift reporting.
- **Grok AI Integration**: A floating AI chat widget that uses Server-Sent Events (SSE) to provide real-time assistance based on the current page context.
- **Operational Health**: Real-time integration with backend monitoring metrics.

## 🚀 Key Technical Features

- **Drift-Aware Retraining**: Automated detection of statistical shifts in production data triggers retraining workflows via Airflow `BranchPythonOperator`.
- **Memory Optimized**: Vectorized feature engineering and numeric downcasting for handling large datasets efficiently.
- **High Availability**: Docker profiles (`linux-host`, `celery`, `clearml`) for scaling from local dev to production clusters.
- **Security-First**: Integrated **Bandit** and **Safety** scanning in the CI/CD pipeline.

## 🛠️ Tech Stack & Requirements

- **Languages**: Python 3.9+, Bash, SQL
- **Core Frameworks**: Kedro 1.1.1, Apache Airflow 2.x, Dash, Flask
- **Machine Learning**: CatBoost 1.2.8, XGBoost 2.0+, LightGBM 4.0+, Optuna 4.3.0, SHAP 0.50.0
- **Storage & Monitoring**: MinIO, MLflow, ClearML, Prometheus, Grafana, PostgreSQL

## 📦 Deployment & Setup

### Environment Configuration
```bash
# Clone and navigate
git clone https://github.com/CollinsNyatundo/demandforecastingsystem-v2.git
cd demandforecastingsystem-v2

# Setup environment
cp app-ml/.env.example app-ml/.env
```

### Starting the Stack
The system uses Docker Compose with profiles for granular control:
```bash
# Start core services
docker compose -f app-ml/docker-compose.yml up -d

# Start with monitoring and experiment tracking
docker compose --profile linux-host --profile clearml up -d
```

---
*Developed by Collins Nyatundo (Machine Learning Engineer)*
