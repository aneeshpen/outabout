"""The warden's activity log feed and the late-return report."""

from datetime import date, datetime, timedelta, timezone

from app.models import LogAction, PassStatus, PassType, StudentStatus
from app.utils.timezone import IST
from tests.conftest import make_log, make_pass, utc_naive

TODAY = date.today()


def ist_hour_as_utc_naive(hour: int, minute: int = 15) -> datetime:
    """A naive-UTC timestamp that is ``hour`` o'clock in IST today."""
    local = datetime.now(IST).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return local.astimezone(timezone.utc).replace(tzinfo=None)


# --- /pass/logs -----------------------------------------------------------

def test_logs_feed_returns_latest_entry_per_pass(
    client, db, student, guard, warden_headers
):
    first = make_pass(db, student.id, pass_status=PassStatus.approved)
    second = make_pass(db, student.id, pass_status=PassStatus.approved)

    make_log(
        db,
        first.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
        scan_time=utc_naive(hours=5),
    )
    make_log(
        db,
        first.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
        scan_time=utc_naive(hours=4),
    )
    make_log(
        db,
        second.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
        scan_time=utc_naive(hours=1),
    )

    response = client.get("/pass/logs", headers=warden_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["currentPage"] == 1
    assert body["totalPages"] == 1
    assert len(body["logs"]) == 2  # one per pass, not three rows

    newest = body["logs"][0]
    assert newest["pass_id"] == second.pass_id
    assert newest["action"] == "checked_out"
    # Nested shapes the warden table reads.
    assert newest["staff"]["first_name"] == "Gita"
    assert newest["leave_pass"]["college"]["id"] == student.id
    assert newest["leave_pass"]["college"]["first_name"] == "Asha"
    assert newest["scan_time"].endswith("Z")

    older = body["logs"][1]
    assert older["pass_id"] == first.pass_id
    assert older["action"] == "checked_in"


def test_logs_feed_ignores_entries_older_than_24_hours(
    client, db, student, guard, warden_headers
):
    stale = make_pass(db, student.id, pass_status=PassStatus.approved)
    make_log(
        db,
        stale.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
        scan_time=utc_naive(hours=30),
    )

    body = client.get("/pass/logs", headers=warden_headers).json()
    assert body["logs"] == []
    assert body["totalPages"] == 1


def test_logs_feed_paginates(client, db, student, guard, warden_headers):
    for index in range(5):
        leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
        make_log(
            db,
            leave_pass.pass_id,
            guard.id,
            action=LogAction.checked_out,
            student_status=StudentStatus.out,
            scan_time=utc_naive(minutes=index + 1),
        )

    page_one = client.get("/pass/logs?page=1&limit=2", headers=warden_headers).json()
    assert len(page_one["logs"]) == 2
    assert page_one["totalPages"] == 3
    assert page_one["currentPage"] == 1

    page_three = client.get(
        "/pass/logs?page=3&limit=2", headers=warden_headers
    ).json()
    assert len(page_three["logs"]) == 1
    assert page_three["currentPage"] == 3

    seen = {log["pass_id"] for log in page_one["logs"]} | {
        log["pass_id"] for log in page_three["logs"]
    }
    assert len(seen) == 3


def test_logs_feed_rejects_invalid_pagination(client, warden_headers):
    assert client.get("/pass/logs?page=0", headers=warden_headers).status_code == 422
    assert (
        client.get("/pass/logs?limit=500", headers=warden_headers).status_code == 422
    )


def test_logs_feed_is_warden_or_admin_only(
    client, warden_headers, admin_headers, student_headers, guard_headers
):
    assert client.get("/pass/logs", headers=warden_headers).status_code == 200
    assert client.get("/pass/logs", headers=admin_headers).status_code == 200
    assert client.get("/pass/logs", headers=student_headers).status_code == 403
    assert client.get("/pass/logs", headers=guard_headers).status_code == 403


# --- /pass/late-returns ---------------------------------------------------

def test_late_return_report_lists_students_back_after_9pm_ist(
    client, db, student, guard, warden_headers
):
    late = make_pass(
        db,
        student.id,
        pass_type=PassType.market,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=TODAY,
    )
    make_log(
        db,
        late.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
        scan_time=ist_hour_as_utc_naive(22),
    )

    response = client.get("/pass/late-returns", headers=warden_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["pass_id"] == late.pass_id
    assert body[0]["college"]["first_name"] == "Asha"
    # The warden's "call parent" button needs this field.
    assert body[0]["college"]["parents_phone"] == "9876543210"
    assert len(body[0]["logs"]) == 1


def test_on_time_returns_are_not_reported(
    client, db, student, guard, warden_headers
):
    on_time = make_pass(
        db,
        student.id,
        pass_type=PassType.market,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=TODAY,
    )
    make_log(
        db,
        on_time.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
        scan_time=ist_hour_as_utc_naive(19),
    )

    assert client.get("/pass/late-returns", headers=warden_headers).json() == []


def test_leave_passes_are_not_part_of_the_late_report(
    client, db, student, guard, warden_headers
):
    leave_pass = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=TODAY + timedelta(days=2),
    )
    make_log(
        db,
        leave_pass.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
        scan_time=ist_hour_as_utc_naive(23),
    )

    assert client.get("/pass/late-returns", headers=warden_headers).json() == []


def test_passes_without_a_checkin_are_not_reported(
    client, db, student, guard, warden_headers
):
    still_out = make_pass(
        db,
        student.id,
        pass_type=PassType.market,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=TODAY,
    )
    make_log(
        db,
        still_out.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
        scan_time=ist_hour_as_utc_naive(22),
    )

    assert client.get("/pass/late-returns", headers=warden_headers).json() == []


def test_late_report_is_warden_or_admin_only(
    client, admin_headers, student_headers, guard_headers
):
    assert client.get("/pass/late-returns", headers=admin_headers).status_code == 200
    assert (
        client.get("/pass/late-returns", headers=student_headers).status_code == 403
    )
    assert client.get("/pass/late-returns", headers=guard_headers).status_code == 403
