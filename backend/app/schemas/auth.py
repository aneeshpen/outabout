"""Login request / response contracts.

The React client posts ``{"username": ..., "password": ...}`` as JSON to
``POST /login/`` (see ``frontend/src/services/api.js``), so the request model is
a plain Pydantic body - *not* ``OAuth2PasswordRequestForm``, which would expect
form-encoded credentials and break the untouched frontend.
"""

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class LoginRequest(BaseModel):
    username: str = Field(description="College ID used as the login name")
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    user: UserPublic
