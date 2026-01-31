# Suppress verbose logging warnings
import logging
import warnings

# Suppress Kedro documentation registration warnings
logging.getLogger("kedro.io.docs_decorators").setLevel(logging.ERROR)

# Suppress Great Expectations metric registration warnings
logging.getLogger("great_expectations.core.metric_registry").setLevel(logging.ERROR)

# Suppress closure warnings (harmless)
warnings.filterwarnings(
    "ignore", message=".*Skipping registering function.*because it is a closure.*"
)
warnings.filterwarnings("ignore", message=".*Multiple declarations of metric.*")

# Set a cleaner logging level for the system
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
