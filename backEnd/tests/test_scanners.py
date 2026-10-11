from app.core.security import generate_scanner_api_key
from app.models import ScannerDevice
from tests.conftest import membership_payload


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_active_membership(client, member_account, admin_account):
    response = client.post(
        "/api/memberships",
        headers=auth(admin_account["token"]),
        json=membership_payload(member_account["user"]["id"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_scanner(db_session, *, location="Downtown Club", active=True):
    key_id, raw_key, key_hash = generate_scanner_api_key()
    scanner = ScannerDevice(
        name="Front Door Reader",
        location_name=location,
        key_id=key_id,
        key_hash=key_hash,
        is_active=active,
    )
    db_session.add(scanner)
    db_session.commit()
    db_session.refresh(scanner)
    return scanner, raw_key


def issue_qr(client, member_account):
    response = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert response.status_code == 200, response.text
    return response.json()["qr_token"]


def test_scanner_can_validate_qr_and_location_is_server_controlled(
    client, member_account, admin_account, db_session
):
    membership = create_active_membership(client, member_account, admin_account)
    scanner, key = create_scanner(db_session, location="Downtown Club")
    qr = issue_qr(client, member_account)

    response = client.post(
        "/api/scanner/check-ins/validate",
        headers={"X-Scanner-Key": key},
        json={"qr_token": qr},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_id"] == member_account["user"]["id"]
    assert body["membership_id"] == membership["id"]
    assert body["location_name"] == "Downtown Club"
    assert body["scanner_device_id"] == scanner.id

    db_session.refresh(scanner)
    assert scanner.last_used_at is not None


def test_scanner_cannot_spoof_location_in_request_body(
    client, member_account, admin_account, db_session
):
    create_active_membership(client, member_account, admin_account)
    _, key = create_scanner(db_session, location="Downtown Club")
    response = client.post(
        "/api/scanner/check-ins/validate",
        headers={"X-Scanner-Key": key},
        json={"qr_token": issue_qr(client, member_account), "location_name": "VIP Club"},
    )
    assert response.status_code == 422


def test_scanner_endpoint_rejects_missing_and_invalid_keys(client):
    missing = client.get("/api/scanner/check-ins/whoami")
    assert missing.status_code == 401
    invalid = client.get(
        "/api/scanner/check-ins/whoami",
        headers={"X-Scanner-Key": "fscan_0000000000000000.not-a-valid-scanner-secret"},
    )
    assert invalid.status_code == 401


def test_inactive_scanner_is_rejected(client, db_session):
    _, key = create_scanner(db_session, active=False)
    response = client.get("/api/scanner/check-ins/whoami", headers={"X-Scanner-Key": key})
    assert response.status_code == 401


def test_scanner_key_is_not_stored_in_plaintext(db_session):
    scanner, raw_key = create_scanner(db_session)
    assert raw_key not in scanner.key_hash
    assert len(scanner.key_hash) == 64


def test_replayed_qr_is_rejected_across_scanners(
    client, member_account, admin_account, db_session
):
    create_active_membership(client, member_account, admin_account)
    _, key_a = create_scanner(db_session, location="Downtown Club")
    _, key_b = create_scanner(db_session, location="Uptown Club")
    qr = issue_qr(client, member_account)

    first = client.post("/api/scanner/check-ins/validate", headers={"X-Scanner-Key": key_a}, json={"qr_token": qr})
    replay = client.post("/api/scanner/check-ins/validate", headers={"X-Scanner-Key": key_b}, json={"qr_token": qr})
    assert first.status_code == 201
    assert replay.status_code == 409


def test_rotating_scanner_key_invalidates_old_key(client, db_session):
    scanner, old_key = create_scanner(db_session)
    new_id, new_key, new_hash = generate_scanner_api_key()
    scanner.key_id = new_id
    scanner.key_hash = new_hash
    db_session.commit()

    old_response = client.get("/api/scanner/check-ins/whoami", headers={"X-Scanner-Key": old_key})
    new_response = client.get("/api/scanner/check-ins/whoami", headers={"X-Scanner-Key": new_key})
    assert old_response.status_code == 401
    assert new_response.status_code == 200


def test_scanner_cannot_use_pass_after_membership_frozen(
    client, member_account, admin_account, db_session
):
    membership = create_active_membership(client, member_account, admin_account)
    _, key = create_scanner(db_session)
    qr = issue_qr(client, member_account)
    frozen = client.patch(
        f"/api/memberships/{membership['id']}/status",
        headers=auth(admin_account["token"]),
        json={"status": "frozen"},
    )
    assert frozen.status_code == 200
    response = client.post("/api/scanner/check-ins/validate", headers={"X-Scanner-Key": key}, json={"qr_token": qr})
    assert response.status_code == 403


def test_rotating_key_does_not_reactivate_a_disabled_scanner(client, db_session):
    scanner, _ = create_scanner(db_session, active=False)
    new_id, new_key, new_hash = generate_scanner_api_key()
    scanner.key_id = new_id
    scanner.key_hash = new_hash
    db_session.commit()
    response = client.get("/api/scanner/check-ins/whoami", headers={"X-Scanner-Key": new_key})
    assert response.status_code == 401
    assert scanner.is_active is False

    scanner.is_active = True
    db_session.commit()
    response = client.get("/api/scanner/check-ins/whoami", headers={"X-Scanner-Key": new_key})
    assert response.status_code == 200
