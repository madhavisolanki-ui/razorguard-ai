"""Session State and Backend Service Manager for Streamlit Dashboard."""

import time
from typing import Dict, Any, List, Optional
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.database.repository import Repository
from src.database.init_db import DEFAULT_MERCHANTS
from src.engine.service import EventProcessingService
from src.graph.builder import FraudGraphBuilder
from src.agent.investigator import RiskInvestigationService
from src.agent.llm import GeminiLLMClient
from src.generator.scenarios import ScenarioGenerator


@st.cache_resource
def get_database_session():
    """Creates a persistent in-memory SQLite database for the dashboard lifecycle."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repo = Repository(session)
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])
    return session, repo


def init_dashboard_state():
    """Initializes Streamlit session state on first run."""
    if "initialized" not in st.session_state:
        db, repo = get_database_session()
        builder = FraudGraphBuilder()
        service = EventProcessingService(db, graph_builder=builder)
        llm_client = GeminiLLMClient()
        investigator = RiskInvestigationService(db, graph_builder=builder, llm_client=llm_client)
        generator = ScenarioGenerator(seed=int(time.time()))

        st.session_state["db"] = db
        st.session_state["repo"] = repo
        st.session_state["graph_builder"] = builder
        st.session_state["event_service"] = service
        st.session_state["investigator"] = investigator
        st.session_state["generator"] = generator
        st.session_state["transactions"] = []
        st.session_state["selected_tx_id"] = None
        st.session_state["latest_investigation"] = None
        st.session_state["is_streaming"] = False
        st.session_state["stream_speed"] = 1.0
        st.session_state["scenario_history"] = []
        st.session_state["latency_metrics"] = {
            "engine_ms": [],
            "xgboost_ms": [],
            "isolation_forest_ms": [],
            "shap_ms": [],
            "graph_ms": [],
            "agent_ms": [],
        }
        st.session_state["initialized"] = True

        # Pre-seed with 3 initial transactions so dashboard opens with active data
        for _ in range(3):
            ev = generator.generate_normal_event()
            process_dashboard_event(ev)


def process_dashboard_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Processes an event through the deterministic multi-modal pipeline and records it."""
    service: EventProcessingService = st.session_state["event_service"]
    
    t0 = time.perf_counter()
    result = service.process_event(event_dict)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    
    record = {
        "transaction_id": result["transaction_id"],
        "user_id": result.get("user_id") or event_dict.get("user_id", "usr_anon"),
        "merchant_id": result.get("merchant_id") or event_dict.get("merchant_id", "mer_anon"),
        "amount": result.get("amount", 0.0),
        "currency": result.get("currency", "INR"),
        "risk_score": result["risk_score"],
        "risk_level": result["risk_level"],
        "recommended_action": result["recommended_action"],
        "fraud_probability": result.get("fraud_probability", 0.0),
        "anomaly_score": result.get("anomaly_score", 0.0),
        "graph_risk_score": result.get("graph_risk_score", 0.0),
        "primary_rule_triggered": result.get("primary_rule_triggered"),
        "shap_signals": result.get("top_risk_signals") or result.get("shap_signals", []),
        "timestamp": time.strftime("%H:%M:%S"),
        "processing_latency_ms": elapsed_ms,
        "raw_event": event_dict,
        "result": result,
    }
    
    # Prepend to transactions list
    st.session_state["transactions"].insert(0, record)
    if len(st.session_state["transactions"]) > 100:
        st.session_state["transactions"] = st.session_state["transactions"][:100]
        
    st.session_state["selected_tx_id"] = record["transaction_id"]
    
    # Record latency tracking
    st.session_state["latency_metrics"]["engine_ms"].append(elapsed_ms)
    
    return record


def trigger_scenario_run(scenario_name: str, count: int = 1) -> List[Dict[str, Any]]:
    """Runs a canonical scenario through the live pipeline."""
    generator: ScenarioGenerator = st.session_state["generator"]
    records = []
    
    if scenario_name == "fraud_ring":
        # Syndicate multi-account scenario sharing card & device
        shared_card = f"card_syndicate_{int(time.time()) % 1000}"
        shared_dev = f"dev_syndicate_{int(time.time()) % 1000}"
        for i in range(4):
            ev = {
                "event_id": f"evt_syn_{int(time.time())}_{i}",
                "user_id": f"usr_syn_op_{i}",
                "merchant_id": "mer_luxury_watches",
                "amount": 75000.0,
                "currency": "INR",
                "device": {"id": shared_dev, "is_headless": False},
                "network": {"ip": f"49.36.14.{i+90}", "is_datacenter_proxy": False, "reputation_score": 0.90},
                "card": {"card_hash": shared_card},
                "context": {"checkout_duration_sec": 16.0, "is_flash_sale": False},
            }
            rec = process_dashboard_event(ev)
            records.append(rec)
    elif scenario_name == "legitimate_spike":
        for _ in range(count):
            ev = generator.generate_legitimate_spike_event()
            rec = process_dashboard_event(ev)
            records.append(rec)
    elif scenario_name == "bot_abuse":
        for _ in range(count):
            ev = generator.generate_bot_abuse_event()
            rec = process_dashboard_event(ev)
            records.append(rec)
    elif scenario_name == "payment_abuse":
        for _ in range(count):
            ev = generator.generate_payment_abuse_event()
            rec = process_dashboard_event(ev)
            records.append(rec)
    elif scenario_name == "coordinated_abuse":
        for _ in range(count):
            ev = generator.generate_coordinated_abuse_event()
            rec = process_dashboard_event(ev)
            records.append(rec)
    else:  # normal
        for _ in range(count):
            ev = generator.generate_normal_event()
            rec = process_dashboard_event(ev)
            records.append(rec)
            
    if records:
        st.session_state["selected_tx_id"] = records[-1]["transaction_id"]
        # Trigger investigation for latest scenario transaction
        run_investigation_for_selected()
        
    return records


def run_investigation_for_selected() -> Optional[Any]:
    """Runs LangGraph agent investigation for the currently selected transaction."""
    tx_id = st.session_state.get("selected_tx_id")
    if not tx_id:
        return None
        
    investigator: RiskInvestigationService = st.session_state["investigator"]
    t0 = time.perf_counter()
    report = investigator.investigate_transaction(tx_id)
    lat_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    st.session_state["latest_investigation"] = report
    st.session_state["latency_metrics"]["agent_ms"].append(lat_ms)
    return report


def reset_dashboard():
    """Resets the in-memory database and graph."""
    db, repo = get_database_session()
    builder: FraudGraphBuilder = st.session_state["graph_builder"]
    builder.clear()
    
    # Clear tables
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    
    for m in DEFAULT_MERCHANTS:
        repo.get_or_create_merchant(m["id"], m["name"], m["category"], m["risk_category"])
        
    st.session_state["transactions"] = []
    st.session_state["selected_tx_id"] = None
    st.session_state["latest_investigation"] = None
    st.session_state["latency_metrics"] = {
        "engine_ms": [],
        "xgboost_ms": [],
        "isolation_forest_ms": [],
        "shap_ms": [],
        "graph_ms": [],
        "agent_ms": [],
    }
