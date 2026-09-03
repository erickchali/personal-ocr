from typing import Annotated, Literal

from langchain.agents import AgentState
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class FinancialAssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Literal["query", "chat"] | None


class OCRCustomState(AgentState):
    """State for the legacy create_agent implementation in pdf_reader_agent.py."""

    files_to_process: list[str] | None = []
