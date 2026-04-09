from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.models import CreditCardStatement


class FinancialAssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str | None
    pending_files: list[str] | None
    processed_count: int | None
    pending_statements: list[CreditCardStatement] | None
