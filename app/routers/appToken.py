from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.appToken import AppTokenCreate, AppTokenCreateResponse
from app.services.appToken import AppTokenService

router = APIRouter(prefix="/app-tokens", tags=["app-tokens"])


@router.post(
    "",
    response_model=AppTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_app_token(payload: AppTokenCreate, db: Session = Depends(get_db)):
    service = AppTokenService(db)
    return service.generate_token(label=payload.label)
