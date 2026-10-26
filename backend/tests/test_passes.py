"""Pass application, approval, conversion, extension and history."""

from datetime import date, timedelta

from app.models import LogAction, PassStatus, PassType, StudentStatus
from tests.conftest import make_log, make_pass

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)


def iso(value: date) -> str:
    return value.isoformat()


# --- create ---------------------------------------------------------------

def test_student_can_apply_for_market_pass(client, student_headers, student):
    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": iso(TODAY),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pass_type"] == "market"
    assert body["pass_status"] == "pending"
    assert body["college_id"] == student.id
    assert body["is_extension"] is False
    assert body["pass_id"] > 0


def test_student_can_apply_for_leave_pass(client, student_headers):
    response = client.post(
        "/pass/",
        json={
            "pass_type": "leave",
            "leave_start": iso(TODAY),
            "leave_end": iso(NEXT_WEEK),
        },
        headers=student_headers,
    )
    assert response.status_code == 200
    assert response.json()["leave_end"] == iso(NEXT_WEEK)


def test_market_pass_must_start_and_end_on_the_same_day(client, student_headers):
    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": iso(TODAY),
            "leave_end": iso(TOMORROW),
        },
        headers=student_headers,
    )
    assert response.status_code == 400
    assert "same" in response.json()["detail"]


