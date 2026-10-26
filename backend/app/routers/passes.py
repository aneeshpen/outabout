"""``/pass`` - the pass lifecycle endpoints used by the student and warden
screens.

Note how each handler names the role it requires as a dependency
(``Depends(require_student)``), so authorisation is enforced before the body
runs, and every handler is one call into :class:`LeavePassService`.
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import (
    require_student,
    require_warden,
    require_warden_or_admin,
)
from app.dependencies.database import get_db
from app.models import User
from app.schemas.leave_pass import (
    LatePassResponse,
    PassConvertRequest,
    PassConvertResponse,
    PassCreateRequest,
    PassEvaluationRequest,
    PassExtendRequest,
    PassExtendResponse,
    PassRemarkRequest,
    PassRemarkResponse,
    PassResponse,
    PassWithLogsResponse,
    PendingPassResponse,
)
from app.schemas.log import LogPage
from app.services.leave_pass_service import LeavePassService

router = APIRouter(prefix="/pass", tags=["Pass"])


# --- student ---------------------------------------------------------------

@router.post("/", response_model=PassResponse)
@router.post("", response_model=PassResponse, include_in_schema=False)
def create_pass(
    request: PassCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Apply for a market or leave pass."""
    return LeavePassService(db).create_pass(current_user, request)


@router.get("/my_pass", response_model=List[PassWithLogsResponse])
def get_my_passes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Pass history of the signed-in student, newest first."""
    return LeavePassService(db).list_my_passes(current_user)


@router.post("/convert", response_model=PassConvertResponse)
def convert_pass(
    request: PassConvertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Upgrade the student's most recent market pass into a leave pass."""
    detail = LeavePassService(db).convert_market_pass(
        current_user, request.leave_end
    )
    return PassConvertResponse(detail=detail)


@router.post("/extend/{pass_id}", response_model=PassExtendResponse)
def extend_pass(
    pass_id: int,
    request: PassExtendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Push back the return date of an active leave pass."""
    updated = LeavePassService(db).extend_leave_pass(
        current_user, pass_id, request.new_leave_end
    )
    return PassExtendResponse(
        detail="Leave pass successfully extended and is pending warden approval.",
        pass_=PassResponse.model_validate(updated),
    )


# --- warden ----------------------------------------------------------------

@router.get("/pending", response_model=List[PendingPassResponse])
def get_pending_passes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_warden),
):
    """The warden's approval queue, with applicant contact details attached."""
    return LeavePassService(db).list_pending_passes()


@router.get("/all", response_model=List[PassResponse])
def get_all_passes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_warden),
):
    return LeavePassService(db).list_all_passes()


@router.put("/status/{pass_id}", response_model=PassResponse)
def update_pass_status(
    pass_id: int,
    request: PassEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_warden),
):
    """Approve or reject a pass, optionally recording a remark."""
    return LeavePassService(db).evaluate_pass(
        pass_id, request.pass_status, request.remark
    )


@router.get("/late-returns", response_model=List[LatePassResponse])
def get_late_returns(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_warden_or_admin),
):
    """Today's market passes whose student returned at or after 9 PM IST."""
    return LeavePassService(db).list_late_returns()


@router.put("/remark/{pass_id}", response_model=PassRemarkResponse)
def add_pass_remark(
    pass_id: int,
    request: PassRemarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_warden_or_admin),
):
    updated = LeavePassService(db).set_remark(pass_id, request.remark)
    return PassRemarkResponse(
        success=True, pass_=PassResponse.model_validate(updated)
    )


@router.get("/logs", response_model=LogPage)
def get_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_warden_or_admin),
):
    """Paginated gate activity: the latest scan per pass in the last 24 hours."""
    logs, total_pages, current_page = LeavePassService(db).list_recent_logs(
        page, limit
    )
    return LogPage(logs=logs, totalPages=total_pages, currentPage=current_page)
