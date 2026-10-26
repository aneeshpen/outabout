"""All ``users`` table access lives here.

A repository owns the SQL for one aggregate.  Services ask it questions in
domain terms ("give me the user with this college id") and never build queries
themselves, which keeps SQLAlchemy out of the business rules and out of the
routers entirely.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, college_id: str) -> Optional[User]:
        return self.db.get(User, college_id)

    def exists(self, college_id: str) -> bool:
        return (
            self.db.execute(
                select(User.id).where(User.id == college_id)
            ).first()
            is not None
        )

    def create(self, user: User, *, commit: bool = True) -> User:
        self.db.add(user)
        if commit:
            self.db.commit()
            self.db.refresh(user)
        else:
            self.db.flush()
        return user

    def save(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
