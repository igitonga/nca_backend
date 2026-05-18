from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.metricEvent import MetricEventCreate, MetricEventResponse
from app.services.metricEvent import MetricEventService

router = APIRouter(prefix="/metric-events", tags=["metric-events"])


@router.post(
    "",
    response_model=MetricEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_metric_event(
    payload: MetricEventCreate,
    db: Session = Depends(get_db),
):
    service = MetricEventService(db)
    return service.create_event(
        app_token_id=payload.app_token_id,
        event_type=payload.event_type,
        session_id=payload.session_id,
        device_id=payload.device_id,
        value=payload.value,
        unit=payload.unit,
        attributes=payload.attributes,
    )
