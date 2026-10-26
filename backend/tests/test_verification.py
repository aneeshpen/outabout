"""Gate verification: manual lookup, barcode upload, check-in / check-out."""

import io
from datetime import date, timedelta

from app.models import LogAction, PassStatus, PassType, StudentStatus
from tests.conftest import make_log, make_pass

TODAY = date.today()
NEXT_WEEK = TODAY + timedelta(days=7)


# --- manual verification --------------------------------------------------

def test_valid_approved_pass_is_accepted(client, db, student, guard_headers):
    leave_pass = make_pass(
        db,
        student.id,
        pass_type=PassType.leave,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
    )

    response = client.get(f"/verify/manual/{student.id}", headers=guard_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert "Valid leave pass found" in body["message"]
    assert body["pass_details"]["pass_id"] == leave_pass.pass_id
    assert body["pass_details"]["logs"] == []
    assert body["user_details"]["id"] == student.id
    assert "password" not in body["user_details"]


def test_unknown_college_id_is_rejected(client, guard_headers):
    response = client.get("/verify/manual/NOBODY", headers=guard_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "not found" in body["message"]
    assert body["user_details"] is None


def test_pending_pass_is_not_valid_at_the_gate(client, db, student, guard_headers):
    make_pass(
        db,
        student.id,
        pass_status=PassStatus.pending,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
    )
    response = client.get(f"/verify/manual/{student.id}", headers=guard_headers)
    body = response.json()
    assert body["valid"] is False
    assert "No valid approved pass" in body["message"]
    assert body["user_details"]["first_name"] == "Asha"


def test_expired_pass_is_not_valid(client, db, student, guard_headers):
    make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY - timedelta(days=10),
        leave_end=TODAY - timedelta(days=2),
    )
    response = client.get(f"/verify/manual/{student.id}", headers=guard_headers)
    assert response.json()["valid"] is False


def test_future_pass_is_not_valid_yet(client, db, student, guard_headers):
    make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY + timedelta(days=3),
        leave_end=TODAY + timedelta(days=5),
    )
    assert (
        client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()[
            "valid"
        ]
        is False
    )


def test_already_used_pass_is_rejected(client, db, student, guard, guard_headers):
    leave_pass = make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
        pass_type=PassType.leave,
    )
    make_log(
        db,
        leave_pass.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
    )
    make_log(
        db,
        leave_pass.pass_id,
        guard.id,
        action=LogAction.checked_in,
        student_status=StudentStatus.in_,
    )

    body = client.get(
        f"/verify/manual/{student.id}", headers=guard_headers
    ).json()
    assert body["valid"] is False
    assert "already been used" in body["message"]


def test_checked_out_student_can_still_be_verified(
    client, db, student, guard, guard_headers
):
    """A student who is out must still verify so the guard can check them in."""
    leave_pass = make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
        pass_type=PassType.leave,
    )
    make_log(
        db,
        leave_pass.pass_id,
        guard.id,
        action=LogAction.checked_out,
        student_status=StudentStatus.out,
    )

    body = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert body["valid"] is True
    # The UI uses logs[0].student_status to decide which button to show.
    assert body["pass_details"]["logs"][0]["student_status"] == "out"


def test_only_guards_can_verify(client, student_headers, warden_headers):
    assert (
        client.get("/verify/manual/A1", headers=student_headers).status_code == 403
    )
    assert client.get("/verify/manual/A1", headers=warden_headers).status_code == 403


def test_verify_requires_authentication(client):
    assert client.get("/verify/manual/A1").status_code == 401


# --- check-out / check-in --------------------------------------------------

