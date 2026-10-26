"""Admin console: onboarding, bulk import, soft delete, password override."""

import io

from app.core.security import verify_password
from app.models import Role, User
from tests.conftest import TEST_PASSWORD, make_user


# --- single user onboarding -----------------------------------------------

def test_admin_creates_a_user(client, db, admin_headers):
    response = client.post(
        "/admin/users",
        data={
            "id": "A1234CS2002",
            "first_name": "Ravi",
            "last_name": "Kumar",
            "role": "student",
            "contact_details": "9000000001",
            "parent_email": "parent2@example.com",
            "parents_phone": "9000000002",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["user"]["id"] == "A1234CS2002"
    assert body["user"]["role"] == "student"
    assert body["default_password"]

    created = db.get(User, "A1234CS2002")
    assert created is not None
    assert created.is_active is True
    assert created.parents_phone == "9000000002"
    # The stored value is a hash of the advertised default password.
    assert verify_password(body["default_password"], created.password)


def test_created_user_can_log_in_with_the_default_password(client, admin_headers):
    create = client.post(
        "/admin/users",
        data={"id": "A1234CS2003", "first_name": "Nina", "last_name": "Rao"},
        headers=admin_headers,
    )
    default_password = create.json()["default_password"]

    login = client.post(
        "/login/",
        json={"username": "A1234CS2003", "password": default_password},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "student"


def test_duplicate_user_id_is_rejected(client, student, admin_headers):
    response = client.post(
        "/admin/users",
        data={"id": student.id, "first_name": "Clone", "last_name": "User"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User ID already exists"


def test_photo_upload_is_stored_and_referenced(
    client, db, admin_headers, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))

    response = client.post(
        "/admin/users",
        data={"id": "A1234CS2004", "first_name": "Photo", "last_name": "Test"},
        files={"photo": ("face.jpg", io.BytesIO(b"\xff\xd8\xff-fake-jpeg"), "image/jpeg")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    created = db.get(User, "A1234CS2004")
    assert created.photo_url == "A1234CS2004.jpg"
    assert (tmp_path / "A1234CS2004.jpg").exists()


def test_non_admin_cannot_create_users(client, student_headers, warden_headers):
    payload = {"id": "X9", "first_name": "No", "last_name": "Way"}
    assert (
        client.post("/admin/users", data=payload, headers=student_headers).status_code
        == 403
    )
    assert (
        client.post("/admin/users", data=payload, headers=warden_headers).status_code
        == 403
    )


def test_create_user_requires_authentication(client):
    response = client.post(
        "/admin/users", data={"id": "X9", "first_name": "No", "last_name": "Way"}
    )
    assert response.status_code == 401


# --- bulk import ----------------------------------------------------------

BULK_CSV = b"""id,first_name,last_name,role
A1234CS3001,Meera,Nair,student
A1234CS3002,Dev,Patel,student
,Broken,Row,student
A1234CS3003,,Missing,student
A1234CS3004,Sana,Khan,guard
"""


def test_bulk_upload_creates_valid_rows_and_reports_failures(
    client, db, admin_headers
):
    response = client.post(
        "/admin/users/bulk",
        files={"file": ("users.csv", io.BytesIO(BULK_CSV), "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total_processed"] == 5
    assert body["success_count"] == 3
    assert body["failed_count"] == 2
    assert {failure["reason"] for failure in body["failures"]} == {
        "Missing fields in CSV row"
    }
    # The dashboard builds its password sheet from this list.
    assert {entry["id"] for entry in body["successful_users"]} == {
        "A1234CS3001",
        "A1234CS3002",
        "A1234CS3004",
    }
    assert body["successful_users"][0]["name"] == "Meera Nair"

    assert db.get(User, "A1234CS3001") is not None
    assert db.get(User, "A1234CS3004").role == Role.guard


def test_bulk_upload_reports_duplicates_without_aborting(
    client, db, admin_headers
):
    make_user(db, "A1234CS3001", Role.student)

    response = client.post(
        "/admin/users/bulk",
        files={"file": ("users.csv", io.BytesIO(BULK_CSV), "text/csv")},
        headers=admin_headers,
    )
    body = response.json()
    assert body["success_count"] == 2
    assert any(
        failure["reason"] == "User Id already exists in database"
        for failure in body["failures"]
    )


def test_bulk_upload_rejects_a_csv_without_required_columns(client, admin_headers):
    response = client.post(
        "/admin/users/bulk",
        files={"file": ("bad.csv", io.BytesIO(b"name,email\nx,y\n"), "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "columns" in response.json()["detail"]


def test_bulk_upload_requires_admin(client, warden_headers):
    response = client.post(
        "/admin/users/bulk",
        files={"file": ("users.csv", io.BytesIO(BULK_CSV), "text/csv")},
        headers=warden_headers,
    )
    assert response.status_code == 403


# --- deactivate -----------------------------------------------------------

def test_deactivate_user_blocks_login_and_keeps_the_row(
    client, db, student, admin_headers
):
    response = client.delete(f"/admin/users/{student.id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    db.expire_all()
    assert db.get(User, student.id) is not None  # soft delete, row preserved
    assert db.get(User, student.id).is_active is False

    login = client.post(
        "/login/", json={"username": student.id, "password": TEST_PASSWORD}
    )
    assert login.status_code == 403


def test_deactivate_missing_user_is_404(client, admin_headers):
    response = client.delete("/admin/users/NOPE", headers=admin_headers)
    assert response.status_code == 404


def test_deactivate_requires_admin(client, student, warden_headers):
    response = client.delete(f"/admin/users/{student.id}", headers=warden_headers)
    assert response.status_code == 403


# --- password override ----------------------------------------------------

def test_admin_resets_a_password(client, student, admin_headers):
    response = client.put(
        f"/admin/users/{student.id}/password",
        json={"new_password": "BrandNew#1"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    assert (
        client.post(
            "/login/", json={"username": student.id, "password": "BrandNew#1"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/login/", json={"username": student.id, "password": TEST_PASSWORD}
        ).status_code
        == 404
    )


def test_short_password_is_rejected(client, student, admin_headers):
    response = client.put(
        f"/admin/users/{student.id}/password",
        json={"new_password": "123"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "at least 6 characters" in response.json()["detail"]


def test_reset_password_for_missing_user_is_404(client, admin_headers):
    response = client.put(
        "/admin/users/NOPE/password",
        json={"new_password": "LongEnough1"},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_reset_password_requires_admin(client, student, student_headers):
    response = client.put(
        f"/admin/users/{student.id}/password",
        json={"new_password": "LongEnough1"},
        headers=student_headers,
    )
    assert response.status_code == 403


# --- /user router ---------------------------------------------------------

def test_user_router_creates_a_user_with_an_explicit_password(
    client, db, admin_headers
):
    response = client.post(
        "/user/",
        json={
            "id": "A1234CS4001",
            "password": "ChosenPass1",
            "first_name": "Ira",
            "last_name": "Sen",
            "role": "warden",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["id"] == "A1234CS4001"
    assert "password" not in response.json()

    assert (
        client.post(
            "/login/", json={"username": "A1234CS4001", "password": "ChosenPass1"}
        ).status_code
        == 200
    )


def test_user_router_rejects_duplicates(client, student, admin_headers):
    response = client.post(
        "/user/",
        json={
            "id": student.id,
            "password": "ChosenPass1",
            "first_name": "Dup",
            "last_name": "User",
            "role": "student",
        },
        headers=admin_headers,
    )
    assert response.status_code == 409


def test_user_router_rejects_a_short_password(client, admin_headers):
    response = client.post(
        "/user/",
        json={
            "id": "A1234CS4002",
            "password": "123",
            "first_name": "Short",
            "last_name": "Pass",
            "role": "student",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


def test_admin_accounts_cannot_be_hard_deleted(client, admin, admin_headers):
    response = client.delete(f"/user/{admin.id}", headers=admin_headers)
    assert response.status_code == 403
    assert "strictly prohibited" in response.json()["detail"]


def test_hard_delete_removes_a_student(client, db, student, admin_headers):
    student_id = student.id
    response = client.delete(f"/user/{student_id}", headers=admin_headers)
    assert response.status_code == 200
    # Drop the cached instance so the lookup really hits the database.
    db.expunge_all()
    assert db.get(User, student_id) is None
