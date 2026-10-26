"""All ``leave_pass`` table access."""

from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import LeavePass, Log, PassStatus, PassType, User


class LeavePassRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- reads -----------------------------------------------------------

    def get_by_id(self, pass_id: int) -> Optional[LeavePass]:
        return self.db.get(LeavePass, pass_id)

    def get_by_id_with_logs(self, pass_id: int) -> Optional[LeavePass]:
        return self.db.scalars(
            select(LeavePass)
            .options(selectinload(LeavePass.logs))
            .where(LeavePass.pass_id == pass_id)
        ).first()

    def list_all(self) -> List[LeavePass]:
        return list(self.db.scalars(select(LeavePass)).all())

    def list_by_status(self, status: PassStatus) -> List[LeavePass]:
        """Pending queue for the warden, with the applicant joined in."""
        return list(
            self.db.scalars(
                select(LeavePass)
                .options(selectinload(LeavePass.college))
                .where(LeavePass.pass_status == status)
                .order_by(LeavePass.request_time.asc())
            ).all()
        )

    def list_for_student(self, college_id: str) -> List[LeavePass]:
        return list(
            self.db.scalars(
                select(LeavePass)
                .options(selectinload(LeavePass.logs))
                .where(LeavePass.college_id == college_id)
                .order_by(LeavePass.request_time.desc(), LeavePass.pass_id.desc())
            ).all()
        )

    def find_pending_for_student(self, college_id: str) -> Optional[LeavePass]:
        return self.db.scalars(
            select(LeavePass)
            .where(
                LeavePass.college_id == college_id,
                LeavePass.pass_status == PassStatus.pending,
            )
            .order_by(LeavePass.request_time.desc(), LeavePass.pass_id.desc())
        ).first()

    def find_latest_for_student(self, college_id: str) -> Optional[LeavePass]:
        return self.db.scalars(
            select(LeavePass)
            .where(LeavePass.college_id == college_id)
            .order_by(LeavePass.request_time.desc(), LeavePass.pass_id.desc())
        ).first()

    def find_unused_approved_pass(
        self, college_id: str, today: date
    ) -> Optional[LeavePass]:
        """An approved, still-valid pass that has never been scanned."""
        return self.db.scalars(
            select(LeavePass)
            .where(
                LeavePass.college_id == college_id,
                LeavePass.pass_status == PassStatus.approved,
                LeavePass.leave_end >= today,
                ~LeavePass.logs.any(),
            )
            .order_by(LeavePass.pass_id.desc())
        ).first()

    def find_valid_pass_for_date(
        self, college_id: str, on_date: date
    ) -> Optional[LeavePass]:
        """The approved pass that covers ``on_date`` - used at the gate."""
        return self.db.scalars(
            select(LeavePass)
            .options(selectinload(LeavePass.logs))
            .where(
                LeavePass.college_id == college_id,
                LeavePass.pass_status == PassStatus.approved,
                LeavePass.leave_start <= on_date,
                LeavePass.leave_end >= on_date,
            )
            .order_by(LeavePass.request_time.desc(), LeavePass.pass_id.desc())
        ).first()

    def list_checked_in_market_passes(self, since: date) -> List[LeavePass]:
        """Market passes starting on/after ``since`` that have a check-in log.

        The "was the student late?" decision depends on the IST wall-clock hour
        of the check-in and is applied by the service layer.
        """
        return list(
            self.db.scalars(
                select(LeavePass)
                .options(
                    selectinload(LeavePass.logs), selectinload(LeavePass.college)
                )
                .where(
                    LeavePass.pass_type == PassType.market,
                    LeavePass.leave_start >= since,
                    LeavePass.logs.any(Log.action == "checked_in"),
                )
            ).all()
        )

    # --- writes ----------------------------------------------------------

    def create(
        self,
        *,
        college_id: str,
        pass_type: PassType,
        leave_start: date,
        leave_end: date,
    ) -> LeavePass:
        leave_pass = LeavePass(
            college_id=college_id,
            pass_type=pass_type,
            leave_start=leave_start,
            leave_end=leave_end,
            pass_status=PassStatus.pending,
        )
        self.db.add(leave_pass)
        self.db.commit()
        self.db.refresh(leave_pass)
        return leave_pass

    def save(self, leave_pass: LeavePass) -> LeavePass:
        self.db.commit()
        self.db.refresh(leave_pass)
        return leave_pass
