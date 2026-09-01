"""Comprehensive Performance & Latency Benchmark for Phase 3 ML Pipeline."""

import time
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
from src.ml.features import ML_FEATURE_NAMES, extract_feature_array
from src.ml.predict import MLInferenceService
from src.generator.scenarios import ScenarioGenerator


def run_phase3_benchmarks(num_events: int = 500):
    """Measures actual empirical latencies for XGBoost, Isolation Forest, SHAP, and full Pipeline."""
    # Setup test DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    repo = Repository(db)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    generator = ScenarioGenerator(seed=42)
    service = EventProcessingService(db)
    ml_service = MLInferenceService()
    calc = FeatureCalculator(repo)

    # Generate 500 events
    events = [
        generator.generate_normal_event() if i % 2 == 0 else generator.generate_bot_abuse_event()
        for i in range(num_events)
    ]
    feature_vectors = [calc.calculate_features(ev) for ev in events]
    feature_arrays = [extract_feature_array(fv) for fv in feature_vectors]

    # Warmup
    for i in range(10):
        ml_service.predict_array(feature_arrays[i])
        service.process_event(events[i], dry_run=False)

    # 1. Measure Pure XGBoost Inference Latency
    xgb_latencies = []
    for arr in feature_arrays:
        t0 = time.perf_counter()
        _ = ml_service.xgb_model.predict_proba(arr.reshape(1, -1))
        t1 = time.perf_counter()
        xgb_latencies.append((t1 - t0) * 1000.0)

    # 2. Measure Pure Isolation Forest Anomaly Scoring Latency
    iforest_latencies = []
    for arr in feature_arrays:
        t0 = time.perf_counter()
        _ = ml_service.anomaly_detector.score_samples(arr.reshape(1, -1))
        t1 = time.perf_counter()
        iforest_latencies.append((t1 - t0) * 1000.0)

    # 3. Measure Pure SHAP TreeExplainer Attribution Latency
    shap_latencies = []
    for arr in feature_arrays:
        t0 = time.perf_counter()
        _ = ml_service.shap_explainer.explain_sample(arr.reshape(1, -1), top_k=5)
        t1 = time.perf_counter()
        shap_latencies.append((t1 - t0) * 1000.0)

    # 4. Measure End-to-End Synchronous Processing Pipeline Latency
    e2e_latencies = []
    total_start = time.perf_counter()
    for ev in events:
        t0 = time.perf_counter()
        service.process_event(ev, dry_run=False)
        t1 = time.perf_counter()
        e2e_latencies.append((t1 - t0) * 1000.0)
    total_elapsed = time.perf_counter() - total_start
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

    xgb_s = _stats(xgb_latencies)
    ifo_s = _stats(iforest_latencies)
    shp_s = _stats(shap_latencies)
    e2e_s = _stats(e2e_latencies)

    print("\n" + "=" * 70)
    print("        RAZORGUARD AI - PHASE 3 ML & PIPELINE LATENCY BENCHMARK")
    print("=" * 70)
    print(f" Total Events Evaluated : {num_events}")
    print(f" Total E2E Elapsed Time : {total_elapsed:.3f} s")
    print(f" Overall Throughput     : {throughput} events/sec")
    print("-" * 70)
    print(f" {'Component':<26} {'Mean':<8} {'P50':<8} {'P90':<8} {'P95':<8} {'P99':<8}")
    print("-" * 70)
    print(f" {'XGBoost Inference':<26} {xgb_s['mean']:<8.2f} {xgb_s['p50']:<8.2f} {xgb_s['p90']:<8.2f} {xgb_s['p95']:<8.2f} {xgb_s['p99']:<8.2f} ms")
    print(f" {'Isolation Forest Anomaly':<26} {ifo_s['mean']:<8.2f} {ifo_s['p50']:<8.2f} {ifo_s['p90']:<8.2f} {ifo_s['p95']:<8.2f} {ifo_s['p99']:<8.2f} ms")
    print(f" {'SHAP TreeExplainer':<26} {shp_s['mean']:<8.2f} {shp_s['p50']:<8.2f} {shp_s['p90']:<8.2f} {shp_s['p95']:<8.2f} {shp_s['p99']:<8.2f} ms")
    print(f" {'Full End-to-End Pipeline':<26} {e2e_s['mean']:<8.2f} {e2e_s['p50']:<8.2f} {e2e_s['p90']:<8.2f} {e2e_s['p95']:<8.2f} {e2e_s['p99']:<8.2f} ms")
    print("=" * 70 + "\n")

    db.close()
    return {
        "num_events": num_events,
        "throughput_eps": throughput,
        "xgboost": xgb_s,
        "isolation_forest": ifo_s,
        "shap": shp_s,
        "end_to_end": e2e_s,
    }


if __name__ == "__main__":
    run_phase3_benchmarks(500)
