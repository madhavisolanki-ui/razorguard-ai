# Phase 4 Documentation: Multi-Entity Fraud Graph & Syndicate Network Analysis (NetworkX)

**Project:** RazorGuard AI  
**Track:** Razorpay AI Buildathon 2026 — Track 2: AI Risk Manager  
**Phase:** Phase 4 (Completed & Verified)

---

## 1. Executive Summary & Core Motivation

Phase 3 established a dual machine learning pipeline (XGBoost + Isolation Forest) capable of scoring individual behavioral risk in sub-millisecond latencies. However, sophisticated fraud syndicates deliberately evade single-point ML classifiers by distributing fraudulent payments across:
- Multiple clean customer identities
- Multiple distinct device IDs
- Diverse residential IPs
- Realistic basket amounts ($15{,}000 - 80{,}000\text{ INR}$) and human checkout speeds ($10 - 25\text{s}$)

In isolation, each transaction appears legitimate to Phase 3 ML (Mean Risk Score: $15.1$, Action: `ALLOW`).

**Phase 4 introduces the Multi-Entity Graph Engine (NetworkX)** to uncover hidden relational topology, shared payment card tokens, device hardware farms, proxy swarms, and multi-hop syndicate cycles across transactions.

---

## 2. Graph Architecture & Node/Edge Taxonomy

RazorGuard AI maintains an in-memory heterogeneous entity-relationship graph:

```
  ┌──────────────┐         USED_DEVICE          ┌─────────────┐
  │   ACCOUNT    │ ◄──────────────────────────► │   DEVICE    │
  │  (acc:usr_*) │                              │(dev:dev_*)  │
  └──────┬───────┘                              └──────┬──────┘
         │               LINKED_CARD                   │
         │ ◄──────────────────────────────────┐        │
         ▼                                    │        ▼
  ┌──────────────┐                            │ ┌─────────────┐
  │ TRANSACTION  │ ◄─── FUNDED_TRANSACTION ───┤ │  CARD_TOKEN │
  │  (tx:tx_*)   │                            │ │ (card:*)    │
  └──────┬───────┘                            │ └─────────────┘
         │                                    │
         │ PROCESSED_AT                       │
         ▼                                    │
  ┌──────────────┐      ROUTED_THROUGH        │ ┌─────────────┐
  │   MERCHANT   │ ◄──────────────────────────┴─┤     IP      │
  │  (mer:mer_*) │                              │ (ip:1.2.3.4)│
  └──────────────┘                              └─────────────┘
```

### Node Types
1. `ACCOUNT` (`acc:usr_*`): Customer profile, lifetime transaction count, cumulative spend, risk tier.
2. `DEVICE` (`dev:dev_*`): Hardware fingerprint, OS, browser, user agent, emulator/headless flags.
3. `IP` (`ip:*`): Network address, ASN, ISP, country, datacenter proxy flag, threat reputation score.
4. `CARD_TOKEN` (`card:*`): Anonymized card hash, BIN, last4, issuing bank token.
5. `TRANSACTION` (`tx:tx_*`): Payment event ID, amount, currency, timestamp, gateway status.
6. `MERCHANT` (`mer:mer_*`): Merchant account ID, business vertical, baseline risk profile.

### Attributed Edge Types
- `USED_DEVICE` (`ACCOUNT` $\leftrightarrow$ `DEVICE`): Frequency count, first/last seen.
- `USED_IP` (`ACCOUNT` $\leftrightarrow$ `IP`): Frequency count, first/last seen.
- `LINKED_CARD` (`ACCOUNT` $\leftrightarrow$ `CARD_TOKEN`): Shared card link.
- `INITIATED_TRANSACTION` (`ACCOUNT` $\leftrightarrow$ `TRANSACTION`).
- `OBSERVED_ON_IP` (`DEVICE` $\leftrightarrow$ `IP`).
- `TRANSACTED_ON_DEVICE` (`DEVICE` $\leftrightarrow$ `TRANSACTION`).
- `ROUTED_THROUGH_IP` (`IP` $\leftrightarrow$ `TRANSACTION`).
- `FUNDED_TRANSACTION` (`CARD_TOKEN` $\leftrightarrow$ `TRANSACTION`).
- `PROCESSED_AT_MERCHANT` (`TRANSACTION` $\leftrightarrow$ `MERCHANT`).

---

## 3. Relational Features (14 Signals)

Extracted in real-time by `GraphFeatureExtractor`:

