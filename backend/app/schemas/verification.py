"""Gate verification contracts (``/verify/*``).

``VerificationPage.jsx`` reads ``valid``, ``message``,
``user_details.photo_url`` and ``pass_details.logs[0].student_status``, so the
response keeps exactly that shape.
"""

from typing import Optional

from pydantic import BaseModel

from app.schemas.leave_pass import PassWithLogsResponse
from app.schemas.user import UserPublic


class VerificationResponse(BaseModel):
    valid: bool
    message: str
    pass_details: Optional[PassWithLogsResponse] = None
    user_details: Optional[UserPublic] = None
