import os

import redis.asyncio as redis
from langgraph.checkpoint.memory import MemorySaver

from demand_forecasting.serving.chat.agents import workflow

# Configure Redis connection
redis_password = os.environ.get("REDIS_PASSWORD", "")
redis_auth = f":{redis_password}@" if redis_password else ""
redis_url = os.environ.get("REDIS_URL", f"redis://{redis_auth}redis:6379/0")
r = redis.Redis.from_url(redis_url)

# Setup Checkpointer with strict TTL (1440 minutes = 24 hours)
# designed to prevent unbounded orphaned session memory ballooning
ttl_config = {"default_ttl": 1440, "refresh_on_read": True}

# The redis_client must be passed as a keyword argument according to the package signature
checkpointer = MemorySaver()

# Compile the overarching Multi-Agent Supervisor framework
app = workflow.compile(checkpointer=checkpointer)
