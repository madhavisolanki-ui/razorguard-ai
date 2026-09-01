"""Integration Tests for Phase 3 API with ML, Anomaly Detection, Rules, and SHAP."""

import pytest
import uuid
from fastapi.testclient import TestClient
from src.api.main import app
from src.core.database import get_db
from src.database.init_db import DEFAULT_MERCHANTS
from src.database.repository import Repository
from src.generator.scenarios import ScenarioGenerator

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
    yield
    app.dependency_overrides.clear()


def test_health_check_phase3():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "RazorGuard AI" in data["app_name"]


def test_api_ingest_with_ml_and_shap():
    uid = uuid.uuid4().hex[:8]
    event_id = f"evt_ml_test_{uid}"
    user_id = f"usr_ml_buyer_{uid}"

    payload = {
        "event_id": event_id,
        "user_id": user_id,
        "merchant_id": "mer_fashion_trends",
        "amount": 3499.00,
        "currency": "INR",
        "payment_method": "credit_card",
        "card": {
            "bin": "411111",
            "last4": "1111",
            "network": "VISA",
            "issuer_bank": "HDFC",
        },
        "device": {
            "id": f"dev_iphone_{uid}",
            "is_headless": False,
        },
        "network": {
            "ip": f"49.37.14.{int(uid[:2], 16) % 250 + 1}",
            "is_datacenter_proxy": False,
            "reputation_score": 0.95,
        },
        "context": {
            "checkout_duration_sec": 18.5,
            "is_flash_sale": False,
        },
    }

    res = client.post("/events", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["event_id"] == event_id
    assert "transaction_id" in data
    assert 0.0 <= data["risk_score"] <= 100.0
    assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert data["recommended_action"] in ("ALLOW", "MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert "fraud_probability" in data
    assert "anomaly_score" in data
    assert "model_scores" in data
    assert "top_risk_signals" in data
    assert "explanation" in data
    assert len(data["explanation"]) > 10

    tx_id = data["transaction_id"]

    # Retrieve stored risk assessment
    get_res = client.get(f"/risk/{tx_id}")
    assert get_res.status_code == 200
    stored = get_res.json()
    assert stored["transaction_id"] == tx_id
    assert stored["composite_risk_score"] == data["risk_score"]
    assert stored["xgboost_score"] == data["fraud_probability"]
    assert stored["iforest_score"] == data["anomaly_score"]


def test_api_dry_run_analysis_with_shap():
    uid = uuid.uuid4().hex[:8]
    payload = {
        "event_id": f"evt_dry_{uid}",
        "user_id": f"usr_bot_{uid}",
        "merchant_id": "mer_digital_gaming",
        "amount": 15.00,
        "device": {"id": f"dev_bot_{uid}", "is_headless": True},
        "network": {"ip": "185.220.101.99", "is_datacenter_proxy": True, "reputation_score": 0.15},
        "context": {"checkout_duration_sec": 0.2, "is_flash_sale": False},
    }

    res = client.post("/risk/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["dry_run"] is True
    assert "feature_values" in data
    assert data["risk_score"] >= 70.0
    assert data["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert len(data["top_risk_signals"]) > 0


def test_scenario_1_normal_traffic_ml(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_normal_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert data["risk_score"] <= 35.0
    assert data["recommended_action"] in ("ALLOW", "MONITOR")


def test_scenario_2_legitimate_spike_ml(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_legitimate_spike_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    # Flash sale with high entropy must NOT be penalized as fraud
    assert data["recommended_action"] in ("ALLOW", "MONITOR")
    assert data["risk_score"] <= 35.0


def test_scenario_3_bot_abuse_ml(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_bot_abuse_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert data["risk_score"] >= 65.0
    assert data["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT")


def test_scenario_4_payment_abuse_ml(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_payment_abuse_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert data["risk_score"] >= 40.0


def test_scenario_5_coordinated_abuse_ml(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_coordinated_abuse_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert "transaction_id" in data
