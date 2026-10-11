from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # Register ORM models before create_all
from backEnd.app.api import memberships
from backEnd.app.api import health, users
from backEnd.app.core.config import settings
from backEnd.app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Suitable for local development.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=[
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"
    ],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(memberships.router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Fitness Membership API",
        "docs": "/docs",
        "health": "/api/health",
    }