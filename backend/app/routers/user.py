"""``/user`` - direct user records management (admin only)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models import User
from app.schemas.user import UserCreate, UserPublic
from app.services.user_service import UserService

router = APIRouter(prefix="/user", tags=["User"])


@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    """Create a user from a JSON body with an explicit password.

    ``response_model=UserPublic`` is what stops the password hash from ever
    reaching the client, even though the service returns the full ORM row.
    """
    return UserService(db).create_user(request)


@router.delete("/{college_id}")
def delete_user(
    college_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Hard-delete a user. Admin accounts are protected.

    Day-to-day offboarding should use ``DELETE /admin/users/{id}``, which
    deactivates the account and preserves the pass/gate history.
    """
    return {"detail": UserService(db).delete_user(college_id)}
