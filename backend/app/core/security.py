"""Password hashing and JWT helpers.

The Express backend used ``bcrypt`` (cost 10) for passwords and
``jsonwebtoken`` (HS256, 20 minute expiry, payload ``{"sub": user_id}``) for
access tokens.  Both are reproduced here with the ``bcrypt`` and ``PyJWT``
packages so that password hashes and tokens stay interchangeable between the
two implementations: an existing ``$2b$10$...`` hash in the database still
verifies, and a token minted here has exactly the same payload shape.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


# --- Passwords -----------------------------------------------------------

def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        # Malformed / non-bcrypt hash stored in the column.
        return False


# --- Access tokens -------------------------------------------------------

def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Return the subject (college id) of a valid token, else ``None``."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except InvalidTokenError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None
