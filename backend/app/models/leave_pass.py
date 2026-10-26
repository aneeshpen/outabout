"""``leave_pass`` table - one row per market / leave pass request."""

import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import PassStatus, PassType, enum_values

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.log import Log
    from app.models.user import User


class LeavePass(Base):
    __tablename__ = "leave_pass"
    __table_args__ = (Index("college_id", "college_id"),)

    pass_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    college_id: Mapped[str] = mapped_column(
        String(25), ForeignKey("users.id"), nullable=False
    )
    pass_type: Mapped[PassType] = mapped_column(
        Enum(PassType, name="PassType", values_callable=enum_values), nullable=False
    )
    leave_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    leave_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    pass_status: Mapped[PassStatus] = mapped_column(
        Enum(PassStatus, name="PassStatus", values_callable=enum_values),
        nullable=False,
        default=PassStatus.pending,
    )
    request_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    is_extension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[Optional[str]] = mapped_column(Text)

    college: Mapped["User"] = relationship(
        "User", back_populates="leave_passes", foreign_keys=[college_id]
    )
    logs: Mapped[List["Log"]] = relationship(
        "Log",
        back_populates="leave_pass",
        order_by="desc(Log.scan_time), desc(Log.scan_id)",
        foreign_keys="Log.pass_id",
    )
