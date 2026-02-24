from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """The strict state definition for the UrbanFlow AI Multi-Agent Chatbot.

    Attributes:
        messages: The conversation history, managed by the add_messages reducer.
        user_auth_token: The validated Argon2-backed API key injected securely via FastAPI.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    user_auth_token: str
    remaining_steps: int
