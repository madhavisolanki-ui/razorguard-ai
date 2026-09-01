# Phase 2 Documentation: Real-time Feature Engineering & Behavioural Risk Engine

**Project:** RazorGuard AI  
**Track:** Razorpay AI Buildathon 2026 — Track 2: AI Risk Manager  
**Phase:** Phase 2 (Completed & Verified)

---

## 1. Overview & Architecture

Phase 2 introduces the real-time feature engineering pipeline, merchant baseline evaluation engine, transparent behavioural rule engine, and synchronous FastAPI event processing service.

```
Incoming Payment Event
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. Real-Time Feature Calculation (calculator.py)       │
│ • User / IP / Device 1m & 5m request velocity          │
│ • Sliding window payment failure / decline ratio       │
│ • Multi-account IP / device concentration              │
│ • User amount baseline & amount deviation              │
│ • Time since previous transaction & account age        │
│ • Repeated transaction ratio & micro-transaction flag  │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 2. Baseline & Spike Context Engine (baselines.py)      │
│ • Merchant-specific historical baseline volume & stats │
│ • Shannon entropy calculation over IPs and Devices     │
│ • Flash sale spike vs. botnet attack surge classifier  │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 3. Transparent Behavioural Rule Engine (rules.py)      │
│ • Abnormal velocity rules (R_VEL_IP_BURST, etc.)       │
│ • Excessive decline clusters (R_FAIL_DECLINES, etc.)   │
│ • Headless browser / proxy threat intelligence         │
│ • Micro-transaction card testing pattern detection     │
│ • Legitimate Flash Sale discount (R_SPIKE_DISCOUNT)    │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 4. Preliminary Behavioural Risk Scorer (scorer.py)     │
│ • Calibrated 0–100 numerical risk score                │
│ • Bounded Defensive Actions (ALLOW, MONITOR,           │
│   STEP_UP_VERIFICATION, RATE_LIMIT)                    │
│ • Human-readable audit explanation                     │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 5. Persistence & Fast-Path API (service.py & events.py)│
│ • POST /events (Ingest & persist < 25ms P95)           │
│ • POST /risk/analyze (On-the-fly dry-run evaluation)   │
│ • GET /risk/{transaction_id} (Audit dossier retrieval) │
└────────────────────────────────────────────────────────┘
```

---

## 2. Feature Definitions & Computational Rules

| Feature Name | Type | Window / Scope | Description |
|---|---|---|---|
| `user_requests_per_minute` | `int` | Rolling 60s | Velocity of requests for the specific `user_id`. |
| `user_requests_per_5_minutes` | `int` | Rolling 300s | 5-minute velocity for the `user_id`. |
| `ip_requests_per_minute` | `int` | Rolling 60s | Velocity of requests from the origin `ip_address`. |
| `ip_requests_per_5_minutes` | `int` | Rolling 300s | 5-minute velocity from the origin `ip_address`. |
| `device_requests_per_minute` | `int` | Rolling 60s | Velocity of requests from the specific `device_id`. |
| `transaction_velocity` | `float` | Rolling 60s | Transactions per second from the IP. |
| `payment_failure_rate_5m` | `float` | Rolling 300s | Failed transaction ratio on origin IP (`failed_tx / total_tx`). |
| `payment_success_rate_5m` | `float` | Rolling 300s | Successful transaction ratio on origin IP (`1.0 - failure_rate`). |
| `unique_accounts_per_ip_1h` | `int` | Rolling 1 hour | Distinct `user_id` count originating from this IP. |
| `unique_devices_per_ip_1h` | `int` | Rolling 1 hour | Distinct `device_id` count originating from this IP. |
| `unique_ips_per_account_24h` | `int` | Rolling 24 hours | Distinct IP count used by the user account. |
| `transactions_per_device_1h` | `int` | Rolling 1 hour | Total transaction count on device hardware token. |
| `average_user_amount` | `float` | Historical | User's historical mean basket amount. |
| `amount_deviation` | `float` | Historical | `current_amount / average_user_amount`. |
| `account_age_hours` | `float` | Lifetime | Hours elapsed since `user.created_at`. |
| `time_since_previous_transaction` | `float` | Lifetime | Elapsed seconds since user's previous transaction. |
| `repeated_transaction_ratio` | `float` | Rolling 300s | Fraction of 5m transactions with identical amount. |
| `is_micro_transaction` | `bool` | Current | `True` if `amount <= 50.00 INR`. |
| `merchant_5m_volume` | `int` | Rolling 300s | Current 5-minute volume on target merchant. |
| `merchant_volume_multiplier` | `float` | Rolling 300s | `merchant_5m_volume / merchant_baseline_5m_volume`. |
| `merchant_ip_entropy` | `float` | Rolling 300s | Shannon entropy over IP addresses in merchant window. |
| `merchant_device_entropy` | `float` | Rolling 300s | Shannon entropy over devices in merchant window. |
| `is_legitimate_spike_candidate`| `bool` | Rolling 300s | `True` if volume surge has high entropy & success rate. |

---

