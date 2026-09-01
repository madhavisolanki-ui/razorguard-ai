"""Phase 4 Comprehensive Audit Script: Legitimate Infrastructure, Fraud Rings, and Scoring Verification."""

import sys
from pathlib import Path
import json

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.database.repository import Repository
from src.database.init_db import DEFAULT_MERCHANTS
from src.engine.service import EventProcessingService
from src.features.calculator import FeatureCalculator
from src.graph.builder import FraudGraphBuilder
from src.graph.analysis import GraphRiskAnalyzer
from src.ml.composite_scorer import UnifiedRiskScorer


def audit_legitimate_scenarios():
    """Audits legitimate shared infrastructure scenarios to verify false positive = 0%."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    repo = Repository(db)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    builder = FraudGraphBuilder()
    analyzer = GraphRiskAnalyzer(builder.graph)
    service = EventProcessingService(db, graph_builder=builder, graph_analyzer=analyzer)

    results = {}

    # 1. University Campus NAT
    campus_ip = "103.25.130.50"
    os_list = ["iOS", "Android", "MacOS", "Windows", "Linux", "iOS", "Android", "Windows"]
    merchants = ["mer_digital_gaming", "mer_fashion_trends", "mer_electronics_hub", "mer_food_delivery"] * 2

    campus_events_results = []
    for i in range(8):
        ev = {
            "event_id": f"evt_student_{i}",
            "user_id": f"usr_student_{i}",
            "merchant_id": merchants[i],
            "amount": 299.0 + (i * 20),
            "device": {"id": f"dev_student_phone_{i}", "os": os_list[i], "is_headless": False},
            "network": {"ip": campus_ip, "is_datacenter_proxy": False, "reputation_score": 0.95},
            "card": {"card_hash": f"card_student_unique_{i}"},
            "context": {"checkout_duration_sec": 16.0, "is_flash_sale": False},
        }
        res = service.process_event(ev)
        campus_events_results.append(res)

    last_campus = campus_events_results[-1]
    results["campus_nat"] = {
        "scenario": "University / Campus NAT",
        "sample_count": 8,
        "last_event_graph_score": last_campus["graph_risk_score"],
        "last_event_final_score": last_campus["risk_score"],
        "last_event_action": last_campus["recommended_action"],
        "is_fraud_ring": last_campus["is_fraud_ring"],
        "is_legitimate_shared_infra": last_campus["is_legitimate_shared_infra"],
        "graph_signals": last_campus["graph_signals"],
        "false_positive": last_campus["is_fraud_ring"] or last_campus["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT"),
    }

    # 2. Corporate Office Network
    builder.clear()
    corp_ip = "14.143.45.10"
    corp_os = ["Windows", "MacOS", "MacOS", "Windows", "Linux", "Windows"]
    corp_events_results = []
    for i in range(6):
        ev = {
            "event_id": f"evt_employee_{i}",
            "user_id": f"usr_employee_{i}",
            "merchant_id": "mer_fashion_trends" if i % 2 == 0 else "mer_food_delivery",
            "amount": 1200.0 + (i * 100),
            "device": {"id": f"dev_corp_laptop_{i}", "os": corp_os[i], "is_headless": False},
            "network": {"ip": corp_ip, "is_datacenter_proxy": False, "reputation_score": 0.98},
            "card": {"card_hash": f"card_employee_unique_{i}"},
            "context": {"checkout_duration_sec": 22.0, "is_flash_sale": False},
        }
        res = service.process_event(ev)
        corp_events_results.append(res)

    last_corp = corp_events_results[-1]
    results["corporate_office"] = {
        "scenario": "Corporate Office Network",
        "sample_count": 6,
        "last_event_graph_score": last_corp["graph_risk_score"],
        "last_event_final_score": last_corp["risk_score"],
        "last_event_action": last_corp["recommended_action"],
        "is_fraud_ring": last_corp["is_fraud_ring"],
        "is_legitimate_shared_infra": last_corp["is_legitimate_shared_infra"],
        "graph_signals": last_corp["graph_signals"],
        "false_positive": last_corp["is_fraud_ring"] or last_corp["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT"),
    }

    # 3. Family / Shared Tablet
    builder.clear()
    family_device = "dev_family_ipad_living_room"
    family_events_results = []
    for i, member in enumerate(["dad", "mom"]):
        ev = {
            "event_id": f"evt_family_{member}",
            "user_id": f"usr_family_{member}",
            "merchant_id": "mer_fashion_trends",
            "amount": 2500.0 if member == "dad" else 1800.0,
            "device": {"id": family_device, "os": "iOS", "is_headless": False},
            "network": {"ip": "103.20.10.15", "is_datacenter_proxy": False, "reputation_score": 0.90},
            "card": {"card_hash": f"card_family_{member}"},
            "context": {"checkout_duration_sec": 28.0, "is_flash_sale": False},
        }
        res = service.process_event(ev)
        family_events_results.append(res)

    last_fam = family_events_results[-1]
    results["family_shared_device"] = {
        "scenario": "Family Shared Tablet (2 Users)",
        "sample_count": 2,
        "last_event_graph_score": last_fam["graph_risk_score"],
        "last_event_final_score": last_fam["risk_score"],
        "last_event_action": last_fam["recommended_action"],
        "is_fraud_ring": last_fam["is_fraud_ring"],
        "is_legitimate_shared_infra": last_fam["is_legitimate_shared_infra"],
        "graph_signals": last_fam["graph_signals"],
        "false_positive": last_fam["is_fraud_ring"] or last_fam["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT"),
    }

    # 4. Corporate VPN
    builder.clear()
    vpn_ip = "185.199.108.153"
    vpn_results = []
    for i in range(4):
        ev = {
            "event_id": f"evt_vpn_{i}",
            "user_id": f"usr_vpn_worker_{i}",
            "merchant_id": "mer_electronics_hub",
            "amount": 3499.0,
            "device": {"id": f"dev_vpn_mac_{i}", "os": "MacOS", "is_headless": False},
            "network": {"ip": vpn_ip, "is_datacenter_proxy": True, "reputation_score": 0.80},
            "card": {"card_hash": f"card_vpn_worker_{i}"},
            "context": {"checkout_duration_sec": 18.0, "is_flash_sale": False},
        }
        res = service.process_event(ev)
        vpn_results.append(res)

    last_vpn = vpn_results[-1]
    results["corporate_vpn"] = {
        "scenario": "Corporate Remote VPN",
        "sample_count": 4,
        "last_event_graph_score": last_vpn["graph_risk_score"],
        "last_event_final_score": last_vpn["risk_score"],
        "last_event_action": last_vpn["recommended_action"],
        "is_fraud_ring": last_vpn["is_fraud_ring"],
        "is_legitimate_shared_infra": last_vpn["is_legitimate_shared_infra"],
        "graph_signals": last_vpn["graph_signals"],
        "false_positive": last_vpn["is_fraud_ring"] or last_vpn["recommended_action"] == "RATE_LIMIT",
    }

    # 5. Legitimate Flash Sale
    builder.clear()
    from src.generator.scenarios import ScenarioGenerator
    gen = ScenarioGenerator(seed=42)
    flash_results = []
    for _ in range(20):
        ev = gen.generate_legitimate_spike_event()
        res = service.process_event(ev)
        flash_results.append(res)

    mean_flash_score = round(sum(r["risk_score"] for r in flash_results) / len(flash_results), 1)
    mean_flash_graph = round(sum(r["graph_risk_score"] for r in flash_results) / len(flash_results), 1)
    results["legitimate_flash_sale"] = {
        "scenario": "Legitimate Flash Sale Spike (20 Events)",
        "sample_count": 20,
        "mean_graph_score": mean_flash_graph,
        "mean_final_score": mean_flash_score,
        "action_distribution": {
            act: round(float([r["recommended_action"] for r in flash_results].count(act) / len(flash_results)), 2)
            for act in set(r["recommended_action"] for r in flash_results)
        },
        "fraud_ring_count": sum(1 for r in flash_results if r["is_fraud_ring"]),
        "false_positive": any(r["recommended_action"] in ("STEP_UP_VERIFICATION", "RATE_LIMIT") for r in flash_results),
    }

    db.close()
    return results


def audit_fraud_ring_comparison():
    """Audits Fraud Ring scenario under Phase 3 alone vs Phase 4 with Graph."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    repo = Repository(db)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    calc = FeatureCalculator(repo)
    scorer = UnifiedRiskScorer()
    builder = FraudGraphBuilder()
    analyzer = GraphRiskAnalyzer(builder.graph)
    service = EventProcessingService(db, graph_builder=builder, graph_analyzer=analyzer)

    # 4 Syndicate Members sharing credit card and hardware
    shared_card = "card_syndicate_amex_corp_999"
    shared_dev = "dev_syndicate_tablet_pad_999"

    syndicate_events = [
        {
            "event_id": f"evt_ring_{i}",
            "user_id": f"usr_ring_operative_{i}",
            "merchant_id": "mer_luxury_watches",
            "amount": 68000.0,
            "currency": "INR",
            "device": {"id": shared_dev, "is_headless": False},
            "network": {"ip": f"49.36.14.{i+20}", "is_datacenter_proxy": False, "reputation_score": 0.90},
            "card": {"bin": "524123", "last4": "9999", "card_hash": shared_card},
            "context": {"checkout_duration_sec": 18.0, "is_flash_sale": False},
        }
        for i in range(4)
    ]

    # Evaluation under Phase 3 Alone (Individual event without graph)
    fv0 = calc.calculate_features(syndicate_events[0])
    p3_decision = scorer.evaluate(fv0, graph_analyzer=None)

    # Ingest all 4 events into Phase 4 service
    p4_results = []
    for ev in syndicate_events:
        res = service.process_event(ev)
        p4_results.append(res)

    last_p4 = p4_results[-1]

    db.close()
    return {
        "phase3_individual_score": p3_decision.risk_score,
        "phase3_fraud_prob": p3_decision.fraud_probability,
        "phase3_action": p3_decision.recommended_action,
        "phase4_graph_score": last_p4["graph_risk_score"],
        "phase4_final_score": last_p4["risk_score"],
        "phase4_action": last_p4["recommended_action"],
        "is_fraud_ring": last_p4["is_fraud_ring"],
        "ring_type": "SHARED_PAYMENT_CARD_SYNDICATE",
        "cluster_id": last_p4["cluster_id"],
        "cluster_size": last_p4["cluster_size"],
        "suspicious_entities": last_p4["suspicious_entities"],
        "graph_signals": last_p4["graph_signals"],
    }


if __name__ == "__main__":
    legit = audit_legitimate_scenarios()
    ring = audit_fraud_ring_comparison()

    print("\n" + "=" * 70)
    print("           PHASE 4 AUDIT: LEGITIMATE INFRASTRUCTURE RESULTS")
    print("=" * 70)
    print(json.dumps(legit, indent=2))
    print("\n" + "=" * 70)
    print("           PHASE 4 AUDIT: FRAUD RING COMPARISON RESULTS")
    print("=" * 70)
    print(json.dumps(ring, indent=2))
