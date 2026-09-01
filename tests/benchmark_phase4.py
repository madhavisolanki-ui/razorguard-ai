"""Empirical Performance & Latency Benchmark for Phase 4 Multi-Entity Graph Engine."""

import time
import json
import sys
from pathlib import Path
import numpy as np

# Add project root to sys.path
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
from src.graph.features import GraphFeatureExtractor
from src.graph.detector import FraudRingDetector
from src.graph.analysis import GraphRiskAnalyzer
from src.generator.scenarios import ScenarioGenerator


def run_phase4_benchmarks(num_events: int = 500):
    """Measures empirical latencies for NetworkX graph operations, relational features, and full E2E pipeline."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    repo = Repository(db)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    generator = ScenarioGenerator(seed=42)
    builder = FraudGraphBuilder()
    extractor = GraphFeatureExtractor(builder.graph)
    detector = FraudRingDetector(builder.graph)
    analyzer = GraphRiskAnalyzer(builder.graph)
    service = EventProcessingService(db, graph_builder=builder, graph_analyzer=analyzer)

    # Pre-generate 500 heterogeneous events
    events = []
    for i in range(num_events):
        scenario_idx = i % 6
        if scenario_idx == 0:
            events.append(generator.generate_normal_event())
        elif scenario_idx == 1:
            events.append(generator.generate_legitimate_spike_event())
        elif scenario_idx == 2:
            events.append(generator.generate_bot_abuse_event())
        elif scenario_idx == 3:
            events.append(generator.generate_payment_abuse_event())
        elif scenario_idx == 4:
            events.append(generator.generate_coordinated_abuse_event())
        else:
            events.append(generator.generate_fraud_ring_event())

    # Warmup
    for i in range(10):
        service.process_event(events[i], dry_run=False)

    # 1. Measure Pure Graph Incremental Update Latency
    graph_update_latencies = []
    test_builder = FraudGraphBuilder()
    for i, ev in enumerate(events):
        t0 = time.perf_counter()
        test_builder.add_event(ev, f"tx_bench_{i}", risk_score=20.0)
        t1 = time.perf_counter()
        graph_update_latencies.append((t1 - t0) * 1000.0)

    # 2. Measure Relational Feature Extraction Latency
    test_extractor = GraphFeatureExtractor(test_builder.graph)
    feature_extract_latencies = []
    for ev in events:
        dev_id = ev.get("device", {}).get("id") or "dev_1"
        ip = ev.get("network", {}).get("ip") or "127.0.0.1"
        card_h = ev.get("card", {}).get("card_hash")
        t0 = time.perf_counter()
        _ = test_extractor.extract_features(ev["user_id"], dev_id, ip, card_h)
        t1 = time.perf_counter()
        feature_extract_latencies.append((t1 - t0) * 1000.0)

    # 3. Measure Syndicate / Fraud Ring Detection Latency
    test_detector = FraudRingDetector(test_builder.graph)
    detection_latencies = []
    for ev in events:
        dev_id = ev.get("device", {}).get("id") or "dev_1"
        ip = ev.get("network", {}).get("ip") or "127.0.0.1"
        card_h = ev.get("card", {}).get("card_hash")
        gf = test_extractor.extract_features(ev["user_id"], dev_id, ip, card_h)
        t0 = time.perf_counter()
        _ = test_detector.detect(gf)
        t1 = time.perf_counter()
        detection_latencies.append((t1 - t0) * 1000.0)

    # 4. Measure Full End-to-End Phase 1-4 Synchronous Pipeline Latency
    e2e_latencies = []
    e2e_start = time.perf_counter()
    for ev in events:
        t0 = time.perf_counter()
        service.process_event(ev, dry_run=False)
        t1 = time.perf_counter()
        e2e_latencies.append((t1 - t0) * 1000.0)
    total_elapsed = time.perf_counter() - e2e_start
    throughput = round(num_events / total_elapsed, 1)

    def _stats(arr_list):
        arr = np.array(arr_list)
        return {
            "mean": round(float(np.mean(arr)), 2),
            "p50": round(float(np.percentile(arr, 50)), 2),
            "p90": round(float(np.percentile(arr, 90)), 2),
            "p95": round(float(np.percentile(arr, 95)), 2),
            "p99": round(float(np.percentile(arr, 99)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
        }

    g_up = _stats(graph_update_latencies)
    f_ex = _stats(feature_extract_latencies)
    d_la = _stats(detection_latencies)
    e2e = _stats(e2e_latencies)

    print("\n" + "=" * 74)
    print("      RAZORGUARD AI - PHASE 4 MULTI-ENTITY GRAPH LATENCY BENCHMARK")
    print("=" * 74)
    print(f" Total Events Evaluated : {num_events}")
    print(f" Total Nodes in Graph   : {builder.node_count}")
    print(f" Total Edges in Graph   : {builder.edge_count}")
    print(f" Total E2E Elapsed Time : {total_elapsed:.3f} s")
    print(f" Overall Throughput     : {throughput} events/sec")
    print("-" * 74)
    print(f" {'Component':<28} {'Mean':<8} {'P50':<8} {'P90':<8} {'P95':<8} {'P99':<8}")
    print("-" * 74)
    print(f" {'Graph Incremental Update':<28} {g_up['mean']:<8.2f} {g_up['p50']:<8.2f} {g_up['p90']:<8.2f} {g_up['p95']:<8.2f} {g_up['p99']:<8.2f} ms")
    print(f" {'Relational Features':<28} {f_ex['mean']:<8.2f} {f_ex['p50']:<8.2f} {f_ex['p90']:<8.2f} {f_ex['p95']:<8.2f} {f_ex['p99']:<8.2f} ms")
    print(f" {'Syndicate Detection':<28} {d_la['mean']:<8.2f} {d_la['p50']:<8.2f} {d_la['p90']:<8.2f} {d_la['p95']:<8.2f} {d_la['p99']:<8.2f} ms")
    print(f" {'Full E2E ML+Graph Pipeline':<28} {e2e['mean']:<8.2f} {e2e['p50']:<8.2f} {e2e['p90']:<8.2f} {e2e['p95']:<8.2f} {e2e['p99']:<8.2f} ms")
    print("=" * 74 + "\n")

    # 5. Measure Scenario Performance with Graph
    scenario_names = ["normal", "legitimate_spike", "bot_abuse", "payment_abuse", "coordinated_abuse", "fraud_ring"]
    scenario_results = {}

    for sc in scenario_names:
        sc_scores = []
        sc_graph_scores = []
        sc_actions = []
        sc_rings = []

        sc_builder = FraudGraphBuilder()
        sc_analyzer = GraphRiskAnalyzer(sc_builder.graph)
        sc_service = EventProcessingService(db, graph_builder=sc_builder, graph_analyzer=sc_analyzer)

        for _ in range(50):
            ev = generator.generate_by_scenario_name(sc)
            res = sc_service.process_event(ev, dry_run=False)
            sc_scores.append(res["risk_score"])
            sc_graph_scores.append(res["graph_risk_score"])
            sc_actions.append(res["recommended_action"])
            sc_rings.append(1 if res["is_fraud_ring"] else 0)

        scenario_results[sc] = {
            "scenario": sc,
            "sample_count": 50,
            "mean_risk_score": round(float(np.mean(sc_scores)), 1),
            "median_risk_score": round(float(np.median(sc_scores)), 1),
            "mean_graph_score": round(float(np.mean(sc_graph_scores)), 1),
            "fraud_ring_detection_rate": round(float(sum(sc_rings) / len(sc_rings)), 2),
            "action_distribution": {
                act: round(float(sc_actions.count(act) / len(sc_actions)), 2)
                for act in set(sc_actions)
            },
        }

    # Save Results
    metrics_path = ROOT_DIR / "docs" / "results" / "graph_metrics.json"
    scenarios_path = ROOT_DIR / "docs" / "results" / "graph_scenarios.json"

    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_payload = {
        "num_events": num_events,
        "nodes_count": builder.node_count,
        "edges_count": builder.edge_count,
        "throughput_eps": throughput,
        "graph_update": g_up,
        "relational_features": f_ex,
        "syndicate_detection": d_la,
        "full_pipeline": e2e,
    }

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    with open(scenarios_path, "w", encoding="utf-8") as f:
        json.dump(scenario_results, f, indent=2)

    db.close()
    return metrics_payload, scenario_results


if __name__ == "__main__":
    run_phase4_benchmarks(500)
