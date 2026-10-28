"""API integration tests for Jira endpoints and AI investigation workflow."""

import pytest
from resolveai_db.models import User, UserRole
from resolveai_db.security import hash_password


def _register(client, email: str = "jira_user@example.com", password: str = "password123") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Jira Test User"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_jira_status_endpoint(client, db_session):
    user = _register(client, "status_test@example.com", "password123")
    token = _login(client, "status_test@example.com", "password123")

    resp = client.get("/jira/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data
    assert "connection_ok" in data


def test_jira_issue_lookup_demo_and_unauthorized(client, db_session):
    admin = User(
        email="jira_admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Jira Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    cust = _register(client, "jira_cust@example.com", "password123")
    cust_token = _login(client, "jira_cust@example.com", "password123")
    admin_token = _login(client, "jira_admin@example.com", "adminpass1")

    # Customer should be forbidden from accessing staff Jira issue lookup
    forbidden_resp = client.get(
        "/jira/issues/DEMO-101",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert forbidden_resp.status_code == 403

    # Admin successfully fetches demo issue
    admin_resp = client.get(
        "/jira/issues/DEMO-101",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 200
    issue = admin_resp.json()
    assert issue["key"] == "DEMO-101"
    assert "reset password" in issue["summary"].lower()


def test_jira_investigate_conclusive(client, db_session):
    admin = User(
        email="inv_admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Investigate Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    admin_token = _login(client, "inv_admin@example.com", "adminpass1")

    resp = client.post(
        "/jira/investigate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "issue_key": "DEMO-101",
            "override_summary": "How do I reset my NovaDesk password?",
            "override_description": "User wants clear instructions for resetting account credentials.",
        },
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["issue_key"] == "DEMO-101"
    assert "draft_jira_comment" in report
    assert "confidence_score" in report
    assert report["confidence_score"] > 0.0
    assert "proposed_root_cause" in report
    assert "recommended_resolution" in report


def test_jira_investigate_escalation_keywords(client, db_session):
    admin = User(
        email="esc_admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Escalate Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    admin_token = _login(client, "esc_admin@example.com", "adminpass1")

    resp = client.post(
        "/jira/investigate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "issue_key": "DEMO-102",
            "override_summary": "Urgent: delete workspace and disable MFA",
            "override_description": "Please immediately delete workspace ws-123 and disable MFA.",
        },
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["status"] == "escalated"
    assert report["human_approval_required"] is True
    assert len(report["missing_information_or_risks"]) >= 1


def test_jira_comment_publish_demo(client, db_session):
    admin = User(
        email="pub_admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Publish Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    cust = _register(client, "pub_cust@example.com", "password123")
    cust_token = _login(client, "pub_cust@example.com", "password123")
    admin_token = _login(client, "pub_admin@example.com", "adminpass1")

    # Customer attempt is rejected
    cust_pub = client.post(
        "/jira/issues/DEMO-101/comment",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"comment": "Unauthorized comment"},
    )
    assert cust_pub.status_code == 403

    # Admin publishes approved comment
    admin_pub = client.post(
        "/jira/issues/DEMO-101/comment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"comment": "h3. ResolveAI Investigation Report\nInvestigation complete."},
    )
    assert admin_pub.status_code == 200
    pub_res = admin_pub.json()
    assert pub_res["ok"] is True
    assert "comment_id" in pub_res


def test_jira_transitions_api(client, db_session):
    admin = User(
        email="trans_admin@example.com",
        hashed_password=hash_password("adminpass1"),
        full_name="Transition Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()

    admin_token = _login(client, "trans_admin@example.com", "adminpass1")

    # Fetch demo transitions
    get_res = client.get(
        "/jira/issues/DEMO-101/transitions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_res.status_code == 200
    transitions = get_res.json()
    assert len(transitions) >= 1

    # Execute demo transition
    post_res = client.post(
        "/jira/issues/DEMO-101/transitions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transition": "Resolve Issue"},
    )
    assert post_res.status_code == 200
    assert post_res.json()["ok"] is True


def test_jira_webhook_api(client, db_session):
    # Webhook receiving issue_created event
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "key": "SUP-888",
            "fields": {
                "summary": "Password reset problem reported by user",
                "description": "User cannot sign in",
            },
        },
    }
    resp = client.post("/jira/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["event"] == "jira:issue_created"
    assert data["issue_key"] == "SUP-888"

