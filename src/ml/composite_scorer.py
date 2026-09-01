"""Unified Multi-Modal Risk Engine fusing ML, Anomaly, Velocity, Rules, and Graph Syndicates."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.core.config import settings
from src.features.calculator import FeatureVector
from src.engine.rules import RuleEngine, RuleResult
from src.ml.predict import MLInferenceService
from src.core.logging import get_logger

logger = get_logger("unified_risk_scorer")


class UnifiedRiskDecision(BaseModel):
    """Complete multi-signal risk assessment decision."""

    risk_score: float  # 0.0 to 100.0
    risk_level: str    # LOW, MEDIUM, HIGH, CRITICAL
    recommended_action: str  # ALLOW, MONITOR, STEP_UP_VERIFICATION, RATE_LIMIT

    fraud_probability: float  # XGBoost P(fraud)
    anomaly_score: float      # Isolation Forest S(iso)
    velocity_anomaly_score: float
    graph_risk_score: float = 0.0
    graph_risk_level: str = "LOW"
    cluster_id: str = "cluster_none"
    cluster_size: int = 1
    suspicious_entities: List[str] = Field(default_factory=list)
    graph_signals: List[str] = Field(default_factory=list)
    is_fraud_ring: bool = False
    is_legitimate_shared_infra: bool = False
    relationship_explanation: Optional[str] = None

    model_scores: Dict[str, float]
    triggered_rules: List[Dict[str, Any]]
    top_risk_signals: List[str]
    shap_feature_attributions: List[Dict[str, Any]]
    explanation: str

    primary_rule_triggered: Optional[str] = None
    is_legitimate_spike: bool = False
    is_suspicious_spike: bool = False


class UnifiedRiskScorer:
    """Fuses Supervised ML, Unsupervised Anomaly Detection, Velocity Signals,
    Heuristic Rules, and Multi-Entity Network Graph Syndicate Signals."""

    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
        ml_service: Optional[MLInferenceService] = None,
    ):
        self.rule_engine = rule_engine or RuleEngine()
        self.ml_service = ml_service or MLInferenceService()

    def evaluate(
        self,
        features: FeatureVector,
        graph_analyzer: Optional[Any] = None,
    ) -> UnifiedRiskDecision:
        """Evaluates an incoming FeatureVector across ML models, rules, and network graph."""
        # 1. Evaluate Rule Engine
        all_rules = self.rule_engine.evaluate_all_rules(features)
        triggered_rules = [r for r in all_rules if r.triggered]

        # 2. Run ML Inference (XGBoost + Isolation Forest + SHAP)
        ml_res = self.ml_service.predict_features(features)
        fraud_prob = ml_res["fraud_probability"]
        anomaly_score = ml_res["anomaly_score"]
        shap_data = ml_res.get("shap_explanation", {})

        # 3. Calculate Velocity Anomaly Component
        velocity_score = round(min(1.0, float(features.transaction_velocity) / 0.5), 3)

        # 4. Run Graph Network Analysis (if graph_analyzer provided)
        graph_score = 0.0
        graph_level = "LOW"
        cluster_id = "cluster_none"
        cluster_size = 1
        suspicious_entities = []
        graph_signals = []
        is_fraud_ring = False
        is_legitimate_shared_infra = False
        rel_explanation = None

        if graph_analyzer is not None:
            try:
                graph_res = graph_analyzer.analyze(
                    user_id=features.user_id,
                    device_id=features.device_id,
                    ip_address=features.ip_address,
                    card_hash=features.card_hash,
                )
                graph_score = graph_res.graph_risk_score
                graph_level = graph_res.graph_risk_level
                cluster_id = graph_res.cluster_id
                cluster_size = graph_res.cluster_size
                suspicious_entities = graph_res.suspicious_entities
                graph_signals = graph_res.graph_signals
                is_fraud_ring = graph_res.is_fraud_ring
                is_legitimate_shared_infra = graph_res.is_legitimate_shared_infra
                rel_explanation = graph_res.relationship_explanation
            except Exception as e:
                logger.warning("Graph analysis failed during evaluation: %s", e)

        # 5. Composite Scoring Fusion Formula
        if is_fraud_ring:
            # High-confidence syndicate ring: elevated graph weighting
            w_xgb = 0.35
            w_iso = 0.20
            w_vel = 0.15
            w_graph = 0.30
            base_ml_component = (w_xgb * fraud_prob + w_iso * anomaly_score + w_vel * velocity_score + w_graph * (graph_score / 100.0)) * 100.0
            # Ensure confirmed multi-hop fraud ring receives minimum score >= 68.0 (STEP_UP or RATE_LIMIT)
            base_ml_component = max(base_ml_component, 68.0)
        elif graph_score > 0.0:
            w_xgb = 0.40
            w_iso = 0.20
            w_vel = 0.15
            w_graph = 0.25
            base_ml_component = (w_xgb * fraud_prob + w_iso * anomaly_score + w_vel * velocity_score + w_graph * (graph_score / 100.0)) * 100.0
        else:
            w_xgb = 0.50
            w_iso = 0.25
            w_vel = 0.25
            base_ml_component = (w_xgb * fraud_prob + w_iso * anomaly_score + w_vel * velocity_score) * 100.0

        # Additive Rule Penalties & Flash Sale Discounts
        rule_penalty = sum(r.score_impact for r in triggered_rules)

        # Discount if verified legitimate shared infrastructure (campus NAT/VPN)
        if is_legitimate_shared_infra:
            rule_penalty -= 25.0

        raw_score = base_ml_component + rule_penalty

        # Legitimate shared infrastructure protection: cap at MONITOR max to prevent false step-ups
        if is_legitimate_shared_infra and not is_fraud_ring:
            raw_score = min(settings.THRESHOLD_MONITOR_MAX, raw_score)

        final_risk_score = round(max(0.0, min(100.0, raw_score)), 1)

        # 6. Assign Bounded Defensive Action
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

        # 7. Extract Top Risk Signals (Combining Rules, SHAP, and Graph)
        top_signals: List[str] = []
        for g_sig in graph_signals:
            top_signals.append(f"[Graph Syndicate] {g_sig}")

        for r in triggered_rules:
            if r.score_impact > 0:
                top_signals.append(f"[Rule Triggered] {r.rule_name} (+{r.score_impact:.0f} pts)")

        for b_point in shap_data.get("summary_bullet_points", [])[:2]:
            top_signals.append(f"[ML Driver] {b_point}")

        if not top_signals:
            top_signals.append("Clean topological neighborhood and normal request velocity.")

        # 8. Identify Primary Rule Triggered
        positive_rules = [r for r in triggered_rules if r.score_impact > 0]
        positive_rules.sort(key=lambda r: r.score_impact, reverse=True)
        primary_rule = positive_rules[0].rule_name if positive_rules else (graph_signals[0] if graph_signals else None)

        # 9. Build Grounded Explainable Text
        explanation = self._build_explanation(
            risk_score=final_risk_score,
            risk_level=risk_level,
            action=action,
            fraud_prob=fraud_prob,
            anomaly_score=anomaly_score,
            graph_score=graph_score,
            is_fraud_ring=is_fraud_ring,
            is_legitimate_shared_infra=is_legitimate_shared_infra,
            triggered_rules=triggered_rules,
            top_signals=top_signals,
            features=features,
            rel_explanation=rel_explanation,
        )

        return UnifiedRiskDecision(
            risk_score=final_risk_score,
            risk_level=risk_level,
            recommended_action=action,
            fraud_probability=fraud_prob,
            anomaly_score=anomaly_score,
            velocity_anomaly_score=velocity_score,
            graph_risk_score=graph_score,
            graph_risk_level=graph_level,
            cluster_id=cluster_id,
            cluster_size=cluster_size,
            suspicious_entities=suspicious_entities,
            graph_signals=graph_signals,
            is_fraud_ring=is_fraud_ring,
            is_legitimate_shared_infra=is_legitimate_shared_infra,
            relationship_explanation=rel_explanation,
            model_scores={
                "xgboost_fraud_prob": fraud_prob,
                "isolation_forest_anomaly": anomaly_score,
                "velocity_score": velocity_score,
                "graph_risk_score": graph_score,
                "rule_impact_points": rule_penalty,
            },
            triggered_rules=[r.model_dump() for r in triggered_rules],
            top_risk_signals=top_signals,
            shap_feature_attributions=shap_data.get("top_risk_drivers", []),
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
        fraud_prob: float,
        anomaly_score: float,
        graph_score: float,
        is_fraud_ring: bool,
        is_legitimate_shared_infra: bool,
        triggered_rules: List[RuleResult],
        top_signals: List[str],
        features: FeatureVector,
        rel_explanation: Optional[str] = None,
    ) -> str:
        """Constructs a factual, multi-modal risk explanation."""
        sections = [
            f"Unified Risk Score: {risk_score}/100 ({risk_level} Tier). Assigned Action: {action}."
        ]

        sections.append(
            f"Multi-Modal Scores: XGBoost Fraud Probability = {round(fraud_prob * 100, 1)}%, "
            f"Isolation Forest Anomaly Score = {round(anomaly_score * 100, 1)}%, "
            f"Network Graph Risk Score = {round(graph_score, 1)}/100."
        )

        if is_fraud_ring and rel_explanation:
            sections.append(f"Syndicate Alert: {rel_explanation}")
        elif is_legitimate_shared_infra and rel_explanation:
            sections.append(f"Infrastructure Clearance: {rel_explanation}")

        flash_rules = [r for r in triggered_rules if r.severity == "DISCOUNT"]
        if flash_rules:
            sections.append(
                f"Flash Sale Context: Traffic recognized as a high-entropy legitimate surge "
                f"(IP entropy: {features.merchant_ip_entropy}, Device entropy: {features.merchant_device_entropy})."
            )

        if top_signals:
            sections.append("Key Driving Signals:\n" + "\n".join(f"• {s}" for s in top_signals))

        return "\n\n".join(sections)
