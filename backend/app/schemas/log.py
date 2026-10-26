"""Activity-log contracts for the warden's "Logs" tab.

``ApprovalPage.jsx`` reads ``data.logs[].staff.first_name`` and
``data.logs[].leave_pass.college.id``, plus the camelCase ``totalPages`` /
``currentPage`` pagination keys that the Express route returned - so those two
keys keep their camelCase spelling here.
"""

from typing import List, Optional

from pydantic import BaseModel

from app.models.enums import LogAction, StudentStatus
from app.schemas.common import ORMModel, OptionalUTCDateTime


class LogStaff(ORMModel):
    first_name: str
    last_name: str


class LogStudent(ORMModel):
    id: str
    first_name: str
    last_name: str


class LogLeavePass(ORMModel):
    college: Optional[LogStudent] = None


class LogEntry(ORMModel):
    scan_id: int
    pass_id: int
    staff_id: str
    action: LogAction
    student_status: StudentStatus
    scan_time: OptionalUTCDateTime = None
    staff: Optional[LogStaff] = None
    leave_pass: Optional[LogLeavePass] = None


class LogPage(BaseModel):
    logs: List[LogEntry]
    totalPages: int  # noqa: N815 - camelCase is part of the existing contract
    currentPage: int  # noqa: N815
