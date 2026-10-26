"""User request / response contracts.

``UserPublic`` deliberately has no ``password`` field: the hash physically
cannot leak through a response that is validated by this schema.
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import Role
from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    id: str = Field(max_length=25, description="College ID")
    password: str = Field(min_length=6)
    first_name: str = Field(max_length=20)
    last_name: str = Field(max_length=20)
    role: Role
    contact_details: Optional[str] = Field(default=None, max_length=50)
    parent_email: Optional[str] = Field(default=None, max_length=100)
    parents_phone: Optional[str] = Field(default=None, max_length=10)


class UserPublic(ORMModel):
    id: str
    first_name: str
    last_name: str
    role: Role
    contact_details: Optional[str] = None
    parent_email: Optional[str] = None
    photo_url: Optional[str] = None
    parents_phone: Optional[str] = None
    is_active: bool = True


class UserSummary(ORMModel):
    """Shape embedded as ``pass.college`` in the warden's queues."""

    id: str
    first_name: str
    last_name: str
    contact_details: Optional[str] = None
    parent_email: Optional[str] = None
    parents_phone: Optional[str] = None


class AdminCreatedUser(ORMModel):
    id: str
    first_name: str
    last_name: str
    role: Role


class AdminCreateUserResponse(BaseModel):
    success: bool = True
    user: AdminCreatedUser
    default_password: str


class PasswordResetRequest(BaseModel):
    # Length is checked in AdminService so the client gets the Express
    # backend's 400 + message instead of a 422 validation envelope.
    new_password: str


class SimpleSuccessResponse(BaseModel):
    success: bool = True
    message: str


class BulkUploadSuccess(BaseModel):
    id: str
    name: str
    initial_password: str


class BulkUploadFailure(BaseModel):
    id: str
    reason: str


class BulkUploadResponse(BaseModel):
    message: str
    total_processed: int
    success_count: int
    failed_count: int
    successful_users: list[BulkUploadSuccess]
    failures: list[BulkUploadFailure]
