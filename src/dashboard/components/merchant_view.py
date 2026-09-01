"""Merchant Baseline & Traffic Surge Comparison Component ("Not Every Spike is an Attack")."""

import streamlit as st
import plotly.graph_objects as go
import numpy as np


def render_merchant_view():
    """Renders merchant baseline traffic analytics and the core USP visualizer."""
    st.subheader("📈 Merchant Traffic Baselines & Surge Analytics")
    st.markdown("### Core Innovation: *'Not every traffic spike is an attack.'*")
    st.caption(
        "RazorGuard AI distinguishes legitimate revenue surges (e.g., promotional flash sales) from automated bot attacks "
        "by combining merchant velocity baselines with Shannon entropy diversity and IP reputation."
    )

    # 1. Side-by-Side Architectural Contrast
    c_flash, c_bot = st.columns(2)

    with c_flash:
        st.markdown(
            """
            <div style="background-color: #1E293B; border-top: 4px solid #10B981; padding: 16px; border-radius: 8px;">
                <h4 style="margin: 0; color: #10B981;">🟢 Scenario A: Legitimate Flash Sale</h4>
                <ul style="color: #CBD5E1; font-size: 0.9rem; margin-top: 8px; padding-left: 20px;">
                    <li><b>Traffic Volume:</b> 10× baseline surge</li>
                    <li><b>Account Diversity:</b> High (Shannon Entropy = 0.96)</li>
                    <li><b>Payment Success Rate:</b> 98.5%</li>
                    <li><b>Relational Topology:</b> Unique devices & distinct IPs</li>
                </ul>
                <div style="background-color: #0F172A; padding: 8px 12px; border-radius: 6px; text-align: center;">
                    <b style="color: #10B981; font-size: 1.1rem;">Verdict: ALLOW (Risk Score: 0 - 25)</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_bot:
        st.markdown(
            """
            <div style="background-color: #1E293B; border-top: 4px solid #EF4444; padding: 16px; border-radius: 8px;">
                <h4 style="margin: 0; color: #EF4444;">🔴 Scenario B: Automated Botnet Attack</h4>
                <ul style="color: #CBD5E1; font-size: 0.9rem; margin-top: 8px; padding-left: 20px;">
                    <li><b>Traffic Volume:</b> 10× baseline surge</li>
                    <li><b>Account Diversity:</b> Concentrated (Shannon Entropy = 0.04)</li>
                    <li><b>Payment Failure Rate:</b> 94.2% (Decline Velocity)</li>
                    <li><b>Relational Topology:</b> Shared proxy IP subnet / Headless</li>
                </ul>
                <div style="background-color: #0F172A; padding: 8px 12px; border-radius: 6px; text-align: center;">
                    <b style="color: #EF4444; font-size: 1.1rem;">Verdict: RATE_LIMIT (Risk Score: 90 - 100)</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # 2. Time-Series Comparative Simulation Chart
    st.markdown("#### ⏱️ Real-Time Volume vs. Risk Score Divergence")
    
    # Generate synthetic 60-second time series for both scenarios
    time_pts = np.linspace(0, 60, 30)
    
    # Baseline traffic
    baseline = np.full(30, 20)
    
    # Spike at t=20..45
    spike_vol = np.where((time_pts >= 20) & (time_pts <= 45), 200 + np.random.normal(0, 10, 30), 20 + np.random.normal(0, 2, 30))
    
    # Flash sale risk score remains flat / low
    flash_risk = np.where((time_pts >= 20) & (time_pts <= 45), 15 + np.random.normal(0, 3, 30), 10 + np.random.normal(0, 2, 30))
    flash_risk = np.clip(flash_risk, 0, 30)

    # Bot attack risk score shoots up to 98
    bot_risk = np.where((time_pts >= 20) & (time_pts <= 45), 95 + np.random.normal(0, 2, 30), 12 + np.random.normal(0, 2, 30))
    bot_risk = np.clip(bot_risk, 0, 100)

    fig_surge = go.Figure()
    
    # Volume trace (bars)
    fig_surge.add_trace(go.Bar(
        x=time_pts,
        y=spike_vol,
        name="Incoming Request Volume (RPM)",
        marker_color="rgba(56, 189, 248, 0.25)",
        yaxis="y1",
    ))
    
    # Flash sale risk trace (green line)
    fig_surge.add_trace(go.Scatter(
        x=time_pts,
        y=flash_risk,
        name="Flash Sale Risk Score (ALLOW)",
        line=dict(color="#10B981", width=3),
        yaxis="y2",
    ))

    # Bot attack risk trace (red line)
    fig_surge.add_trace(go.Scatter(
        x=time_pts,
        y=bot_risk,
        name="Botnet Attack Risk Score (RATE_LIMIT)",
        line=dict(color="#EF4444", width=3, dash="dot"),
        yaxis="y2",
    ))

    fig_surge.update_layout(
        title="<b>10× Traffic Surge Comparison: Organic Revenue vs. Adversarial Botnet</b>",
        xaxis=dict(title="Event Timeline (Seconds)"),
        yaxis=dict(title="Requests Per Minute (RPM)", side="left"),
        yaxis2=dict(title="Unified Risk Score (0-100)", side="right", overlaying="y", range=[0, 105]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=50, b=10),
        height=360,
    )

    st.plotly_chart(fig_surge, use_container_width=True)
