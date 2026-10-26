"""Login, token handling and role enforcement."""

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import Role
from tests.conftest import TEST_PASSWORD, make_user


# --- unit: password + token primitives ------------------------------------

def test_password_hash_roundtrip():
    hashed = hash_password("hunter2")
    assert hashed.startswith("$2b$")
    assert verify_password("hunter2", hashed)
    assert not verify_password("hunter3", hashed)


def test_verify_password_rejects_garbage():
    assert not verify_password("hunter2", "not-a-bcrypt-hash")
    assert not verify_password("hunter2", None)
    assert not verify_password("", hash_password("hunter2"))


def test_precomputed_bcrypt_hash_still_verifies():
    """A hash that was already in the database must keep working.

    This is a literal ``$2b$10$`` hash - the same algorithm, variant and cost
    factor the Express backend wrote with ``bcrypt.genSalt(10)`` - so rows
    created by the old backend authenticate unchanged against this one.
    """
    stored_hash = "$2b$10$XtfSn5ALTJdiII2MTIboA.jolmL.j.l7VfRanJievCeF7jvAttFvO"
    assert verify_password("Passw0rd!", stored_hash)
    assert not verify_password("wrong", stored_hash)


# --- API: login -----------------------------------------------------------

def test_login_success_returns_token_and_user(client, student):
    response = client.post(
        "/login/", json={"username": student.id, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["id"] == student.id
    assert body["user"]["role"] == "student"
    # The password hash must never be serialised.
    assert "password" not in body["user"]


def test_login_unknown_user_returns_404(client):
    response = client.post(
        "/login/", json={"username": "NOPE", "password": "whatever"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Couldn't find the user"


def test_login_wrong_password_returns_404(client, student):
    response = client.post(
        "/login/", json={"username": student.id, "password": "wrong"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Incorrect credentials"


def test_login_deactivated_account_returns_403(client, db):
    make_user(db, "X0001", Role.student, is_active=False)
    response = client.post(
        "/login/", json={"username": "X0001", "password": TEST_PASSWORD}
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


def test_login_requires_both_fields(client):
    assert client.post("/login/", json={"username": "A"}).status_code == 422


# --- API: protected endpoints ---------------------------------------------

def test_missing_token_is_401(client):
    response = client.get("/pass/my_pass")
    assert response.status_code == 401
    assert response.json()["detail"] == "Recheck your credentials"


def test_malformed_token_is_401(client):
    response = client.get(
        "/pass/my_pass", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert response.status_code == 401


def test_token_for_deleted_user_is_401(client):
    token = create_access_token({"sub": "GHOST"})
    response = client.get(
        "/pass/my_pass", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


def test_token_for_deactivated_user_is_403(client, db):
    user = make_user(db, "Z0001", Role.student)
    token = create_access_token({"sub": user.id})
    user.is_active = False
    db.commit()

    response = client.get(
        "/pass/my_pass", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_wrong_role_is_403(client, student_headers):
    # A student may not read the warden's approval queue.
    response = client.get("/pass/pending", headers=student_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "You are not authorized"


def test_guard_cannot_create_pass(client, guard_headers):
    response = client.post(
        "/pass/",
        json={
            "pass_type": "market",
            "leave_start": "2030-01-01",
            "leave_end": "2030-01-01",
        },
        headers=guard_headers,
    )
    assert response.status_code == 403


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.headers["Cache-Control"].startswith("no-store")