## 3. Shannon Entropy & Spike Differentiation Logic

To distinguish a legitimate traffic surge (e.g. flash sale) from an automated bot assault:

$$\text{Entropy}(X) = -\sum_{i=1}^{k} P(x_i) \log_2 P(x_i)$$
$$\text{Normalized Entropy} = \frac{\text{Entropy}(X)}{\log_2(n)}$$

- **Legitimate Flash Sale:** High volume surge ($\ge 3\times$ baseline) + High IP entropy ($\ge 0.65$) + High Device entropy ($\ge 0.65$) + Normal Success Rate ($\ge 75\%$) $\rightarrow$ `is_legitimate_spike = True`. Applies `R_SPIKE_LEGITIMATE_FLASH_SALE_DISCOUNT` ($-25$ score modifier).
- **Automated Bot Attack Surge:** High volume surge ($\ge 3\times$ baseline) + Low IP/Device entropy ($< 0.40$) OR High decline rate ($> 50\%$) $\rightarrow$ `is_suspicious_attack_surge = True`. Applies `R_SPIKE_SUSPICIOUS_ATTACK_SURGE` ($+45$ score modifier).

---

## 4. Behavioural Rule Matrix

| Rule ID | Category | Severity | Score Impact | Trigger Condition |
|---|---|---|---|---|
| `R_VEL_IP_BURST` | Velocity | `HIGH` | $+35.0$ | `ip_requests_per_minute > max_ip_requests_per_minute` (20) |
| `R_VEL_USER_BURST` | Velocity | `MEDIUM` | $+20.0$ | `user_requests_per_minute > max_user_requests_per_minute` (5) |
| `R_BOT_SUB_SECOND_CHECKOUT` | Velocity | `HIGH` | $+40.0$ | `checkout_duration_sec < 1.5` (inhuman bot checkout speed) |
| `R_FAIL_EXCESSIVE_DECLINES` | Failure Rate | `HIGH` | $+35.0$ | `payment_failure_rate_5m >= 0.60` with $\ge 3$ transactions |
| `R_FAIL_HIGH_RISK_CODE` | Failure Rate | `HIGH` | $+30.0$ | `failure_code` in `[INCORRECT_CVV, INVALID_EXPIRY, DO_NOT_HONOR, STOLEN_CARD]` |
| `R_CONC_ACCOUNTS_ON_IP` | Concentration | `HIGH` | $+30.0$ | `unique_accounts_per_ip_1h > 4` |
| `R_THREAT_HEADLESS_BROWSER` | Threat Intel | `HIGH` | $+35.0$ | `is_headless == True` or `is_emulator == True` |
| `R_THREAT_DATACENTER_PROXY` | Threat Intel | `MEDIUM` | $+25.0$ | `is_datacenter_proxy == True` or `ip_reputation < 0.40` |
| `R_PAT_MICRO_CARD_TESTING` | Pattern | `HIGH` | $+35.0$ | `is_micro_transaction == True` with rapid cadence / failure signals |
| `R_PAT_REPEATED_AMOUNTS` | Pattern | `MEDIUM` | $+20.0$ | `repeated_transaction_ratio >= 0.70` with $\ge 4$ transactions |
| `R_REL_NEW_ACCOUNT_LARGE_AMOUNT` | Concentration | `MEDIUM` | $+20.0$ | `account_age_hours < 2.0` and `amount_deviation > 5.0` |
| `R_SPIKE_SUSPICIOUS_ATTACK_SURGE` | Merchant Spike | `CRITICAL`| $+45.0$ | Volume surge on merchant with low IP/device entropy |
| `R_SPIKE_LEGITIMATE_FLASH_SALE_DISCOUNT` | Merchant Spike | `DISCOUNT` | $-25.0$ | Confirmed high-entropy flash sale; mitigates false positives |

---

## 5. Bounded Defensive Actions

```
Score: 0.0 ───────── 30.0 ────────────── 65.0 ────────────── 85.0 ───────── 100.0
Action:      ALLOW            MONITOR           STEP_UP           RATE_LIMIT
Tier:        (LOW)           (MEDIUM)           (HIGH)            (CRITICAL)
```

---

## 6. Empirical Performance Benchmarks

Measured on $500$ sequential real-time event evaluations through the full processing pipeline (Feature calculation + Entropy evaluation + Rule execution + DB persistence):

| Metric | Target | Empirical Measured Value | Status |
|---|---|---|---|
| **Mean Latency** | $< 25\text{ ms}$ | **$10.06\text{ ms}$** | PASS |
| **P50 (Median) Latency** | $< 15\text{ ms}$ | **$8.66\text{ ms}$** | PASS |
| **P90 Latency** | $< 25\text{ ms}$ | **$17.05\text{ ms}$** | PASS |
| **P95 Latency** | $< 25\text{ ms}$ | **$21.54\text{ ms}$** | PASS |
| **P99 Latency** | $< 35\text{ ms}$ | **$29.41\text{ ms}$** | PASS |
| **Throughput** | $> 50\text{ eps}$ | **$99.4\text{ events/sec}$** | PASS |
