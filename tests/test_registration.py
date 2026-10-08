from tests.conftest import login

NEW_USER = {"fullName": "Ravi Kumar", "email": "Ravi@Example.com", "password": "RaviPass123"}


def test_register_creates_active_user_who_can_log_in(client, admin_headers):
    response = client.post("/api/v1/auth/register", json=NEW_USER)

    assert response.status_code == 201, response.text
    user = response.json()
    assert user == {"id": user["id"], "email": "ravi@example.com", "fullName": "Ravi Kumar", "roles": ["VIEWER"], "active": True}
    assert login(client, ("ravi@example.com", "RaviPass123"))["user"]["id"] == user["id"]

    audit = client.get("/api/v1/audit-logs", headers=admin_headers).json()["content"]
    assert "USER_REGISTERED" in [entry["action"] for entry in audit]


def test_client_cannot_choose_its_own_role(client):
    response = client.post("/api/v1/auth/register", json={**NEW_USER, "role": "ADMIN", "roles": ["ADMIN"]})
    assert response.json()["roles"] == ["VIEWER"]


def test_duplicate_email_is_rejected(client):
    response = client.post("/api/v1/auth/register", json={**NEW_USER, "email": "ADMIN@example.com"})
    assert response.status_code == 409
    assert response.json()["message"] == "A user with this email already exists"


def test_invalid_input_lists_each_field(client):
    response = client.post("/api/v1/auth/register", json={"fullName": "R", "email": "nope", "password": "short"})

    assert response.status_code == 400
    assert {detail.split(":")[0] for detail in response.json()["details"]} == {"fullName", "email", "password"}
