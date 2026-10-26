"""End-to-end integration: the complete journey every role performs in the UI.

This exercises router -> service -> repository -> database for all four roles
in one continuous story, using only HTTP calls - the same calls the React app
makes.
"""

from datetime import date, timedelta

from app.utils.timezone import ist_today
from tests.conftest import TEST_PASSWORD, auth_headers

TODAY = ist_today()
NEXT_WEEK = TODAY + timedelta(days=7)


def test_full_lifecycle_market_pass(client, student, warden, guard):
    student_headers = auth_headers(client, student.id)
    warden_headers = auth_headers(client, warden.id)
    guard_headers = auth_headers(client, guard.id)

    # 1. Student applies for a market pass.
    created = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": TODAY.isoformat(),
            "leave_end": TODAY.isoformat(),
        },
        headers=student_headers,
    )
    assert created.status_code == 200, created.text
    pass_id = created.json()["pass_id"]

    # 2. It shows up pending in the student's history and the warden's queue.
    mine = client.get("/pass/my_pass", headers=student_headers).json()
    assert [p["pass_status"] for p in mine] == ["pending"]

    queue = client.get("/pass/pending", headers=warden_headers).json()
    assert [p["pass_id"] for p in queue] == [pass_id]

    # 3. The gate rejects it while it is still pending.
    gate = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert gate["valid"] is False

    # 4. Warden approves it.
    approved = client.put(
        f"/pass/status/{pass_id}",
        json={"pass_status": "approved", "remark": "OK"},
        headers=warden_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["pass_status"] == "approved"
    assert client.get("/pass/pending", headers=warden_headers).json() == []

    # 5. The gate now accepts it and offers a check-out.
    gate = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert gate["valid"] is True
    assert gate["pass_details"]["pass_id"] == pass_id
    assert gate["pass_details"]["logs"] == []

    # 6. Guard checks the student out.
    out = client.post(f"/verify/checkout/{pass_id}", headers=guard_headers)
    assert out.status_code == 200

    # 7. While out, the student cannot apply for anything new.
    blocked = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": TODAY.isoformat(),
            "leave_end": TODAY.isoformat(),
        },
        headers=student_headers,
    )
    assert blocked.status_code == 403

    # 8. Re-verifying shows the student as out, so the UI offers check-in.
    gate = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert gate["valid"] is True
    assert gate["pass_details"]["logs"][0]["student_status"] == "out"

    # 9. Guard checks the student back in.
    back_in = client.post(f"/verify/checkin/{pass_id}", headers=guard_headers)
    assert back_in.status_code == 200

    # 10. The pass is now spent.
    gate = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert gate["valid"] is False
    assert "already been used" in gate["message"]

    # 11. Both scans are on the pass; the warden feed shows the latest one.
    feed = client.get("/pass/logs", headers=warden_headers).json()
    assert len(feed["logs"]) == 1
    assert feed["logs"][0]["action"] == "checked_in"
    assert feed["logs"][0]["leave_pass"]["college"]["id"] == student.id

    # 12. And the student may apply again.
    again = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": TODAY.isoformat(),
            "leave_end": TODAY.isoformat(),
        },
        headers=student_headers,
    )
    assert again.status_code == 200


def test_full_lifecycle_leave_pass_with_extension(client, student, warden, guard):
    student_headers = auth_headers(client, student.id)
    warden_headers = auth_headers(client, warden.id)
    guard_headers = auth_headers(client, guard.id)

    created = client.post(
        "/pass/",
        json={
            "pass_type": "leave",
            "leave_start": TODAY.isoformat(),
            "leave_end": (TODAY + timedelta(days=2)).isoformat(),
        },
        headers=student_headers,
    )
    pass_id = created.json()["pass_id"]

    client.put(
        f"/pass/status/{pass_id}",
        json={"pass_status": "approved"},
        headers=warden_headers,
    )

    # Student leaves campus.
    assert (
        client.post(f"/verify/checkout/{pass_id}", headers=guard_headers).status_code
        == 200
    )

    # ...then asks for more time, which sends the pass back to pending.
    extended = client.post(
        f"/pass/extend/{pass_id}",
        json={"new_leave_end": NEXT_WEEK.isoformat()},
        headers=student_headers,
    )
    assert extended.status_code == 200
    assert extended.json()["pass"]["pass_status"] == "pending"
    assert extended.json()["pass"]["is_extension"] is True

    # A pending pass does not open the gate.
    gate = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert gate["valid"] is False

    # Warden approves the extension, and the gate works again.
    client.put(
        f"/pass/status/{pass_id}",
        json={"pass_status": "approved", "remark": "Extension granted"},
        headers=warden_headers,
    )
    gate = client.get(f"/verify/manual/{student.id}", headers=guard_headers).json()
    assert gate["valid"] is True
    assert gate["pass_details"]["leave_end"] == NEXT_WEEK.isoformat()

    # The remark reaches the student's history.
    mine = client.get("/pass/my_pass", headers=student_headers).json()
    assert mine[0]["remark"] == "Extension granted"


