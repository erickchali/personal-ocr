"""FastAPI app for uploads and statement data.

Deliberately has no chat route. The Next.js client talks to `langgraph dev` directly via
useStream, which already handles streaming, threads and interrupts — proxying that through
here would mean reimplementing all three.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import metrics, statements, uploads
from api.storage import ensure_bucket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the bucket on boot — cheaper than a compose init container."""
    ensure_bucket()
    yield


app = FastAPI(
    title="Personal OCR",
    description="Credit card statement ingestion and analytics",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(statements.router)
app.include_router(metrics.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
