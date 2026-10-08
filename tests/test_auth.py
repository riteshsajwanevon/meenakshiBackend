from app.services import email_service

from tests.conftest import ADMIN, OPERATOR, login


def test_login_returns_tokens_and_user_in_camel_case(client):
    body = login(client, ADMIN)

    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == 30 * 60
    assert body["accessToken"] and body["refreshToken"]
    assert body["user"] == {"id": 1, "email": "admin@example.com", "fullName": "Meenakshi Admin", "roles": ["ADMIN"], "active": True}


def test_login_is_case_insensitive_on_email(client):
    response = client.post("/api/v1/auth/login", json={"email": "ADMIN@Example.com", "password": ADMIN[1]})
    assert response.status_code == 200


def test_wrong_password_returns_standard_error_with_correlation_id(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN[0], "password": "wrong"},
        headers={"X-Correlation-Id": "test-correlation-1"},
    )

    assert response.status_code == 401
    assert response.headers["X-Correlation-Id"] == "test-correlation-1"
    body = response.json()
    assert body["message"] == "The email or password is incorrect"
    assert body["error"] == "Unauthorized"
    assert body["path"] == "/api/v1/auth/login"
    assert body["correlationId"] == "test-correlation-1"
    assert body["timestamp"].endswith("Z")
    assert body["details"] == []


def test_correlation_id_is_generated_when_missing(client):
    response = client.get("/actuator/health")
    assert response.status_code == 200
    assert len(response.headers["X-Correlation-Id"]) == 36  # UUID


def test_validation_error_format(client):
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": ""})

    assert response.status_code == 400
    body = response.json()
    assert body["message"] == "Validation failed"
    assert any(detail.startswith("email:") for detail in body["details"])
    assert any(detail.startswith("password:") for detail in body["details"])


def test_profile_requires_a_valid_token(client):
    assert client.get("/api/v1/auth/profile").status_code == 401
    assert client.get("/api/v1/auth/profile", headers={"Authorization": "Bearer nonsense"}).status_code == 401

    token = login(client, OPERATOR)["accessToken"]
    me = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["roles"] == ["OPERATOR"]

    # The old path stays as an alias for the existing frontend.
    legacy = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert legacy.json() == me.json()


def test_refresh_token_cannot_be_used_as_access_token(client):
    refresh_token = login(client, ADMIN)["refreshToken"]
    assert client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {refresh_token}"}).status_code == 401


def test_refresh_rotates_the_refresh_token(client):
    first = login(client, ADMIN)

    refreshed = client.post("/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["refreshToken"] != first["refreshToken"]

    reused = client.post("/api/v1/auth/refresh", json={"refreshToken": first["refreshToken"]})
    assert reused.status_code == 401


def test_logout_revokes_refresh_token(client):
    tokens = login(client, ADMIN)

    assert client.post("/api/v1/auth/logout", json={"refreshToken": tokens["refreshToken"]}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}).status_code == 401
    assert client.post("/api/v1/auth/logout").status_code == 200  # body is optional


def test_forgot_and_reset_password(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(email_service, "send_password_reset", lambda email, name, token: sent.update(email=email, token=token))
    old_session = login(client, OPERATOR)

    response = client.post("/api/v1/auth/forgot-password", json={"email": OPERATOR[0]})
    assert response.status_code == 200
    assert response.json()["message"] == "If an account exists for that email, a reset token has been issued."
    assert sent["email"] == OPERATOR[0]

    reset = client.post("/api/v1/auth/reset-password", json={"token": sent["token"], "password": "BrandNew123"})
    assert reset.status_code == 200
    assert reset.json()["message"] == "Your password has been updated."

    assert client.post("/api/v1/auth/login", json={"email": OPERATOR[0], "password": "BrandNew123"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": OPERATOR[0], "password": OPERATOR[1]}).status_code == 401
    # Existing sessions are signed out and the token cannot be reused.
    assert client.post("/api/v1/auth/refresh", json={"refreshToken": old_session["refreshToken"]}).status_code == 401
    assert client.post("/api/v1/auth/reset-password", json={"token": sent["token"], "password": "Another123"}).status_code == 400


def test_forgot_password_gives_same_answer_for_unknown_email(client, monkeypatch):
    monkeypatch.setattr(email_service, "send_password_reset", lambda *args: (_ for _ in ()).throw(AssertionError("no email")))
    response = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200


def test_unknown_route_uses_standard_error_format(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["path"] == "/api/v1/does-not-exist"
