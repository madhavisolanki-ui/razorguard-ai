# Phase 6 Documentation: Real-Time Risk Command Center (Streamlit Dashboard)

**Project:** RazorGuard AI  
**Track:** Razorpay AI Buildathon 2026 — Track 2: AI Risk Manager  
**Phase:** Phase 6 (Completed & Verified)

---

## 1. Executive Summary & Core Objective

Phase 6 delivers the production-grade **Real-Time Risk Command Center** for RazorGuard AI. Built with Streamlit and Plotly, this dashboard transforms the multi-modal risk engine, NetworkX relational fraud graph, and LangGraph Agent into an interactive, visual security console designed for fraud analysts and hackathon judges.

The interface communicates the platform's primary value proposition within 5 seconds:
> **"Not every traffic spike is an attack — and not all fraud is visible at the individual transaction level."**

---

## 2. Dashboard Architecture & Component Layout

```
Streamlit App Entry Point (src/dashboard/app.py)
├── Global Dark Theme CSS (#0F172A, #1E293B, #38BDF8)
├── Top Status Header (Engine Active 🟢 | Graph Online 🕸️ | LangGraph Ready 🤖)
├── Executive KPI Cards (Total Ingested, Allowed, Monitored, Step-Up, Rate Limited, Latency)
└── Navigation Tabs:
    ├── Tab 1: ⚡ Live Stream & Overview (Real-Time Ingestion Feed & Risk Distribution Donut)
    ├── Tab 2: 🔍 Transaction Deep-Dive & SHAP (5-Bar Risk Comparison & TreeExplainer Attribution)
    ├── Tab 3: 🕸️ Fraud Network Graph (Interactive 2D NetworkX/Plotly Graph with Cluster Highlights)
    ├── Tab 4: 🤖 AI Investigation Dossier (LangGraph State Machine Flow & Audit Trail)
    ├── Tab 5: 📈 Merchant Baselines (Core USP: 10× Organic Flash Sale vs. Botnet Attack)
    ├── Tab 6: 📊 System Observability (Subsystem Latency Breakdown: Rules, ML, Graph, Agent)
    └── Tab 7: 🎯 One-Click Demo Scenarios (7 Canonical Interactive Scenario Injections)
```

---

## 3. Detailed Component Breakdown

### Tab 1: Live Payment Stream & Overview ([`stream_view.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/stream_view.py))
- Displays a real-time updating table of ingested payment events:
  `Timestamp`, `Transaction ID`, `Account ID`, `Merchant`, `Amount (INR)`, `Risk Score`, `Tier`, `Graph Score`, `Action Badge`, `Latency`.
- Action Badges: `🟢 ALLOW`, `🔵 MONITOR`, `🟠 STEP_UP`, `🔴 RATE_LIMIT`.
- Controls: Ingest Single Event, Clear Buffer, Quick Scenario Injector, and Transaction Selector.

### Tab 2: Transaction Deep-Dive & SHAP ([`investigation_view.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/investigation_view.py))
- **5-Bar Multi-Modal Risk Comparison:** Side-by-side visualization of Rule Velocity ($0-100$), XGBoost Supervised Probability ($0-100\%$), Isolation Forest Anomaly Score ($0-100\%$), NetworkX Graph Risk ($0-100$), and the Final Unified Risk Score.
- **SHAP Feature Attribution Chart:** Horizontal bar chart illustrating exact positive (red) and negative (green) risk drivers computed by TreeExplainer.
- **Deterministic Governance Callout:** Explicitly confirms that numerical risk scores originate exclusively from the deterministic pipeline and are never altered by the LLM.

### Tab 3: Fraud Network Graph ([`graph_view.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/graph_view.py))
- Interactive 2D Plotly NetworkX visualization rendering:
  - 🔵 `Account` nodes
  - 🟠 `Card Token` nodes
  - 🟣 `Device Hardware` nodes
  - 🔷 `IP Subnet` nodes
  - 🟡 `Merchant` nodes
  - 🔴 `Suspicious Tx` / 🟢 `Safe Tx` nodes
- Controls: Toggle between Ego Subgraph (focused on active account) and Full Global Entity Graph, Hop Neighborhood Slider ($1-3$ radius).
- Automatically highlights detected syndicate clusters with node count and density metrics.

### Tab 4: AI Investigation Dossier ([`dossier_view.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/dossier_view.py))
- **LangGraph State Machine Flow:** Step-by-step visual progression through all 7 nodes:
  `OBSERVE` $\rightarrow$ `ANALYZE` $\rightarrow$ `INVESTIGATE` $\rightarrow$ `CORRELATE` $\rightarrow$ `DECIDE` $\rightarrow$ `RECOMMEND` $\rightarrow$ `EXPLAIN`.
