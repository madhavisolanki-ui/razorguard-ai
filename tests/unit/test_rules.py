"""Unit Tests for Behavioural Rule Engine and Risk Scorer."""

import pytest
from src.features.calculator import FeatureVector
from src.engine.rules import RuleEngine
from src.engine.scorer import BehaviouralRiskScorer, RiskAssessmentResult


def test_rule_engine_clean_traffic():
    scorer = BehaviouralRiskScorer()

    clean_features = FeatureVector(
        event_id="evt_clean_01",
        user_id="usr_clean_01",
        merchant_id="mer_fashion",
        device_id="dev_clean_01",
        ip_address="49.37.10.1",
        amount=1499.00,
        checkout_duration_sec=15.0,
        user_requests_per_minute=1,
        user_requests_per_5_minutes=1,
        ip_requests_per_minute=1,
        ip_requests_per_5_minutes=1,
        device_requests_per_minute=1,
        device_requests_per_5_minutes=1,
        payment_failure_rate_5m=0.0,
        payment_success_rate_5m=1.0,
        unique_accounts_per_ip_1h=1,
        unique_devices_per_ip_1h=1,
        is_headless_device=False,
        is_datacenter_proxy=False,
        ip_reputation_score=1.0,
    )

    result: RiskAssessmentResult = scorer.evaluate_event(clean_features)

    assert result.risk_score <= 30.0
    assert result.risk_level == "LOW"
    assert result.recommended_action == "ALLOW"
    assert len(result.triggered_rules) == 0


def test_rule_engine_bot_abuse_trigger():
    scorer = BehaviouralRiskScorer()

    bot_features = FeatureVector(
        event_id="evt_bot_01",
        user_id="usr_bot_01",
        merchant_id="mer_electronics",
        device_id="dev_bot_01",
        ip_address="185.220.101.5",
        amount=1200.00,
        checkout_duration_sec=0.3,  # Sub-second checkout
        ip_requests_per_minute=25,  # High velocity burst
        payment_failure_rate_5m=0.75, # High decline rate
        is_headless_device=True,    # Headless browser
        is_datacenter_proxy=True,   # Proxy
        ip_reputation_score=0.20,
    )

    result: RiskAssessmentResult = scorer.evaluate_event(bot_features)

    assert result.risk_score >= 85.0
    assert result.risk_level == "CRITICAL"
    assert result.recommended_action == "RATE_LIMIT"

    rule_ids = [r.rule_id for r in result.triggered_rules]
    assert "R_BOT_SUB_SECOND_CHECKOUT" in rule_ids
    assert "R_VEL_IP_BURST" in rule_ids
    assert "R_THREAT_HEADLESS_BROWSER" in rule_ids


def test_rule_engine_legitimate_flash_sale_discount():
    scorer = BehaviouralRiskScorer()

    # Flash sale event: high merchant volume + high IP entropy + high success rate
    flash_sale_features = FeatureVector(
        event_id="evt_flash_01",
        user_id="usr_flash_01",
        merchant_id="mer_electronics_hub",
        device_id="dev_flash_01",
        ip_address="49.37.100.2",
        amount=49999.00,
        checkout_duration_sec=11.0,
        merchant_5m_volume=200,
        merchant_volume_multiplier=6.5,
        merchant_ip_entropy=0.92,
        merchant_device_entropy=0.91,
        payment_success_rate_5m=0.90,
        is_legitimate_spike_candidate=True,
        declared_flash_sale=True,
    )

    result: RiskAssessmentResult = scorer.evaluate_event(flash_sale_features)

    assert result.risk_score <= 30.0
    assert result.recommended_action == "ALLOW"
    assert result.is_legitimate_spike is True

    rule_ids = [r.rule_id for r in result.triggered_rules]
    assert "R_SPIKE_LEGITIMATE_FLASH_SALE_DISCOUNT" in rule_ids


def test_rule_engine_micro_card_testing():
    scorer = BehaviouralRiskScorer()

    carding_features = FeatureVector(
        event_id="evt_carding_01",
        user_id="usr_carder_01",
        merchant_id="mer_digital",
        device_id="dev_carder_01",
        ip_address="194.26.29.10",
        amount=5.00,  # Micro amount
        checkout_duration_sec=2.5,
        ip_requests_per_5_minutes=8,
        is_micro_transaction=True,
        payment_failure_rate_5m=0.80,
    )

    result: RiskAssessmentResult = scorer.evaluate_event(carding_features)

    assert result.risk_score >= 65.0
    rule_ids = [r.rule_id for r in result.triggered_rules]
    assert "R_PAT_MICRO_CARD_TESTING" in rule_ids
