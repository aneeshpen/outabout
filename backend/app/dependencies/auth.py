"""Authentication / authorisation dependencies.

The Express backend expressed this as middleware (``getCurrentUser`` and
``requireRole([...])``).  In FastAPI the equivalent is a dependency: the
router declares what it needs and FastAPI resolves it before the handler body
runs, so an unauthenticated or under-privileged request never reaches the
service layer.
"""

from typing import Iterable, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.dependencies.database import get_db
from app.models import Role, User
from app.repositories.user_repository import UserRepository

# ``auto_error=False`` so a missing header produces our own 401 payload
# (``{"detail": "Recheck your credentials"}``) instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Recheck your credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise CREDENTIALS_EXCEPTION

    college_id = decode_access_token(credentials.credentials)
    if college_id is None:
        raise CREDENTIALS_EXCEPTION

    user = UserRepository(db).get_by_id(college_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # A deactivated account must not be able to keep using a token that was
    # minted before the admin soft-deleted it.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated by administrator.",
        )

    return user


def require_roles(*roles: Role | str):
    """Build a dependency that allows only the given roles."""

    allowed: List[str] = [
        role.value if isinstance(role, Role) else str(role).lower() for role in roles
    ]

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if _role_value(current_user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized",
            )
        return current_user

    return dependency


def _role_value(role: Role | str) -> str:
    return (role.value if isinstance(role, Role) else str(role)).lower()


def roles_of(user: User) -> str:
    return _role_value(user.role)


# Convenience dependencies for the role sets the application actually uses.
require_student = require_roles(Role.student)
require_warden = require_roles(Role.warden)
require_guard = require_roles(Role.guard)
require_admin = require_roles(Role.admin)
require_warden_or_admin = require_roles(Role.warden, Role.admin)


def iter_role_values(roles: Iterable[Role | str]) -> List[str]:
    return [_role_value(role) for role in roles]
