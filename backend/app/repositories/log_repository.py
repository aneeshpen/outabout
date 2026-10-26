"""All ``logs`` table access (gate scans, check-ins, check-outs)."""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import LeavePass, Log, LogAction, StudentStatus


class LogRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- reads -----------------------------------------------------------

    def find_latest_for_pass(self, pass_id: int) -> Optional[Log]:
        return self.db.scalars(
            select(Log)
            .where(Log.pass_id == pass_id)
            .order_by(Log.scan_time.desc(), Log.scan_id.desc())
        ).first()

    def find_latest_for_student(self, college_id: str) -> Optional[Log]:
        """Most recent scan across every pass belonging to the student."""
        return self.db.scalars(
            select(Log)
            .join(LeavePass, Log.pass_id == LeavePass.pass_id)
            .where(LeavePass.college_id == college_id)
            .order_by(Log.scan_time.desc(), Log.scan_id.desc())
        ).first()

    def list_latest_per_pass_since(
        self, since: datetime, *, limit: int, offset: int
    ) -> Tuple[List[Log], int]:
        """Latest log per pass within a time window, newest first.

        The Express version did this with PostgreSQL's ``DISTINCT ON``.  The
        portable equivalent is a ``row_number()`` window function, which runs
        unchanged on PostgreSQL and SQLite.
        """
        ranked = (
            select(
                Log.scan_id,
                func.row_number()
                .over(
                    partition_by=Log.pass_id,
                    order_by=(Log.scan_time.desc(), Log.scan_id.desc()),
                )
                .label("row_number"),
            )
            .where(Log.scan_time >= since)
            .subquery()
        )
        latest_ids = select(ranked.c.scan_id).where(ranked.c.row_number == 1)

        total = self.db.scalar(
            select(func.count()).select_from(latest_ids.subquery())
        ) or 0

        logs = list(
            self.db.scalars(
                select(Log)
                .options(
                    selectinload(Log.staff),
                    selectinload(Log.leave_pass).selectinload(LeavePass.college),
                )
                .where(Log.scan_id.in_(latest_ids))
                .order_by(Log.scan_time.desc(), Log.scan_id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return logs, total

    # --- writes ----------------------------------------------------------

    def create(
        self,
        *,
        pass_id: int,
        staff_id: str,
        action: LogAction,
        student_status: StudentStatus,
    ) -> Log:
        log = Log(
            pass_id=pass_id,
            staff_id=staff_id,
            action=action,
            student_status=student_status,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
