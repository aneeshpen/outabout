"""Shared test fixtures.

Every test runs against its own throwaway SQLite file, so nothing ever
touches a real database.  ``get_db`` is overridden with a session bound to
that file - the same seam the application uses in production, which is what
makes the layered design testable end to end.
"""

import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from typing import Iterator

import pytest

os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-that-is-long-enough-for-hs256"
)
os.environ.setdefault("DEFAULT_PASSWORD", "digipass@123")
# Tests build their own SQLite schema, so the app must not touch the
# configured development database on start-up.
os.environ.setdefault("CREATE_TABLES_ON_STARTUP", "false")
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.dependencies.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    LeavePass,
    Log,
    LogAction,
    PassStatus,
    PassType,
    Role,
    StudentStatus,
    User,
)

TEST_PASSWORD = "Passw0rd!"


@pytest.fixture()
def db_path() -> Iterator[str]:
    handle, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(handle)
    yield path
    try:
        os.remove(path)
    except OSError:  # pragma: no cover - Windows file locking
        pass


@pytest.fixture()
def engine(db_path):
    test_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def db(session_factory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- data helpers ---------------------------------------------------------

def make_user(
    db: Session,
    college_id: str,
    role: Role,
    *,
    password: str = TEST_PASSWORD,
    is_active: bool = True,
    **extra,
) -> User:
    user = User(
        id=college_id,
        password=hash_password(password),
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", role.value.title()),
        role=role,
        is_active=is_active,
        **extra,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def student(db) -> User:
    return make_user(
        db,
        "A1234CS1001",
        Role.student,
        first_name="Asha",
        last_name="Verma",
        parent_email="parent@example.com",
        parents_phone="9876543210",
        contact_details="9998887770",
    )


@pytest.fixture()
def warden(db) -> User:
    return make_user(db, "W0001", Role.warden, first_name="Wally", last_name="Warden")


@pytest.fixture()
def guard(db) -> User:
    return make_user(db, "G0001", Role.guard, first_name="Gita", last_name="Guard")


@pytest.fixture()
def admin(db) -> User:
    return make_user(db, "AD001", Role.admin, first_name="Ada", last_name="Admin")


def auth_headers(client: TestClient, college_id: str, password: str = TEST_PASSWORD):
    response = client.post(
        "/login/", json={"username": college_id, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def student_headers(client, student):
    return auth_headers(client, student.id)


@pytest.fixture()
def warden_headers(client, warden):
    return auth_headers(client, warden.id)


@pytest.fixture()
def guard_headers(client, guard):
    return auth_headers(client, guard.id)


@pytest.fixture()
def admin_headers(client, admin):
    return auth_headers(client, admin.id)


def make_pass(
    db: Session,
    college_id: str,
    *,
    pass_type: PassType = PassType.market,
    pass_status: PassStatus = PassStatus.pending,
    leave_start: date | None = None,
    leave_end: date | None = None,
    remark: str | None = None,
) -> LeavePass:
    today = date.today()
    leave_pass = LeavePass(
        college_id=college_id,
        pass_type=pass_type,
        pass_status=pass_status,
        leave_start=leave_start or today,
        leave_end=leave_end or today,
        remark=remark,
    )
    db.add(leave_pass)
    db.commit()
    db.refresh(leave_pass)
    return leave_pass


def make_log(
    db: Session,
    pass_id: int,
    staff_id: str,
    *,
    action: LogAction = LogAction.checked_out,
    student_status: StudentStatus = StudentStatus.out,
    scan_time: datetime | None = None,
) -> Log:
    log = Log(
        pass_id=pass_id,
        staff_id=staff_id,
        action=action,
        student_status=student_status,
        scan_time=scan_time or datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def utc_naive(**delta) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(**delta)).replace(tzinfo=None)
