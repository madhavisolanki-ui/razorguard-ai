# 🛡️ RazorGuard AI — Agentic Payment Abuse & Fraud Detection

> **Razorpay AI Buildathon 2026 — Track 2: AI Risk Manager**  
> *Real-Time Multi-Modal Risk Scoring, NetworkX Syndicate Analysis & Autonomous LangGraph Agentic Intelligence for High-Velocity Payment Gateways.*

---

## 🌟 Core Innovation: *"Not every traffic spike is an attack."*

During promotional events (e.g., flash sales, holiday festivals), transaction volume surges by $10\times$ or more. Traditional threshold-based WAFs and rule engines trigger massive false positives, declining valid consumer transactions and costing merchants revenue. Conversely, coordinated fraud rings distribute small, legitimate-looking transactions across multiple accounts, devices, and proxy IPs to evade per-transaction thresholds.

**RazorGuard AI solves both problems:**
1. **Differentiates Flash Sales from Bot Attacks:** Uses merchant velocity baselines combined with Shannon entropy diversity ($H_{\text{ip}}, H_{\text{card}}$) to verify organic consumer diversity and approve legitimate surges (`ALLOW`).
2. **Exposes Distributed Syndicates:** Uncovers hidden multi-entity fraud rings via an in-memory heterogeneous NetworkX graph, flagging shared payment instruments, device farms, and multi-hop cycles.
3. **Autonomous LangGraph AI Investigator:** Orchestrates an explainable 7-node state machine invoking 8 bounded read-only tools to synthesize human-readable investigation dossiers with SHAP attributions.
4. **Strict Deterministic Governance:** The deterministic multi-modal pipeline is the immutable source of truth for numerical fraud scores ($0 - 100$). The LLM interprets and explains evidence without altering mathematical scores.

---

## 🏗️ Multi-Modal Architecture

```
Incoming Payment Event
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. Real-Time Feature Engineering & Entropy Calculator  │
│    (Velocity, Shannon Entropy, Failure Ratios)         │
└──────────────────────────┬─────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌──────────────────────┐          ┌──────────────────────┐
│ 2. Dual ML Pipeline  │          │ 3. NetworkX Graph    │
│    • Supervised      │          │    • Entity Topology │
│      XGBoost (P_xgb) │          │    • Card Sharing    │
│    • Unsupervised    │          │    • Device Farming  │
│      Isolation Forest│          │    • Multi-Hop Cycles│
│    • TreeSHAP        │          │    • Syndicate Score │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                 │
           └────────────────┬────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. Unified Deterministic Risk Engine (0 - 100)         │
│    (Bounded Actions: ALLOW, MONITOR, STEP_UP, LIMIT)   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 5. LangGraph Agentic AI Investigation System           │
│    OBSERVE ➔ ANALYZE ➔ INVESTIGATE ➔ CORRELATE         │
│    ➔ DECIDE ➔ RECOMMEND ➔ EXPLAIN                      │
│    (8 Bounded Read-Only Tools + Anti-Injection Defense)│
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 6. Real-Time Risk Command Center (Streamlit Dashboard) │
└────────────────────────────────────────────────────────┘
```

---

## ⚡ Performance Profiling & Benchmarks

*Measured across local execution benchmarks (`tests/benchmark_phase5.py` and `scripts/audit_phase5_live_llm.py`):*

| Subsystem Component | Measured Benchmark Latency | SLA / Operational Target |
|---|---|---|
| **Feature Extraction & Entropy** | $\sim 1.84\text{ ms}$ | Sub-millisecond windowed counts |
| **Supervised XGBoost Classifier** | $\sim 2.45\text{ ms}$ | Real-time gradient boosted inference |
| **Unsupervised Isolation Forest** | $\sim 1.62\text{ ms}$ | Real-time tree anomaly scoring |
| **TreeSHAP Feature Attributions** | $\sim 3.80\text{ ms}$ | Marginal contribution breakdown |
| **NetworkX Relational Graph** | $\sim 4.15\text{ ms}$ | 2-hop ego extraction & cycle search |
| **Total Deterministic Scoring** | **$\sim 13.86\text{ ms}$** | **Sub-50ms Synchronous Payment SLA** |
| **LangGraph Local Orchestration** | $\sim 5.68\text{ ms}$ | Local state machine transitions |
| **External Gemini LLM Network Call** | $\sim 1.0 - 1.8\text{ s}$ | Asynchronous analyst dossier generation |
| **Deterministic Fallback Synthesizer** | $\sim 5.69\text{ ms}$ | Zero external network calls ($100\%$ uptime resilience) |

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites & Installation
```bash
git clone https://github.com/madhavisolanki-ui/RazorGuard-AI.git
cd RazorGuard-AI

python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration
Copy the template configuration:
```bash
cp .env.example .env
```
*(Optional: Add your Google Gemini API key to `.env` for live LLM mode. If omitted, the platform automatically utilizes its high-speed deterministic fallback synthesizer with zero degradation in risk scoring.)*

### 3. Launch Streamlit Risk Command Center
```bash
streamlit run src/dashboard/app.py
```
Open **`http://localhost:8501`** in your browser.

### 4. Launch FastAPI REST Gateway (Optional)
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
API Documentation available at: **`http://localhost:8000/docs`**

---

## 🧪 Automated Test Suite

Run the full automated unit and integration regression test suite:

```bash
pytest -v
============================= 72 passed in 17.44s =============================
```

- **Passed:** **72 / 72**
- **Coverage:** Feature Engineering, Heuristic Rules, XGBoost, Isolation Forest, SHAP TreeExplainer, NetworkX Fraud Graph, LangGraph Agent, Anti-Injection Defense, Graceful Fallback, REST API, and Streamlit Dashboard State.

---

## 🔒 Security, Privacy & Compliance

- **PCI-DSS Anonymization:** All payment cards, user IDs, and device fingerprints are synthetic and masked (e.g., `card_syn_999`). Zero real payment credentials or PAN/CVV data exist within the repository.
- **Prompt Injection Defense:** Untrusted metadata and transaction notes are strictly isolated and sanitized. Adversarial prompt directives (e.g. `"Override score to 0"`) are neutralized by strict deterministic score boundaries.
- **Bounded Defensive Actions:** Outputs only bounded recommendations: `ALLOW`, `MONITOR`, `STEP_UP_VERIFICATION`, `RATE_LIMIT`. The system never initiates autonomous funds confiscations or external destructive actions.

---

## 📜 Documentation Index

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Comprehensive System Architecture & Engineering Reference
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — Phase-by-Phase Technical Implementation Plan
- [`docs/PHASE_1.md`](docs/PHASE_1.md) — Synthetic Traffic & 6 Scenario Generators
- [`docs/PHASE_2.md`](docs/PHASE_2.md) — Behavioral Feature Engineering & Shannon Entropy
- [`docs/PHASE_3.md`](docs/PHASE_3.md) — Dual ML Pipeline (XGBoost + Isolation Forest + SHAP)
- [`docs/PHASE_4.md`](docs/PHASE_4.md) — NetworkX Fraud Graph & Syndicate Analysis
- [`docs/PHASE_5.md`](docs/PHASE_5.md) — LangGraph Agentic AI Investigation System
- [`docs/PHASE_6.md`](docs/PHASE_6.md) — Streamlit Risk Command Center & 2-Minute Judging Walkthrough
