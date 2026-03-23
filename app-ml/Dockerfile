FROM apache/airflow:2.10.4

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    apt-get autoremove -yqq --purge && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for warning suppression
ENV KEDRO_LOGGING_CONFIG=conf/logging.yml
ENV GE_SUPPRESS_WARNINGS=true
ENV GE_LOG_LEVEL=ERROR
ENV PYTHONWARNINGS=ignore::UserWarning,ignore::DeprecationWarning,ignore::FutureWarning
ENV LOGGING_LEVEL=INFO
ENV GREAT_EXPECTATIONS_LOG_LEVEL=ERROR
ENV KEDRO_LOG_LEVEL=ERROR

USER airflow

# Upgrade pip first for better dependency resolution
RUN pip install --upgrade pip

# Copy requirements and install dependencies
# Install requirements in order to avoid conflicts
COPY requirements*.txt /requirements/
# Install core requirements first
RUN pip install --default-timeout=1000 --no-cache-dir --upgrade -r /requirements/requirements.core.txt
# Install framework requirements (includes kedro)
RUN pip install --default-timeout=1000 --no-cache-dir --upgrade -r /requirements/requirements.framework.txt
# Install ML libraries
RUN pip install --default-timeout=1000 --no-cache-dir --upgrade -r /requirements/requirements.ml.txt
# Install Airflow requirements
RUN pip install --default-timeout=1000 --no-cache-dir --upgrade -r /requirements/requirements.airflow.txt
# Install main requirements last (may override versions)
RUN pip install --default-timeout=1000 --no-cache-dir --upgrade -r /requirements/requirements.txt

# Note: s3fs and pandera are already installed via requirements files above — no extra step needed

# Copy application code
COPY . /opt/airflow
WORKDIR /opt/airflow

# Ensure PYTHONPATH includes our source directory
ENV PYTHONPATH=/opt/airflow/src

USER airflow
