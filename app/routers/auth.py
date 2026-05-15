from fastapi import APIRouter, HTTPException
from app.schemas.user import UserCreate, UserLogin, Token
from app.services.user import create_user, login_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserCreate)
def createUser(user: UserCreate):
    user = create_user(user)
    return user

@router.post("/login", response_model=Token)
def login(user: UserLogin):
    auth = login_user(user.email, user.password)
    return auth