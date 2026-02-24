import pytest
from langchain_core.messages import HumanMessage
from demand_forecasting.serving.chat.agents import workflow

@pytest.mark.asyncio
async def test_supervisor_graph_compilation_and_schema():
    """Verify that the supervisor graph compiles statelessly and validates the custom AgentState schema."""
    
    # Compile statelessly (no Redis checkpointer) to simulate isolated unit environments
    app = workflow.compile(checkpointer=False)
    
    assert app is not None
    # Validate the injected workers exist natively in the graph
    node_names = list(app.nodes.keys())
    assert "analytics_worker" in node_names
    assert "pipeline_worker" in node_names
    assert "storage_worker" in node_names

@pytest.mark.asyncio
async def test_agent_state_schema_retains_auth_token():
    """Verify the AgentState TypedDict schema explicitly supports user_auth_token injection for middleware."""
    from demand_forecasting.serving.chat.state import AgentState
    from typing import get_type_hints
    
    hints = get_type_hints(AgentState)
    assert "user_auth_token" in hints
    assert hints["user_auth_token"] == str
