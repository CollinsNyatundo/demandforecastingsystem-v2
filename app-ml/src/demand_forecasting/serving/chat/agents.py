from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from demand_forecasting.serving.chat.state import AgentState
from demand_forecasting.serving.chat.tools import (
    check_airflow_dag_status,
    read_minio_object,
    search_mlflow_runs,
)

import os

# Core LLM initialized for the backend
# Relies on GROQ_API_KEY environment variable injected via Docker
if "GROQ_API_KEY" not in os.environ:
    # Provide a dummy key for pytest or linting
    os.environ["GROQ_API_KEY"] = "dummy_test_key_for_pytest_bypass"

model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# -------------------------------------------------------------------------
# Worker Agents
# -------------------------------------------------------------------------

analytics_worker = create_react_agent(
    model=model,
    tools=[search_mlflow_runs],
    name="analytics_worker",
    prompt="You are an MLOps analytics expert. Use the search_mlflow_runs tool to fetch model performance metrics and help the user analyze them."
)

pipeline_worker = create_react_agent(
    model=model,
    tools=[check_airflow_dag_status],
    name="pipeline_worker",
    prompt="You are a data engineering pipeline specialist. Use the check_airflow_dag_status tool to examine Airflow DAG execution states."
)

storage_worker = create_react_agent(
    model=model,
    tools=[read_minio_object],
    name="storage_worker",
    prompt="You are an infrastructure storage expert. Use the read_minio_object tool to inspect CSV datasets or raw debug logs residing in MinIO buckets."
)

# -------------------------------------------------------------------------
# Orchestrating Supervisor
# -------------------------------------------------------------------------

# The orchestrator dynamically builds the Command(goto=...) framework internally 
workflow = create_supervisor(
    [analytics_worker, pipeline_worker, storage_worker],
    model=model,
    prompt=(
        "You are the UrbanFlow AI Supervisor. Your job is to triage user requests to the correct specialized worker.\n"
        "- For MLflow metrics and model performance, use analytics_worker.\n"
        "- For Airflow pipelines and DAG execution, use pipeline_worker.\n"
        "- For raw data logs or CSVs in S3/MinIO, use storage_worker.\n"
        "If a request spans multiple areas, route them sequentially to gather all necessary context before drafting your final reply to the user."
    ),
    state_schema=AgentState,
)
