"""``/verify`` - the guard's gate endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_guard
from app.dependencies.database import get_db
from app.models import User
from app.schemas.leave_pass import CheckLogResponse, LogBrief
from app.schemas.verification import VerificationResponse
from app.services.leave_pass_service import LeavePassService
from app.services.verification_service import VerificationService
from app.utils.barcode import extract_barcode

router = APIRouter(prefix="/verify", tags=["Verification"])


@router.get("/manual/{college_id}", response_model=VerificationResponse)
def verify_manual(
    college_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_guard),
):
    """Verify a student by a typed or camera-scanned college id.

    The React scanner decodes the barcode in the browser and then calls this
    endpoint with the decoded text, which is why this single endpoint backs
    both the "Manual Entry" and "Scan Barcode" tabs.
    """
    return VerificationService(db).verify_college_id(college_id)


@router.post("/scan", response_model=VerificationResponse)
async def verify_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_guard),
):
    """Verify a student from an uploaded photo of their ID card barcode."""
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload"
        )

    result = extract_barcode(contents)
    if not result.ok or not result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to scan barcode: {result.reason or 'unknown error'}",
        )

    return VerificationService(db).verify_college_id(result.data)


@router.post("/checkout/{pass_id}", response_model=CheckLogResponse)
def check_out(
    pass_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_guard),
):
    """Record a student leaving the campus on a given pass."""
    log = LeavePassService(db).check_out(current_user, pass_id)
    return CheckLogResponse(
        detail="Student successfully checked out", log=LogBrief.model_validate(log)
    )


@router.post("/checkin/{pass_id}", response_model=CheckLogResponse)
def check_in(
    pass_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_guard),
):
    """Record a student returning to the campus on a given pass."""
    log = LeavePassService(db).check_in(current_user, pass_id)
    return CheckLogResponse(
        detail="Student successfully checked in", log=LogBrief.model_validate(log)
    )
