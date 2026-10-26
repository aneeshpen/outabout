"""Pass lifecycle business rules.

Every rule the Express backend enforced inline in its route handlers lives
here instead, so the rules are testable without an HTTP request and the
routers stay thin.  The flow for a request is always:

    router  ->  service (this file)  ->  repository  ->  model/database

``HTTPException`` is raised here rather than returning error tuples: FastAPI
turns it into the same status code and ``detail`` body the React client
already parses via ``error.response.data.detail``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    LeavePass,
    Log,
    LogAction,
    PassStatus,
    PassType,
    StudentStatus,
    User,
)
from app.repositories.leave_pass_repository import LeavePassRepository
from app.repositories.log_repository import LogRepository
from app.schemas.leave_pass import PassCreateRequest
from app.utils.notifications import notify_parent
from app.utils.timezone import LATE_RETURN_HOUR_IST, ist_today, to_ist

LOG_WINDOW_HOURS = 24


class LeavePassService:
    def __init__(self, db: Session):
        self.db = db
        self.passes = LeavePassRepository(db)
        self.logs = LogRepository(db)

    # --- student: apply ---------------------------------------------------

    def create_pass(self, student: User, request: PassCreateRequest) -> LeavePass:
        today = ist_today()
        leave_start = request.leave_start or today
        leave_end = request.leave_end or today

        if request.pass_type == PassType.market and leave_start != leave_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For market pass the leave start and end should be same",
            )

        if leave_end < leave_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The return date cannot be earlier than the departure date",
            )

        if self.passes.find_pending_for_student(student.id) is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Action denied: You already have a pending pass request "
                    "waiting for warden approval."
                ),
            )

        latest_log = self.logs.find_latest_for_student(student.id)
        if latest_log is not None and latest_log.student_status != StudentStatus.in_:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Action denied: The security logs show you are currently out "
                    "of the hostel. You must check back in before applying for a "
                    "new pass."
                ),
            )

        unused = self.passes.find_unused_approved_pass(student.id, today)
        if unused is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Action denied: You have an unused approved "
                    f"{_value(unused.pass_type)} pass. You must use it (or let it "
                    f"expire) before applying again."
                ),
            )

        new_pass = self.passes.create(
            college_id=student.id,
            pass_type=request.pass_type,
            leave_start=leave_start,
            leave_end=leave_end,
        )

        notify_parent(
            student.parent_email, student.first_name, _value(request.pass_type)
        )
        return new_pass

    # --- student: read ----------------------------------------------------

    def list_my_passes(self, student: User) -> List[LeavePass]:
        # ``logs`` arrives newest-first and PassWithLogsResponse keeps only the
        # most recent entry, which is all the UI reads.
        return self.passes.list_for_student(student.id)

    # --- student: convert a market pass into a leave pass -----------------

    def convert_market_pass(self, student: User, new_leave_end: date) -> str:
        recent = self.passes.find_latest_for_student(student.id)
        if recent is None or recent.pass_type != PassType.market:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action denied. Your most rescent pass is not a market pass.",
            )

        if new_leave_end < recent.leave_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The new return date cannot be before the departure date",
            )

        recent.pass_type = PassType.leave
        recent.leave_end = new_leave_end
        recent.pass_status = PassStatus.pending
        self.passes.save(recent)

        notify_parent(
            student.parent_email,
            student.first_name,
            "leave (extended from a market pass)",
        )
        return (
            "Market pass successfully converted to a Leave pass and is pending "
            "warden approval."
        )

    # --- student: extend an existing leave pass ---------------------------

    def extend_leave_pass(
        self, student: User, pass_id: int, new_leave_end: date
    ) -> LeavePass:
        leave_pass = self.passes.get_by_id_with_logs(pass_id)

        if (
            leave_pass is None
            or leave_pass.college_id != student.id
            or leave_pass.pass_type != PassType.leave
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Action denied. Invalid pass.",
            )

        if leave_pass.pass_status not in (PassStatus.approved, PassStatus.pending):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only approved or pending passes can be extended.",
            )

        today = ist_today()
        if leave_pass.leave_end <= today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This pass has already expired. You must apply for a new pass "
                    "instead of extending it."
                ),
            )

        if new_leave_end <= leave_pass.leave_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Extension can only be made for future date. If returning "
                    "early, simply scan your ID at the gate."
                ),
            )

        latest_log = self.logs.find_latest_for_pass(pass_id)
        if latest_log is not None and latest_log.student_status == StudentStatus.in_:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot extend a pass after you have already checked back "
                    "into the hostel."
                ),
            )

        leave_pass.leave_end = new_leave_end
        leave_pass.pass_status = PassStatus.pending
        leave_pass.is_extension = True
        return self.passes.save(leave_pass)

    # --- warden ------------------------------------------------------------

    def list_pending_passes(self) -> List[LeavePass]:
        return self.passes.list_by_status(PassStatus.pending)

    def list_all_passes(self) -> List[LeavePass]:
        return self.passes.list_all()

    def evaluate_pass(
        self, pass_id: int, new_status: PassStatus, remark: Optional[str]
    ) -> LeavePass:
        leave_pass = self.passes.get_by_id(pass_id)
        if leave_pass is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pass with id {pass_id} not found",
            )

        leave_pass.pass_status = new_status
        leave_pass.remark = remark or None
        return self.passes.save(leave_pass)

    def set_remark(self, pass_id: int, remark: Optional[str]) -> LeavePass:
        leave_pass = self.passes.get_by_id(pass_id)
        if leave_pass is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pass with id {pass_id} not found",
            )

        leave_pass.remark = remark
        return self.passes.save(leave_pass)

    def list_late_returns(self) -> List[LeavePass]:
        """Market passes whose student checked back in at or after 9 PM IST."""
        candidates = self.passes.list_checked_in_market_passes(ist_today())

        late: List[LeavePass] = []
        for leave_pass in candidates:
            latest = _latest_log(leave_pass.logs)
            if latest is None or latest.scan_time is None:
                continue
            local_time = to_ist(latest.scan_time)
            if local_time and local_time.hour >= LATE_RETURN_HOUR_IST:
                late.append(leave_pass)
        return late

    def list_recent_logs(self, page: int, limit: int) -> Tuple[List[Log], int, int]:
        page = max(page, 1)
        limit = min(max(limit, 1), 100)
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=LOG_WINDOW_HOURS
        )

        logs, total = self.logs.list_latest_per_pass_since(
            since, limit=limit, offset=(page - 1) * limit
        )
        total_pages = max(1, -(-total // limit))  # ceiling division
        return logs, total_pages, page

    # --- guard -------------------------------------------------------------

    def check_out(self, guard: User, pass_id: int) -> Log:
        self._require_pass(pass_id)

        latest = self.logs.find_latest_for_pass(pass_id)
        if latest is not None and latest.student_status == StudentStatus.out:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action detected: Student is already checked out.",
            )

        return self.logs.create(
            pass_id=pass_id,
            staff_id=guard.id,
            action=LogAction.checked_out,
            student_status=StudentStatus.out,
        )

    def check_in(self, guard: User, pass_id: int) -> Log:
        self._require_pass(pass_id)

        latest = self.logs.find_latest_for_pass(pass_id)
        if latest is None or latest.student_status == StudentStatus.in_:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Action denied. Student is already checked in or did not "
                    "check out."
                ),
            )

        return self.logs.create(
            pass_id=pass_id,
            staff_id=guard.id,
            action=LogAction.checked_in,
            student_status=StudentStatus.in_,
        )

    def _require_pass(self, pass_id: int) -> LeavePass:
        leave_pass = self.passes.get_by_id(pass_id)
        if leave_pass is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pass not found"
            )
        return leave_pass


# --- helpers ---------------------------------------------------------------

def _latest_log(logs: List[Log]) -> Optional[Log]:
    if not logs:
        return None
    return max(
        logs,
        key=lambda log: (log.scan_time or datetime.min, log.scan_id or 0),
    )


def _value(enum_member) -> str:
    return getattr(enum_member, "value", str(enum_member))
