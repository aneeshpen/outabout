"""User creation / deletion rules that are not admin-console specific."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Role, User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)

    def create_user(self, request: UserCreate) -> User:
        if self.users.exists(request.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with {request.id} already present",
            )

        user = User(
            id=request.id,
            password=hash_password(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
            role=request.role,
            contact_details=request.contact_details,
            parent_email=request.parent_email,
            parents_phone=request.parents_phone,
            is_active=True,
        )
        return self.users.create(user)

    def delete_user(self, college_id: str) -> str:
        user = self.users.get_by_id(college_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with {college_id} not found",
            )

        if user.role == Role.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Action forbidden: Deletion of admin accounts is strictly "
                    "prohibited."
                ),
            )

        self.users.delete(user)
        return f"User {college_id} successfully deleted"
