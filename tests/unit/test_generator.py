"""Unit Tests for Synthetic Data Generator and 6 Canonical Scenarios."""

import pytest
from src.generator.scenarios import ScenarioGenerator
from src.generator.stream_simulator import StreamSimulator


def test_scenario_1_normal_traffic(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_normal_event()
    assert event["scenario"] == "normal"
    assert "event_id" in event
    assert event["amount"] > 0
    assert event["context"]["checkout_duration_sec"] >= 5.0
    assert event["device"]["is_headless"] is False
    assert event["context"]["is_flash_sale"] is False


def test_scenario_2_legitimate_spike(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_legitimate_spike_event()
    assert event["scenario"] == "legitimate_spike"
    assert event["merchant_id"] == "mer_electronics_hub"
    assert event["context"]["is_flash_sale"] is True
    assert event["context"]["checkout_duration_sec"] >= 5.0
    assert event["amount"] >= 10000.0


def test_scenario_3_bot_abuse(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_bot_abuse_event()
    assert event["scenario"] == "bot_abuse"
    assert event["device"]["is_headless"] is True
    assert event["context"]["checkout_duration_sec"] < 2.0
    assert event["network"]["is_datacenter_proxy"] is True
    assert event["network"]["reputation_score"] < 0.5


def test_scenario_4_payment_abuse(scenario_generator: ScenarioGenerator):
    event = scenario_generator.generate_payment_abuse_event()
    assert event["scenario"] == "payment_abuse"
    assert event["amount"] < 50.0  # Micro-transaction
    assert "card" in event
    assert "crd_" in event["card"]["card_hash"]


def test_scenario_5_coordinated_abuse(scenario_generator: ScenarioGenerator):
    events = [scenario_generator.generate_coordinated_abuse_event() for _ in range(5)]
    # All distinct user IDs
    user_ids = {e["user_id"] for e in events}
    assert len(user_ids) == 5

    # Should share canvas hash from the farm set
    canvas_hashes = {e["device"]["canvas_hash"] for e in events}
    assert len(canvas_hashes) <= 3


def test_scenario_6_fraud_ring(scenario_generator: ScenarioGenerator):
    events = [scenario_generator.generate_fraud_ring_event() for _ in range(5)]
    # All events in the ring share the same withdrawal bank account hash
    bank_hashes = {e["bank_account_hash"] for e in events}
    assert len(bank_hashes) == 1
    for e in events:
        assert e["amount"] >= 20000.0


def test_stream_simulator_batch_and_dataframe(stream_simulator: StreamSimulator):
    events = stream_simulator.generate_events(count=100)
    assert len(events) == 100

    df = stream_simulator.events_to_dataframe(events)
    assert len(df) == 100
    assert "is_fraud_or_abuse" in df.columns
    assert "amount" in df.columns
    assert "device_id" in df.columns
    assert "ip_address" in df.columns

    # Verify scenario diversity
    scenarios_present = set(df["scenario"].unique())
    assert "normal" in scenarios_present
    assert "legitimate_spike" in scenarios_present
