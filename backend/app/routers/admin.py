"""``/admin`` - the admin console endpoints.

The admin dashboard submits ``multipart/form-data`` (because a profile photo
and a CSV file can be attached), so these handlers declare ``Form(...)`` /
``File(...)`` parameters instead of a JSON body model.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models import User
from app.schemas.user import (
    AdminCreatedUser,
    AdminCreateUserResponse,
    BulkUploadResponse,
    PasswordResetRequest,
    SimpleSuccessResponse,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/users", response_model=AdminCreateUserResponse)
async def create_user(
    id: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    role: Optional[str] = Form(None),
    contact_details: Optional[str] = Form(None),
    parent_email: Optional[str] = Form(None),
    parents_phone: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Onboard one user, with an optional profile photo, using the configured
    default password."""
    photo_payload = None
    if photo is not None and photo.filename:
        photo_payload = (
            photo.filename,
            await photo.read(),
            photo.content_type or "application/octet-stream",
        )

    user, default_password = AdminService(db).create_user(
        college_id=id,
        first_name=first_name,
        last_name=last_name,
        role=role,
        contact_details=contact_details,
        parent_email=parent_email,
        parents_phone=parents_phone,
        photo=photo_payload,
    )

    return AdminCreateUserResponse(
        success=True,
        user=AdminCreatedUser.model_validate(user),
        default_password=default_password,
    )


@router.post("/users/bulk", response_model=BulkUploadResponse)
async def bulk_create_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Import users from a CSV (``id,first_name,last_name[,role,...]``).

    Valid rows are created even when other rows fail; the failures come back
    per row so the admin can fix and re-upload just those.
    """
    contents = await file.read()
    total, created, failures = AdminService(db).bulk_create_users(contents)

    return BulkUploadResponse(
        message="Bulk upload processed.",
        total_processed=total,
        success_count=len(created),
        failed_count=len(failures),
        successful_users=created,
        failures=failures,
    )


@router.delete("/users/{college_id}", response_model=SimpleSuccessResponse)
def deactivate_user(
    college_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Soft delete: the account loses access but its history is preserved."""
    message = AdminService(db).deactivate_user(college_id)
    return SimpleSuccessResponse(success=True, message=message)


@router.put("/users/{college_id}/password", response_model=SimpleSuccessResponse)
def reset_password(
    college_id: str,
    request: PasswordResetRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    message = AdminService(db).reset_password(college_id, request.new_password)
    return SimpleSuccessResponse(success=True, message=message)
