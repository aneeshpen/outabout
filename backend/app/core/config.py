"""Centralised application configuration.

Every tunable value (database URL, JWT secret, CORS origins, storage
credentials) is read from the environment / a local ``.env`` file so that no
credential is ever hard-coded in the source tree.

This replaces the hard-coded connection string that used to live in
``app/utils/database.py`` and the ad-hoc ``os.getenv`` calls that were spread
across the old modules.
"""

import json
from functools import lru_cache
from typing import Annotated, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -----------------------------------------------------
    PROJECT_NAME: str = "IMSEC Hostel Pass Manager API"
    API_AUTHOR: str = "Abhilash Singh"

    # --- Database --------------------------------------------------------
    # Production target is the PostgreSQL instance that the Prisma schema was
    # pushed to (``postgresql+psycopg2://user:pass@host:5432/db``).  The SQLite
    # default keeps local development and the test-suite self-contained.
    DATABASE_URL: str = "sqlite:///./digipass.db"

    # When true, SQLAlchemy emits ``CREATE TABLE IF NOT EXISTS`` for the mapped
    # models on start-up.  It never drops or alters anything, so it is safe to
    # leave on for SQLite; against the managed PostgreSQL database the tables
    # already exist and the statements are no-ops.
    CREATE_TABLES_ON_STARTUP: bool = True

    # --- Security --------------------------------------------------------
    SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 20
    BCRYPT_ROUNDS: int = 10

    # --- CORS ------------------------------------------------------------
    # The Vite dev server runs over HTTPS (vite plugin-basic-ssl) so both
    # schemes are allowed by default.
    # ``NoDecode`` keeps pydantic-settings from trying to JSON-parse the
    # value, so a plain comma-separated .env entry reaches the validator
    # below.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "https://localhost:5173",
        "http://127.0.0.1:5173",
        "https://127.0.0.1:5173",
        "http://localhost:3000",
        "https://localhost:3000",
    ]

    # --- Admin / user provisioning ---------------------------------------
    DEFAULT_PASSWORD: str = "digipass@123"

    # --- Student photo storage -------------------------------------------
    # If the Supabase variables are set, photos are uploaded to the Supabase
    # storage bucket and the guard screen receives a short-lived signed URL
    # (identical to the Express behaviour).  Otherwise photos are stored on the
    # local filesystem and served from ``/uploads``.
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_BUCKET: str = "student-photos"
    SIGNED_URL_TTL_SECONDS: int = 60
    LOCAL_UPLOAD_DIR: str = "uploads"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Accept either ``http://a,http://b`` or a JSON array in the .env."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
