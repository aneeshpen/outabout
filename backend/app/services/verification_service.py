"""Gate verification workflow.

Decision procedure (identical to the Express ``verifyPassLogic``):

1. The college id must belong to a known user.
2. That user must have an ``approved`` pass whose date range covers today.
3. The pass must not have been closed already - if the latest scan says the
   student is back ``in``, the pass is spent.

On success the student's photo is turned into a short-lived signed URL so the
guard can compare the face at the gate.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import StudentStatus
from app.repositories.leave_pass_repository import LeavePassRepository
from app.repositories.user_repository import UserRepository
from app.schemas.leave_pass import PassWithLogsResponse
from app.schemas.user import UserPublic
from app.schemas.verification import VerificationResponse
from app.utils import storage
from app.utils.timezone import ist_today


class VerificationService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)
        self.passes = LeavePassRepository(db)

    def verify_college_id(self, college_id: str) -> VerificationResponse:
        college_id = (college_id or "").strip()
        user = self.users.get_by_id(college_id)

        if user is None:
            return VerificationResponse(
                valid=False,
                message=f"User with ID {college_id} not found",
                pass_details=None,
                user_details=None,
            )

        user_details = UserPublic.model_validate(user)

        valid_pass = self.passes.find_valid_pass_for_date(college_id, ist_today())
        if valid_pass is None:
            user_details.photo_url = None
            return VerificationResponse(
                valid=False,
                message=(
                    f"No valid approved pass found for "
                    f"{user.first_name} {user.last_name}"
                ),
                pass_details=None,
                user_details=user_details,
            )

        latest_log = valid_pass.logs[0] if valid_pass.logs else None
        if latest_log is not None and latest_log.student_status == StudentStatus.in_:
            user_details.photo_url = None
            return VerificationResponse(
                valid=False,
                message=(
                    "This pass has already been used and checked back in. "
                    "Waiting for new passes to be approved."
                ),
                pass_details=None,
                user_details=user_details,
            )

        # Replace the stored object name with a URL the browser can render.
        user_details.photo_url = storage.build_photo_url(user.photo_url)

        return VerificationResponse(
            valid=True,
            message=(
                f"Valid {_value(valid_pass.pass_type)} pass found for "
                f"{user.first_name} {user.last_name}"
            ),
            pass_details=PassWithLogsResponse.model_validate(valid_pass),
            user_details=user_details,
        )


def _value(enum_member) -> str:
    return getattr(enum_member, "value", str(enum_member))
