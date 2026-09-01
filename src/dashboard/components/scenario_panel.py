"""One-Click Demonstration Scenarios Component for Live Judging."""

import streamlit as st
from src.dashboard.state import trigger_scenario_run, reset_dashboard


def render_scenario_panel():
    """Renders one-click interactive demonstration scenario buttons."""
    st.subheader("🎯 One-Click Live Scenario Triggers")
    st.caption("Click any scenario to inject synthetic payment traffic directly through the multi-modal pipeline, update the graph, and generate the AI dossier.")

    scenarios = [
        {
            "id": "normal",
            "title": "1. Normal Organic Traffic",
            "desc": "Standard consumer checkout within baseline velocity and ticket sizes.",
            "expected": "🟢 ALLOW (Score: 0 - 30)",
            "color": "#10B981",
        },
        {
            "id": "legitimate_spike",
            "title": "2. Legitimate Flash Sale Surge",
            "desc": "10× traffic spike with high account/IP entropy and normal payment success.",
            "expected": "🟢 ALLOW / MONITOR (Score: 0 - 30)",
            "color": "#38BDF8",
        },
        {
            "id": "bot_abuse",
            "title": "3. Automated Bot Abuse",
            "desc": "Sub-second checkout velocity from headless browser on datacenter proxy.",
            "expected": "🔴 RATE_LIMIT (Score: 90 - 100)",
            "color": "#EF4444",
        },
        {
            "id": "payment_abuse",
            "title": "4. Payment Abuse / Card Cracking",
            "desc": "Micro-transaction testing cadence with rapid velocity and decline spikes.",
            "expected": "🟠 STEP_UP (Score: 70 - 85)",
            "color": "#F59E0B",
        },
        {
            "id": "coordinated_abuse",
            "title": "5. Coordinated Multi-Entity Swarm",
            "desc": "Multiple accounts operating across distinct IPs targeting luxury items.",
            "expected": "🔵 MONITOR / STEP_UP",
            "color": "#6366F1",
        },
        {
            "id": "fraud_ring",
            "title": "6. Fraud Ring Syndicate",
            "desc": "4 colluding accounts sharing single payment card token & device hardware.",
            "expected": "🟠 STEP_UP (Graph Score: 75+)",
            "color": "#A855F7",
        },
    ]

    for s in scenarios:
        with st.container():
            c_text, c_btn = st.columns([3.5, 1.5])
            with c_text:
                st.markdown(f"**{s['title']}**")
                st.caption(f"{s['desc']} — *Expected:* **{s['expected']}**")
            with c_btn:
                st.write("")
                if st.button(f"▶️ Run Scenario", key=f"btn_scen_{s['id']}", use_container_width=True):
                    trigger_scenario_run(s["id"], count=4 if s["id"] == "legitimate_spike" else 1)
                    st.success(f"Executed {s['title']}! Transaction selected.")
                    st.rerun()
            st.divider()

    # Reset System Button
    st.write("")
    if st.button("🔄 Reset Entire Database & In-Memory Graph", use_container_width=True):
        reset_dashboard()
        st.info("Database and entity graph reset to clean initial state.")
        st.rerun()
