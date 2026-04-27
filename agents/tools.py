from langchain_core.tools import tool

from agents.embeddings import embed_text
from db.cruds import (
    get_all_statements,
    get_statement,
    search_transactions_by_embedding,
)


@tool
def fetch_statement_transactions(statement_id: int) -> str | None:
    """
    Fetch a specific credit card statement and all its transactions by
    statement ID.

    Args:
        statement_id: The numeric ID of the statement to retrieve

    """
    statement_data = get_statement(statement_id=statement_id)
    if statement_data:
        return statement_data.model_dump_json()
    return None


@tool
def fetch_all_statements() -> str | None:
    """
    List all available credit card statements with their summary info
    (balances, dates, card details).
    """
    statement_data = get_all_statements()
    if statement_data:
        return "[" + ",".join(s.model_dump_json() for s in statement_data) + "]"
    return None


@tool
def search_transactions(query: str, limit: int = 10) -> str:
    """Semantic search over transaction descriptions.

    Use this when the user asks about spending in a fuzzy / categorical way
    (e.g. "food delivery", "streaming services", "gas stations") and exact
    string matching on the description would miss relevant transactions.
    For questions that need aggregates, totals, or filters on dates/amounts,
    prefer the SQL tools instead.

    Args:
        query: Natural language description of what to find.
        limit: Max number of nearest matches to return (default 10).
    """
    vector = embed_text(query)
    matches = search_transactions_by_embedding(vector, limit=limit)
    if not matches:
        return "[]"
    return "[" + ",".join(m.model_dump_json() for m in matches) + "]"
