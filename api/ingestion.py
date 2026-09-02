"""Statement ingestion: bytes in, persisted statement out.

Plain sequential Python — no DAG engine, no scheduler. The only interesting property is
where the checks sit relative to the LLM call:

    sha256 -> already stored?  -> return                    (free)
                     |no
                  MinIO -> PyPDF -> LLM extract -> save     (expensive)
                                                     |
                                       IntegrityError -> already stored

Because the hash check short-circuits before extraction, re-running a lost or retried job
costs nothing. That is what makes a fire-and-forget background task safe here.
"""

import hashlib
import logging
from io import BytesIO

from pypdf import PdfReader

from agents.extraction import extract_structured_data
from api.schemas import IngestResult
from api.storage import ensure_bucket, object_key_for, put_pdf
from db.cruds import DuplicateStatementError, attach_source, save_statement, statement_by_hash

logger = logging.getLogger(__name__)


def extract_pdf_text(data: bytes) -> str:
    """Read PDF text from memory, keeping the page markers the extraction prompt expects."""
    reader = PdfReader(BytesIO(data))
    pages = (f"--- Page {i} ---\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages, 1))
    return "\n\n".join(pages)


def digest_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def already_ingested(digest: str) -> IngestResult | None:
    """The cheap rung, on its own so callers can check before queueing work.

    Costs one indexed lookup, which is why POST /uploads runs it inside the request
    instead of deferring it — a duplicate gets an accurate answer immediately.
    """
    found = statement_by_hash(digest)
    if not found:
        return None
    return IngestResult(statement_id=found.id, status=found.status, created=False, reason="duplicate_file")


def ingest_pdf(filename: str, data: bytes) -> IngestResult:
    """Run one PDF through the pipeline. Safe to call repeatedly with the same bytes."""
    digest = digest_of(data)

    already = already_ingested(digest)
    if already:
        logger.info("%s already ingested as statement %s; skipping extraction", filename, already.statement_id)
        return already

    ensure_bucket()
    key = put_pdf(object_key_for(digest), data)
    logger.info("stored %s at %s", filename, key)

    statement = extract_structured_data(extract_pdf_text(data))

    try:
        statement_id = save_statement(statement, object_key=key, file_sha256=digest)
    except DuplicateStatementError as exc:
        # Same statement reached us as a different file — a re-download, or a race.
        # Teach the existing row this file's hash so a repeat upload skips extraction.
        attach_source(exc.statement_id, key, digest)
        logger.info("%s duplicates existing statement %s", filename, exc.statement_id)
        return IngestResult(
            statement_id=exc.statement_id,
            status=exc.status,
            created=False,
            reason="duplicate_statement",
        )

    logger.info("ingested %s as statement %s (pending review)", filename, statement_id)
    return IngestResult(statement_id=statement_id, status="pending", created=True, reason="created")
