# Phase 3 Documentation: Dual Machine Learning Pipeline (XGBoost + Isolation Forest + SHAP)

**Project:** RazorGuard AI  
**Track:** Razorpay AI Buildathon 2026 — Track 2: AI Risk Manager  
**Phase:** Phase 3 (Completed & Verified)

---

## 1. Overview & Architecture

Phase 3 introduces a dual machine learning pipeline integrating **Supervised XGBoost classification**, **Unsupervised Isolation Forest behavioral anomaly detection**, and **TreeSHAP explainability** with the deterministic rule engine from Phase 2.

```
Incoming Payment Event
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. Real-Time Feature Calculation (calculator.py)       │
│ • Extract 28 numerical behavioral & velocity signals   │
│ • Merchant baseline & Shannon entropy evaluation       │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 2. Dual Machine Learning & Heuristic Inference         │
│ ┌───────────────────────┐   ┌────────────────────────┐ │
│ │ Supervised XGBoost    │   │ Unsupervised Isolation │ │
│ │ P(fraud) Classifier   │   │ Forest Anomaly Detector│ │
│ └───────────────────────┘   └────────────────────────┘ │
│ ┌───────────────────────┐   ┌────────────────────────┐ │
│ │ Transparent Rule      │   │ TreeSHAP Feature       │ │
│ │ Evaluation Matrix     │   │ Attribution Engine     │ │
│ └───────────────────────┘   └────────────────────────┘ │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 3. Unified Multi-Modal Risk Scorer (composite_scorer.py)│
│ • Fused risk score = w_xgb*P + w_iso*S + w_vel*V + Rules│
│ • Bounded Actions (ALLOW, MONITOR, STEP_UP, RATE_LIMIT)│
│ • Grounded, audit-proof explainable dossier            │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 4. Synchronous Fast-Path Persistence (service.py)      │
│ • Writes Transaction & RiskAssessment to database      │
│ • Returns response with ML probabilities & SHAP factors│
└────────────────────────────────────────────────────────┘
```

---

## 2. Feature Schema & ML Inputs (28 Features)

| Feature | Type | Description |
|---|---|---|
| `amount` | `float` | Transaction basket amount (INR). |
| `checkout_duration_sec` | `float` | Total elapsed seconds on checkout page. |
| `user_requests_per_minute` | `float` | Request frequency for the user in 1-minute window. |
| `user_requests_per_5_minutes` | `float` | Request volume for the user in 5-minute window. |
| `ip_requests_per_minute` | `float` | Request velocity from origin IP in 1-minute window. |
| `ip_requests_per_5_minutes` | `float` | Request volume from origin IP in 5-minute window. |
| `device_requests_per_minute` | `float` | Request frequency from device token in 1-minute window. |
| `device_requests_per_5_minutes` | `float` | Request volume from device token in 5-minute window. |
| `transaction_velocity` | `float` | Request rate in transactions per second. |
| `payment_failure_rate_5m` | `float` | Ratio of failed payment attempts in 5-minute window. |
| `payment_success_rate_5m` | `float` | Ratio of successful payment authorizations (`1.0 - failure_rate`). |
| `unique_accounts_per_ip_1h` | `float` | Distinct user accounts mapped to origin IP in 1 hour. |
| `unique_devices_per_ip_1h` | `float` | Distinct device tokens mapped to origin IP in 1 hour. |
| `unique_ips_per_account_24h` | `float` | Distinct IPs associated with user account in 24 hours. |
| `transactions_per_device_1h` | `float` | Total transaction throughput on device in 1 hour. |
| `amount_deviation` | `float` | Ratio of current amount to user historical average. |
| `account_age_hours` | `float` | Hours elapsed since user account registration. |
| `time_since_previous_transaction` | `float` | Elapsed seconds since user's prior transaction. |
| `repeated_transaction_ratio` | `float` | Fraction of 5m transactions with identical monetary amount. |
| `is_micro_transaction` | `int` | Binary flag indicating micro-amount card testing ($\le \text{INR } 50.00$). |
| `is_headless_device` | `int` | Binary flag for headless browser automation (Puppeteer/Playwright). |
| `is_emulator_device` | `int` | Binary flag for Android/iOS device emulator environment. |
| `is_datacenter_proxy` | `int` | Binary flag for datacenter proxy or VPN subnet. |
| `ip_reputation_score` | `float` | Threat intelligence score ($0.0 = \text{malicious}, 1.0 = \text{clean}$). |
| `merchant_volume_multiplier` | `float` | Ratio of current 5m volume to merchant baseline volume. |
| `merchant_ip_entropy` | `float` | Normalized Shannon entropy over IP addresses in merchant window. |
| `merchant_device_entropy` | `float` | Normalized Shannon entropy over devices in merchant window. |
| `is_flash_sale` | `int` | Binary flag indicating merchant-declared flash sale context. |

---