def test_return_date_cannot_precede_departure(client, student_headers):
    response = client.post(
        "/pass/",
        json={
            "pass_type": "leave",
            "leave_start": iso(TOMORROW),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 400


def test_invalid_pass_type_is_rejected(client, student_headers):
    response = client.post(
        "/pass/",
        json={
            "pass_type": "holiday",
            "leave_start": iso(TODAY),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 422


def test_cannot_apply_with_a_pending_pass(client, db, student, student_headers):
    make_pass(db, student.id, pass_status=PassStatus.pending)
    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": iso(TODAY),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 403
    assert "pending pass request" in response.json()["detail"]


def test_cannot_apply_while_checked_out(
    client, db, student, guard, student_headers
):
    old = make_pass(
        db, student.id, pass_status=PassStatus.approved, pass_type=PassType.leave
    )
    make_log(
        db,
        old.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
    )

    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": iso(TODAY),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 403
    assert "out of the hostel" in response.json()["detail"]


def test_cannot_apply_with_an_unused_approved_pass(
    client, db, student, student_headers
):
    make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
        pass_type=PassType.leave,
    )
    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": iso(TODAY),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 403
    assert "unused approved" in response.json()["detail"]


def test_can_apply_again_after_completing_a_pass(
    client, db, student, guard, student_headers
):
    finished = make_pass(
        db, student.id, pass_status=PassStatus.approved, pass_type=PassType.market
    )
    make_log(
        db,
        finished.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
    )
    make_log(
        db,
        finished.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
    )

    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": iso(TODAY),
            "leave_end": iso(TODAY),
        },
        headers=student_headers,
    )
    assert response.status_code == 200, response.text


# --- student history -------------------------------------------------------

def test_my_pass_returns_only_own_passes_with_latest_log(
    client, db, student, guard, warden, student_headers
):
    mine = make_pass(db, student.id, pass_status=PassStatus.approved)
    make_log(
        db,
        mine.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
    )
    make_log(
        db,
        mine.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
    )
    make_pass(db, warden.id)  # a pass belonging to somebody else

    response = client.get("/pass/my_pass", headers=student_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["college_id"] == student.id
    # Only the most recent scan is exposed, newest first.
    assert len(body[0]["logs"]) == 1
    assert body[0]["logs"][0]["student_status"] == "in"
    assert body[0]["logs"][0]["scan_time"].endswith("Z")


def test_my_pass_is_empty_for_a_new_student(client, student_headers):
    response = client.get("/pass/my_pass", headers=student_headers)
    assert response.status_code == 200
    assert response.json() == []


# --- warden queue ---------------------------------------------------------

def test_pending_queue_includes_applicant_details(
    client, db, student, warden_headers
):
    make_pass(db, student.id, pass_status=PassStatus.pending)
    make_pass(db, student.id, pass_status=PassStatus.approved)

    response = client.get("/pass/pending", headers=warden_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["pass_status"] == "pending"
    assert body[0]["college"]["first_name"] == "Asha"
    assert body[0]["college"]["parents_phone"] == "9876543210"


def test_all_passes_endpoint(client, db, student, warden_headers):
    make_pass(db, student.id, pass_status=PassStatus.pending)
    make_pass(db, student.id, pass_status=PassStatus.rejected)

    response = client.get("/pass/all", headers=warden_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_warden_approves_a_pass_with_a_remark(client, db, student, warden_headers):
    leave_pass = make_pass(db, student.id)

    response = client.put(
        f"/pass/status/{leave_pass.pass_id}",
        json={"pass_status": "approved", "remark": "Verified with parent"},
        headers=warden_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pass_status"] == "approved"
    assert body["remark"] == "Verified with parent"


def test_warden_rejects_a_pass(client, db, student, warden_headers):
    leave_pass = make_pass(db, student.id)
    response = client.put(
        f"/pass/status/{leave_pass.pass_id}",
        json={"pass_status": "rejected"},
        headers=warden_headers,
    )
    assert response.status_code == 200
    assert response.json()["pass_status"] == "rejected"


def test_updating_a_missing_pass_returns_404(client, warden_headers):
    response = client.put(
        "/pass/status/999999",
        json={"pass_status": "approved"},
        headers=warden_headers,
    )
    assert response.status_code == 404


def test_invalid_status_value_is_rejected(client, db, student, warden_headers):
    leave_pass = make_pass(db, student.id)
    response = client.put(
        f"/pass/status/{leave_pass.pass_id}",
        json={"pass_status": "maybe"},
        headers=warden_headers,
    )
    assert response.status_code == 422


def test_student_cannot_approve_a_pass(client, db, student, student_headers):
    leave_pass = make_pass(db, student.id)
    response = client.put(
        f"/pass/status/{leave_pass.pass_id}",
        json={"pass_status": "approved"},
        headers=student_headers,
    )
    assert response.status_code == 403


def test_remark_endpoint_returns_pass_key(client, db, student, warden_headers):
    leave_pass = make_pass(db, student.id)
    response = client.put(
        f"/pass/remark/{leave_pass.pass_id}",
        json={"remark": "Returned at 10 PM"},
        headers=warden_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # The React client reads response.data.pass.remark
    assert body["pass"]["remark"] == "Returned at 10 PM"


def test_remark_on_missing_pass_returns_404(client, warden_headers):
    response = client.put(
        "/pass/remark/424242", json={"remark": "x"}, headers=warden_headers
    )
    assert response.status_code == 404


# --- convert --------------------------------------------------------------

def test_convert_market_pass_to_leave(client, db, student, student_headers):
    make_pass(db, student.id, pass_type=PassType.market, pass_status=PassStatus.approved)

    response = client.post(
        "/pass/convert", json={"leave_end": iso(NEXT_WEEK)}, headers=student_headers
    )
    assert response.status_code == 200
    assert "converted" in response.json()["detail"]

    passes = client.get("/pass/my_pass", headers=student_headers).json()
    assert passes[0]["pass_type"] == "leave"
    assert passes[0]["pass_status"] == "pending"
    assert passes[0]["leave_end"] == iso(NEXT_WEEK)


def test_convert_requires_a_market_pass(client, db, student, student_headers):
    make_pass(db, student.id, pass_type=PassType.leave, leave_end=NEXT_WEEK)
    response = client.post(
        "/pass/convert", json={"leave_end": iso(NEXT_WEEK)}, headers=student_headers
    )
    assert response.status_code == 400


def test_convert_without_any_pass(client, student_headers):
    response = client.post(
        "/pass/convert", json={"leave_end": iso(NEXT_WEEK)}, headers=student_headers
    )
    assert response.status_code == 400


def test_convert_requires_a_date(client, student_headers):
    response = client.post("/pass/convert", json={}, headers=student_headers)
    assert response.status_code == 422


# --- extend ---------------------------------------------------------------

def test_extend_leave_pass(client, db, student, student_headers):
    leave_pass = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=TOMORROW,
    )
    response = client.post(
        f"/pass/extend/{leave_pass.pass_id}",
        json={"new_leave_end": iso(NEXT_WEEK)},
        headers=student_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "extended" in body["detail"]
    assert body["pass"]["leave_end"] == iso(NEXT_WEEK)
    assert body["pass"]["pass_status"] == "pending"
    assert body["pass"]["is_extension"] is True


def test_cannot_extend_a_market_pass(client, db, student, student_headers):
    leave_pass = make_pass(
        db, student.id, pass_type=PassType.market, pass_status=PassStatus.approved
    )
    response = client.post(
        f"/pass/extend/{leave_pass.pass_id}",
        json={"new_leave_end": iso(NEXT_WEEK)},
        headers=student_headers,
    )
    assert response.status_code == 403


def test_cannot_extend_someone_elses_pass(
    client, db, student, warden, student_headers
):
    other = make_pass(
        db,
        warden.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_end=NEXT_WEEK,
    )
    response = client.post(
        f"/pass/extend/{other.pass_id}",
        json={"new_leave_end": iso(NEXT_WEEK + timedelta(days=1))},
        headers=student_headers,
    )
    assert response.status_code == 403


def test_cannot_extend_an_expired_pass(client, db, student, student_headers):
    expired = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_start=TODAY - timedelta(days=5),
        leave_end=TODAY - timedelta(days=1),
    )
    response = client.post(
        f"/pass/extend/{expired.pass_id}",
        json={"new_leave_end": iso(NEXT_WEEK)},
        headers=student_headers,
    )
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_cannot_extend_to_an_earlier_date(client, db, student, student_headers):
    leave_pass = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_end=NEXT_WEEK,
    )
    response = client.post(
        f"/pass/extend/{leave_pass.pass_id}",
        json={"new_leave_end": iso(TOMORROW)},
        headers=student_headers,
    )
    assert response.status_code == 400
    assert "future date" in response.json()["detail"]


def test_cannot_extend_a_rejected_pass(client, db, student, student_headers):
    leave_pass = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.rejected,
        leave_end=NEXT_WEEK,
    )
    response = client.post(
        f"/pass/extend/{leave_pass.pass_id}",
        json={"new_leave_end": iso(NEXT_WEEK + timedelta(days=2))},
        headers=student_headers,
    )
    assert response.status_code == 400
    assert "approved or pending" in response.json()["detail"]


def test_cannot_extend_after_checking_back_in(
    client, db, student, guard, student_headers
):
    leave_pass = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_end=NEXT_WEEK,
    )
    make_log(
        db,
        leave_pass.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
    )
    response = client.post(
        f"/pass/extend/{leave_pass.pass_id}",
        json={"new_leave_end": iso(NEXT_WEEK + timedelta(days=2))},
        headers=student_headers,
    )
    assert response.status_code == 400
    assert "checked back" in response.json()["detail"]
