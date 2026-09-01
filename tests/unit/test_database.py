"""Unit Tests for Database Models, Repository, and Relationships."""

import datetime
from src.database.models import (
    User,
    Merchant,
    Device,
    IPAddress,
    Transaction,
    RiskAssessment,
    InvestigationCase,
    GraphEdge,
)
from src.database.repository import Repository


def test_user_creation_and_query(repository: Repository):
    user = repository.get_or_create_user(
        user_id="usr_test_001",
        email="rahul.sharma@example.com",
        phone_country="IN",
    )
    assert user.id == "usr_test_001"
    assert user.email_domain == "example.com"
    assert user.account_status == "ACTIVE"

    fetched = repository.get_user("usr_test_001")
    assert fetched is not None
    assert fetched.email == "rahul.sharma@example.com"


def test_device_and_ip_creation(repository: Repository):
    device = repository.get_or_create_device(
        device_id="dev_canvas_abc123",
        user_agent="Mozilla/5.0 Chrome/128",
        os_name="Windows",
        browser="Chrome",
        is_headless=False,
    )
    assert device.id == "dev_canvas_abc123"
    assert device.browser == "Chrome"

    ip = repository.get_or_create_ip(
        ip="49.37.100.55",
        country="IN",
        isp="Jio Fiber",
    )
    assert ip.ip == "49.37.100.55"
    assert ip.subnet_c == "49.37.100.0/24"


def test_transaction_with_risk_assessment_and_case(repository: Repository):
    # Seed prerequisites
    user = repository.get_or_create_user("usr_tx_test")
    merchant = repository.get_or_create_merchant("mer_tx_test", name="SuperStore")
    device = repository.get_or_create_device("dev_tx_test")
    ip = repository.get_or_create_ip("103.21.244.2")

    # Create Transaction
    tx = repository.create_transaction({
        "id": "tx_test_999",
        "event_time": datetime.datetime.now(datetime.timezone.utc),
        "user_id": user.id,
        "merchant_id": merchant.id,
        "device_id": device.id,
        "ip_address": ip.ip,
        "amount": 1499.00,
        "currency": "INR",
        "payment_method": "credit_card",
        "card_bin": "411111",
        "card_last4": "1111",
        "card_hash": "crd_hash_test_123",
        "status": "SUCCESS",
        "checkout_duration_sec": 15.5,
        "is_flash_sale": False,
        "scenario_tag": "normal",
    })
    assert tx.id == "tx_test_999"
    assert tx.amount == 1499.00

    # Attach Risk Assessment
    assessment = repository.create_risk_assessment({
        "id": "risk_test_999",
        "transaction_id": tx.id,
        "assessed_at": datetime.datetime.now(datetime.timezone.utc),
        "composite_risk_score": 12.5,
        "risk_tier": "LOW",
        "xgboost_score": 0.05,
        "iforest_score": 0.10,
        "velocity_score": 0.05,
        "graph_score": 0.00,
        "fast_action": "ALLOW",
        "latency_ms": 12,
    })
    assert assessment.composite_risk_score == 12.5
    assert tx.risk_assessment.fast_action == "ALLOW"

    # Attach Investigation Case
    case = repository.create_investigation_case({
        "id": "case_test_999",
        "transaction_id": tx.id,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "agent_status": "COMPLETED",
        "traffic_scenario_verdict": "normal",
        "agent_confidence": 0.98,
        "recommended_action": "ALLOW",
        "evidence_bundle": {"device_clean": True},
        "justification_markdown": "Transaction shows genuine organic behavior.",
    })
    assert case.agent_confidence == 0.98
    assert tx.investigation_case.recommended_action == "ALLOW"


def test_sliding_window_velocity_counts(repository: Repository):
    user = repository.get_or_create_user("usr_velocity_user")
    merchant = repository.get_or_create_merchant("mer_velocity")
    device = repository.get_or_create_device("dev_velocity")
    ip = repository.get_or_create_ip("182.70.1.1")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Create 3 transactions in the last 60 seconds
    for i in range(3):
        repository.create_transaction({
            "id": f"tx_vel_{i}",
            "event_time": now - datetime.timedelta(seconds=i * 10),
            "user_id": user.id,
            "merchant_id": merchant.id,
            "device_id": device.id,
            "ip_address": ip.ip,
            "amount": 500.0,
            "status": "SUCCESS" if i > 0 else "FAILED",
        })

    # Query 5-minute window count (300 sec)
    user_count = repository.get_user_tx_count_in_window(user.id, window_seconds=300)
    assert user_count == 3

    ip_count = repository.get_ip_tx_count_in_window(ip.ip, window_seconds=300)
    assert ip_count == 3

    fail_ratio = repository.get_ip_failed_tx_ratio_in_window(ip.ip, window_seconds=300)
    assert round(fail_ratio, 2) == 0.33


def test_graph_edges(repository: Repository):
    edge = repository.add_or_update_edge(
        source_id="usr_ring_1",
        source_type="USER",
        target_id="crd_shared_4412",
        target_type="CARD",
        relation_type="HAS_CARD",
        weight=1.0,
    )
    assert edge.weight == 1.0

    # Add same edge again -> weight increases
    edge_updated = repository.add_or_update_edge(
        source_id="usr_ring_1",
        source_type="USER",
        target_id="crd_shared_4412",
        target_type="CARD",
        relation_type="HAS_CARD",
        weight=2.0,
    )
    assert edge_updated.weight == 3.0

    edges = repository.get_edges_for_entity("usr_ring_1")
    assert len(edges) == 1
