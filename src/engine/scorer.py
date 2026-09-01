"""Preliminary Behavioural Risk Scorer and Decision Logic."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.core.config import settings
from src.features.calculator import FeatureVector
from src.engine.rules import RuleResult, RuleEngine
from src.core.logging import get_logger

logger = get_logger("risk_scorer")


class RiskAssessmentResult(BaseModel):
    """Complete structured risk assessment output for an incoming payment event."""

    risk_score: float  # 0.0 to 100.0
    risk_level: str    # LOW, MEDIUM, HIGH, CRITICAL
    recommended_action: str  # ALLOW, MONITOR, STEP_UP_VERIFICATION, RATE_LIMIT
    triggered_rules: List[RuleResult]
    feature_values: Dict[str, Any]
    explanation: str
    primary_rule_triggered: Optional[str] = None
    is_legitimate_spike: bool = False
    is_suspicious_spike: bool = False


class BehaviouralRiskScorer:
    """Calculates quantitative risk score and assigns bounded defensive actions based on rule evaluations."""

    def __init__(self, rule_engine: Optional[RuleEngine] = None):
        self.rule_engine = rule_engine or RuleEngine()

    def evaluate_event(self, features: FeatureVector) -> RiskAssessmentResult:
        """Evaluates features through rules and computes the preliminary behavioural risk score."""
        all_rules = self.rule_engine.evaluate_all_rules(features)
        triggered_rules = [r for r in all_rules if r.triggered]

        # Base organic risk baseline: 5.0
        base_score = 5.0

        # Calculate sum of score impacts (including negative discounts for legitimate flash sales)
        total_impact = sum(r.score_impact for r in triggered_rules)
        raw_score = base_score + total_impact

        # Clamp score to [0.0, 100.0]
        final_risk_score = round(max(0.0, min(100.0, raw_score)), 1)

        # Determine Risk Level & Bounded Action based on centralized thresholds
        if final_risk_score <= settings.THRESHOLD_ALLOW_MAX:
            risk_level = "LOW"
            action = "ALLOW"
        elif final_risk_score <= settings.THRESHOLD_MONITOR_MAX:
            risk_level = "MEDIUM"
            action = "MONITOR"
        elif final_risk_score <= settings.THRESHOLD_STEP_UP_MAX:
            risk_level = "HIGH"
            action = "STEP_UP_VERIFICATION"
        else:
            risk_level = "CRITICAL"
            action = "RATE_LIMIT"

        # Determine primary rule triggered (highest positive impact)
        positive_rules = [r for r in triggered_rules if r.score_impact > 0]
        positive_rules.sort(key=lambda r: r.score_impact, reverse=True)
        primary_rule = positive_rules[0].rule_name if positive_rules else None

        # Build transparent explanation
        explanation = self._build_explanation(
            risk_score=final_risk_score,
            risk_level=risk_level,
            action=action,
            triggered_rules=triggered_rules,
            features=features,
        )

        return RiskAssessmentResult(
            risk_score=final_risk_score,
            risk_level=risk_level,
            recommended_action=action,
            triggered_rules=triggered_rules,
            feature_values=features.model_dump(),
            explanation=explanation,
            primary_rule_triggered=primary_rule,
            is_legitimate_spike=features.is_legitimate_spike_candidate,
            is_suspicious_spike=features.is_suspicious_spike_candidate,
        )

    def _build_explanation(
        self,
        risk_score: float,
        risk_level: str,
        action: str,
        triggered_rules: List[RuleResult],
        features: FeatureVector,
    ) -> str:
        """Constructs a clean, human-readable justification of the assessment."""
        parts = [
            f"Preliminary Behavioural Risk Score: {risk_score}/100 ({risk_level} Risk). Recommended Action: {action}."
        ]

        if not triggered_rules:
            parts.append("No abnormal velocity, device, or network anomalies detected. Traffic matches organic baseline.")
            return " ".join(parts)

        # Highlight flash sale discount if present
        flash_discounts = [r for r in triggered_rules if r.severity == "DISCOUNT"]
        if flash_discounts:
            parts.append(
                f"Merchant volume surge recognized as a legitimate flash sale with high IP entropy "
                f"({features.merchant_ip_entropy}) and healthy success rate ({round(features.payment_success_rate_5m * 100, 1)}%). "
                f"Legitimacy discount applied."
            )

        # Highlight high-severity triggers
        threat_rules = [r for r in triggered_rules if r.score_impact > 0]
        if threat_rules:
            rule_summaries = [f"• [{r.severity}] {r.rule_name}: {r.description}" for r in threat_rules]
            parts.append("Key Risk Drivers:\n" + "\n".join(rule_summaries))

        return "\n\n".join(parts)
