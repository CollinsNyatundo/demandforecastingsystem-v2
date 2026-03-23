import os
import requests
import boto3
from botocore.client import Config
import mlflow
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, Field
from langchain_core.tools import tool

# -------------------------------------------------------------------------
# MinIO / S3 Storage Tool
# -------------------------------------------------------------------------

class ReadMinioObjectInput(BaseModel):
    bucket_name: str = Field(..., description="Name of the MinIO bucket (e.g., 'demand-forecasting', 'airflow-logs')")
    object_name: str = Field(..., description="The key/path to the object to read")
    lines: int = Field(100, description="Maximum number of lines to return from the file")

@tool("read_minio_object", args_schema=ReadMinioObjectInput)
def read_minio_object(bucket_name: str, object_name: str, lines: int = 100) -> str:
    """Read a text-based object (CSV, JSON, log) from MinIO storage."""
    try:
        s3_endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
        s3_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        s3_secret = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

        s3 = boto3.client(
            "s3",
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_key,
            aws_secret_access_key=s3_secret,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

        response = s3.get_object(Bucket=bucket_name, Key=object_name)
        content = response["Body"].read().decode("utf-8")
        
        # Tail the content to fit inside context windows
        content_lines = content.splitlines()
        max_lines = min(len(content_lines), lines)
        
        return "\n".join(content_lines[-max_lines:])
    except Exception as e:
        return f"Error reading object {object_name} from bucket {bucket_name}: {str(e)}"

# -------------------------------------------------------------------------
# MLflow Analytics Tool
# -------------------------------------------------------------------------

class SearchMlflowRunsInput(BaseModel):
    experiment_name: str = Field(..., description="Name of the experiment (e.g., 'Demand Forecasting')")
    max_results: int = Field(3, description="Maximum number of recent runs to return")

@tool("search_mlflow_runs", args_schema=SearchMlflowRunsInput)
def search_mlflow_runs(experiment_name: str, max_results: int = 3) -> str:
    """Search for the latest runs and metrics in an MLflow experiment."""
    try:
        client = MlflowClient()
        experiment = client.get_experiment_by_name(experiment_name)
        if not experiment:
            return f"Experiment '{experiment_name}' not found."

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            max_results=max_results,
            order_by=["start_time DESC"]
        )

        if not runs:
            return f"No runs found in experiment {experiment_name}."

        results = []
        for run in runs:
            data = {
                "run_id": run.info.run_id,
                "status": run.info.status,
                "metrics": run.data.metrics,
                "params": {k: v for k, v in run.data.params.items() if not k.startswith("system.")}
            }
            results.append(str(data))
            
        return "\n".join(results)
    except Exception as e:
        return f"Error querying MLflow: {str(e)}"

# -------------------------------------------------------------------------
# Airflow Pipeline Tool
# -------------------------------------------------------------------------

class CheckAirflowDagInput(BaseModel):
    dag_id: str = Field(..., description="The ID of the DAG (e.g., 'demand_forecasting_pipeline')")
    limit: int = Field(1, description="Number of recent DAG runs to fetch")

@tool("check_airflow_dag_status", args_schema=CheckAirflowDagInput)
def check_airflow_dag_status(dag_id: str, limit: int = 1) -> str:
    """Check the execution status of an Airflow DAG."""
    try:
        # Internal docker hostname for Airflow Webserver is airflow-webserver:8080
        airflow_url = os.environ.get("AIRFLOW_API_URL", "http://airflow-webserver:8080/api/v1")
        airflow_user = os.environ.get("AIRFLOW_USER", "Cole")
        airflow_pass = os.environ.get("AIRFLOW_PASSWORD", "admin")

        url = f"{airflow_url}/dags/{dag_id}/dagRuns?limit={limit}&order_by=-execution_date"
        response = requests.get(url, auth=(airflow_user, airflow_pass), timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            dag_runs = data.get("dag_runs", [])
            if not dag_runs:
                return f"No runs found for DAG '{dag_id}'."
                
            summaries = []
            for run in dag_runs:
                summaries.append(
                    f"Run ID: {run.get('dag_run_id')}, State: {run.get('state')}, "
                    f"Execution Date: {run.get('execution_date')}"
                )
            return "\n".join(summaries)
        elif response.status_code == 404:
            return f"DAG '{dag_id}' not found."
        else:
            return f"Error from Airflow API: {response.text}"
            
    except Exception as e:
        return f"Error connecting to Airflow API: {str(e)}"
