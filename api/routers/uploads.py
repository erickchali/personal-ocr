import logging

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from api.ingestion import already_ingested, digest_of, ingest_pdf
from api.schemas import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

MAX_BYTES = 20 * 1024 * 1024


@router.post("", response_model=UploadResponse, status_code=202)
async def upload_statement(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> UploadResponse:
    """Accept a statement PDF and queue it for extraction.

    Extraction takes 20-40s, far too long to hold a request open, so it runs after the
    response. The duplicate check is the exception: it is one indexed lookup, so doing it
    inline lets a repeat upload get a real answer instead of a hopeful "accepted".
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_BYTES // 1024 // 1024}MB")

    digest = digest_of(data)
    if existing := already_ingested(digest):
        return UploadResponse(
            filename=file.filename,
            sha256=digest,
            status="duplicate",
            statement_id=existing.statement_id,
            detail=f"Already ingested as statement {existing.statement_id}",
        )

    background_tasks.add_task(ingest_pdf, file.filename, data)
    return UploadResponse(
        filename=file.filename,
        sha256=digest,
        status="accepted",
        detail="Queued for extraction; poll /statements?status=pending",
    )
