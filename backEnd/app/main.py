from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, checkins, health, memberships, users
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.3.0")

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
app.include_router(checkins.scanner_router, prefix="/api")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Fitness Membership API", "docs": "/docs", "health": "/api/health"}
