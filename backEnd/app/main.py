from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, checkins, health, memberships, users
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(memberships.router, prefix="/api")
app.include_router(checkins.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Fitness Membership API", "docs": "/docs", "health": "/api/health"}
