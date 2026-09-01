"""Unit Tests for Real-Time Feature Calculation."""

import datetime
from src.database.repository import Repository
from src.features.calculator import FeatureCalculator, FeatureVector


def test_feature_calculator_normal_event(repository: Repository):
    calculator = FeatureCalculator(repository)

    # Seed baseline merchant & user
    repository.get_or_create_merchant("mer_fashion", name="Fashion House", category="fashion")
    repository.get_or_create_user("usr_fresh_01", email="fresh@example.com")

    event = {
        "event_id": "evt_feat_001",
        "user_id": "usr_fresh_01",
        "merchant_id": "mer_fashion",
        "amount": 1299.00,
        "currency": "INR",
        "payment_method": "credit_card",
        "status": "SUCCESS",
        "device": {
            "id": "dev_normal_01",
            "is_headless": False,
            "is_emulator": False,
        },
        "network": {
            "ip": "49.37.10.1",
            "is_datacenter_proxy": False,
            "reputation_score": 0.95,
        },
        "context": {
            "checkout_duration_sec": 14.5,
            "is_flash_sale": False,
        }
    }

    fv: FeatureVector = calculator.calculate_features(event)

    assert fv.event_id == "evt_feat_001"
    assert fv.amount == 1299.00
    assert fv.user_requests_per_minute == 1
    assert fv.ip_requests_per_minute == 1
    assert fv.payment_failure_rate_5m == 0.0
    assert fv.payment_success_rate_5m == 1.0
    assert fv.is_headless_device is False
    assert fv.is_micro_transaction is False
    assert fv.checkout_duration_sec == 14.5


def test_feature_calculator_velocity_and_failures(repository: Repository):
    calculator = FeatureCalculator(repository)

    user_id = "usr_burst_01"
    ip_addr = "185.220.101.5"
    dev_id = "dev_burst_01"
    merchant_id = "mer_digital"

    repository.get_or_create_user(user_id)
    repository.get_or_create_merchant(merchant_id, category="digital_goods")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Insert 4 historical transactions in the last 30s with failures
    for i in range(4):
        repository.create_transaction({
            "id": f"tx_hist_fail_{i}",
            "event_time": now - datetime.timedelta(seconds=i * 5),
            "user_id": user_id,
            "merchant_id": merchant_id,
            "device_id": dev_id,
            "ip_address": ip_addr,
            "amount": 25.00,  # Micro transaction
            "status": "FAILED" if i < 3 else "SUCCESS",
            "failure_code": "INCORRECT_CVV",
        })

    # Calculate features for 5th incoming transaction
    incoming_event = {
        "event_id": "evt_burst_05",
        "user_id": user_id,
        "merchant_id": merchant_id,
        "amount": 25.00,
        "status": "FAILED",
        "device": {"id": dev_id, "is_headless": True},
        "network": {"ip": ip_addr, "is_datacenter_proxy": True, "reputation_score": 0.20},
        "context": {"checkout_duration_sec": 0.4, "is_flash_sale": False},
    }

    fv: FeatureVector = calculator.calculate_features(incoming_event)

    # 4 existing + 1 current = 5
    assert fv.user_requests_per_minute == 5
    assert fv.ip_requests_per_minute == 5
    assert fv.is_micro_transaction is True
    assert fv.is_headless_device is True
    assert fv.is_datacenter_proxy is True
    assert fv.checkout_duration_sec < 1.0
    assert fv.payment_failure_rate_5m >= 0.70  # High failure rate
    assert fv.repeated_transaction_ratio == 1.0  # All 5 transactions are 25.00 INR