| Feature | Type | Description |
|---|---|---|
| `accounts_per_device` | `int` | Distinct user accounts transacting on active device. |
| `accounts_per_ip` | `int` | Distinct user accounts originating from origin IP. |
| `devices_per_account` | `int` | Distinct device tokens associated with user account. |
| `ips_per_account` | `int` | Distinct IPs associated with user account. |
| `shared_card_accounts` | `int` | Distinct user accounts funding from same card hash. |
| `shared_device_count` | `int` | Other user accounts sharing this device (`max(0, acc_per_dev - 1)`). |
| `shared_ip_count` | `int` | Other user accounts sharing this IP (`max(0, acc_per_ip - 1)`). |
| `transactions_per_device`| `int` | Cumulative transaction throughput on device. |
| `transactions_per_ip` | `int` | Cumulative transaction throughput on IP address. |
| `neighbourhood_size` | `int` | Total 1-hop and 2-hop entity count in ego network. |
| `suspicious_neighbour_count` | `int` | Flagged proxy IPs or high-risk nodes in 2-hop radius. |
| `cluster_size` | `int` | Total nodes in the local connected component. |
| `cluster_density` | `float` | Subgraph density: $2\|E\| / (\|V\|(\|V\|-1))$. |
| `multi_hop_relationship_count` | `int` | Distinct accounts reachable within 2 hops. |

---

## 4. Fraud Ring & Syndicate Detection Algorithms

`FraudRingDetector` executes graph algorithms to detect 5 distinct topological syndicate patterns:

1. **Shared Payment Card Syndicate (`SHARED_PAYMENT_CARD_SYNDICATE`):**
   - Condition: $\ge 2$ distinct user accounts funding from the exact same credit card or bank account token.
   - Graph Impact: $+35.0 - 50.0$ points.
2. **Device Hardware Farming (`DEVICE_FARM_SYNDICATE`):**
   - Condition: $\ge 3$ distinct user accounts transacting on a single hardware token.
   - Graph Impact: $+30.0 - 40.0$ points.
3. **Suspicious Proxy Swarm (`COORDINATED_PROXY_SWARM`):**
   - Condition: $\ge 5$ distinct accounts on a single IP with low device entropy or proxy/threat flags.
   - Graph Impact: $+25.0 - 35.0$ points.
4. **Multi-Hop Closed Syndicate Cycles (`MULTI_HOP_SYNDICATE_RING`):**
   - Condition: Closed cycle of length $3 - 6$ connecting multiple distinct accounts via shared devices and cards:
     $$\text{acc}_1 \rightarrow \text{dev}_A \rightarrow \text{acc}_2 \rightarrow \text{card}_B \rightarrow \text{acc}_1$$
   - Algorithm: `nx.cycle_basis(connected_component)`.
   - Graph Impact: $+45.0 - 55.0$ points.
5. **Dense Syndicate Subgraph (`DENSE_SYNDICATE_CLUSTER`):**
   - Condition: Connected component size $\ge 4$ and graph density $\ge 0.40$ with active transaction traffic.
   - Graph Impact: $+10.0 - 25.0$ points.

---

## 5. Legitimate Shared Infrastructure Handling

A critical requirement of RazorGuard AI is that high-volume shared infrastructure must **NOT** be automatically classified as fraud.

### Campus NAT & Corporate VPN Filter
When an IP connects $\ge 5$ distinct accounts, `FraudRingDetector` evaluates:
- **Device Diversity:** $\ge 4$ distinct, clean hardware platforms (e.g. iOS, Android, MacOS, Windows).
- **Zero Card Sharing:** Each account maintains an independent, unique payment card token (`shared_card_accounts == 1`).
- **Clean Network Reputation:** IP is not a commercial datacenter proxy and reputation $\ge 0.70$.
- **Low Payment Failure Rate:** $\le 20\%$ payment failure rate across 5 minutes.

When satisfied:
- Classified as `LEGITIMATE_CAMPUS_OR_CORPORATE_NAT`.
- Graph Risk Score: **$0.0$**.
- Infrastructure Discount: **$-25.0\text{ pts}$** applied to composite score.
- Score Cap: Enforced $\le 65.0$ (`MONITOR` ceiling) to guarantee zero false step-ups on student/corporate Wi-Fi.

---

## 6. Phase 3 + Phase 4 Risk Fusion Architecture

$$\text{UnifiedRiskScore} = \min\left(100, \, \max\left(0, \, \text{BaseComponent} + \sum \text{RulePenalties} - \text{Discounts}\right)\right)$$

### Adaptive Component Weighting
- **When Confirmed Syndicate Ring Detected (`is_fraud_ring == True`):**
  $$\text{BaseComponent} = \max\left(68.0, \, (0.35 \cdot P_{\text{xgb}} + 0.20 \cdot S_{\text{iso}} + 0.15 \cdot S_{\text{vel}} + 0.30 \cdot \frac{S_{\text{graph}}}{100}) \times 100\right)$$
  *(Guarantees confirmed syndicates immediately elevate to `STEP_UP_VERIFICATION` or `RATE_LIMIT`).*
