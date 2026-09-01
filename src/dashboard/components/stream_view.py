"""Live Streaming Payment Feed Component with Controls."""

import streamlit as st
import pandas as pd
from src.dashboard.state import (
    process_dashboard_event,
    run_investigation_for_selected,
)


def render_stream_view():
    """Renders the live updating payment event feed and streaming controls."""
    txs = st.session_state.get("transactions", [])
    
    st.subheader("⚡ Live Payment Ingestion Stream")
    st.caption("Continuously monitors incoming transactions, calculating behavioral velocity, dual ML inference, and graph syndicates in real time.")

    # Control Bar
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 3])
    with c1:
        if st.button("➕ Ingest Single Event", use_container_width=True):
            generator = st.session_state["generator"]
            ev = generator.generate_normal_event()
            process_dashboard_event(ev)
            st.rerun()

    with c2:
        if st.button("🗑️ Clear Stream Buffer", use_container_width=True):
            st.session_state["transactions"] = []
            st.session_state["selected_tx_id"] = None
            st.session_state["latest_investigation"] = None
            st.rerun()

    with c3:
        # Quick Scenario Injection
        scen_choice = st.selectbox(
            "Inject Scenario",
            [
                "normal",
                "legitimate_spike",
                "bot_abuse",
                "payment_abuse",
                "coordinated_abuse",
                "fraud_ring",
            ],
            format_func=lambda x: {
                "normal": "Normal Traffic (ALLOW)",
                "legitimate_spike": "Legitimate Flash Sale (ALLOW)",
                "bot_abuse": "Botnet Surge (RATE_LIMIT)",
                "payment_abuse": "Card Testing (STEP_UP)",
                "coordinated_abuse": "Coordinated Swarm (MONITOR)",
                "fraud_ring": "Fraud Ring Syndicate (STEP_UP)",
            }.get(x, x),
            label_visibility="collapsed"
        )
    with c4:
        if st.button(f"🚀 Inject Scenario Event", use_container_width=True):
            generator = st.session_state["generator"]
            ev = generator.generate_by_scenario_name(scen_choice)
            process_dashboard_event(ev)
            run_investigation_for_selected()
            st.rerun()

    # Transaction Table
    if not txs:
        st.info("Payment stream is currently empty. Ingest events using the buttons above.")
        return

    df_rows = []
    for t in txs:
        action = t["recommended_action"]
        badge = {
            "ALLOW": "🟢 ALLOW",
            "MONITOR": "🔵 MONITOR",
            "STEP_UP_VERIFICATION": "🟠 STEP_UP",
            "RATE_LIMIT": "🔴 RATE_LIMIT",
        }.get(action, action)
        
        df_rows.append({
            "Timestamp": t["timestamp"],
            "Transaction ID": t["transaction_id"],
            "Account ID": t["user_id"],
            "Merchant": t["merchant_id"],
            "Amount (INR)": f"₹{t['amount']:,.2f}",
            "Risk Score": f"{t['risk_score']:.1f}",
            "Tier": t["risk_level"],
            "Graph Score": f"{t.get('graph_risk_score', 0):.1f}",
            "Action": badge,
            "Latency": f"{t['processing_latency_ms']} ms",
        })

    df = pd.DataFrame(df_rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Risk Score": st.column_config.NumberColumn(format="%.1f"),
            "Amount (INR)": st.column_config.TextColumn(),
        },
    )

    # Transaction Quick-Selector
    tx_options = [t["transaction_id"] for t in txs]
    current_selected = st.session_state.get("selected_tx_id")
    idx = tx_options.index(current_selected) if current_selected in tx_options else 0
    
    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        selected = st.selectbox(
            "Select Transaction to Investigate in Tabs 2, 3 & 4:",
            tx_options,
            index=idx,
            key="stream_tx_selector",
        )
    with col_btn:
        st.write("")
        st.write("")
        if st.button("🔎 Investigate Selected", use_container_width=True):
            st.session_state["selected_tx_id"] = selected
            run_investigation_for_selected()
            st.rerun()
            
    if selected != st.session_state.get("selected_tx_id"):
        st.session_state["selected_tx_id"] = selected
        run_investigation_for_selected()
        st.rerun()
