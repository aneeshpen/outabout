"""``logs`` table - gate scan / check-in / check-out audit trail."""

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import LogAction, StudentStatus, enum_values

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.leave_pass import LeavePass
    from app.models.user import User


class Log(Base):
    __tablename__ = "logs"
    __table_args__ = (
        Index("pass_id", "pass_id"),
        Index("staff_id", "staff_id"),
    )

    scan_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pass_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leave_pass.pass_id"), nullable=False
    )
    staff_id: Mapped[str] = mapped_column(
        String(25), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[LogAction] = mapped_column(
        Enum(LogAction, name="LogAction", values_callable=enum_values), nullable=False
    )
    student_status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, name="StudentStatus", values_callable=enum_values),
        nullable=False,
        default=StudentStatus.in_,
    )
    scan_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        server_default=func.now()
    )

    leave_pass: Mapped["LeavePass"] = relationship(
        "LeavePass", back_populates="logs", foreign_keys=[pass_id]
    )
    staff: Mapped["User"] = relationship(
        "User", back_populates="logs", foreign_keys=[staff_id]
    )
