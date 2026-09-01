"""Transaction Deep-Dive, 5-Bar Multi-Modal Risk Scores & SHAP Attribution Component."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def render_investigation_view():
    """Renders transaction deep-dive, multi-modal risk score breakdown, and SHAP attributions."""
    txs = st.session_state.get("transactions", [])
    selected_id = st.session_state.get("selected_tx_id")
    
    if not txs or not selected_id:
        st.info("No transaction selected. Ingest or select a transaction from the live stream.")
        return

    # Find selected record
    record = next((t for t in txs if t["transaction_id"] == selected_id), None)
    if not record:
        st.warning(f"Transaction {selected_id} not found in buffer.")
        return

    st.subheader(f"🔍 Transaction Deep-Dive: `{record['transaction_id']}`")
    st.caption(f"Account: `{record['user_id']}` | Merchant: `{record['merchant_id']}` | Amount: ₹{record['amount']:,.2f}")

    # Top Decision Callout Banner
    score = record["risk_score"]
    tier = record["risk_level"]
    action = record["recommended_action"]
    
    color_map = {
        "ALLOW": ("#10B981", "🟢 ALLOW — Safe Organic Transaction"),
        "MONITOR": ("#38BDF8", "🔵 MONITOR — Moderate Risk Surveillance"),
        "STEP_UP_VERIFICATION": ("#F59E0B", "🟠 STEP-UP VERIFICATION — Suspicious Multi-Factor Check"),
        "RATE_LIMIT": ("#EF4444", "🔴 RATE LIMIT — Critical Abuse Mitigated"),
    }
    hex_col, action_title = color_map.get(action, ("#64748B", action))

    st.markdown(
        f"""
        <div style="background-color: #1E293B; border-left: 6px solid {hex_col}; padding: 14px 20px; border-radius: 8px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin: 0; color: #F8FAFC; font-size: 1.3rem;">{action_title}</h3>
                    <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 0.9rem;">
                        Deterministic Multi-Modal Risk: <b>{score:.1f} / 100</b> ({tier} Tier) | Latency: <b>{record['processing_latency_ms']} ms</b>
                    </p>
                </div>
                <div style="text-align: right;">
                    <span style="background: {hex_col}22; color: {hex_col}; padding: 6px 14px; border-radius: 20px; font-weight: bold; border: 1px solid {hex_col}; font-size: 0.95rem;">
                        {action}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. 5-Bar Multi-Modal Risk Score Comparison
    st.markdown("#### 📊 Multi-Modal Risk Scoring Components")
    st.caption("The Unified Risk Score is mathematically computed from 4 independent sub-engines. The LLM does not alter or calculate these scores.")

    col_chart, col_meta = st.columns([3, 2])
    
    with col_chart:
        # Extract component scores
        res = record.get("result", {})
        p_xgb = float(res.get("fraud_probability", record.get("fraud_probability", 0.0))) * 100.0
        p_iso = float(res.get("anomaly_score", record.get("anomaly_score", 0.0))) * 100.0
        s_graph = float(res.get("graph_risk_score", record.get("graph_risk_score", 0.0)))
        s_rule = float(res.get("velocity_score", 0.0))
        s_unified = float(record["risk_score"])

        categories = [
            "Rule / Velocity",
            "XGBoost Supervised",
            "Isolation Forest",
            "NetworkX Graph",
            "<b>Unified Decision</b>",
        ]
        values = [s_rule, p_xgb, p_iso, s_graph, s_unified]
        bar_colors = ["#94A3B8", "#38BDF8", "#A855F7", "#F59E0B", "#EF4444" if s_unified > 65 else "#10B981"]

        fig_scores = go.Figure(go.Bar(
            x=values,
            y=categories,
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{v:.1f}" for v in values],
            textposition="auto",
        ))

        fig_scores.update_layout(
            xaxis=dict(range=[0, 100], title="Score / Probability (0 - 100)"),
            yaxis=dict(autorange="reversed"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            height=220,
        )
        st.plotly_chart(fig_scores, use_container_width=True)

    with col_meta:
        st.markdown("**Core Risk Signals Detected:**")
        rule_trig = record.get("primary_rule_triggered")
        if rule_trig:
            st.warning(f"⚡ Heuristic Rule: `{rule_trig}`")
        else:
            st.success("✅ Clean Behavioral Cadence (No heuristic rule breaches)")
            
        if s_graph >= 50.0:
            st.error(f"🕸️ Coordinated Graph Syndicate (Graph Risk: {s_graph:.1f}/100)")
        else:
            st.info("🌐 Entity Graph: Isolated / Standard Relational Topology")

        st.caption("🔒 **Governance:** Deterministic risk engine is the sole source of truth. The AI Agent investigates evidence and explains the decision without altering numerical scores.")

    # 2. SHAP Feature Attribution Chart
    st.markdown("---")
    st.markdown("#### 🔬 Explainable ML: SHAP Feature Attributions (TreeExplainer)")
    st.caption("Exact marginal contribution of real-time behavioral features toward the XGBoost fraud prediction.")

    shap_signals = record.get("shap_signals", [])
    if shap_signals:
        # Parse signals into dataframe
        parsed_shap = []
        for s in shap_signals:
            if "increased risk by" in s:
                feat = s.split("increased risk by")[0].replace("[ML Driver]", "").strip()
                pct_str = s.split("increased risk by")[1].replace("%", "").replace("+", "").strip()
                try:
                    pct = float(pct_str)
                    parsed_shap.append({"feature": feat, "impact": pct, "direction": "Positive Risk Driver (Escalation)"})
                except ValueError:
                    parsed_shap.append({"feature": s, "impact": 10.0, "direction": "Positive Risk Driver (Escalation)"})
            elif "decreased risk by" in s:
                feat = s.split("decreased risk by")[0].replace("[ML Driver]", "").strip()
                pct_str = s.split("decreased risk by")[1].replace("%", "").replace("-", "").strip()
                try:
                    pct = -float(pct_str)
                    parsed_shap.append({"feature": feat, "impact": pct, "direction": "Negative Risk Driver (Mitigation)"})
                except ValueError:
                    parsed_shap.append({"feature": s, "impact": -10.0, "direction": "Negative Risk Driver (Mitigation)"})

        if parsed_shap:
            df_shap = pd.DataFrame(parsed_shap)
            df_shap = df_shap.sort_values(by="impact", ascending=True)

            colors_shap = ["#EF4444" if imp > 0 else "#10B981" for imp in df_shap["impact"]]

            fig_shap = go.Figure(go.Bar(
                x=df_shap["impact"],
                y=df_shap["feature"],
                orientation="h",
                marker=dict(color=colors_shap),
                text=[f"{imp:+.1f}%" for imp in df_shap["impact"]],
                textposition="auto",
            ))

            fig_shap.update_layout(
                title="<b>Feature Contribution to ML Fraud Probability (% SHAP Value)</b>",
                xaxis=dict(title="Marginal Risk Impact (%)"),
                yaxis=dict(title=""),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=35, b=10),
                height=230,
            )
            st.plotly_chart(fig_shap, use_container_width=True)
        else:
            for s in shap_signals:
                st.write(f"- {s}")
    else:
        st.write("🌿 Organic transaction within normal feature boundaries — all SHAP attributions close to zero baseline.")
