from fastapi import HTTPException
from app.models.user import User
from app.db.database import get_db
from app.utils.password import Hasher
from app.utils.jwt import create_access_token

db = next(get_db())

def create_user(user):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already in use")
    
    hashed_password = Hasher.get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def login_user(email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not Hasher.verify_password(password, user.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "expiry": 3600
    }
