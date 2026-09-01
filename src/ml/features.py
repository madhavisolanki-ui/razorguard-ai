"""ML Feature Definitions, Extraction, and Schema Mapping."""

from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from src.features.calculator import FeatureVector

# Ordered list of numerical features fed to XGBoost and Isolation Forest
ML_FEATURE_NAMES: List[str] = [
    "amount",
    "checkout_duration_sec",
    "user_requests_per_minute",
    "user_requests_per_5_minutes",
    "ip_requests_per_minute",
    "ip_requests_per_5_minutes",
    "device_requests_per_minute",
    "device_requests_per_5_minutes",
    "transaction_velocity",
    "payment_failure_rate_5m",
    "payment_success_rate_5m",
    "unique_accounts_per_ip_1h",
    "unique_devices_per_ip_1h",
    "unique_ips_per_account_24h",
    "transactions_per_device_1h",
    "amount_deviation",
    "account_age_hours",
    "time_since_previous_transaction",
    "repeated_transaction_ratio",
    "is_micro_transaction",
    "is_headless_device",
    "is_emulator_device",
    "is_datacenter_proxy",
    "ip_reputation_score",
    "merchant_volume_multiplier",
    "merchant_ip_entropy",
    "merchant_device_entropy",
    "is_flash_sale",
]

# Human-readable feature descriptions for SHAP explainability
FEATURE_HUMAN_NAMES: Dict[str, str] = {
    "amount": "Transaction amount",
    "checkout_duration_sec": "Checkout duration speed",
    "user_requests_per_minute": "Account request rate (1 min)",
    "user_requests_per_5_minutes": "Account request volume (5 min)",
    "ip_requests_per_minute": "IP request velocity (1 min)",
    "ip_requests_per_5_minutes": "IP request volume (5 min)",
    "device_requests_per_minute": "Device request velocity (1 min)",
    "device_requests_per_5_minutes": "Device request volume (5 min)",
    "transaction_velocity": "High-frequency transaction velocity",
    "payment_failure_rate_5m": "Payment failure/decline rate (5 min)",
    "payment_success_rate_5m": "Payment authorization success rate",
    "unique_accounts_per_ip_1h": "Multi-account concentration on IP",
    "unique_devices_per_ip_1h": "Device concentration on IP",
    "unique_ips_per_account_24h": "IP hopping per account",
    "transactions_per_device_1h": "Device transaction volume",
    "amount_deviation": "Amount deviation from baseline",
    "account_age_hours": "Account tenure/age",
    "time_since_previous_transaction": "Time since last transaction",
    "repeated_transaction_ratio": "Repeated amount pattern ratio",
    "is_micro_transaction": "Micro-transaction carding signal",
    "is_headless_device": "Headless browser automation",
    "is_emulator_device": "Device emulator signature",
    "is_datacenter_proxy": "Datacenter/VPN proxy network",
    "ip_reputation_score": "IP threat reputation score",
    "merchant_volume_multiplier": "Merchant traffic surge multiplier",
    "merchant_ip_entropy": "Merchant IP diversity/entropy",
    "merchant_device_entropy": "Merchant device diversity/entropy",
    "is_flash_sale": "Flash sale merchant context",
}


def extract_feature_array(features: FeatureVector) -> np.ndarray:
    """Converts a production FeatureVector into a 1D numpy array matching ML_FEATURE_NAMES."""
    return np.array([
        float(features.amount),
        float(features.checkout_duration_sec),
        float(features.user_requests_per_minute),
        float(features.user_requests_per_5_minutes),
        float(features.ip_requests_per_minute),
        float(features.ip_requests_per_5_minutes),
        float(features.device_requests_per_minute),
        float(features.device_requests_per_5_minutes),
        float(features.transaction_velocity),
        float(features.payment_failure_rate_5m),
        float(features.payment_success_rate_5m),
        float(features.unique_accounts_per_ip_1h),
        float(features.unique_devices_per_ip_1h),
        float(features.unique_ips_per_account_24h),
        float(features.transactions_per_device_1h),
        float(features.amount_deviation),
        float(features.account_age_hours),
        float(features.time_since_previous_transaction),
        float(features.repeated_transaction_ratio),
        1.0 if features.is_micro_transaction else 0.0,
        1.0 if features.is_headless_device else 0.0,
        1.0 if features.is_emulator_device else 0.0,
        1.0 if features.is_datacenter_proxy else 0.0,
        float(features.ip_reputation_score),
        float(features.merchant_volume_multiplier),
        float(features.merchant_ip_entropy),
        float(features.merchant_device_entropy),
        1.0 if features.declared_flash_sale else 0.0,
    ], dtype=np.float32)


