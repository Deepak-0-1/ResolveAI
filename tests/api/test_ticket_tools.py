from resolveai_db.models import User, UserRole
from resolveai_db.security import hash_password


def _login(client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _register(client, email: str, password: str = "password123") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "T"},
    )
    assert response.status_code == 201
    return response.json()


def test_status_and_draft_rbac(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            hashed_password=hash_password("adminpass1"),
            full_name="Admin",
            role=UserRole.admin,
        )
    )
    db_session.commit()

    owner = _register(client, "owner@example.com")
    owner_token = _login(client, "owner@example.com", "password123")
    created = client.post(
        "/tickets",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"subject": "Need help", "body": "Password reset failed"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    assert created.json()["user_id"] == owner["id"]

    status_ok = client.get(
        f"/tickets/{ticket_id}/status",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert status_ok.status_code == 200
    assert status_ok.json()["ticket_id"] == ticket_id

    other = _register(client, "other@example.com")
    other_token = _login(client, "other@example.com", "password123")
    forbidden = client.get(
        f"/tickets/{ticket_id}/status",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 403
    assert other["role"] == "customer"

    draft_forbidden = client.post(
        f"/tickets/{ticket_id}/draft",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"body": "Sorry for the trouble — try Forgot password."},
    )
    assert draft_forbidden.status_code == 403

    admin_token = _login(client, "admin@example.com", "adminpass1")
    draft_ok = client.post(
        f"/tickets/{ticket_id}/draft",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "Sorry for the trouble — try Forgot password."},
    )
    assert draft_ok.status_code == 200
    assert draft_ok.json()["sent"] is False
    assert "[DRAFT]" in draft_ok.json()["draft_preview"]

    detail = client.get(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail.status_code == 200
    assert any("[DRAFT]" in m["content"] for m in detail.json()["messages"])
