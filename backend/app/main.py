from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine, ensure_schema, install_guards
from app.routers import audit, auth, offers, policy, recruitment, reports, students, users
from app.seed import seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("placement")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema()
    install_guards()
    if settings.seed:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
    if settings.secret_key == "dev-only-change-me":
        logger.warning("SECRET_KEY is the development default. Change it before any real deployment.")
    yield


app = FastAPI(
    title="NFSU Placement Cell",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def request_context(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
        if request.headers.get("x-requested-with") != "placement":
            return JSONResponse({"detail": "Missing request context"}, status_code=403)
    return await call_next(request)


origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(offers.router)
app.include_router(recruitment.router)
app.include_router(policy.router)
app.include_router(reports.router)
app.include_router(audit.router)
app.include_router(users.router)


@app.get("/api/health")
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    return {"status": "ok"}
