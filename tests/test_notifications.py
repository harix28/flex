"""Tests for Notification Webhooks and Alert Dispatcher."""
from uuid import uuid4
from sentinel.notifications import dispatcher


def test_webhook_crud_and_signing():
    tenant_id = uuid4()
    secret = "super_secret_webhook_key_123"

    # 1. Register webhook
    wh = dispatcher.register_webhook(
        tenant_id=tenant_id,
        url="https://alerts.aviation-plant.example.com/webhook",
        secret=secret,
        events=["alert.urgent", "alert.high"],
        label="Test Webhook"
    )
    assert wh["label"] == "Test Webhook"
    assert "secret" not in wh  # secret never leaked

    # 2. List webhooks
    listed = dispatcher.list_webhooks(tenant_id)
    assert len(listed) == 1
    assert listed[0]["id"] == wh["id"]
    assert listed[0]["secret"] == "••••••••"

    # 3. Test HMAC signing
    sig = dispatcher.sign_payload(b"test_payload", secret)
    assert len(sig) == 64  # sha256 hex string

    # 4. Dispatch event
    res = dispatcher.dispatch_event(
        tenant_id=tenant_id,
        event_type="alert.urgent",
        payload={"machine_id": "ENG-001", "rul": 5.2},
        machine_id="ENG-001",
        priority="urgent",
        force=True
    )
    assert res["status"] == "dispatched"
    assert res["subscriber_count"] == 1

    # 5. Check dispatch history
    history = dispatcher.get_dispatch_history(tenant_id)
    assert len(history) >= 1
    assert history[0]["event_type"] == "alert.urgent"

    # 6. Delete webhook
    deleted = dispatcher.delete_webhook(tenant_id, wh["id"])
    assert deleted is True
    assert len(dispatcher.list_webhooks(tenant_id)) == 0


def test_alert_fatigue_deduplication():
    tenant_id = uuid4()
    secret = "secret_key_456"
    dispatcher.register_webhook(
        tenant_id=tenant_id,
        url="https://alerts.example.com",
        secret=secret,
        events=["alert.urgent"]
    )

    # First alert passes
    first = dispatcher.dispatch_event(
        tenant_id=tenant_id,
        event_type="alert.urgent",
        payload={"rul": 3.0},
        machine_id="ENG-DEDUP-TEST",
        priority="urgent"
    )
    assert first["status"] == "dispatched"

    # Immediate second alert for same engine is suppressed
    second = dispatcher.dispatch_event(
        tenant_id=tenant_id,
        event_type="alert.urgent",
        payload={"rul": 2.9},
        machine_id="ENG-DEDUP-TEST",
        priority="urgent"
    )
    assert second["status"] == "suppressed_duplicate"

