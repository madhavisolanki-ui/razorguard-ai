import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.core.database import get_db
from src.generator.scenarios import ScenarioGenerator
from src.database.init_db import DEFAULT_MERCHANTS
from src.database.repository import Repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_db(db_session):
    """Overrides get_db dependency in FastAPI app for test isolation."""
    # Seed default merchants in test session
    repo = Repository(db_session)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "RazorGuard AI" in data["app_name"]


def test_api_ingest_and_get_risk():
    import uuid
    uid = uuid.uuid4().hex[:8]
    event_id = f"evt_api_test_{uid}"
    user_id = f"usr_api_buyer_{uid}"

    # 1. Post valid payment event
    payload = {
        "event_id": event_id,
        "user_id": user_id,
        "merchant_id": "mer_fashion_trends",
        "amount": 2499.00,
        "currency": "INR",
        "payment_method": "credit_card",
        "card": {
            "bin": "411111",
            "last4": "1111",
            "network": "VISA",
            "issuer_bank": "HDFC",
        },
        "device": {
            "id": f"dev_api_iphone_{uid}",
            "is_headless": False,
        },
        "network": {
            "ip": f"49.37.12.{int(uid[:2], 16) % 250 + 1}",
            "is_datacenter_proxy": False,
        },
        "context": {
            "checkout_duration_sec": 16.2,
            "is_flash_sale": False,
        },
    }

    res = client.post("/events", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["event_id"] == event_id
    assert data["risk_score"] <= 30.0
    assert data["recommended_action"] == "ALLOW"
    assert "transaction_id" in data
    assert "X-Process-Time-Ms" in res.headers

    tx_id = data["transaction_id"]

    # 2. Retrieve persisted risk assessment
    get_res = client.get(f"/risk/{tx_id}")
    assert get_res.status_code == 200
    stored = get_res.json()
    assert stored["transaction_id"] == tx_id
    assert stored["user_id"] == user_id
    assert stored["composite_risk_score"] == data["risk_score"]


def test_api_dry_run_analysis():
    payload = {
        "user_id": "usr_dryrun_01",
        "merchant_id": "mer_digital_gaming",
        "amount": 15.00,
        "device": {"id": "dev_dry_01", "is_headless": True},
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


def test_scenario_1_normal_traffic_api(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_normal_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert data["risk_score"] <= 35.0
    assert data["recommended_action"] in ("ALLOW", "MONITOR")


def test_scenario_2_legitimate_spike_api(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_legitimate_spike_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    # Flash sale with high entropy must NOT be penalized as fraud
    assert data["recommended_action"] in ("ALLOW", "MONITOR")


def test_scenario_3_bot_abuse_api(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_bot_abuse_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    # Bot abuse must be flagged with high/critical action
    assert data["risk_score"] >= 65.0
    assert data["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT")


def test_scenario_4_payment_abuse_api(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_payment_abuse_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert data["risk_score"] >= 40.0


def test_scenario_5_coordinated_abuse_api(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_coordinated_abuse_event()
    res = client.post("/events", json=event)
    assert res.status_code == 201
    data = res.json()
    assert "transaction_id" in data
