from fastapi import APIRouter, HTTPException, Query

from db.cruds import approve_statement, get_all_statements, get_statement
from db.schemas import StatementDetailResponse, StatementListItem

router = APIRouter(prefix="/statements", tags=["statements"])


@router.get("", response_model=list[StatementListItem])
def list_statements(
    status: str | None = Query(default=None, description="Filter by status, e.g. 'pending'"),
) -> list[StatementListItem]:
    return get_all_statements(status=status)


@router.get("/{statement_id}", response_model=StatementDetailResponse)
def read_statement(statement_id: int) -> StatementDetailResponse:
    found = get_statement(statement_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return found


@router.post("/{statement_id}/approve", response_model=StatementListItem)
def approve(statement_id: int) -> StatementListItem:
    """The human-in-the-loop gate — the async stand-in for the graph's old interrupt()."""
    updated = approve_statement(statement_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return updated