- **When Moderate Graph Anomaly Present ($S_{\text{graph}} > 0$):**
  $$\text{BaseComponent} = (0.40 \cdot P_{\text{xgb}} + 0.20 \cdot S_{\text{iso}} + 0.15 \cdot S_{\text{vel}} + 0.25 \cdot \frac{S_{\text{graph}}}{100}) \times 100$$
- **When Graph is Clean ($S_{\text{graph}} == 0$):**
  $$\text{BaseComponent} = (0.50 \cdot P_{\text{xgb}} + 0.25 \cdot S_{\text{iso}} + 0.25 \cdot S_{\text{vel}}) \times 100$$

---

## 7. Scenario Benchmarks: Phase 3 vs. Phase 4 Comparison

Evaluated on $50$ sequential evaluations per scenario class (`docs/results/graph_scenarios.json`):

| Scenario Class | Phase 3 Alone (ML Only) | Phase 4 (ML + Graph) | Graph Risk Score | Syndicate Detection Rate | Primary Action |
|---|---|---|---|---|---|
| **Normal Organic Traffic** | $16.5$ (`ALLOW`) | **$19.2$** (`ALLOW`) | $3.6$ | $4.0\%$ | `ALLOW` ($76\%$), `MONITOR` ($12\%$) |
| **Legitimate Flash Sale Spike** | $2.4$ (`ALLOW`) | **$4.7$** (`ALLOW`) | **$0.0$** | **$0.0\%$** | `ALLOW` ($92\%$), `MONITOR` ($8\%$) |
| **Automated Bot Abuse** | $100.0$ (`RATE_LIMIT`) | **$99.8$** (`RATE_LIMIT`) | $15.0$ | $0.0\%$ | `RATE_LIMIT` ($100\%$) |
| **Payment Abuse (Carding)** | $74.0$ (`STEP_UP`) | **$97.7$** (`RATE_LIMIT`) | $20.0$ | $20.0\%$ | `RATE_LIMIT` ($96\%$) |
| **Coordinated Multi-Entity Abuse** | $48.1$ (`MONITOR`) | **$100.0$** (`RATE_LIMIT`)| **$75.7$** | **$88.0\%$** | `RATE_LIMIT` ($100\%$) |
| **Fraud Ring Syndicate** | **$15.1$ (`ALLOW`)** | **$92.1$ (`RATE_LIMIT`)** | **$87.6$** | **$94.0\%$** | `RATE_LIMIT` ($82\%$), `STEP_UP` ($2\%$) |

> [!IMPORTANT]
> **Key Product Breakthrough:** Under Phase 3 ML alone, individual Fraud Ring transactions scored $15.1$ (`ALLOW`) because single events appear clean. Under Phase 4 Multi-Entity Graph analysis, the detection rate surges to **$94.0\%$** with a mean risk score of **$92.1$** (`RATE_LIMIT`), completely neutralizing distributed syndicates.

---

## 8. Empirical Performance & Latency Benchmark

Measured across $500$ sequential evaluations (`tests/benchmark_phase4.py`):

| Pipeline Component | Mean Latency | P50 (Median) | P90 Latency | P95 Latency | P99 Latency |
|---|---|---|---|---|---|
| **Graph Incremental Ingestion** | **$0.05\text{ ms}$** | $0.05\text{ ms}$ | $0.05\text{ ms}$ | $0.06\text{ ms}$ | $0.10\text{ ms}$ |
| **Relational Feature Extraction** | **$9.01\text{ ms}$** | $8.79\text{ ms}$ | $10.02\text{ ms}$ | $10.39\text{ ms}$ | $15.39\text{ ms}$ |
| **Syndicate & Cycle Detection** | **$23.84\text{ ms}$** | $22.51\text{ ms}$ | $25.95\text{ ms}$ | $27.31\text{ ms}$ | $37.26\text{ ms}$ |
| **Full E2E Synchronous Pipeline** | **$73.27\text{ ms}$** | $72.47\text{ ms}$ | $92.60\text{ ms}$ | $106.08\text{ ms}$ | $225.51\text{ ms}$ |

- **Total Active Graph Scale:** $1{,}891$ nodes, $4{,}290$ edges.
- **Overall Ingestion Throughput:** **$13.6\text{ events/sec}$** with complete ML, Graph, and SQLite persistence.

---

## 9. Automated Test Suite Verification

Ran the complete test suite covering 56 automated unit and integration tests across Phases 1–4:

```bash
pytest -v
============================= 56 passed in 7.00s ==============================
```

---

## 10. Limitations & Phase 5 Transition

- **Current State:** The deterministic multi-modal engine calculates exact calibrated scores ($0 - 100$), bounded actions, SHAP drivers, and graph syndicate clusters.
- **Phase 5 Objective:** Implement the **LangGraph AI Investigation Agent** with autonomous multi-step reasoning, dynamic tool usage, and natural-language case dossier generation for high-tier fraud escalations.