def dataframe_to_features(
    df: pd.DataFrame,
    inject_noise: bool = True,
    noise_rate: float = 0.025,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Converts a tabular DataFrame into X, y matrices with realistic continuous feature distributions,
    significant class overlap, and realistic borderline cases (e.g. fast legitimate checkouts, corporate NATs, stealth bots)."""
    np.random.seed(42)
    feature_matrix = []
    labels = []

    for _, row in df.iterrows():
        amt = float(row.get("amount", 1000.0))
        dur = float(row.get("checkout_duration_sec", 12.0))
        is_fraud = int(row.get("is_fraud_or_abuse", 0))
        scenario = str(row.get("scenario", "normal"))

        # Base device and network properties from row
        is_headless = 1.0 if bool(row.get("is_headless", False)) else 0.0
        is_emulator = 1.0 if bool(row.get("is_emulator", False)) else 0.0
        is_proxy = 1.0 if bool(row.get("is_datacenter_proxy", False)) else 0.0
        rep = float(row.get("ip_reputation", 1.0))
        is_flash = 1.0 if bool(row.get("is_flash_sale", False)) else 0.0

        # Continuous realistic feature synthesis with stochastic overlap
        if is_fraud == 1:
            # Fraudulent / Abuse Profiles (Botnets, Carding, Coordinated Proxies, Syndicates)
            # 25% of fraud uses stealth residential proxies with clean reputation and human speeds
            is_stealth = np.random.rand() < 0.25

            if is_stealth:
                dur = float(np.random.uniform(4.0, 16.0))  # Human-like delay
                user_req_1m = float(np.random.randint(1, 4))
                user_req_5m = float(np.random.randint(2, 6))
                ip_req_1m = float(np.random.randint(2, 8))
                ip_req_5m = float(np.random.randint(4, 15))
                fail_rate = float(np.random.uniform(0.15, 0.45))
                success_rate = 1.0 - fail_rate
                mult_acc_ip = float(np.random.randint(2, 6))
                rep_ratio = float(np.random.uniform(0.30, 0.65))
                tx_vel = float(ip_req_1m / 60.0)
                merch_mult = float(np.random.uniform(1.0, 3.0))
                ip_entropy = float(np.random.uniform(0.45, 0.75))
                dev_entropy = float(np.random.uniform(0.35, 0.65))
                if np.random.rand() < 0.7:
                    is_headless = 0.0
                    is_proxy = 0.0
                    rep = float(np.random.uniform(0.70, 0.95))
            else:
                # Overt aggressive abuse (High-speed bots, credential stuffing, micro-card testing)
                dur = float(np.random.uniform(0.2, 3.5))
                user_req_1m = float(np.random.randint(4, 20))
                user_req_5m = user_req_1m * float(np.random.uniform(2.0, 4.0))
                ip_req_1m = float(np.random.randint(12, 55))
                ip_req_5m = ip_req_1m * float(np.random.uniform(2.0, 4.0))
                fail_rate = float(np.random.uniform(0.55, 0.92))
                success_rate = 1.0 - fail_rate
                mult_acc_ip = float(np.random.randint(4, 16))
                rep_ratio = float(np.random.uniform(0.60, 0.95))
                tx_vel = float(ip_req_1m / 60.0)
                merch_mult = float(np.random.uniform(1.5, 4.5))
                ip_entropy = float(np.random.uniform(0.15, 0.45))
                dev_entropy = float(np.random.uniform(0.10, 0.35))

            amount_dev = float(np.random.uniform(1.2, 8.0))
            account_age = float(np.random.uniform(0.1, 48.0))  # Mostly fresh accounts
            time_since_prev = float(np.random.uniform(0.5, 45.0))  # Rapid succession

        else:
            # Legitimate Profiles (Normal Organic Shoppers + Flash Sale Buyers)
            # Realistic noise in legitimate traffic:
            # 12% shared NAT/college wifi, 10% corporate VPNs, 15% quick checkouts, 8% card retries
            is_corporate_or_campus = np.random.rand() < 0.12
            is_quick_buyer = np.random.rand() < 0.15
            has_failed_attempts = np.random.rand() < 0.08
            on_vpn = np.random.rand() < 0.10

            if is_quick_buyer:
                dur = float(np.random.uniform(2.5, 6.0))  # Quick saved-card 1-click buy
            else:
                dur = float(np.random.uniform(8.0, 45.0))

            if is_corporate_or_campus:
                mult_acc_ip = float(np.random.randint(3, 9))  # Shared NAT/public IP
                ip_req_1m = float(np.random.randint(2, 6))
                ip_req_5m = float(np.random.randint(5, 15))
            else:
                mult_acc_ip = 1.0
                ip_req_1m = float(np.random.randint(1, 3))
                ip_req_5m = float(np.random.randint(1, 5))

            user_req_1m = 1.0 if not has_failed_attempts else float(np.random.randint(2, 4))
            user_req_5m = user_req_1m * float(np.random.uniform(1.0, 2.0))

            fail_rate = float(np.random.uniform(0.20, 0.45)) if has_failed_attempts else float(np.random.uniform(0.0, 0.08))
            success_rate = 1.0 - fail_rate

            rep_ratio = float(np.random.uniform(0.0, 0.15))
            tx_vel = float(ip_req_1m / 60.0)

            if scenario == "legitimate_spike":
                merch_mult = float(np.random.uniform(3.5, 10.0))
                ip_entropy = float(np.random.uniform(0.80, 0.98))
                dev_entropy = float(np.random.uniform(0.80, 0.98))
            else:
                merch_mult = float(np.random.uniform(0.05, 1.8))
                ip_entropy = float(np.random.uniform(0.75, 1.0))
                dev_entropy = float(np.random.uniform(0.75, 1.0))

            if on_vpn:
                is_proxy = 1.0
                rep = float(np.random.uniform(0.55, 0.85))
            else:
                is_proxy = 0.0
                rep = float(np.random.uniform(0.85, 1.0))

            is_headless = 0.0
            is_emulator = 0.0
            amount_dev = float(np.random.uniform(0.6, 2.2))
            account_age = float(np.random.uniform(48.0, 5000.0))  # Established accounts
            time_since_prev = float(np.random.uniform(120.0, 25000.0))

        is_micro = 1.0 if amt <= 50.0 else 0.0

        # Inject 2.5% realistic ground truth label noise
        if inject_noise and np.random.rand() < noise_rate:
            final_label = 1 - is_fraud
        else:
            final_label = is_fraud

        vec = [
            amt,
            dur,
            user_req_1m,
            user_req_5m,
            ip_req_1m,
            ip_req_5m,
            user_req_1m,
            user_req_1m * 1.5,
            tx_vel,
            fail_rate,
            success_rate,
            mult_acc_ip,
            mult_acc_ip,
            1.0,
            user_req_1m,
            amount_dev,
            account_age,
            time_since_prev,
            rep_ratio,
            is_micro,
            is_headless,
            is_emulator,
            is_proxy,
            rep,
            merch_mult,
            ip_entropy,
            dev_entropy,
            is_flash,
        ]
        feature_matrix.append(vec)
        labels.append(final_label)

    X = np.array(feature_matrix, dtype=np.float32)
    y = np.array(labels, dtype=np.int32)
    return X, y, ML_FEATURE_NAMES
