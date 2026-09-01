"""Real-Time Feature Engineering and Feature Vector Assembly."""

import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.database.repository import Repository
from src.features.baselines import BaselineEvaluator
from src.core.logging import get_logger

logger = get_logger("feature_calculator")


class FeatureVector(BaseModel):
    """Calculated behavioural feature values for a single payment event."""

    # Event identification & basics
    event_id: str
    user_id: str
    merchant_id: str
    device_id: str
    ip_address: str
    amount: float
    checkout_duration_sec: float
    status: str = "SUCCESS"
    failure_code: Optional[str] = None

    # Request Velocities
    user_requests_per_minute: int = 1
    user_requests_per_5_minutes: int = 1
    ip_requests_per_minute: int = 1
    ip_requests_per_5_minutes: int = 1
    device_requests_per_minute: int = 1
    device_requests_per_5_minutes: int = 1
    transaction_velocity: float = 0.0  # requests per second in 1 minute

    # Success / Failure Rates (5-minute window)
    payment_failure_rate_5m: float = 0.0
    payment_success_rate_5m: float = 1.0

    # Entity Concentration & Network Graph Indicators
    unique_accounts_per_ip_1h: int = 1
    unique_devices_per_ip_1h: int = 1
    unique_ips_per_account_24h: int = 1
    transactions_per_device_1h: int = 1

    # Amount & Profile Baselines
    average_user_amount: float = 0.0
    amount_deviation: float = 1.0  # Current amount / user average
    account_age_hours: float = 24.0
    account_age_days: float = 1.0
    time_since_previous_transaction: float = 9999.0  # seconds

    # Pattern & Repetition Indicators
    repeated_transaction_ratio: float = 0.0  # repeated amounts in 5m
    is_micro_transaction: bool = False

    # Device & Network Threat Signals
    is_headless_device: bool = False
    is_emulator_device: bool = False
    is_datacenter_proxy: bool = False
    ip_reputation_score: float = 1.0

    # Merchant & Spike Baseline Signals
    merchant_5m_volume: int = 1
    merchant_volume_multiplier: float = 1.0
    merchant_ip_entropy: float = 1.0
    merchant_device_entropy: float = 1.0
    is_legitimate_spike_candidate: bool = False
    is_suspicious_spike_candidate: bool = False
    declared_flash_sale: bool = False