## 3. Dataset Generation & Training Methodology

### Dataset Synthesis & Partitioning
- **Total Samples:** $50{,}000$ synthetic payment events generated using `StreamSimulator(seed=42)`.
- **Class Distribution:**
  - Legitimate / Normal Traffic: $\approx 78\%$
  - Fraud / Automated Abuse Traffic: $\approx 22\%$
- **Data Partitioning:**
  - **Train Set (70%):** $35{,}000$ samples used for model fitting.
  - **Validation Set (15%):** $7{,}500$ samples used for early stopping.
  - **Held-Out Test Set (15%):** $1{,}500$ samples used for final unbiased metric calculation.
- **Leakage Prevention:** Features are extracted strictly on sliding windows and historical aggregations prior to event timestamp. No target information or future timestamps contaminate feature matrices.

### Model Configurations

#### 1. Supervised XGBoost Classifier
```python
xgb.XGBClassifier(
    n_estimators=150,
    max_depth=5,
    learning_rate=0.08,
    scale_pos_weight=3.55,  # Balanced class weighting
    subsample=0.85,
    colsample_bytree=0.85,
    eval_metric="logloss",
    random_state=42,
    n_jobs=-1,
    early_stopping_rounds=15,
)
```

#### 2. Unsupervised Isolation Forest Anomaly Detector
```python
IsolationForest(
    n_estimators=100,
    contamination=0.15,
    random_state=42,
    n_jobs=-1,
)
```
- **Anomaly Score Normalization:**
  $$\text{Normalized Anomaly Score} = \frac{1}{1 + \exp((\text{raw\_score} + 0.05) \times 12.0)}$$
  Maps raw decision function values into calibrated $[0.0, 1.0]$ probabilities, ensuring normal baselines score $\approx 0.05 - 0.15$ and severe outliers score $\approx 0.75 - 0.95$.

---

## 4. Unified Risk Engine & Scoring Formula

The system fuses machine learning probabilities, anomaly scores, velocity measurements, and heuristic rule impacts into a deterministic $0 - 100$ risk score:

$$\text{RiskScore} = \min\left(100, \, \max\left(0, \, (w_{\text{xgb}} \cdot P_{\text{fraud}} + w_{\text{iso}} \cdot S_{\text{iso}} + w_{\text{vel}} \cdot S_{\text{vel}}) \times 100 + \sum \text{RulePenalties}\right)\right)$$

- **Weights:** $w_{\text{xgb}} = 0.50$, $w_{\text{iso}} = 0.25$, $w_{\text{vel}} = 0.25$.
- **Bounded Defensive Action Thresholds:**
  - $\le 30.0$: `ALLOW` (`LOW`)
  - $30.1 - 65.0$: `MONITOR` (`MEDIUM`)
  - $65.1 - 85.0$: `STEP_UP_VERIFICATION` (`HIGH`)
  - $> 85.0$: `RATE_LIMIT` (`CRITICAL`)

---

## 5. SHAP TreeExplainer & Grounded Explainability

`SHAPExplainer` executes `shap.TreeExplainer` on the trained XGBoost tree ensemble in $< 1\text{ms}$.

- Computes exact directional feature contributions for each transaction.
- Converts top SHAP drivers into factual, user-facing explanations:
  - *"[ML Driver] Account request rate (1 min) (12.0) increased risk by +28.4%"*
  - *"[ML Driver] Payment failure/decline rate (5 min) (0.85) increased risk by +22.1%"*
  - *"[Rule Triggered] Headless Browser or Emulator Detected (+35 pts)"*
- Zero fabrication: all explanations originate directly from calculated model SHAP values and triggered rules.

---

## 6. Critical Validation Audit & Empirical Test Set Evaluation Metrics

### Validation Audit Summary
In the initial naive baseline, the synthetic feature mapping had artificially sharp boundaries between classes, resulting in 100% separability. A rigorous validation audit resolved this:
1. **Removed Synthetic Feature Leakage:** Replaced scenario-derived deterministic constants with realistic, continuous feature distributions containing natural variance across all classes.
2. **Strict Entity-Disjoint Splitting:** Implemented user-level disjoint partitioning (`unique_users` split into 70% train, 15% validation, 15% test). No user account or customer profile in the training set appears in the held-out test set.
3. **Realistic Borderline Cases Injected:** Added corporate VPN/proxy users, college campus shared NATs, quick 1-click buyers, legitimate payment retries (2-3 failed CVVs), stealth residential botnets with human checkout speeds (4-16s), and 2.5% ground-truth label noise.

### Evaluated on the Held-Out Entity-Disjoint Test Set ($N=1,376$ samples):

