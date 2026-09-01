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


def dataframe_to_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Converts a tabular DataFrame (e.g. synthetic benchmark dataset) into X, y matrices."""
    # Ensure all required features exist or compute defaults
    feature_matrix = []

    for _, row in df.iterrows():
        amt = float(row.get("amount", 1000.0))
        dur = float(row.get("checkout_duration_sec", 12.0))
        is_micro = 1.0 if amt <= 50.0 else 0.0
        is_headless = 1.0 if bool(row.get("is_headless", False)) else 0.0
        is_emulator = 1.0 if bool(row.get("is_emulator", False)) else 0.0
        is_proxy = 1.0 if bool(row.get("is_datacenter_proxy", False)) else 0.0
        rep = float(row.get("ip_reputation", 1.0))
        is_flash = 1.0 if bool(row.get("is_flash_sale", False)) else 0.0

        # Scenario-specific contextual adjustments for synthetic training
        scenario = str(row.get("scenario", "normal"))
        if scenario == "bot_abuse":
            user_req_1m = 12.0
            ip_req_1m = 35.0
            ip_req_5m = 90.0
            fail_rate = 0.85
            success_rate = 0.15
            mult_acc_ip = 8.0
            rep_ratio = 0.80
            tx_vel = 0.58
            merch_mult = 3.0
            ip_entropy = 0.25
            dev_entropy = 0.20
        elif scenario == "payment_abuse":
            user_req_1m = 4.0
            ip_req_1m = 15.0
            ip_req_5m = 25.0
            fail_rate = 0.90
            success_rate = 0.10
            mult_acc_ip = 2.0
            rep_ratio = 0.95
            tx_vel = 0.25
            merch_mult = 1.2
            ip_entropy = 0.75
            dev_entropy = 0.70
        elif scenario == "coordinated_abuse":
            user_req_1m = 3.0
            ip_req_1m = 8.0
            ip_req_5m = 30.0
            fail_rate = 0.20
            success_rate = 0.80
            mult_acc_ip = 9.0  # High multi-account on proxy subnet
            rep_ratio = 0.75
            tx_vel = 0.15
            merch_mult = 2.5
            ip_entropy = 0.40
            dev_entropy = 0.10  # Shared canvas hash farm
        elif scenario == "fraud_ring":
            user_req_1m = 2.0
            ip_req_1m = 6.0
            ip_req_5m = 20.0
            fail_rate = 0.05
            success_rate = 0.95
            mult_acc_ip = 4.0
            rep_ratio = 0.40
            tx_vel = 0.10
            merch_mult = 2.0
            ip_entropy = 0.50
            dev_entropy = 0.35
        elif scenario == "legitimate_spike":
            user_req_1m = 1.0
            ip_req_1m = 2.0
            ip_req_5m = 4.0
            fail_rate = 0.12
            success_rate = 0.88
            mult_acc_ip = 1.0
            rep_ratio = 0.10
            tx_vel = 0.03
            merch_mult = 8.0  # 8x volume surge
            ip_entropy = 0.94 # High IP entropy
            dev_entropy = 0.92# High Device entropy
        else:  # normal
            user_req_1m = 1.0
            ip_req_1m = 1.0
            ip_req_5m = 2.0
            fail_rate = 0.06
            success_rate = 0.94
            mult_acc_ip = 1.0
            rep_ratio = 0.05
            tx_vel = 0.01
            merch_mult = 1.0
            ip_entropy = 0.95
            dev_entropy = 0.95

        vec = [
            amt,
            dur,
            user_req_1m,
            user_req_1m * 3.0,
            ip_req_1m,
            ip_req_5m,
            user_req_1m,
            user_req_1m * 2.5,
            tx_vel,
            fail_rate,
            success_rate,
            mult_acc_ip,
            mult_acc_ip,
            1.0,
            user_req_1m * 2.0,
            1.0, # amount_dev
            720.0, # account_age
            9999.0,# time_since_prev
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

    X = np.array(feature_matrix, dtype=np.float32)
    y = np.array(df["is_fraud_or_abuse"].values, dtype=np.int32)
    return X, y, ML_FEATURE_NAMES
