"""Login workflow.

Router responsibility: receive the body, call this service, return the result.
Service responsibility (here): look the user up through the repository, verify
the password, enforce the account state, mint the token.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserPublic


class AuthService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)

    def login(self, request: LoginRequest) -> LoginResponse:
        user = self.users.get_by_id(request.username)

        # Same status codes and messages the Express backend returned, so the
        # login screen keeps showing the same errors.
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Couldn't find the user",
            )

        if not verify_password(request.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incorrect credentials",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated by administrator.",
            )

        access_token = create_access_token({"sub": user.id})
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserPublic.model_validate(user),
        )
