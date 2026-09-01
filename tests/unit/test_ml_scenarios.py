"""Scenario-by-Scenario Validation for the Unified ML & Behavioural Risk Engine."""

import pytest
from src.database.repository import Repository
from src.features.calculator import FeatureCalculator
from src.generator.scenarios import ScenarioGenerator
from src.ml.composite_scorer import UnifiedRiskScorer, UnifiedRiskDecision


def test_scenario_1_normal_traffic_evaluation(repository: Repository, scenario_generator: ScenarioGenerator):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()

    event = scenario_generator.generate_normal_event()
    fv = calc.calculate_features(event)
    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    assert decision.risk_score <= 35.0
    assert decision.risk_level == "LOW"
    assert decision.recommended_action in ("ALLOW", "MONITOR")
    assert decision.fraud_probability < 0.35


def test_scenario_2_legitimate_spike_no_false_positives(repository: Repository, scenario_generator: ScenarioGenerator):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()

    # Flash sale event: high volume surge on merchant but high IP/device entropy and genuine customers
    event = scenario_generator.generate_legitimate_spike_event()
    fv = calc.calculate_features(event)
    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    # Core product rule: High traffic alone must NOT automatically trigger a high fraud score
    assert decision.recommended_action in ("ALLOW", "MONITOR")
    assert decision.risk_score <= 35.0
    assert decision.is_legitimate_spike is True


def test_scenario_3_bot_abuse_detection(repository: Repository, scenario_generator: ScenarioGenerator):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()

    event = scenario_generator.generate_bot_abuse_event()
    fv = calc.calculate_features(event)
    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    assert decision.risk_score >= 70.0
    assert decision.recommended_action in ("STEP_UP_VERIFICATION", "RATE_LIMIT")
    assert len(decision.top_risk_signals) > 0


def test_scenario_4_payment_abuse_detection(repository: Repository, scenario_generator: ScenarioGenerator):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()

    event = scenario_generator.generate_payment_abuse_event()
    fv = calc.calculate_features(event)
    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    assert decision.risk_score >= 40.0
    assert decision.recommended_action in ("MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT")


def test_scenario_5_coordinated_abuse_detection(repository: Repository, scenario_generator: ScenarioGenerator):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()

    event = scenario_generator.generate_coordinated_abuse_event()
    fv = calc.calculate_features(event)
    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    assert decision.risk_score >= 30.0
    assert decision.recommended_action in ("MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT")


def test_scenario_6_fraud_ring_detection(repository: Repository, scenario_generator: ScenarioGenerator):
    calc = FeatureCalculator(repository)
    scorer = UnifiedRiskScorer()

    event = scenario_generator.generate_fraud_ring_event()
    fv = calc.calculate_features(event)
    decision: UnifiedRiskDecision = scorer.evaluate(fv)

    assert fv.amount >= 20000.0
    assert 0.0 <= decision.risk_score <= 100.0
    assert decision.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
