# Demand Forecasting System v2

An end-to-end MLOps pipeline for demand forecasting, built with Kedro, Airflow, and MLflow. This system implements a robust machine learning lifecycle including data engineering, model training, optimization with Optuna, and automated deployment.

## 🏗️ System Architecture

The project is structured into two main components:
- **`app-ml`**: The core machine learning engine.
  - **Kedro Pipelines**: Managed data processing, feature engineering, and modeling.
  - **Airflow DAGs**: Orchestrated workflow scheduling.
  - **MLflow & ClearML**: Experiment tracking and model versioning.
  - **MinIO**: S3-compatible object storage for data and logs.
  - **Monitoring**: Prometheus and Grafana integration for system health and model drift.
- **`app-ui`**: A Streamlit/Dash-based dashboard for visualizing forecasts and system status.

## 🚀 Key Features

- **Advanced Modeling**: High-performance forecasting using CatBoost, XGBoost, and LightGBM.
- **Automated Hyperparameter Tuning**: Integrated Optuna for model optimization.
- **Explainable AI**: Integrated SHAP for feature importance and model transparency.
- **Scalable Infrastructure**: Containerized with Docker Compose, featuring high-availability profiles.
- **CI/CD Integration**: Automated testing and documentation updates via GitHub Actions.

## 🛠️ Tech Stack

- **Frameworks**: Kedro, Apache Airflow
- **ML Libraries**: CatBoost, XGBoost, LightGBM, Scikit-learn, Optuna, SHAP
- **MLOps**: MLflow, ClearML, MinIO
- **Monitoring**: Prometheus, Grafana
- **Infrastructure**: Docker, Nginx

## 📦 Getting Started

### Prerequisites
- Docker and Docker Compose
- Python 3.9+ (for local development)

### Deployment
1. Clone the repository and navigate to the root directory.
2. Initialize environment variables:
   ```bash
   cp app-ml/.env.example app-ml/.env
   ```
3. Start the full stack using Docker:
   ```bash
   docker compose up -d
   ```

### Accessing Services
- **App UI**: `http://localhost:8050`
- **Airflow**: `http://localhost:8081`
- **MLflow**: `http://localhost:5000`
- **Grafana**: `http://localhost:3000`

## 📖 Documentation
Detailed documentation is available in the `app-ml/analysis_reports` and various `.md` guides within the `app-ml` directory.