def test_checkout_then_checkin(client, db, student, guard_headers):
    leave_pass = make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
        pass_type=PassType.leave,
    )

    out = client.post(
        f"/verify/checkout/{leave_pass.pass_id}", headers=guard_headers
    )
    assert out.status_code == 200
    assert out.json()["detail"] == "Student successfully checked out"
    assert out.json()["log"]["action"] == "checked_out"
    assert out.json()["log"]["student_status"] == "out"

    back_in = client.post(
        f"/verify/checkin/{leave_pass.pass_id}", headers=guard_headers
    )
    assert back_in.status_code == 200
    assert back_in.json()["log"]["action"] == "checked_in"
    assert back_in.json()["log"]["student_status"] == "in"


def test_double_checkout_is_rejected(client, db, student, guard_headers):
    leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
    client.post(f"/verify/checkout/{leave_pass.pass_id}", headers=guard_headers)

    second = client.post(
        f"/verify/checkout/{leave_pass.pass_id}", headers=guard_headers
    )
    assert second.status_code == 400
    assert "already checked out" in second.json()["detail"]


def test_checkin_without_checkout_is_rejected(client, db, student, guard_headers):
    leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
    response = client.post(
        f"/verify/checkin/{leave_pass.pass_id}", headers=guard_headers
    )
    assert response.status_code == 400
    assert "already checked in" in response.json()["detail"]


def test_checkout_on_missing_pass_is_404(client, guard_headers):
    response = client.post("/verify/checkout/987654", headers=guard_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Pass not found"


def test_student_cannot_check_themselves_out(
    client, db, student, student_headers
):
    leave_pass = make_pass(db, student.id, pass_status=PassStatus.approved)
    response = client.post(
        f"/verify/checkout/{leave_pass.pass_id}", headers=student_headers
    )
    assert response.status_code == 403


# --- barcode upload --------------------------------------------------------

def test_scan_endpoint_decodes_a_barcode(client, db, student, guard_headers):
    """Generate a real Code 128 barcode image and post it to /verify/scan."""
    image_bytes = _render_code128(student.id)
    if image_bytes is None:  # pragma: no cover - optional dependency missing
        import pytest

        pytest.skip("barcode encoder not available")

    make_pass(
        db,
        student.id,
        pass_status=PassStatus.approved,
        leave_start=TODAY,
        leave_end=NEXT_WEEK,
        pass_type=PassType.leave,
    )

    response = client.post(
        "/verify/scan",
        files={"file": ("id-card.png", io.BytesIO(image_bytes), "image/png")},
        headers=guard_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["user_details"]["id"] == student.id


def test_scan_endpoint_rejects_an_unreadable_image(client, guard_headers):
    blank = _render_blank()
    if blank is None:  # pragma: no cover
        import pytest

        pytest.skip("Pillow not available")

    response = client.post(
        "/verify/scan",
        files={"file": ("blank.png", io.BytesIO(blank), "image/png")},
        headers=guard_headers,
    )
    assert response.status_code == 400
    assert "Failed to scan barcode" in response.json()["detail"]


def test_scan_endpoint_rejects_an_empty_upload(client, guard_headers):
    response = client.post(
        "/verify/scan",
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
        headers=guard_headers,
    )
    assert response.status_code == 400


# --- helpers ---------------------------------------------------------------

def _render_code128(text: str):
    try:
        import zxingcpp
        from PIL import Image
    except ImportError:  # pragma: no cover
        return None

    try:
        image = zxingcpp.write_barcode(
            zxingcpp.BarcodeFormat.Code128, text, width=600, height=200
        )
    except Exception:  # pragma: no cover - older binding signature
        return None

    if not isinstance(image, Image.Image):
        image = Image.fromarray(image)
    # Quiet zone around the symbol so the decoder can lock on.
    padded = Image.new("L", (image.width + 80, image.height + 80), 255)
    padded.paste(image.convert("L"), (40, 40))

    import io as _io

    buffer = _io.BytesIO()
    padded.save(buffer, format="PNG")
    return buffer.getvalue()


def _render_blank():
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return None

    import io as _io

    buffer = _io.BytesIO()
    Image.new("L", (300, 200), 255).save(buffer, format="PNG")
    return buffer.getvalue()
