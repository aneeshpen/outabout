"""FastAPI application entry point.

Responsibilities kept here, and nowhere else:

* build the ``FastAPI`` instance,
* register middleware (CORS, the no-store cache headers the Express server
  sent),
* mount the local photo directory,
* register the routers,
* create the mapped tables on start-up when that is enabled.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from app.core.config import settings
from app.dependencies.database import engine
from app.models import Base
from app.routers import admin, login, passes, user, verification

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.CREATE_TABLES_ON_STARTUP:
        # Emits CREATE TABLE IF NOT EXISTS only; never drops or alters.
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    description=(
        "Hostel leave / market pass management API. Replaces the original "
        "Node.js + Express backend."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_store_headers(request: Request, call_next):
    """Pass data must never be served from a cache (same headers as before)."""
    response = await call_next(request)
    response.headers["X-Author"] = settings.API_AUTHOR
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, private"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# Local fallback for student photos when Supabase is not configured.
_upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")

app.include_router(login.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(passes.router)
app.include_router(verification.router)


@app.get("/", tags=["Health"])
def root() -> dict:
    return {"message": settings.PROJECT_NAME, "status": "running"}
