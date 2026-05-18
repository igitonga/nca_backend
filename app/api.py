from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.user import UserCreate, UserLogin, Token
from app.services.user import create_user, login_user

from app.routers import auth
from app.routers import metrics
from app.routers import appToken
from app.routers import metricEvent

app = FastAPI()

origins = [
    "http://localhost:5173",
    "localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router)

app.include_router(metrics.router)

app.include_router(appToken.router)

app.include_router(metricEvent.router)

@app.get("/", tags=["root"])
async def read_root() -> dict:
    return {"message": "Welcome to my backend"}


