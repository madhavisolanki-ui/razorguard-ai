"""Unit Tests for Phase 4 Multi-Entity Fraud Graph & Syndicate Analysis."""

import pytest
import datetime
from src.graph.builder import FraudGraphBuilder
from src.graph.features import GraphFeatureExtractor, GraphFeatures
from src.graph.detector import FraudRingDetector, RingDetectionResult
from src.graph.analysis import GraphRiskAnalyzer, GraphRiskResult
from src.features.calculator import FeatureCalculator, FeatureVector
from src.ml.composite_scorer import UnifiedRiskScorer, UnifiedRiskDecision
from src.database.repository import Repository
from src.generator.scenarios import ScenarioGenerator


def test_graph_builder_node_and_edge_creation():
    builder = FraudGraphBuilder()
    event = {
        "user_id": "usr_alice",
        "merchant_id": "mer_fashion_hub",
        "amount": 2500.0,
        "currency": "INR",
        "status": "SUCCESS",
        "device": {"id": "dev_iphone_12", "is_headless": False},
        "network": {"ip": "49.37.10.5", "is_datacenter_proxy": False, "reputation_score": 0.95},
        "card": {"bin": "411111", "last4": "1111", "card_hash": "card_alice_hash_01"},
    }

    builder.add_event(event, transaction_id="tx_test_001", risk_score=15.0)

    assert builder.graph.has_node("acc:usr_alice")
    assert builder.graph.has_node("dev:dev_iphone_12")
    assert builder.graph.has_node("ip:49.37.10.5")
    assert builder.graph.has_node("card:card_alice_hash_01")
    assert builder.graph.has_node("tx:tx_test_001")
    assert builder.graph.has_node("mer:mer_fashion_hub")

    assert builder.graph.has_edge("acc:usr_alice", "dev:dev_iphone_12")
    assert builder.graph.has_edge("acc:usr_alice", "card:card_alice_hash_01")
    assert builder.graph.has_edge("dev:dev_iphone_12", "ip:49.37.10.5")
    assert builder.node_count >= 6
    assert builder.edge_count >= 8


def test_graph_feature_extractor():
    builder = FraudGraphBuilder()
    extractor = GraphFeatureExtractor(builder.graph)

    # Ingest 2 events from same user with different devices
    ev1 = {
        "user_id": "usr_bob",
        "amount": 1000.0,
        "device": {"id": "dev_laptop_bob"},
        "network": {"ip": "103.20.10.1"},
        "card": {"card_hash": "card_bob_visa"},
    }
    ev2 = {
        "user_id": "usr_bob",
        "amount": 1200.0,
        "device": {"id": "dev_mobile_bob"},
        "network": {"ip": "103.20.10.1"},
        "card": {"card_hash": "card_bob_visa"},
    }
    builder.add_event(ev1, "tx_bob_1")
    builder.add_event(ev2, "tx_bob_2")

    features = extractor.extract_features(
        user_id="usr_bob",
        device_id="dev_laptop_bob",
        ip_address="103.20.10.1",
        card_hash="card_bob_visa",
    )

    assert features.devices_per_account == 2
    assert features.accounts_per_device == 1
    assert features.accounts_per_ip == 1
    assert features.shared_card_accounts == 1
    assert features.cluster_size >= 4


def test_device_farming_detection():
    builder = FraudGraphBuilder()
    detector = FraudRingDetector(builder.graph)
    extractor = GraphFeatureExtractor(builder.graph)

    # 4 distinct synthetic accounts transacting from the exact same hardware token
    shared_device = "dev_hardware_farm_99"
    for i in range(4):
        builder.add_event({
            "user_id": f"usr_puppet_{i}",
            "amount": 500.0 * (i + 1),
            "device": {"id": shared_device, "is_headless": True},
            "network": {"ip": f"185.220.101.{i+1}"},
            "card": {"card_hash": f"card_puppet_{i}"},
        }, f"tx_puppet_{i}")

    features = extractor.extract_features(
        user_id="usr_puppet_3",
        device_id=shared_device,
        ip_address="185.220.101.4",
        card_hash="card_puppet_3",
    )

    result = detector.detect(features)
    assert result.is_fraud_ring is True
    assert result.ring_type == "DEVICE_FARM_SYNDICATE"
    assert any("DEVICE_FARM" in sig for sig in result.triggered_graph_signals)
    assert f"dev:{shared_device}" in result.suspicious_entities


def test_shared_payment_card_syndicate():
    builder = FraudGraphBuilder()
    detector = FraudRingDetector(builder.graph)
    extractor = GraphFeatureExtractor(builder.graph)

    # 3 distinct accounts funding from a single shared credit card token
    shared_card = "card_stolen_amex_888"
    for i in range(3):
        builder.add_event({
            "user_id": f"usr_mule_{i}",
            "amount": 35000.0,
            "device": {"id": f"dev_mule_{i}"},
            "network": {"ip": f"49.36.12.{i+10}"},
            "card": {"card_hash": shared_card},
        }, f"tx_mule_{i}")

    features = extractor.extract_features(
        user_id="usr_mule_2",
        device_id="dev_mule_2",
        ip_address="49.36.12.12",
        card_hash=shared_card,
    )

    result = detector.detect(features)
    assert result.is_fraud_ring is True
    assert result.ring_type == "SHARED_PAYMENT_CARD_SYNDICATE"
    assert any("SHARED_CARD" in sig for sig in result.triggered_graph_signals)


