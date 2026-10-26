"""``users`` table - students, wardens, guards and admins."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import Role, enum_values

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.leave_pass import LeavePass
    from app.models.log import Log


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(25), primary_key=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(20), nullable=False)
    last_name: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="Role", values_callable=enum_values), nullable=False
    )
    contact_details: Mapped[Optional[str]] = mapped_column(String(50))
    parent_email: Mapped[Optional[str]] = mapped_column(String(100))
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    parents_phone: Mapped[Optional[str]] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    leave_passes: Mapped[List["LeavePass"]] = relationship(
        "LeavePass", back_populates="college", foreign_keys="LeavePass.college_id"
    )
    logs: Mapped[List["Log"]] = relationship(
        "Log", back_populates="staff", foreign_keys="Log.staff_id"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
