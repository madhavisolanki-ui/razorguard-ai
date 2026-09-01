"""Integration Tests for Phase 5 AI Investigation API Endpoints."""

import uuid
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_api_investigate_normal_transaction():
    """Ingests a normal transaction and requests an AI agent investigation."""
    uid = uuid.uuid4().hex[:8]
    event_payload = {
        "event_id": f"evt_agent_norm_{uid}",
        "user_id": f"usr_agent_buyer_{uid}",
        "merchant_id": "mer_fashion_trends",
        "amount": 1850.0,
        "currency": "INR",
        "device": {"id": f"dev_pixel_{uid}", "is_headless": False},
        "network": {"ip": "49.36.14.22", "is_datacenter_proxy": False, "reputation_score": 0.95},
        "card": {"card_hash": f"card_norm_{uid}"},
        "context": {"checkout_duration_sec": 19.0, "is_flash_sale": False},
    }

    # 1. Ingest event
    res = client.post("/events", json=event_payload)
    assert res.status_code == 201
    event_data = res.json()
    tx_id = event_data["transaction_id"]

    # 2. Trigger Investigation API
    inv_res = client.post(f"/investigate/{tx_id}")
    assert inv_res.status_code == 200
    report = inv_res.json()

    assert report["transaction_id"] == tx_id
    assert report["investigation_status"] in ("COMPLETED", "FALLBACK_DETERMINISTIC")
    assert report["risk_score"] == event_data["risk_score"]
    assert report["recommended_action"] == event_data["recommended_action"]
    assert len(report["investigation_path"]) > 0
    assert len(report["explanation"]) > 0


def test_api_investigate_fraud_ring_transaction():
    """Ingests syndicate transactions and verifies agent dossier exposes fraud ring evidence."""
    uid = uuid.uuid4().hex[:6]
    shared_card = f"card_syndicate_api_{uid}"
    shared_dev = f"dev_syndicate_api_{uid}"

    tx_ids = []
    for i in range(3):
        payload = {
            "event_id": f"evt_api_syn_{uid}_{i}",
            "user_id": f"usr_api_syn_{uid}_{i}",
            "merchant_id": "mer_luxury_watches",
            "amount": 80000.0,
            "currency": "INR",
            "device": {"id": shared_dev, "is_headless": False},
            "network": {"ip": f"49.36.14.{i+50}", "is_datacenter_proxy": False, "reputation_score": 0.90},
            "card": {"card_hash": shared_card},
            "context": {"checkout_duration_sec": 14.0, "is_flash_sale": False},
        }
        res = client.post("/events", json=payload)
        assert res.status_code == 201
        tx_ids.append(res.json()["transaction_id"])

    # Investigate the last transaction
    last_tx = tx_ids[-1]
    inv_res = client.post(f"/investigate/{last_tx}")
    assert inv_res.status_code == 200
    report = inv_res.json()

    assert report["transaction_id"] == last_tx
    assert report["fraud_ring_detected"] is True
    assert report["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert len(report["tools_used"]) > 0


def test_api_investigate_audit_retrieval():
    """Verifies that an investigation's audit trail can be retrieved via GET /investigate/{id}/audit."""
    uid = uuid.uuid4().hex[:8]
    event_payload = {
        "event_id": f"evt_audit_api_{uid}",
        "user_id": f"usr_audit_api_{uid}",
        "merchant_id": "mer_digital_gaming",
        "amount": 650.0,
        "currency": "INR",
        "device": {"id": f"dev_audit_api_{uid}", "is_headless": False},
        "network": {"ip": "49.36.14.33", "is_datacenter_proxy": False, "reputation_score": 0.95},
        "card": {"card_hash": f"card_audit_api_{uid}"},
        "context": {"checkout_duration_sec": 16.0, "is_flash_sale": False},
    }

    res = client.post("/events", json=event_payload)
    assert res.status_code == 201
    tx_id = res.json()["transaction_id"]

    inv_res = client.post(f"/investigate/{tx_id}")
    assert inv_res.status_code == 200
    inv_id = inv_res.json()["investigation_id"]

    audit_res = client.get(f"/investigate/{inv_id}/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()

    assert audit_data["investigation_id"] == inv_id
    assert audit_data["transaction_id"] == tx_id
    assert len(audit_data["investigation_path"]) > 0


def test_api_investigate_nonexistent_tx_404():
    """Verifies that requesting investigation on a non-existent transaction returns HTTP 404."""
    fake_tx = f"tx_nonexistent_{uuid.uuid4().hex[:8]}"
    res = client.post(f"/investigate/{fake_tx}")
    assert res.status_code == 404
