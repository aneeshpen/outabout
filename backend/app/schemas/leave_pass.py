"""Leave / market pass contracts.

Field names and nesting mirror exactly what the React components read, e.g.
``ViewPass.jsx`` reads ``pass.logs[0].student_status`` and
``ApprovalPage.jsx`` reads ``pass.college.parents_phone``.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import LogAction, PassStatus, PassType, StudentStatus
from app.schemas.common import ORMModel, OptionalUTCDateTime
from app.schemas.user import UserSummary


# --- requests --------------------------------------------------------------

class PassCreateRequest(BaseModel):
    pass_type: PassType
    leave_start: Optional[date] = None
    leave_end: Optional[date] = None


class PassEvaluationRequest(BaseModel):
    pass_status: PassStatus
    remark: Optional[str] = None


class PassRemarkRequest(BaseModel):
    remark: Optional[str] = None


class PassConvertRequest(BaseModel):
    leave_end: date


class PassExtendRequest(BaseModel):
    new_leave_end: date


# --- responses -------------------------------------------------------------

class LogBrief(ORMModel):
    scan_id: int
    pass_id: int
    staff_id: str
    action: LogAction
    student_status: StudentStatus
    scan_time: OptionalUTCDateTime = None


class PassResponse(ORMModel):
    pass_id: int
    college_id: str
    pass_type: PassType
    leave_start: date
    leave_end: date
    pass_status: PassStatus
    request_time: OptionalUTCDateTime = None
    updated_at: OptionalUTCDateTime = None
    is_extension: bool = False
    remark: Optional[str] = None


class PassWithLogsResponse(PassResponse):
    """Used wherever the UI needs the latest gate scan of a pass.

    The React components only ever read ``logs[0]``, and the Express routes
    only ever sent one entry (``take: 1``), so the list is truncated to the
    most recent scan here - at serialisation time, never by mutating the
    SQLAlchemy relationship.
    """

    logs: List[LogBrief] = []

    @field_validator("logs", mode="after")
    @classmethod
    def _only_latest(cls, logs: List[LogBrief]) -> List[LogBrief]:
        return logs[:1]


class PendingPassResponse(PassResponse):
    college: Optional[UserSummary] = None


class LatePassResponse(PassWithLogsResponse):
    college: Optional[UserSummary] = None


class PassConvertResponse(BaseModel):
    detail: str


class PassExtendResponse(BaseModel):
    """``pass`` is a Python keyword, so the attribute is ``pass_`` and the
    serialisation alias restores the ``{"detail": ..., "pass": {...}}`` body
    the Express route returned."""

    detail: str
    pass_: PassResponse = Field(serialization_alias="pass")


class PassRemarkResponse(BaseModel):
    success: bool = True
    pass_: PassResponse = Field(serialization_alias="pass")


class CheckLogResponse(BaseModel):
    detail: str
    log: LogBrief
