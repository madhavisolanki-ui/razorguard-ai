"""RazorGuard AI: Real-Time Risk Command Center Dashboard (Streamlit)."""

import streamlit as st
from pathlib import Path
import sys

# Ensure root dir is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dashboard.state import init_dashboard_state
from src.dashboard.components.kpi_cards import render_kpi_cards, render_risk_distribution_chart
from src.dashboard.components.stream_view import render_stream_view
from src.dashboard.components.investigation_view import render_investigation_view
from src.dashboard.components.graph_view import render_graph_view
from src.dashboard.components.dossier_view import render_dossier_view
from src.dashboard.components.merchant_view import render_merchant_view
from src.dashboard.components.observability_view import render_observability_view
from src.dashboard.components.scenario_panel import render_scenario_panel


# 1. Configure Streamlit Page
st.set_page_config(
    page_title="RazorGuard AI — Risk Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Inject Custom Fintech Command Center Dark Theme CSS
st.markdown(
    """
    <style>
    /* Dark Command Center Aesthetics */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    
    /* Header Bar */
    .header-bar {
        background: linear-gradient(90deg, #1E293B 0%, #0F172A 100%);
        border-bottom: 2px solid #38BDF8;
        padding: 16px 24px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    
    /* KPI Card styling */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.85rem !important;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1E293B;
        border-radius: 6px 6px 0px 0px;
        padding: 10px 18px;
        color: #94A3B8;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #38BDF8 !important;
        color: #0F172A !important;
    }
    
    /* Tables */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 3. Initialize State
init_dashboard_state()

# 4. Top Header & Subtitle
st.markdown(
    """
    <div class="header-bar">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="margin: 0; font-size: 1.8rem; color: #F8FAFC;">
                    🛡️ RazorGuard AI <span style="font-size: 1.0rem; color: #38BDF8; font-weight: normal;">| Real-Time Risk Command Center</span>
                </h1>
                <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 0.95rem;">
                    Agentic Payment Abuse & Fraud Syndicate Detection Engine — <i>Razorpay AI Buildathon 2026</i>
                </p>
            </div>
            <div style="text-align: right;">
                <span style="background: #10B98122; color: #10B981; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; border: 1px solid #10B981;">
                    🟢 Engine Active
                </span>
                <span style="background: #38BDF822; color: #38BDF8; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; border: 1px solid #38BDF8; margin-left: 6px;">
                    🕸️ Graph Online
                </span>
                <span style="background: #A855F722; color: #A855F7; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; border: 1px solid #A855F7; margin-left: 6px;">
                    🤖 LangGraph Ready
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 5. Top Executive KPI Cards
render_kpi_cards()
st.write("")

# 6. Main Navigation Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "⚡ Live Stream & Overview",
    "🔍 Transaction Deep-Dive & SHAP",
    "🕸️ Fraud Network Graph",
    "🤖 AI Investigation Dossier",
    "📈 Merchant Baselines (Core USP)",
    "📊 System Observability",
    "🎯 One-Click Demo Scenarios",
])

with tab1:
    col_str, col_dist = st.columns([3.5, 1.5])
    with col_str:
        render_stream_view()
    with col_dist:
        render_risk_distribution_chart()

with tab2:
    render_investigation_view()

with tab3:
    render_graph_view()

with tab4:
    render_dossier_view()

with tab5:
    render_merchant_view()

with tab6:
    render_observability_view()

with tab7:
    render_scenario_panel()

# 7. Global Sidebar Controls
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=64)
    st.markdown("### **RazorGuard AI Controls**")
    st.caption("AI Risk Manager Platform")
    
    st.divider()
    st.markdown("#### **Active Transaction**")
    sel_id = st.session_state.get("selected_tx_id", "None")
    st.info(f"Target: `{sel_id}`")
    
    st.divider()
    st.markdown("#### **Core Architecture**")
    st.markdown(
        """
        - ⚡ **Phase 2:** Behavioral Entropy
        - 🤖 **Phase 3:** Supervised XGBoost
        - 🌲 **Phase 3:** Isolation Forest
        - 🕸️ **Phase 4:** NetworkX Syndicates
        - 🧠 **Phase 5:** LangGraph Agent
        """
    )
    
    st.divider()
    st.caption("🔒 PCI-DSS Compliant Synthetic Sandbox. Zero real cardholder credentials.")
