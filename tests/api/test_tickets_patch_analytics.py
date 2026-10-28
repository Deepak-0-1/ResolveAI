from resolveai_db.models import User, UserRole
from resolveai_db.security import hash_password


def _register(client, email: str = "patch_user@example.com", password: str = "password123") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Patch User"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_patch_ticket_and_messages(client, db_session) -> None:
    admin = User(
        email="admin_patch@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Admin Patch",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    cust = _register(client, "customer_patch@example.com", "password123")
    cust_token = _login(client, "customer_patch@example.com", "password123")
    admin_token = _login(client, "admin_patch@example.com", "adminpass1")

    # 1. Create ticket
    create_resp = client.post(
        "/tickets",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"subject": "Login problem", "body": "Cannot login to app", "priority": "medium"},
    )
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["id"]

    # 2. Customer posts message
    msg_resp = client.post(
        f"/tickets/{ticket_id}/messages",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"content": "Here is an extra detail about the bug"},
    )
    assert msg_resp.status_code == 201
    assert msg_resp.json()["role"] == "user"

    # 3. Customer cannot change priority
    fail_patch = client.patch(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"priority": "critical"},
    )
    assert fail_patch.status_code == 403

    # 4. Admin updates priority and category
    admin_patch = client.patch(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"priority": "high", "category": "Authentication", "status": "escalated"},
    )
    assert admin_patch.status_code == 200
    assert admin_patch.json()["priority"] == "high"
    assert admin_patch.json()["category"] == "Authentication"
    assert admin_patch.json()["status"] == "escalated"

    # 5. Admin replies with agent message
    agent_msg = client.post(
        f"/tickets/{ticket_id}/messages",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"content": "We have resolved your login issue. Please try now.", "role": "agent"},
    )
    assert agent_msg.status_code == 201
    assert agent_msg.json()["role"] == "agent"

    # 6. Customer closes own ticket
    close_resp = client.patch(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"status": "closed"},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "closed"


def test_analytics_overview(client, db_session) -> None:
    admin = User(
        email="admin_analytics@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Admin Analytics",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    cust = _register(client, "cust_analytics@example.com", "password123")
    cust_token = _login(client, "cust_analytics@example.com", "password123")
    admin_token = _login(client, "admin_analytics@example.com", "adminpass1")

    # Create ticket
    client.post(
        "/tickets",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"subject": "Billing query", "body": "Invoice question"},
    )

    # Fetch customer analytics
    cust_overview = client.get(
        "/analytics/overview",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert cust_overview.status_code == 200
    data = cust_overview.json()
    assert data["total_tickets"] >= 1
    assert "status_distribution" in data
    assert "priority_distribution" in data

    # Fetch admin analytics
    admin_overview = client.get(
        "/analytics/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_overview.status_code == 200
    admin_data = admin_overview.json()
    assert admin_data["total_tickets"] >= 1
    assert "kb_stats" in admin_data
