"""Users, departments, templates, settings and audit logs."""


def test_admin_creates_user_who_can_log_in_with_temporary_password(client, admin_headers):
    response = client.post(
        "/api/v1/users", headers=admin_headers, json={"email": "New@Example.com", "fullName": "New User", "role": "OPERATOR"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["roles"] == ["OPERATOR"]
    assert body["user"]["reportsSubmitted"] == 0

    login = client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": body["temporaryPassword"]})
    assert login.status_code == 200


def test_duplicate_email_is_rejected(client, admin_headers):
    payload = {"email": "operator@example.com", "fullName": "Dup", "role": "OPERATOR"}
    assert client.post("/api/v1/users", headers=admin_headers, json=payload).status_code == 409


def test_non_admin_cannot_manage_users(client, inspector_headers):
    assert client.get("/api/v1/users", headers=inspector_headers).status_code == 403
    payload = {"email": "x@example.com", "fullName": "X", "role": "VIEWER"}
    assert client.post("/api/v1/users", headers=inspector_headers, json=payload).status_code == 403


def test_list_filter_and_update_users(client, admin_headers):
    page = client.get("/api/v1/users", headers=admin_headers, params={"role": "QUALITY_INSPECTOR"}).json()
    assert page["totalElements"] == 1
    inspector = page["content"][0]
    assert inspector["email"] == "inspector@example.com"

    updated = client.patch(
        f"/api/v1/users/{inspector['id']}", headers=admin_headers, json={"fullName": "Chief Inspector", "role": "VIEWER", "active": False}
    )
    assert updated.status_code == 200
    assert updated.json()["fullName"] == "Chief Inspector"
    assert updated.json()["roles"] == ["VIEWER"]
    assert updated.json()["active"] is False

    # Deactivated users cannot log in.
    assert client.post("/api/v1/auth/login", json={"email": "inspector@example.com", "password": "InspectPass123"}).status_code == 401
    assert client.get("/api/v1/users", headers=admin_headers, params={"role": "BOGUS"}).status_code == 400


def test_admin_cannot_lock_themselves_out(client, admin_headers):
    me = client.get("/api/v1/auth/profile", headers=admin_headers).json()
    response = client.patch(f"/api/v1/users/{me['id']}", headers=admin_headers, json={"active": False})
    assert response.status_code == 409


def test_user_stats(client, admin_headers):
    stats = client.get("/api/v1/users/stats", headers=admin_headers).json()
    assert stats == {"totalUsers": 3, "activeNow": 3, "activeAccounts": 3, "reportsToday": 0}


def test_departments_visible_to_any_user(client, operator_headers):
    departments = client.get("/api/v1/departments", headers=operator_headers).json()
    assert any(d["code"] == "INCOMING_QA" and d["name"] == "Incoming QA" for d in departments)
    assert [d["name"] for d in departments] == sorted(d["name"] for d in departments)


def test_templates_list_get_and_admin_patch(client, admin_headers, operator_headers):
    templates = client.get("/api/v1/templates", headers=operator_headers).json()
    assert {t["code"] for t in templates} == {
        "SUPPLIER_REJECTION", "SUPPLIER_REWORK", "SUPPLIER_SEGREGATION", "SUPPLIER_LOT_REJECTION_SUMMARY", "SCRAP_NOTE",
    }
    rejection = next(t for t in templates if t["code"] == "SUPPLIER_REJECTION")
    assert rejection["quantityFieldKey"] == "rejectionQty"
    month = rejection["fields"][0]
    assert (month["fieldKey"], month["scope"], month["dataType"], month["required"]) == ("month", "HEADER", "MONTH", True)

    assert client.patch(f"/api/v1/templates/{rejection['id']}", headers=operator_headers, json={"active": False}).status_code == 403

    patched = client.patch(f"/api/v1/templates/{rejection['id']}", headers=admin_headers, json={"active": False})
    assert patched.json()["active"] is False
    active_only = client.get("/api/v1/templates", headers=admin_headers, params={"activeOnly": "true"}).json()
    assert rejection["id"] not in [t["id"] for t in active_only]
    client.patch(f"/api/v1/templates/{rejection['id']}", headers=admin_headers, json={"active": True})


def test_settings_update_and_validation(client, admin_headers, inspector_headers):
    assert client.get("/api/v1/settings", headers=inspector_headers).status_code == 403

    settings = {s["key"]: s["value"] for s in client.get("/api/v1/settings", headers=admin_headers).json()}
    assert settings["ocr.verified-threshold"] == "0.85"

    updated = client.patch("/api/v1/settings", headers=admin_headers, json={"ocr.verified-threshold": 0.9, "unknown.key": "x"})
    assert {s["key"]: s["value"] for s in updated.json()}["ocr.verified-threshold"] == "0.9"
    assert client.patch("/api/v1/settings", headers=admin_headers, json={"ocr.review-threshold": "2"}).status_code == 400

    client.patch("/api/v1/settings", headers=admin_headers, json={"ocr.verified-threshold": "0.85"})


def test_audit_logs_record_admin_actions(client, admin_headers):
    client.post("/api/v1/users", headers=admin_headers, json={"email": "a@example.com", "fullName": "A", "role": "VIEWER"})

    logs = client.get("/api/v1/audit-logs", headers=admin_headers).json()
    assert logs["content"][0]["action"] == "USER_CREATED"
    assert logs["content"][0]["actor"] == "Meenakshi Admin"
    assert logs["content"][0]["correlationId"]


def test_health_and_info(client):
    assert client.get("/actuator/health").json()["status"] == "UP"
    assert client.get("/actuator/health/liveness").json() == {"status": "UP"}
    assert "version" in client.get("/actuator/info").json()["app"]
