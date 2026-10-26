"""Unit tests for the pieces that have no HTTP surface of their own."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models import PassStatus, PassType
from app.schemas.leave_pass import PassCreateRequest, PassWithLogsResponse
from app.services.leave_pass_service import LeavePassService
from app.utils import storage
from app.utils.timezone import IST, as_utc, ist_today, to_ist
from tests.conftest import make_log, make_pass


# --- timezone helpers -----------------------------------------------------

def test_as_utc_marks_naive_values_as_utc():
    naive = datetime(2026, 5, 1, 12, 0, 0)
    assert as_utc(naive).tzinfo == timezone.utc
    assert as_utc(None) is None


def test_as_utc_leaves_aware_values_alone():
    aware = datetime(2026, 5, 1, 12, 0, 0, tzinfo=IST)
    assert as_utc(aware) is aware


def test_to_ist_shifts_by_five_thirty():
    naive_utc = datetime(2026, 5, 1, 16, 0, 0)  # 16:00 UTC
    local = to_ist(naive_utc)
    assert (local.hour, local.minute) == (21, 30)  # 21:30 IST -> a late return


def test_ist_today_is_a_date():
    assert isinstance(ist_today(), date)


# --- service-level business rules (no HTTP) -------------------------------

def test_create_pass_rejects_mismatched_market_dates(db, student):
    service = LeavePassService(db)
    with pytest.raises(HTTPException) as error:
        service.create_pass(
            student,
            PassCreateRequest(
                pass_type=PassType.market,
                leave_start=date(2030, 1, 1),
                leave_end=date(2030, 1, 2),
            ),
        )
    assert error.value.status_code == 400


def test_create_pass_defaults_missing_dates_to_today(db, student):
    created = LeavePassService(db).create_pass(
        student, PassCreateRequest(pass_type=PassType.market)
    )
    assert created.leave_start == ist_today()
    assert created.leave_end == ist_today()
    assert created.pass_status == PassStatus.pending


def test_evaluate_pass_clears_an_empty_remark(db, student):
    service = LeavePassService(db)
    leave_pass = make_pass(db, student.id, remark="old note")

    updated = service.evaluate_pass(leave_pass.pass_id, PassStatus.approved, "")
    assert updated.remark is None


def test_extend_requires_an_existing_pass(db, student):
    with pytest.raises(HTTPException) as error:
        LeavePassService(db).extend_leave_pass(
            student, 123456, date.today() + timedelta(days=3)
        )
    assert error.value.status_code == 403


def test_list_recent_logs_clamps_pagination(db, student, guard):
    leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
    make_log(db, leave_pass.pass_id, guard.id)

    logs, total_pages, current_page = LeavePassService(db).list_recent_logs(0, 0)
    assert current_page == 1
    assert total_pages == 1
    assert len(logs) == 1


# --- schema guarantees ----------------------------------------------------

def test_pass_schema_exposes_only_the_latest_log(db, student, guard):
    leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
    make_log(db, leave_pass.pass_id, guard.id)
    make_log(db, leave_pass.pass_id, guard.id)
    db.refresh(leave_pass)

    payload = PassWithLogsResponse.model_validate(leave_pass)
    assert len(payload.logs) == 1
    # Trimming happens at serialisation time only - the rows are untouched.
    assert db.query(type(leave_pass)).count() == 1
    assert len(leave_pass.logs) == 2


def test_timestamps_serialise_with_an_explicit_utc_offset(db, student, guard):
    leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
    make_log(db, leave_pass.pass_id, guard.id)
    db.refresh(leave_pass)

    dumped = PassWithLogsResponse.model_validate(leave_pass).model_dump(mode="json")
    assert dumped["logs"][0]["scan_time"].endswith("Z")


# --- photo storage --------------------------------------------------------

def test_local_photo_storage_roundtrip(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))

    stored = storage.upload_photo("A1234CS1001.jpg", b"bytes", "image/jpeg")
    assert stored == "A1234CS1001.jpg"
    assert storage.build_photo_url(stored) == "/uploads/A1234CS1001.jpg"


def test_photo_url_is_none_when_nothing_is_stored(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
    assert storage.build_photo_url(None) is None
    assert storage.build_photo_url("missing.jpg") is None


def test_photo_path_is_sanitised(tmp_path, monkeypatch):
    """Only a bare object name is ever stored or fetched."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))

    stored = storage.upload_photo(
        "https://example.com/bucket/../A1.jpg", b"x", "image/jpeg"
    )
    assert "/" not in stored and ".." not in stored
    assert (tmp_path / stored).exists()
