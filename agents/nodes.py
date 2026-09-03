from typing import Literal

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from agents.graph_state import FinancialAssistantState
from agents.llm import get_llm
from db.database import DATABASE_READ_URL

router_llm = get_llm("router")
query_llm = get_llm("query")
respond_llm = get_llm("respond")


read_only_db = SQLDatabase.from_uri(DATABASE_READ_URL)
# query_llm, not router_llm: the toolkit's query-checker writes SQL itself.
toolkit = SQLDatabaseToolkit(db=read_only_db, llm=query_llm)
sql_tools = toolkit.get_tools()

QUERY_SYSTEM_PROMPT = (
    "You are a financial data analyst. You have access to tools that let you inspect "
    "database schema and run SQL queries against a PostgreSQL database containing "
    "credit card statements and transactions.\n\n"
    "Rules:\n"
    "- Only generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, "
    "TRUNCATE, or any write/modify operations.\n"
    "- Always inspect the schema before writing a query.\n"
    "- Use proper date functions (EXTRACT, TO_CHAR) for date columns.\n"
    "- Format monetary amounts with 2 decimal places.\n"
    "- If a query fails, read the error and try a corrected query."
)


class IntentClassification(BaseModel):
    """Classify user intent into one of two categories."""

    # Literal, not str: this constrains the structured-output schema itself, so the model
    # cannot return a value route_by_intent would silently drop into the chat branch.
    intent: Literal["query", "chat"] = Field(
        description=(
            'The user intent. "query" when the user asks about their financial data '
            '(spending, balances, transactions); "chat" for general conversation, '
            "greetings, or help."
        )
    )


def router_node(state: FinancialAssistantState) -> dict:
    """Classify the user's intent from their last message."""
    last_message = state["messages"][-1]
    classifier = router_llm.with_structured_output(IntentClassification)
    result = classifier.invoke(
        f"Classify this user message as either query or chat.\n\nMessage: {last_message.content}"
    )
    return {"intent": result.intent}


def query_node(state: FinancialAssistantState) -> dict:
    llm_with_tools = query_llm.bind_tools(sql_tools)
    messages = [SystemMessage(content=QUERY_SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def respond_node(state: FinancialAssistantState) -> dict:
    """Generate a conversational response using the full message history."""
    response = respond_llm.invoke(state["messages"])
    return {"messages": [response]}
