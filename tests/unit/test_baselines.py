"""Unit Tests for Baseline Calculations and Entropy Evaluation."""

import pytest
from src.features.baselines import BaselineEvaluator


def test_shannon_entropy_diverse_vs_concentrated():
    # 1. High Diversity List (e.g. 50 distinct residential IPs)
    diverse_ips = [f"103.21.244.{i}" for i in range(50)]
    high_entropy = BaselineEvaluator.calculate_shannon_entropy(diverse_ips)
    assert high_entropy >= 0.90, f"Expected high entropy >= 0.90, got {high_entropy}"

    # 2. Concentrated Single IP Repeating (e.g. 50 requests from same IP)
    concentrated_ips = ["185.220.101.5"] * 50
    low_entropy = BaselineEvaluator.calculate_shannon_entropy(concentrated_ips)
    assert low_entropy == 0.0, f"Expected zero entropy, got {low_entropy}"

    # 3. Small Cluster (e.g. 2 IPs dominating)
    semi_concentrated = ["185.220.101.5"] * 45 + ["185.220.101.6"] * 5
    semi_entropy = BaselineEvaluator.calculate_shannon_entropy(semi_concentrated)
    assert semi_entropy < 0.35, f"Expected low entropy < 0.35, got {semi_entropy}"


def test_legitimate_flash_sale_spike_evaluation():
    # 10x traffic surge during flash sale with 100 diverse organic customers & high success rate
    diverse_ips = [f"49.37.{i // 10}.{i % 10}" for i in range(100)]
    diverse_devices = [f"dev_usr_canvas_{i}" for i in range(100)]

    result = BaselineEvaluator.evaluate_merchant_spike(
        merchant_id="mer_electronics_hub",
        merchant_category="electronics",
        current_5m_count=150,  # 5x normal baseline
        current_success_rate=0.88,  # Healthy authorization rate
        ip_list_5m=diverse_ips,
        device_list_5m=diverse_devices,
        declared_flash_sale=True,
    )

    assert result["is_volume_surge"] is True
    assert result["is_legitimate_spike"] is True
    assert result["is_suspicious_attack_surge"] is False
    assert result["spike_verdict"] == "LEGITIMATE_FLASH_SALE_SPIKE"
    assert result["ip_entropy"] >= 0.80


def test_suspicious_botnet_surge_evaluation():
    # 10x traffic surge from a proxy farm (low IP diversity + low payment success rate)
    botnet_ips = ["185.220.101.5"] * 80 + ["185.220.101.6"] * 20
    botnet_devices = ["dev_headless_farm_001"] * 100

    result = BaselineEvaluator.evaluate_merchant_spike(
        merchant_id="mer_electronics_hub",
        merchant_category="electronics",
        current_5m_count=150,
        current_success_rate=0.15,  # Low success rate / carding decline burst
        ip_list_5m=botnet_ips,
        device_list_5m=botnet_devices,
        declared_flash_sale=False,
    )

    assert result["is_volume_surge"] is True
    assert result["is_legitimate_spike"] is False
    assert result["is_suspicious_attack_surge"] is True
    assert result["spike_verdict"] == "SUSPICIOUS_ATTACK_SURGE"
