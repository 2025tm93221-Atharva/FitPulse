from app.core.config import settings


def auth(account):
    return {"Authorization": f"Bearer {account['token']}"}


def configure_vapid(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "B" + "a" * 85)
    monkeypatch.setattr(settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(settings, "vapid_claims_email", "mailto:push@example.test")


def test_web_push_configuration_disabled_by_default(client, member_account, monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", None)
    monkeypatch.setattr(settings, "vapid_private_key", None)
    monkeypatch.setattr(settings, "vapid_claims_email", None)
    response = client.get("/api/notifications/push/public-key", headers=auth(member_account))
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "public_key": None}
    saved = client.post("/api/notifications/push/subscriptions", headers=auth(member_account), json={
        "endpoint": "https://push.example.test/some-endpoint", "p256dh": "p" * 32, "auth": "a" * 16,
    })
    assert saved.status_code == 503


def test_push_subscription_create_list_and_delete(client, member_account, monkeypatch):
    configure_vapid(monkeypatch)
    response = client.post("/api/notifications/push/subscriptions", headers=auth(member_account), json={
        "endpoint": "https://push.example.test/some-endpoint", "p256dh": "p" * 32, "auth": "a" * 16,
    })
    assert response.status_code == 201, response.text
    subscription_id = response.json()["id"]
    listed = client.get("/api/notifications/push/subscriptions/me", headers=auth(member_account))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [subscription_id]
    removed = client.delete(f"/api/notifications/push/subscriptions/{subscription_id}", headers=auth(member_account))
    assert removed.status_code == 204
    assert client.get("/api/notifications/push/subscriptions/me", headers=auth(member_account)).json() == []


def test_push_endpoint_is_bound_to_single_account(client, member_account, monkeypatch):
    from tests.conftest import create_account

    configure_vapid(monkeypatch)
    subscription = client.post("/api/notifications/push/subscriptions", headers=auth(member_account), json={
        "endpoint": "https://push.example.test/another-endpoint", "p256dh": "p" * 32, "auth": "a" * 16,
    })
    other = create_account(client, "push-other@example.com")
    denied = client.delete(f"/api/notifications/push/subscriptions/{subscription.json()['id']}", headers=auth(other))
    assert denied.status_code == 403


def test_push_subscription_requires_https(client, member_account, monkeypatch):
    configure_vapid(monkeypatch)
    response = client.post("/api/notifications/push/subscriptions", headers=auth(member_account), json={
        "endpoint": "http://push.example.test/insecure", "p256dh": "p" * 32, "auth": "a" * 16,
    })
    assert response.status_code == 422
