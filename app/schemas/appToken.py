from datetime import datetime
from pydantic import BaseModel, Field


class AppTokenCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class AppTokenCreateResponse(BaseModel):
    token: str
    token_id: int
    label: str
    created_at: datetime
