"""Integration Tests for Phase 4 API with Multi-Entity Graph Syndicate Detection."""

import pytest
import uuid
from fastapi.testclient import TestClient
from src.api.main import app
from src.core.database import get_db
from src.database.init_db import DEFAULT_MERCHANTS
from src.database.repository import Repository
from src.generator.scenarios import ScenarioGenerator
from src.engine.service import get_global_graph_builder

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_db(db_session):
    """Overrides get_db dependency in FastAPI app for test isolation."""
    repo = Repository(db_session)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    # Clear graph between tests
    get_global_graph_builder().clear()
    yield
    app.dependency_overrides.clear()
    get_global_graph_builder().clear()


def test_api_ingest_with_graph_and_ml():
    uid = uuid.uuid4().hex[:8]
    event_id = f"evt_graph_{uid}"
    user_id = f"usr_graph_shopper_{uid}"

    payload = {
        "event_id": event_id,
        "user_id": user_id,
        "merchant_id": "mer_fashion_trends",
        "amount": 4299.00,
        "currency": "INR",
        "payment_method": "credit_card",
        "card": {
            "bin": "524123",
            "last4": "8888",
            "card_hash": f"card_clean_{uid}",
        },
        "device": {
            "id": f"dev_pixel_{uid}",
            "is_headless": False,
        },
        "network": {
            "ip": f"49.36.20.{int(uid[:2], 16) % 250 + 1}",
            "is_datacenter_proxy": False,
            "reputation_score": 0.95,
        },
        "context": {
            "checkout_duration_sec": 22.0,
            "is_flash_sale": False,
        },
    }

    res = client.post("/events", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["event_id"] == event_id
    assert "transaction_id" in data
    assert 0.0 <= data["risk_score"] <= 100.0
    assert "graph_risk_score" in data
    assert "graph_risk_level" in data
    assert "cluster_id" in data
    assert "cluster_size" in data
    assert "is_fraud_ring" in data
    assert "is_legitimate_shared_infra" in data
    assert data["is_fraud_ring"] is False

    tx_id = data["transaction_id"]
    get_res = client.get(f"/risk/{tx_id}")
    assert get_res.status_code == 200
    stored = get_res.json()
    assert stored["transaction_id"] == tx_id
    assert stored["graph_score"] == data["graph_risk_score"]


def test_api_syndicate_card_ring_detection():
    shared_card = "card_syndicate_shared_api_99"
    shared_device = "dev_syndicate_shared_api_99"

    # Ingest 3 successive transactions from different users sharing card and device
    responses = []
    for i in range(3):
        payload = {
            "event_id": f"evt_syndicate_{i}",
            "user_id": f"usr_syndicate_puppet_{i}",
            "merchant_id": "mer_luxury_watches",
            "amount": 75000.0,
            "currency": "INR",
            "card": {"bin": "411111", "last4": "9999", "card_hash": shared_card},
            "device": {"id": shared_device, "is_headless": False},
            "network": {"ip": f"185.220.101.{i+10}"},
            "context": {"checkout_duration_sec": 12.0, "is_flash_sale": False},
        }
        res = client.post("/events", json=payload)
        assert res.status_code == 201
        responses.append(res.json())

    # Third transaction triggers fraud ring detection on the graph
    last_res = responses[-1]
    assert last_res["is_fraud_ring"] is True
    assert last_res["graph_risk_score"] >= 70.0
    assert last_res["risk_score"] >= 68.0
    assert last_res["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert len(last_res["graph_signals"]) > 0


def test_api_legitimate_campus_clearance():
    campus_ip = "103.21.244.77"
    os_choices = ["Windows", "MacOS", "iOS", "Android", "Linux"]
    merchants = ["mer_digital_gaming", "mer_fashion_trends", "mer_electronics_hub", "mer_food_delivery", "mer_travel_portal"]

    for i in range(5):
        payload = {
            "event_id": f"evt_campus_{i}",
            "user_id": f"usr_student_{i}",
            "merchant_id": merchants[i],
            "amount": 350.0,
            "card": {"card_hash": f"card_student_{i}"},
            "device": {"id": f"dev_student_{i}", "os": os_choices[i]},
            "network": {"ip": campus_ip, "is_datacenter_proxy": False, "reputation_score": 0.95},
            "context": {"checkout_duration_sec": 15.0, "is_flash_sale": False},
        }
        res = client.post("/events", json=payload)
        assert res.status_code == 201
        data = res.json()

    # Campus shared IP must NOT trigger fraud ring
    assert data["is_fraud_ring"] is False
    assert data["recommended_action"] in ("ALLOW", "MONITOR")
