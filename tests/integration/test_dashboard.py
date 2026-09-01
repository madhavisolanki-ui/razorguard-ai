"""Integration tests for Phase 6 Streamlit Dashboard components and state management."""

import pytest
import streamlit as st
from src.dashboard.state import (
    init_dashboard_state,
    process_dashboard_event,
    trigger_scenario_run,
    run_investigation_for_selected,
    reset_dashboard,
)
from src.generator.scenarios import ScenarioGenerator


@pytest.fixture(autouse=True)
def clean_dashboard_state():
    """Ensures clean dashboard state before each test."""
    init_dashboard_state()
    reset_dashboard()
    yield


def test_dashboard_state_initialization():
    """Verifies that all services, database session, and graph builder are initialized."""
    assert "db" in st.session_state
    assert "repo" in st.session_state
    assert "graph_builder" in st.session_state
    assert "event_service" in st.session_state
    assert "investigator" in st.session_state
    gen: ScenarioGenerator = st.session_state["generator"]
    rec = process_dashboard_event(gen.generate_normal_event())
    assert len(st.session_state["transactions"]) >= 1
    assert st.session_state["selected_tx_id"] == rec["transaction_id"]


def test_dashboard_event_processing():
    """Verifies ingesting a synthetic event updates transaction buffer and latency metrics."""
    gen: ScenarioGenerator = st.session_state["generator"]
    ev = gen.generate_normal_event()
    
    initial_count = len(st.session_state["transactions"])
    rec = process_dashboard_event(ev)
    
    assert len(st.session_state["transactions"]) == initial_count + 1
    assert rec["transaction_id"] == st.session_state["selected_tx_id"]
    assert rec["risk_score"] >= 0.0
    assert rec["recommended_action"] in ("ALLOW", "MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT")


def test_dashboard_scenario_fraud_ring_trigger():
    """Verifies running the fraud ring scenario produces connected entities and investigation dossier."""
    recs = trigger_scenario_run("fraud_ring", count=1)
    assert len(recs) == 4
    
    # Selected tx should be the last syndicate transaction
    selected_id = st.session_state["selected_tx_id"]
    assert selected_id == recs[-1]["transaction_id"]
    
    # Investigation should be triggered
    report = st.session_state.get("latest_investigation")
    assert report is not None
    assert report.transaction_id == selected_id
    assert report.fraud_ring_detected is True
    assert report.cluster_size >= 4
    assert report.recommended_action == "STEP_UP_VERIFICATION"


def test_dashboard_scenario_flash_sale_trigger():
    """Verifies running the legitimate flash sale scenario results in ALLOW action."""
    recs = trigger_scenario_run("legitimate_spike", count=3)
    assert len(recs) == 3
    
    report = st.session_state.get("latest_investigation")
    assert report is not None
    assert report.fraud_ring_detected is False
    assert report.recommended_action in ("ALLOW", "MONITOR")


def test_dashboard_score_preservation_in_state():
    """Verifies that the dashboard preserves deterministic scores from Phase 2-4 without modification."""
    gen: ScenarioGenerator = st.session_state["generator"]
    ev = gen.generate_payment_abuse_event()
    rec = process_dashboard_event(ev)
    
    report = run_investigation_for_selected()
    assert report.risk_score == rec["risk_score"]
    assert report.recommended_action == rec["recommended_action"]
    assert report.fraud_probability == rec["fraud_probability"]


def test_dashboard_reset_behavior():
    """Verifies resetting the dashboard restores clean state."""
    trigger_scenario_run("bot_abuse", count=2)
    assert len(st.session_state["transactions"]) > 0
    
    reset_dashboard()
    assert len(st.session_state["transactions"]) == 0
    assert st.session_state["selected_tx_id"] is None
    assert st.session_state["latest_investigation"] is None
    assert st.session_state["graph_builder"].node_count == 0
