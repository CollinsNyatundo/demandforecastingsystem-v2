# Environment variables to suppress verbose warnings
# Add these to your .env file or set them before running the DAGs

# Suppress Kedro documentation warnings
KEDRO_LOGGING_CONFIG=conf/logging.yml

# Suppress Great Expectations verbose logging
GE_SUPPRESS_WARNINGS=true
GE_LOG_LEVEL=ERROR

# General Python warnings
PYTHONWARNINGS=ignore::UserWarning
PYTHONWARNINGS=ignore::DeprecationWarning
PYTHONWARNINGS=ignore::FutureWarning

# Set logging level to reduce verbosity
LOGGING_LEVEL=INFO
