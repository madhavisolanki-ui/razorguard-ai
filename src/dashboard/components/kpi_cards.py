"""Executive Overview KPI Cards & Risk Distribution Component."""

import streamlit as st
import plotly.graph_objects as go
import numpy as np


def render_kpi_cards():
    """Renders top-level executive KPI cards and risk distribution."""
    txs = st.session_state.get("transactions", [])
    
    total = len(txs)
    allowed = sum(1 for t in txs if t["recommended_action"] == "ALLOW")
    monitored = sum(1 for t in txs if t["recommended_action"] == "MONITOR")
    step_up = sum(1 for t in txs if t["recommended_action"] == "STEP_UP_VERIFICATION")
    rate_limited = sum(1 for t in txs if t["recommended_action"] == "RATE_LIMIT")
    
    # Calculate fraud rings detected from graph score or cluster
    fraud_rings = sum(1 for t in txs if t.get("graph_risk_score", 0) >= 60.0)
    
    latencies = st.session_state.get("latency_metrics", {}).get("engine_ms", [])
    avg_latency = round(float(np.mean(latencies)), 2) if latencies else 12.5

    # Top KPI Metrics Row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    with c1:
        st.metric(label="Total Ingested", value=total, help="Total transactions processed through real-time pipeline")
    with c2:
        st.metric(label="🟢 ALLOW", value=allowed, delta=f"{round(allowed/max(1, total)*100)}%")
    with c3:
        st.metric(label="🔵 MONITOR", value=monitored, delta=f"{round(monitored/max(1, total)*100)}%")
    with c4:
        st.metric(label="🟠 STEP-UP", value=step_up, delta=f"{round(step_up/max(1, total)*100)}%")
    with c5:
        st.metric(label="🔴 RATE LIMIT", value=rate_limited, delta=f"{round(rate_limited/max(1, total)*100)}%")
    with c6:
        st.metric(label="⚡ Avg Latency", value=f"{avg_latency} ms", delta="Sub-50ms SLA", delta_color="normal")


def render_risk_distribution_chart():
    """Renders interactive donut chart showing risk level distribution."""
    txs = st.session_state.get("transactions", [])
    if not txs:
        st.info("No transaction data available yet.")
        return

    low_count = sum(1 for t in txs if t["risk_level"] == "LOW")
    med_count = sum(1 for t in txs if t["risk_level"] == "MEDIUM")
    high_count = sum(1 for t in txs if t["risk_level"] == "HIGH")
    crit_count = sum(1 for t in txs if t["risk_level"] == "CRITICAL")

    labels = ["LOW (0-30)", "MEDIUM (31-65)", "HIGH (66-85)", "CRITICAL (86-100)"]
    values = [low_count, med_count, high_count, crit_count]
    colors = ["#10B981", "#38BDF8", "#F59E0B", "#EF4444"]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hoverinfo="label+value+percent",
    )])

    fig.update_layout(
        title="<b>Real-Time Risk Tier Distribution</b>",
        title_font_size=16,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        height=260,
    )
    st.plotly_chart(fig, use_container_width=True)
