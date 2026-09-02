from typing import Literal

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """What POST /uploads returns before extraction has necessarily run."""

    filename: str
    sha256: str
    # "accepted" means queued for background extraction; "duplicate" was resolved inline.
    status: Literal["accepted", "duplicate"]
    statement_id: int | None = None
    detail: str


class IngestResult(BaseModel):
    """Outcome of pushing one PDF through the ingestion pipeline."""

    statement_id: int
    status: str
    created: bool
    # Which rung of the idempotency ladder caught it, if any.
    reason: Literal["created", "duplicate_file", "duplicate_statement"]
