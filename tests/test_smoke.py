from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BOOTSTRAP_HEADERS = {"x-api-key": "change-this-in-production"}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_org_admin_key_expiration_audit_and_rotation_flow():
    org_payload = {
        "id": "org_smoke_1",
        "name": "Smoke Brokerage",
        "org_type": "brokerage",
    }
    response = client.post("/auth/organizations", json=org_payload, headers=BOOTSTRAP_HEADERS)
    assert response.status_code == 201

    response = client.post(
        "/auth/api-keys",
        json={"organization_id": "org_smoke_1", "name": "admin-key", "role": "admin", "rate_limit_per_minute": 50},
        headers=BOOTSTRAP_HEADERS,
    )
    assert response.status_code == 201
    admin_payload = response.json()
    admin_headers = {"x-api-key": admin_payload["api_key"]}
    admin_key_id = admin_payload["id"]

    response = client.post(
        "/auth/api-keys",
        json={
            "organization_id": "org_smoke_1",
            "name": "expired-member-key",
            "role": "member",
            "expires_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    expired_headers = {"x-api-key": response.json()["api_key"]}
    expired_use = client.get("/listings", headers=expired_headers)
    assert expired_use.status_code == 401

    listing_payload = {
        "id": "smoke_listing_1",
        "address": "123 Main St, Nashville, TN",
        "mls_id": "MLS-SMOKE-1",
        "status": "active",
        "property_type": "single_family",
        "city": "Nashville",
        "state": "TN",
        "zip_code": "37215",
        "list_price": 650000,
        "bedrooms": 4,
        "bathrooms": 3,
        "sqft": 2800,
    }
    response = client.post("/listings", json=listing_payload, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["organization_id"] == "org_smoke_1"

    response = client.post(
        "/auth/api-keys",
        json={"organization_id": "org_smoke_1", "name": "member-key", "role": "member", "rate_limit_per_minute": 50},
        headers=admin_headers,
    )
    assert response.status_code == 201
    member_payload = response.json()
    member_headers = {"x-api-key": member_payload["api_key"]}

    signal_payload = {
        "id": "sig_smoke_1",
        "listing_id": "smoke_listing_1",
        "signal_type": "view",
        "signal_value": 5,
        "source": "portal",
    }
    response = client.post("/signals", json=signal_payload, headers=member_headers)
    assert response.status_code == 201
    assert response.json()["organization_id"] == "org_smoke_1"

    response = client.post("/listings/smoke_listing_1/recalculate", headers=member_headers)
    assert response.status_code == 200

    response = client.post("/listings/smoke_listing_1/recommendations/generate", headers=member_headers)
    assert response.status_code == 200
    assert all(item["organization_id"] == "org_smoke_1" for item in response.json())

    forbidden = client.delete("/listings/smoke_listing_1", headers=member_headers)
    assert forbidden.status_code == 403

    response = client.delete("/listings/smoke_listing_1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["deleted_at"] is not None

    response = client.post("/listings/smoke_listing_1/restore", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["deleted_at"] is None

    response = client.get("/auth/organizations/org_smoke_1/audit-events", headers=admin_headers)
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()}
    assert "listing.create" in actions
    assert "signal.create" in actions
    assert "listing.delete" in actions
    assert "listing.restore" in actions

    response = client.post(
        f"/auth/api-keys/{admin_key_id}/rotate",
        json={"name": "rotated-admin", "revoke_old_key": True, "rate_limit_per_minute": 3, "role": "admin"},
        headers=BOOTSTRAP_HEADERS,
    )
    assert response.status_code == 200
    rotated = response.json()
    rotated_headers = {"x-api-key": rotated["api_key"]}

    response = client.get("/listings", headers=admin_headers)
    assert response.status_code == 401

    for _ in range(3):
        ok = client.get("/listings", headers=rotated_headers)
        assert ok.status_code == 200

    limited = client.get("/listings", headers=rotated_headers)
    assert limited.status_code == 429

    response = client.post(f"/auth/api-keys/{rotated['id']}/revoke", headers=BOOTSTRAP_HEADERS)
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["revoked_at"] is not None


def test_auth_required():
    response = client.get("/listings/smoke_listing_1")
    assert response.status_code == 401