| Metric | Target | Initial Naive Value | Audited & Hardened Value | Status |
|---|---|---|---|---|
| **Accuracy** | $> 95\%$ | $100.00\%$ | **$97.82\%$** ($0.9782$) | PASS |
| **Precision** | $> 90\%$ | $100.00\%$ | **$97.54\%$** ($0.9754$) | PASS |
| **Recall** | $> 88\%$ | $100.00\%$ | **$90.84\%$** ($0.9084$) | PASS |
| **F1-Score** | $> 90\%$ | $1.0000$ | **$0.9407$** ($94.07\%$) | PASS |
| **ROC-AUC** | $> 0.95$ | $1.0000$ | **$0.9594$** ($95.94\%$) | PASS |
| **False Positive Rate (FPR)** | $< 2\%$ | $0.00\%$ | **$0.54\%$** ($0.0054$) | PASS |
| **False Negative Rate (FNR)** | $< 12\%$ | $0.00\%$ | **$9.16\%$** ($0.0916$) | PASS |

### Confusion Matrix ($N=1,376$ unseen events)
```
                     Predicted Legitimate    Predicted Fraud
Actual Legitimate:   TN = 1108                FP = 6
Actual Fraud:        FN = 24                  TP = 238
```

### Configurable False-Positive Financial Impact
- **Cost of False Positive ($C_{fp}$):** $\$15.00$ (lost customer lifetime value & tier-2 support overhead).
- **Cost of False Negative ($C_{fn}$):** $\$50.00$ (chargeback loss, dispute penalties, processing fees).
- **Total False Positive Loss ($6 \times \$15$):** $\$90.00$
- **Total False Negative Loss ($24 \times \$50$):** $\$1,200.00$
- **Net Financial Loss on Test Set:** **$\$1,290.00$**

---

## 7. Scenario-by-Scenario Benchmark

Benchmarked on $50$ sequential evaluations per scenario class:

| Scenario Class | Mean Risk Score | Median Risk Score | Action Distribution | Business Impact |
|---|---|---|---|---|
| **Normal Organic Traffic** | **$16.5$** | $16.2$ | `100% ALLOW` | Seamless checkout, minimal friction. |
| **Legitimate Traffic Spike (Flash Sale)** | **$2.4$** | $0.0$ | `100% ALLOW` | **Flash sale discount applied. Zero legitimate customer blockages.** |
| **Automated Bot Abuse** | **$100.0$** | $100.0$ | `100% RATE_LIMIT` | Sub-second checkouts & proxy bursts throttled immediately. |
| **Payment Abuse (Card Cracking)** | **$74.0$** | $78.5$ | `86% STEP_UP`, `14% MONITOR` | Micro-transaction decliners forced into 3DS/OTP verification. |
| **Coordinated Multi-Entity Abuse** | **$48.1$** | $48.0$ | `100% MONITOR` | Concentrated proxy subnets flagged for elevated surveillance. |
| **Fraud Ring (Syndicate)** | **$15.1$** | $14.8$ | `100% ALLOW` | *Individual transactions appear clean in isolation; multi-hop syndicate detection deferred to Phase 4 Graph Engine.* |

---

## 8. Empirical Performance & Latency Benchmark

Measured across $500$ sequential evaluations (`tests/benchmark_phase3.py`):

| Component | Mean Latency | P50 (Median) | P90 | P95 | P99 |
|---|---|---|---|---|---|
| **XGBoost Inference** | **$0.49\text{ ms}$** | $0.46\text{ ms}$ | $0.62\text{ ms}$ | $0.69\text{ ms}$ | $0.89\text{ ms}$ |
| **Isolation Forest Anomaly** | **$4.02\text{ ms}$** | $3.80\text{ ms}$ | $4.70\text{ ms}$ | $5.10\text{ ms}$ | $6.30\text{ ms}$ |
| **SHAP TreeExplainer** | **$0.90\text{ ms}$** | $0.82\text{ ms}$ | $1.17\text{ ms}$ | $1.26\text{ ms}$ | $1.60\text{ ms}$ |
| **Full Synchronous Pipeline** | **$40.41\text{ ms}$** | $41.00\text{ ms}$ | $44.99\text{ ms}$ | $47.22\text{ ms}$ | $58.21\text{ ms}$ |

- **Overall Throughput:** **$24.7\text{ events/sec}$** on single-worker SQLite.

---

## 9. Model Versioning & Artifacts

Metadata persisted at `data/models/feature_metadata.json`:
- `model_version`: `"1.0.0"`
- `feature_version`: `"2.0"`
- `dataset_version`: `"synthetic_v1_50000"`
- `config_version`: `"1.0"`
- `random_seed`: `42`
- `feature_count`: `28`

---

## 10. Limitations & Phase 4 Transition

- **Limitation:** Isolated single-event ML models cannot detect distributed fraud rings where syndicates distribute high-value transactions across clean identities and shared bank accounts.
- **Phase 4 Solution:** NetworkX Graph Engine will construct heterogeneous graph networks connecting `Users`, `Devices`, `IPs`, and `Bank Accounts` to detect cyclical flows and high-degree syndicate hubs.
