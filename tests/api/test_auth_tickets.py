from resolveai_db.models import User, UserRole
from resolveai_db.security import hash_password


def _register(client, email: str = "user@example.com", password: str = "password123") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_register_and_me(client) -> None:
    user = _register(client)
    assert user["role"] == "customer"
    token = _login(client, "user@example.com", "password123")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_login_rejects_bad_password(client) -> None:
    _register(client)
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_customer_cannot_see_others_tickets(client, db_session) -> None:
    admin = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    customer_a = _register(client, "a@example.com", "password123")
    token_a = _login(client, "a@example.com", "password123")
    create = client.post(
        "/tickets",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"subject": "Billing issue", "body": "Invoice missing"},
    )
    assert create.status_code == 201
    ticket_id = create.json()["id"]
    assert create.json()["user_id"] == customer_a["id"]

    _register(client, "b@example.com", "password123")
    token_b = _login(client, "b@example.com", "password123")
    forbidden = client.get(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden.status_code == 403

    admin_token = _login(client, "admin@example.com", "adminpass1")
    allowed = client.get(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    assert len(allowed.json()["messages"]) == 1


def test_admin_lists_all_tickets(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            hashed_password=hash_password("adminpass1"),
            full_name="Admin",
            role=UserRole.admin,
        )
    )
    db_session.commit()

    _register(client, "c@example.com", "password123")
    token_c = _login(client, "c@example.com", "password123")
    client.post(
        "/tickets",
        headers={"Authorization": f"Bearer {token_c}"},
        json={"subject": "API key help", "body": "Where is my key?"},
    )

    admin_token = _login(client, "admin@example.com", "adminpass1")
    listed = client.get("/tickets", headers={"Authorization": f"Bearer {admin_token}"})
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
