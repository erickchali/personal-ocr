from fastapi import APIRouter

from db.cruds import get_metrics
from db.schemas import MetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=MetricsResponse)
def read_metrics() -> MetricsResponse:
    return get_metrics()
