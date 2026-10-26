"""SQLAlchemy engine / session wiring and the ``get_db`` dependency.

``get_db`` is the single place where a database session is opened, and the
``finally`` block guarantees it is returned to the pool even when a request
raises.  Routers never build sessions themselves - they declare
``db: Session = Depends(get_db)`` and hand it to a service.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite needs this to be usable from FastAPI's thread pool.
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
