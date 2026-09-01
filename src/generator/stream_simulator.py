import datetime
import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional
import pandas as pd

# Add project root to sys.path if run directly
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.config import settings
from src.core.logging import get_logger
from src.generator.scenarios import ScenarioGenerator

logger = get_logger("stream_simulator")


class StreamSimulator:
    """Simulates real-time payment traffic streams and generates synthetic benchmark datasets."""

    DEFAULT_SCENARIO_DISTRIBUTION = {
        "normal": 0.60,
        "legitimate_spike": 0.20,
        "bot_abuse": 0.08,
        "payment_abuse": 0.05,
        "coordinated_abuse": 0.04,
        "fraud_ring": 0.03,
    }

    def __init__(self, seed: int = 42):
        self.generator = ScenarioGenerator(seed=seed)

    def generate_events(
        self,
        count: int = 1000,
        distribution: Optional[Dict[str, float]] = None,
        start_time: Optional[datetime.datetime] = None,
        time_span_seconds: int = 3600,
    ) -> List[Dict[str, Any]]:
        """Generates a batch of synthetic payment events distributed over time."""
        dist = distribution or self.DEFAULT_SCENARIO_DISTRIBUTION
        start = start_time or (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=time_span_seconds))
        events = []

        scenarios = list(dist.keys())
        probabilities = list(dist.values())

        logger.info("Generating %d synthetic events with distribution: %s", count, dist)

        for i in range(count):
            # Progressive timestamp with jitter
            offset_ratio = i / max(1, count)
            event_ts = start + datetime.timedelta(
                seconds=offset_ratio * time_span_seconds + random.uniform(0, 1.0)
            )

            chosen_scenario = random.choices(scenarios, weights=probabilities, k=1)[0]
            event = self.generator.generate_by_scenario_name(chosen_scenario, timestamp=event_ts)
            events.append(event)

        logger.info("Generated %d events successfully.", len(events))
        return events

    def stream(
        self,
        events_per_second: float = 10.0,
        distribution: Optional[Dict[str, float]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Yields an infinite real-time event stream."""
        dist = distribution or self.DEFAULT_SCENARIO_DISTRIBUTION
        scenarios = list(dist.keys())
        weights = list(dist.values())

        while True:
            scenario = random.choices(scenarios, weights=weights, k=1)[0]
            event = self.generator.generate_by_scenario_name(
                scenario,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            yield event

    def events_to_dataframe(self, events: List[Dict[str, Any]]) -> pd.DataFrame:
        """Flattens nested event JSON payloads into a clean tabular DataFrame."""
        flat_records = []
        for e in events:
            rec = {
                "event_id": e.get("event_id"),
                "timestamp": e.get("timestamp"),
                "scenario": e.get("scenario"),
                "user_id": e.get("user_id"),
                "merchant_id": e.get("merchant_id"),
                "amount": e.get("amount"),
                "currency": e.get("currency", "INR"),
                "payment_method": e.get("payment_method"),
                "status": e.get("status"),
                "failure_code": e.get("failure_code"),
                # Card features
                "card_bin": e.get("card", {}).get("bin"),
                "card_last4": e.get("card", {}).get("last4"),
                "card_hash": e.get("card", {}).get("card_hash"),
                "card_network": e.get("card", {}).get("network"),
                "card_issuer": e.get("card", {}).get("issuer_bank"),
                # Device features
                "device_id": e.get("device", {}).get("id"),
                "user_agent": e.get("device", {}).get("user_agent"),
                "device_os": e.get("device", {}).get("os"),
                "device_browser": e.get("device", {}).get("browser"),
                "is_headless": e.get("device", {}).get("is_headless", False),
                "is_emulator": e.get("device", {}).get("is_emulator", False),
                "canvas_hash": e.get("device", {}).get("canvas_hash"),
                # Network features
                "ip_address": e.get("network", {}).get("ip"),
                "subnet_c": e.get("network", {}).get("subnet_c"),
                "ip_country": e.get("network", {}).get("country", "IN"),
                "ip_isp": e.get("network", {}).get("isp"),
                "ip_asn": e.get("network", {}).get("asn"),
                "is_datacenter_proxy": e.get("network", {}).get("is_datacenter_proxy", False),
                "ip_reputation": e.get("network", {}).get("reputation_score", 1.0),
                # Context features
                "checkout_duration_sec": e.get("context", {}).get("checkout_duration_sec", 12.0),
                "cart_items_count": e.get("context", {}).get("cart_items_count", 1),
                "is_flash_sale": e.get("context", {}).get("is_flash_sale", False),
                # Ground truth targets
                "is_fraud_or_abuse": 0 if e.get("scenario") in ("normal", "legitimate_spike") else 1,
            }
            flat_records.append(rec)
        return pd.DataFrame(flat_records)


def generate_benchmark_dataset(
    n_events: int = 5000,
    output_path: Optional[Path] = None,
    seed: int = 42
) -> pd.DataFrame:
    """Generates standard benchmark dataset and saves to disk."""
    simulator = StreamSimulator(seed=seed)
    events = simulator.generate_events(count=n_events)
    df = simulator.events_to_dataframe(events)

    target_path = output_path or (settings.SYNTHETIC_DIR / f"benchmark_dataset_{n_events}.csv")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target_path, index=False)
    logger.info("Saved benchmark dataset of %d rows to: %s", len(df), target_path)
    return df


if __name__ == "__main__":
    df = generate_benchmark_dataset(n_events=5000)
    print("Dataset Summary:")
    print(df["scenario"].value_counts())
    print("\nFraud / Abuse Distribution:")
    print(df["is_fraud_or_abuse"].value_counts(normalize=True))
