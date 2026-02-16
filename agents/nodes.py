from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from agents.graph_state import FinancialAssistantState
from agents.llm import get_llm

llm = get_llm()


class IntentClassification(BaseModel):
    """Classify user intent into one of three categories."""

    intent: str = Field(
        description=(
            'The user intent. Must be one of: "upload" (user wants to process/upload '
            'PDF bank statements), "query" (user wants to ask questions about their '
            'financial data), or "chat" (general conversation, greetings, help).'
        )
    )


def router_node(state: FinancialAssistantState) -> dict:
    """Classify the user's intent from their last message."""
    last_message = state["messages"][-1]
    classifier = llm.with_structured_output(IntentClassification)
    result = classifier.invoke(
        f"Classify this user message into one of: upload, query, chat.\n\n"
        f"Message: {last_message.content}"
    )
    return {"intent": result.intent}


def upload_stub_node(state: FinancialAssistantState) -> dict:
    """Stub node for upload processing (coming in Phase 2)."""
    return {"messages": [AIMessage(content="Upload processing coming soon.")]}


def query_stub_node(state: FinancialAssistantState) -> dict:
    """Stub node for query processing (coming in Phase 3)."""
    return {"messages": [AIMessage(content="Query feature coming soon.")]}


def respond_node(state: FinancialAssistantState) -> dict:
    """Generate a conversational response using the full message history."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
