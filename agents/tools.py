from langchain_core.tools import tool

from db.cruds import get_all_statements, get_statement


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
