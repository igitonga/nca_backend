from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.utils.jwt import verify_token


async def get_current_user(
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_token),
):
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = User.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def require_admin_role(current_user: User = Depends(get_current_user)):
    # TODO: User model has no `role` column yet — admin endpoints are
    # disabled until the role column + migration are added (see Section 3
    # of the review). Reject unconditionally so behavior is consistent.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin role required for this operation",
    )
