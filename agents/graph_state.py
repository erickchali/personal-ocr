from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class FinancialAssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Literal["query", "chat"] | None