def test_admin_onboards_a_student_who_then_uses_the_app(client, admin, warden):
    admin_headers = auth_headers(client, admin.id)
    warden_headers = auth_headers(client, warden.id)

    created = client.post(
        "/admin/users",
        data={
            "id": "A1234CS9001",
            "first_name": "Omar",
            "last_name": "Shah",
            "role": "student",
            "parents_phone": "9123456780",
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    default_password = created.json()["default_password"]

    new_student_headers = auth_headers(client, "A1234CS9001", default_password)

    applied = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": TODAY.isoformat(),
            "leave_end": TODAY.isoformat(),
        },
        headers=new_student_headers,
    )
    assert applied.status_code == 200

    queue = client.get("/pass/pending", headers=warden_headers).json()
    assert queue[0]["college"]["first_name"] == "Omar"
    assert queue[0]["college"]["parents_phone"] == "9123456780"

    # Admin resets the password; the old one stops working immediately.
    client.put(
        "/admin/users/A1234CS9001/password",
        json={"new_password": "Reset#2026"},
        headers=admin_headers,
    )
    assert (
        client.post(
            "/login/",
            json={"username": "A1234CS9001", "password": default_password},
        ).status_code
        == 404
    )
    auth_headers(client, "A1234CS9001", "Reset#2026")

    # Admin deactivates the account; login is refused but the pass survives.
    client.delete("/admin/users/A1234CS9001", headers=admin_headers)
    assert (
        client.post(
            "/login/", json={"username": "A1234CS9001", "password": "Reset#2026"}
        ).status_code
        == 403
    )
    assert len(client.get("/pass/all", headers=warden_headers).json()) == 1


def test_roles_are_isolated_end_to_end(client, student, warden, guard, admin):
    student_headers = auth_headers(client, student.id)
    warden_headers = auth_headers(client, warden.id)
    guard_headers = auth_headers(client, guard.id)
    admin_headers = auth_headers(client, admin.id)

    # Each screen's primary endpoint, against every role.
    expectations = [
        ("GET", "/pass/my_pass", {"student": 200, "warden": 403, "guard": 403, "admin": 403}),
        ("GET", "/pass/pending", {"student": 403, "warden": 200, "guard": 403, "admin": 403}),
        ("GET", "/pass/logs", {"student": 403, "warden": 200, "guard": 403, "admin": 200}),
        ("GET", f"/verify/manual/{student.id}", {"student": 403, "warden": 403, "guard": 200, "admin": 403}),
    ]
    headers_by_role = {
        "student": student_headers,
        "warden": warden_headers,
        "guard": guard_headers,
        "admin": admin_headers,
    }

    for method, path, expected in expectations:
        for role, status_code in expected.items():
            response = client.request(method, path, headers=headers_by_role[role])
            assert response.status_code == status_code, (
                f"{method} {path} as {role} -> {response.status_code}"
            )


def test_login_response_shape_matches_the_frontend_contract(client, student):
    """AuthContext stores response.access_token and response.user verbatim."""
    response = client.post(
        "/login/", json={"username": student.id, "password": TEST_PASSWORD}
    )
    body = response.json()
    assert set(body) == {"access_token", "token_type", "user"}
    assert set(body["user"]) == {
        "id",
        "first_name",
        "last_name",
        "role",
        "contact_details",
        "parent_email",
        "photo_url",
        "parents_phone",
        "is_active",
    }
    # ProtectedRoute calls user.role.toLowerCase()
    assert body["user"]["role"] == body["user"]["role"].lower()


def test_cors_preflight_allows_the_vite_dev_server(client):
    response = client.options(
        "/login/",
        headers={
            "Origin": "https://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"] == "https://localhost:5173"
    )
