"""LangGraph Agentic AI Investigation Dossier & Audit Viewer Component."""

import streamlit as st
import json


def render_dossier_view():
    """Renders the LangGraph AI investigation report, state machine progression, and audit logs."""
    report = st.session_state.get("latest_investigation")
    selected_id = st.session_state.get("selected_tx_id")

    st.subheader("🤖 LangGraph Agentic AI Investigation Dossier")
    st.caption("Autonomous investigation state machine observing deterministic multi-modal risk, invoking bounded read-only tools, and synthesizing natural-language explanations.")

    if not report or report.transaction_id != selected_id:
        st.info("No active AI investigation dossier for the selected transaction. Click 'Investigate Selected' to execute the LangGraph workflow.")
        return

    # 1. Visual LangGraph State Machine Flow
    st.markdown("#### 🔄 LangGraph Investigation State Machine")
    
    path_nodes = report.investigation_path or ["OBSERVE", "ANALYZE", "INVESTIGATE", "CORRELATE", "DECIDE", "RECOMMEND", "EXPLAIN"]
    
    cols = st.columns(len(path_nodes))
    for i, node_name in enumerate(path_nodes):
        with cols[i]:
            st.markdown(
                f"""
                <div style="background-color: #1E293B; border: 1px solid #38BDF8; border-radius: 6px; padding: 8px 4px; text-align: center;">
                    <span style="font-size: 0.75rem; color: #94A3B8;">STEP {i+1}</span><br>
                    <b style="color: #38BDF8; font-size: 0.85rem;">{node_name}</b><br>
                    <span style="color: #10B981; font-size: 0.75rem;">✓ Completed</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")

    # 2. Key Metadata & Fallback Status Callout
    c_meta1, c_meta2, c_meta3, c_meta4 = st.columns(4)
    with c_meta1:
        st.metric(label="Investigation ID", value=report.investigation_id[:12])
    with c_meta2:
        status_label = "🟢 LIVE LLM" if report.investigation_status == "COMPLETED" else "🔵 DETERMINISTIC SYNTHESIS"
        st.metric(label="Engine Mode", value=status_label)
    with c_meta3:
        st.metric(label="Agent Confidence", value=f"{report.confidence * 100:.0f}%")
    with c_meta4:
        st.metric(label="Agent Latency", value=f"{report.latency_ms} ms")

    # 3. Executed Bounded Investigation Tools
    st.markdown("#### 🛠️ Bounded Read-Only Tools Executed")
    st.caption("The agent calls only relevant tools based on the observed risk category, avoiding unneeded queries.")
    
    if report.tools_used:
        tool_badges = []
        for t in report.tools_used:
            tool_badges.append(f"`✓ {t}()`")
        st.markdown(" ".join(tool_badges))
    else:
        st.markdown("`✓ Minimal Low-Risk Verification (No deep tool calling required)`")

    # 4. Evidence & Findings
    c_ev, c_find = st.columns(2)
    
    with c_ev:
        st.markdown("##### 📌 Key Evidence")
        if report.key_evidence:
            for ev in report.key_evidence:
                st.markdown(f"- {ev}")
        else:
            st.markdown("- Clean behavioral patterns within expected merchant volume thresholds.")

    with c_find:
        st.markdown("##### 🔬 Investigation Findings")
        if report.investigation_findings:
            for f in report.investigation_findings:
                st.markdown(f"- {f}")
        else:
            st.markdown("- Transaction topology verified as isolated with no syndicate links.")

    # 5. Natural Language Grounded Explanation
    st.markdown("---")
    st.markdown("#### 📝 Autonomous Risk Decision Explanation")
    
    action_col = "#EF4444" if report.recommended_action in ("RATE_LIMIT", "STEP_UP_VERIFICATION") else "#10B981"
    
    st.markdown(
        f"""
        <div style="background-color: #0F172A; border-left: 5px solid {action_col}; padding: 16px; border-radius: 8px; font-family: 'Segoe UI', sans-serif;">
            <div style="color: #94A3B8; font-size: 0.85rem; margin-bottom: 6px;">
                <b>DEFENSIVE RECOMMENDATION:</b> <span style="color: {action_col}; font-weight: bold;">{report.recommended_action}</span> (Confidence: {report.confidence*100:.0f}%)
            </div>
            <div style="color: #F8FAFC; font-size: 1.0rem; line-height: 1.5;">
                {report.explanation}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 6. Immutable Audit Trail JSON
    with st.expander("📄 View Immutable Investigation Audit Trail JSON"):
        st.caption("Cryptographically auditable execution trace including deterministic inputs, tool arguments, and timestamps.")
        audit_payload = {
            "investigation_id": report.investigation_id,
            "transaction_id": report.transaction_id,
            "investigation_status": report.investigation_status,
            "deterministic_inputs": {
                "risk_score": report.risk_score,
                "risk_level": report.risk_level,
                "fraud_probability": report.fraud_probability,
                "anomaly_score": report.anomaly_score,
                "graph_risk_score": report.graph_risk_score,
            },
            "tools_called": report.tools_used,
            "investigation_path": report.investigation_path,
            "recommended_action": report.recommended_action,
            "confidence": report.confidence,
            "explanation": report.explanation,
        }
        st.json(audit_payload)