def test_multi_hop_syndicate_ring_cycles():
    builder = FraudGraphBuilder()
    detector = FraudRingDetector(builder.graph)
    extractor = GraphFeatureExtractor(builder.graph)

    # Ring: usr_A uses dev_1 & card_1
    # usr_B uses dev_1 & card_2
    # usr_C uses dev_2 & card_2 and dev_2 is linked to usr_A
    builder.add_event({"user_id": "usr_ring_A", "device": {"id": "dev_ring_1"}, "card": {"card_hash": "card_ring_1"}}, "tx_r1")
    builder.add_event({"user_id": "usr_ring_B", "device": {"id": "dev_ring_1"}, "card": {"card_hash": "card_ring_2"}}, "tx_r2")
    builder.add_event({"user_id": "usr_ring_C", "device": {"id": "dev_ring_2"}, "card": {"card_hash": "card_ring_2"}}, "tx_r3")
    builder.add_event({"user_id": "usr_ring_A", "device": {"id": "dev_ring_2"}, "card": {"card_hash": "card_ring_1"}}, "tx_r4")

    features = extractor.extract_features(
        user_id="usr_ring_A",
        device_id="dev_ring_1",
        ip_address="127.0.0.1",
        card_hash="card_ring_1",
    )

    result = detector.detect(features)
    assert result.is_fraud_ring is True
    assert result.confidence_score >= 0.85


def test_legitimate_campus_nat_clearance():
    builder = FraudGraphBuilder()
    detector = FraudRingDetector(builder.graph)
    extractor = GraphFeatureExtractor(builder.graph)

    # 6 distinct college students sharing a university campus NAT IP
    campus_ip = "103.25.130.1"
    os_list = ["iOS", "Android", "Windows", "MacOS", "Linux", "Android"]

    for i in range(6):
        builder.add_event({
            "user_id": f"usr_student_{i}",
            "amount": 250.0 + (i * 50),
            "device": {"id": f"dev_student_device_{i}", "os": os_list[i]},
            "network": {"ip": campus_ip, "is_datacenter_proxy": False, "reputation_score": 0.95},
            "card": {"card_hash": f"card_student_unique_{i}"},
        }, f"tx_student_{i}")

    features = extractor.extract_features(
        user_id="usr_student_5",
        device_id="dev_student_device_5",
        ip_address=campus_ip,
        card_hash="card_student_unique_5",
    )

    result = detector.detect(features)
    # Must clear legitimate campus NAT without penalizing as fraud ring
    assert result.is_fraud_ring is False
    assert result.is_legitimate_shared_infra is True
    assert any("CAMPUS" in mit for mit in result.mitigating_factors)


def test_phase3_vs_phase4_fraud_ring_comparison(repository: Repository):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()
    builder = FraudGraphBuilder()
    analyzer = GraphRiskAnalyzer(builder.graph)

    # Synthetic fraud ring: 4 members sharing credit cards and devices
    ring_events = [
        {
            "user_id": f"usr_syndicate_member_{i}",
            "merchant_id": "mer_luxury_watches",
            "amount": 65000.0,
            "currency": "INR",
            "device": {"id": "dev_shared_ring_pad", "is_headless": False},
            "network": {"ip": "49.36.14.99", "is_datacenter_proxy": False, "reputation_score": 0.90},
            "card": {"bin": "524123", "last4": "9999", "card_hash": "card_stolen_corp_999"},
            "context": {"checkout_duration_sec": 14.5, "is_flash_sale": False},
        }
        for i in range(4)
    ]

    # Event 1: First transaction in isolation (Phase 3 ML alone)
    ev0 = ring_events[0]
    fv0 = calc.calculate_features(ev0)
    decision_p3 = scorer.evaluate(fv0, graph_analyzer=None)

    # Individual transaction with human checkout and clean IP appears normal to Phase 3 ML
    assert decision_p3.fraud_probability < 0.40
    assert decision_p3.risk_score <= 35.0

    # Ingest preceding syndicate events into graph
    for idx, ev in enumerate(ring_events):
        builder.add_event(ev, f"tx_ring_ev_{idx}")

    # Event 4: Same syndicate member evaluated WITH Phase 4 Graph
    ev3 = ring_events[3]
    fv3 = calc.calculate_features(ev3)
    decision_p4 = scorer.evaluate(fv3, graph_analyzer=analyzer)

    # Phase 4 Graph detects the coordinated syndicate and elevates risk
    assert decision_p4.is_fraud_ring is True
    assert decision_p4.graph_risk_score >= 70.0
    assert decision_p4.risk_score >= 68.0
    assert decision_p4.recommended_action in ("STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert len(decision_p4.graph_signals) > 0
