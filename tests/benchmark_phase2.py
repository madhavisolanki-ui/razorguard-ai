"""Empirical Latency and Throughput Benchmark for Phase 2 Event Processing."""

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
from src.generator.scenarios import ScenarioGenerator


def run_latency_benchmark(num_events: int = 500):
    """Measures actual processing latency across sequential real-time payment events."""
    # Setup fast test DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed merchants
    repo = Repository(db)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])

    generator = ScenarioGenerator(seed=42)
    service = EventProcessingService(db)

    # Pre-generate 500 events
    events = [generator.generate_normal_event() if i % 2 == 0 else generator.generate_bot_abuse_event() for i in range(num_events)]

    # Warmup
    for i in range(10):
        service.process_event(events[i], dry_run=False)

    latencies_ms = []

    print(f"Starting latency benchmark on {num_events} payment events...")
    total_start = time.perf_counter()

    for event in events:
        t0 = time.perf_counter()
        service.process_event(event, dry_run=False)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    total_elapsed = time.perf_counter() - total_start
    throughput_eps = round(num_events / total_elapsed, 1)

    latencies_arr = np.array(latencies_ms)
    p50 = np.percentile(latencies_arr, 50)
    p90 = np.percentile(latencies_arr, 90)
    p95 = np.percentile(latencies_arr, 95)
    p99 = np.percentile(latencies_arr, 99)
    mean_lat = np.mean(latencies_arr)
    min_lat = np.min(latencies_arr)
    max_lat = np.max(latencies_arr)

    print("\n" + "=" * 60)
    print("           RAZORGUARD AI - PHASE 2 LATENCY BENCHMARK")
    print("=" * 60)
    print(f" Total Events Processed : {num_events}")
    print(f" Total Elapsed Time     : {total_elapsed:.3f} s")
    print(f" Throughput             : {throughput_eps} events/sec")
    print("-" * 60)
    print(f" Mean Latency           : {mean_lat:.2f} ms")
    print(f" Min Latency            : {min_lat:.2f} ms")
    print(f" P50 (Median) Latency   : {p50:.2f} ms")
    print(f" P90 Latency            : {p90:.2f} ms")
    print(f" P95 Latency            : {p95:.2f} ms")
    print(f" P99 Latency            : {p99:.2f} ms")
    print(f" Max Latency            : {max_lat:.2f} ms")
    print("=" * 60 + "\n")

    db.close()
    return {
        "num_events": num_events,
        "throughput_eps": throughput_eps,
        "mean_ms": round(mean_lat, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
    }


if __name__ == "__main__":
    run_latency_benchmark(500)
