"""Admin console workflows: onboarding, bulk import, soft delete, password
override.

The bulk import mirrors the Express route's *intent* (the handler there
returned "Under construction..." before its CSV code could run): every valid
row is created, and structurally broken or duplicate rows are reported back
without aborting the batch.
"""

from __future__ import annotations

import csv
import io
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import Role, User
from app.repositories.user_repository import UserRepository
from app.schemas.user import BulkUploadFailure, BulkUploadSuccess
from app.utils import storage

REQUIRED_CSV_COLUMNS = ("id", "first_name", "last_name")


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    # --- single user onboarding -----------------------------------------

    def create_user(
        self,
        *,
        college_id: str,
        first_name: str,
        last_name: str,
        role: Optional[str] = None,
        contact_details: Optional[str] = None,
        parent_email: Optional[str] = None,
        parents_phone: Optional[str] = None,
        photo: Optional[Tuple[str, bytes, str]] = None,
    ) -> Tuple[User, str]:
        if self.users.exists(college_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID already exists",
            )

        photo_url = None
        if photo is not None:
            filename, content, content_type = photo
            extension = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
            try:
                photo_url = storage.upload_photo(
                    f"{college_id}.{extension}", content, content_type
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload photo: {exc}",
                ) from exc

        default_password = settings.DEFAULT_PASSWORD
        user = User(
            id=college_id,
            password=hash_password(default_password),
            first_name=first_name,
            last_name=last_name,
            role=_parse_role(role) or Role.student,
            contact_details=contact_details,
            parent_email=parent_email,
            parents_phone=parents_phone,
            photo_url=photo_url,
            is_active=True,
        )
        try:
            self.users.create(user)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID already exists",
            ) from exc

        return user, default_password

    # --- bulk import -----------------------------------------------------

    def bulk_create_users(
        self, csv_bytes: bytes
    ) -> Tuple[int, List[BulkUploadSuccess], List[BulkUploadFailure]]:
        try:
            text = csv_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file must be UTF-8 encoded",
            )

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not set(REQUIRED_CSV_COLUMNS).issubset(
            {(name or "").strip() for name in reader.fieldnames}
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "CSV must contain the columns: "
                    + ", ".join(REQUIRED_CSV_COLUMNS)
                ),
            )

        rows = list(reader)
        default_password = settings.DEFAULT_PASSWORD
        hashed = hash_password(default_password)

        created: List[BulkUploadSuccess] = []
        failed: List[BulkUploadFailure] = []

        for row in rows:
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            college_id = row.get("id", "")
            first_name = row.get("first_name", "")
            last_name = row.get("last_name", "")

            if not college_id or not first_name or not last_name:
                failed.append(
                    BulkUploadFailure(
                        id=college_id or "UNKNOWN",
                        reason="Missing fields in CSV row",
                    )
                )
                continue

            if self.users.exists(college_id):
                failed.append(
                    BulkUploadFailure(
                        id=college_id,
                        reason="User Id already exists in database",
                    )
                )
                continue

            role = _parse_role(row.get("role")) or Role.student
            user = User(
                id=college_id,
                password=hashed,
                first_name=first_name[:20],
                last_name=last_name[:20],
                role=role,
                contact_details=row.get("contact_details") or None,
                parent_email=row.get("parent_email") or None,
                parents_phone=row.get("parents_phone") or None,
                is_active=True,
            )
            try:
                self.users.create(user)
            except IntegrityError as exc:
                self.db.rollback()
                failed.append(
                    BulkUploadFailure(id=college_id, reason=_integrity_reason(exc))
                )
                continue

            created.append(
                BulkUploadSuccess(
                    id=user.id,
                    name=f"{user.first_name} {user.last_name}",
                    initial_password=default_password,
                )
            )

        return len(rows), created, failed

    # --- account state ---------------------------------------------------

    def deactivate_user(self, college_id: str) -> str:
        user = self.users.get_by_id(college_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {college_id} not found",
            )
        user.is_active = False
        self.users.save(user)
        return f"User {college_id} has been deactivated"

    def reset_password(self, college_id: str, new_password: str) -> str:
        if not new_password or len(new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters",
            )

        user = self.users.get_by_id(college_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {college_id} not found",
            )

        user.password = hash_password(new_password)
        self.users.save(user)
        return f"Password updated for {college_id}"


def _parse_role(value: Optional[str]) -> Optional[Role]:
    if not value:
        return None
    try:
        return Role(value.strip().lower())
    except ValueError:
        return None


def _integrity_reason(exc: IntegrityError) -> str:
    message = str(getattr(exc, "orig", exc))
    if "foreign key" in message.lower():
        return "Invalid reference in CSV row"
    return "User Id already exists in database"
