from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class MetricEventCreate(BaseModel):
    app_token_id: int = Field(..., gt=0)
    event_type: str = Field(..., min_length=1, max_length=255)
    session_id: str = Field(..., min_length=1, max_length=255)
    device_id: str = Field(..., min_length=1, max_length=255)
    value: Optional[str] = None
    unit: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class MetricEventResponse(BaseModel):
    id: int
    app_token_id: int
    event_type: str
    session_id: str
    device_id: str
    value: Optional[str] = None
    unit: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