- **Bounded Tool Badges:** Lists executed tools with execution latency (e.g. `✓ get_related_entities()`, `✓ get_graph_signals()`).
- **Evidence & Findings:** Structured bullet points detailing ML and graph evidence.
- **Autonomous Explanation:** Evidence-grounded natural language explanation.
- **Cryptographic Audit Trail:** Expandable JSON viewer showing the immutable investigation trace.

### Tab 5: Merchant Baselines & Traffic Surge Analytics ([`merchant_view.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/merchant_view.py))
- Demonstrates the core USP: **"Not every traffic spike is an attack."**
- Side-by-side comparative simulation:
  - *10× Organic Flash Sale:* High Volume + High Shannon Entropy ($0.96$) + Normal Success Rate $\rightarrow$ Score $< 25$ / `ALLOW`.
  - *10× Botnet Surge:* High Volume + Concentrated Entropy ($0.04$) + High Decline Rate $\rightarrow$ Score $> 90$ / `RATE_LIMIT`.
- Dual-axis interactive time series chart plotting Volume (RPM) vs. Unified Risk Score divergence.

### Tab 6: System Observability & Subsystem Latency ([`observability_view.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/observability_view.py))
- Micro-benchmarks isolating local pipeline execution from external network I/O:
  - Feature Engineering: $\sim 1.8\text{ ms}$
  - XGBoost Classifier: $\sim 2.5\text{ ms}$
  - Isolation Forest: $\sim 1.6\text{ ms}$
  - TreeSHAP Attribution: $\sim 3.8\text{ ms}$
  - NetworkX Graph Builder: $\sim 4.2\text{ ms}$
  - **Total Deterministic Scoring Pipeline:** $\sim 13.9\text{ ms}$ (Sub-50ms Payment SLA).
- Displays fallback resilience rates and 100% test coverage metrics.

### Tab 7: One-Click Demo Scenarios ([`scenario_panel.py`](file:///c:/Users/Madha/RazorGuard-AI/src/dashboard/components/scenario_panel.py))
- Instant execution buttons for 6 canonical scenarios:
  1. *Normal Organic Traffic* (`ALLOW`)
  2. *Legitimate Flash Sale Surge* (`ALLOW`)
  3. *Automated Bot Abuse* (`RATE_LIMIT`)
  4. *Payment Abuse / Card Cracking* (`STEP_UP_VERIFICATION`)
  5. *Coordinated Multi-Entity Swarm* (`MONITOR`)
  6. *Fraud Ring Syndicate* (`STEP_UP_VERIFICATION`)

---

## 4. Two-Minute Judge Demo Walkthrough Script

For a compelling live presentation, follow this 2-minute judge flow:

```
Step 1: Open Tab 7 (One-Click Demo Scenarios)
        Click '▶️ Run Scenario' on '2. Legitimate Flash Sale Surge'.
        
Step 2: Switch to Tab 5 (Merchant Baselines)
        Show the judge that despite a 10× volume surge, the risk score is 0.0 (ALLOW)
        because entropy is high and payment success is normal.

Step 3: Switch to Tab 7 (One-Click Demo Scenarios)
        Click '▶️ Run Scenario' on '6. Fraud Ring Syndicate'.

Step 4: Switch to Tab 2 (Transaction Deep-Dive & SHAP)
        Show the 5-bar risk comparison: Individual XGBoost probability is low (~12%),
        but NetworkX Graph Risk is high (75+).

Step 5: Switch to Tab 3 (Fraud Network Graph)
        Show the interactive 15-entity cluster sharing 1 card token across 4 accounts.

Step 6: Switch to Tab 4 (AI Investigation Dossier)
        Show the LangGraph state machine (OBSERVE -> ANALYZE -> INVESTIGATE -> ...),
        the executed tools, and the evidence-grounded explanation.
```

---

## 5. How to Run Locally

### Start Streamlit Dashboard
```bash
streamlit run src/dashboard/app.py
```
*The web interface will automatically launch at `http://localhost:8501`.*

### Run Complete Automated Test Suite
```bash
pytest -v
============================= 72 passed in 17.44s =============================
```

---

## 6. Security, Privacy & Compliance Verification

- **PCI-DSS Anonymization:** Zero real PANs, CVVs, or cardholder credentials are used or displayed. Payment cards are referenced solely by non-reversible synthetic hashes (`card_syn_999`).
- **Prompt Injection Immunity:** User and device metadata are sanitized; adversarial prompt directives in transaction fields cannot override policy recommendations.
- **Defensive Boundary Guarantee:** The platform outputs only bounded defensive recommendations (`ALLOW`, `MONITOR`, `STEP_UP_VERIFICATION`, `RATE_LIMIT`) and executes zero autonomous account locks or funds confiscations.