class FeatureCalculator:
    """Extracts and computes real-time behavioral features from incoming event payloads and repository history."""

    def __init__(self, repository: Repository):
        self.repo = repository

    def calculate_features(self, event: Dict[str, Any]) -> FeatureVector:
        """Calculates real-time features for an incoming payment event dictionary."""
        import uuid
        event_id = event.get("event_id") or f"evt_{uuid.uuid4().hex[:12]}"
        user_id = event.get("user_id") or "usr_unknown"
        merchant_id = event.get("merchant_id") or "mer_unknown"
        amount = float(event.get("amount", 0.0))

        # Device & IP details
        device_data = event.get("device", {})
        device_id = device_data.get("id") or device_data.get("device_id") or "dev_unknown"
        is_headless = bool(device_data.get("is_headless", False))
        is_emulator = bool(device_data.get("is_emulator", False))

        network_data = event.get("network", {})
        ip_address = network_data.get("ip") or network_data.get("ip_address") or "127.0.0.1"
        is_proxy = bool(network_data.get("is_datacenter_proxy", False) or network_data.get("vpn_detected", False))
        ip_reputation = float(network_data.get("reputation_score", network_data.get("ip_reputation", 1.0)))

        context_data = event.get("context", {})
        checkout_duration = float(context_data.get("checkout_duration_sec", 12.0))
        is_flash_sale = bool(context_data.get("is_flash_sale", False))

        # -------------------------------------------------------------
        # 1. Historical & Sliding Window Database Lookups
        # -------------------------------------------------------------
        user = self.repo.get_user(user_id)
        merchant = self.repo.get_merchant(merchant_id)

        # Account age calculation
        account_age_hours = 720.0  # default 30 days
        if user and user.created_at:
            delta = datetime.datetime.now(datetime.timezone.utc) - user.created_at.replace(tzinfo=datetime.timezone.utc)
            account_age_hours = max(0.1, delta.total_seconds() / 3600.0)

        # Time since previous transaction
        prev_tx = self.repo.get_previous_user_transaction(user_id)
        time_since_prev = 9999.0
        if prev_tx and prev_tx.event_time:
            delta = datetime.datetime.now(datetime.timezone.utc) - prev_tx.event_time.replace(tzinfo=datetime.timezone.utc)
            time_since_prev = max(0.1, delta.total_seconds())

        # Sliding window velocities (60s and 300s)
        # Note: We add +1 to account for the current in-flight transaction
        user_req_1m = self.repo.get_user_tx_count_in_window(user_id, window_seconds=60) + 1
        user_req_5m = self.repo.get_user_tx_count_in_window(user_id, window_seconds=300) + 1

        ip_req_1m = self.repo.get_ip_tx_count_in_window(ip_address, window_seconds=60) + 1
        ip_req_5m = self.repo.get_ip_tx_count_in_window(ip_address, window_seconds=300) + 1

        device_req_1m = self.repo.get_device_tx_count_in_window(device_id, window_seconds=60) + 1
        device_req_5m = self.repo.get_device_tx_count_in_window(device_id, window_seconds=300) + 1

        tx_velocity = round(float(ip_req_1m) / 60.0, 3)

        # -------------------------------------------------------------
        # 2. Success / Failure Rates & Repetition on IP / User
        # -------------------------------------------------------------
        ip_txs_5m = self.repo.get_ip_txs_in_window(ip_address, window_seconds=300)
        total_ip_5m = len(ip_txs_5m) + 1
        failed_ip_5m = sum(1 for t in ip_txs_5m if t.status != "SUCCESS")
        if event.get("status") and event.get("status") != "SUCCESS":
            failed_ip_5m += 1

        ip_fail_rate = round(float(failed_ip_5m) / max(1, total_ip_5m), 3)
        ip_success_rate = round(1.0 - ip_fail_rate, 3)

        # Repeated amounts ratio in 5m
        amounts_in_5m = [t.amount for t in ip_txs_5m] + [amount]
        same_amount_count = sum(1 for a in amounts_in_5m if abs(a - amount) < 0.01)
        repeated_ratio = round(float(same_amount_count) / max(1, len(amounts_in_5m)), 3)

        # -------------------------------------------------------------
        # 3. Entity Concentration Metrics
        # -------------------------------------------------------------
        unique_accounts_ip_1h = max(1, self.repo.get_unique_accounts_per_ip(ip_address, window_seconds=3600))
        unique_devices_ip_1h = max(1, self.repo.get_unique_devices_per_ip(ip_address, window_seconds=3600))
        unique_ips_user_24h = max(1, self.repo.get_unique_ips_per_account(user_id, window_seconds=86400))
        txs_device_1h = self.repo.get_device_tx_count_in_window(device_id, window_seconds=3600) + 1

        # -------------------------------------------------------------
        # 4. Amount Deviations & User Baselines
        # -------------------------------------------------------------
        user_stats = self.repo.get_user_historical_stats(user_id)
        user_avg = user_stats["average_amount"] if user_stats["total_transactions"] > 0 else amount
        if user_avg <= 0:
            user_avg = amount if amount > 0 else 1000.0

        amount_dev = round(float(amount / user_avg), 2) if user_avg > 0 else 1.0
        is_micro_tx = amount <= 50.0

        # -------------------------------------------------------------
        # 5. Merchant Baselines & Traffic Spike Evaluation
        # -------------------------------------------------------------
        merchant_cat = merchant.category if merchant else "ecommerce"
        merchant_txs_5m = self.repo.get_merchant_txs_in_window(merchant_id, window_seconds=300)
        merchant_5m_count = len(merchant_txs_5m) + 1

        ips_in_merchant_window = [t.ip_address for t in merchant_txs_5m if t.ip_address] + [ip_address]
        devices_in_merchant_window = [t.device_id for t in merchant_txs_5m if t.device_id] + [device_id]

        spike_eval = BaselineEvaluator.evaluate_merchant_spike(
            merchant_id=merchant_id,
            merchant_category=merchant_cat,
            current_5m_count=merchant_5m_count,
            current_success_rate=ip_success_rate,
            ip_list_5m=ips_in_merchant_window,
            device_list_5m=devices_in_merchant_window,
            declared_flash_sale=is_flash_sale,
        )

        return FeatureVector(
            event_id=event_id,
            user_id=user_id,
            merchant_id=merchant_id,
            device_id=device_id,
            ip_address=ip_address,
            amount=amount,
            checkout_duration_sec=checkout_duration,
            status=event.get("status", "SUCCESS"),
            failure_code=event.get("failure_code"),
            user_requests_per_minute=user_req_1m,
            user_requests_per_5_minutes=user_req_5m,
            ip_requests_per_minute=ip_req_1m,
            ip_requests_per_5_minutes=ip_req_5m,
            device_requests_per_minute=device_req_1m,
            device_requests_per_5_minutes=device_req_5m,
            transaction_velocity=tx_velocity,
            payment_failure_rate_5m=ip_fail_rate,
            payment_success_rate_5m=ip_success_rate,
            unique_accounts_per_ip_1h=unique_accounts_ip_1h,
            unique_devices_per_ip_1h=unique_devices_ip_1h,
            unique_ips_per_account_24h=unique_ips_user_24h,
            transactions_per_device_1h=txs_device_1h,
            average_user_amount=round(user_avg, 2),
            amount_deviation=amount_dev,
            account_age_hours=round(account_age_hours, 1),
            account_age_days=round(account_age_hours / 24.0, 1),
            time_since_previous_transaction=round(time_since_prev, 1),
            repeated_transaction_ratio=repeated_ratio,
            is_micro_transaction=is_micro_tx,
            is_headless_device=is_headless,
            is_emulator_device=is_emulator,
            is_datacenter_proxy=is_proxy,
            ip_reputation_score=ip_reputation,
            merchant_5m_volume=merchant_5m_count,
            merchant_volume_multiplier=spike_eval["volume_multiplier"],
            merchant_ip_entropy=spike_eval["ip_entropy"],
            merchant_device_entropy=spike_eval["device_entropy"],
            is_legitimate_spike_candidate=spike_eval["is_legitimate_spike"],
            is_suspicious_spike_candidate=spike_eval["is_suspicious_attack_surge"],
            declared_flash_sale=is_flash_sale,
        )
