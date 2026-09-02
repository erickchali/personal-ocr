from typing import Literal

from pydantic import BaseModel


class IngestResult(BaseModel):
    """Outcome of pushing one PDF through the ingestion pipeline."""

    statement_id: int
    status: str
    created: bool
    # Which rung of the idempotency ladder caught it, if any.
    reason: Literal["created", "duplicate_file", "duplicate_statement"]
