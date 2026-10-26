"""Student photo storage.

The Express backend pushed photos into a Supabase storage bucket and handed
the guard screen a 60-second signed URL.  That behaviour is reproduced here
over Supabase's REST API (no SDK needed).  When the Supabase variables are not
configured, photos fall back to the local ``uploads/`` directory which
``main.py`` mounts at ``/uploads`` - so the guard verification screen still
shows a photo during local development instead of silently breaking.

Only the stored *object name* ever goes into ``users.photo_url``, exactly as
before; the signed/absolute URL is generated per response.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("digipass.storage")

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _object_name(file_name: str) -> str:
    """Strip any path/URL noise so only a bare object name is stored."""
    name = file_name.strip().replace("\\", "/")
    if name.startswith("http"):
        name = name.rsplit("/", 1)[-1]
    name = name.lstrip("/").rsplit("/", 1)[-1]
    return _SAFE_NAME.sub("_", name)


def _supabase_configured() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _local_dir() -> Path:
    directory = Path(settings.LOCAL_UPLOAD_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def upload_photo(file_name: str, content: bytes, content_type: str) -> str:
    """Store a photo and return the value to persist in ``users.photo_url``."""
    object_name = _object_name(file_name)

    if _supabase_configured():
        url = (
            f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/"
            f"{settings.SUPABASE_BUCKET}/{object_name}"
        )
        response = httpx.post(
            url,
            content=content,
            headers={
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": content_type or "application/octet-stream",
                "x-upsert": "true",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return object_name

    (_local_dir() / object_name).write_bytes(content)
    return object_name


def build_photo_url(stored_value: Optional[str]) -> Optional[str]:
    """Turn a stored object name into a URL the browser can load."""
    if not stored_value:
        return None
    object_name = _object_name(stored_value)

    if _supabase_configured():
        try:
            response = httpx.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/sign/"
                f"{settings.SUPABASE_BUCKET}/{object_name}",
                json={"expiresIn": settings.SIGNED_URL_TTL_SECONDS},
                headers={
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            signed = response.json().get("signedURL") or response.json().get(
                "signedUrl"
            )
            if not signed:
                return None
            return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed}"
        except Exception as exc:  # network / auth failure must not 500 the gate
            logger.error("[Supabase] Error generating signed URL: %s", exc)
            return None

    if (_local_dir() / object_name).exists():
        return f"/uploads/{object_name}"
    return None
