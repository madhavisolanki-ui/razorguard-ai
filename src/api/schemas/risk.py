"""Pydantic Schemas for Risk Analysis Endpoints."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from src.api.schemas.events import PaymentEventInput


class RiskAnalysisRequest(PaymentEventInput):
    """Dry-run risk analysis request payload."""
    pass


class RiskAnalysisResponse(BaseModel):
    """On-the-fly dry-run risk evaluation response with full feature vector."""

    risk_score: float
    risk_level: str
    recommended_action: str
    fraud_probability: Optional[float] = None
    anomaly_score: Optional[float] = None
    graph_risk_score: Optional[float] = None
    graph_risk_level: Optional[str] = None
    cluster_id: Optional[str] = None
    cluster_size: Optional[int] = None
    suspicious_entities: List[str] = Field(default_factory=list)
    graph_signals: List[str] = Field(default_factory=list)
    is_fraud_ring: bool = False
    is_legitimate_shared_infra: bool = False
    model_scores: Optional[Dict[str, float]] = None
    primary_rule_triggered: Optional[str] = None
    triggered_rules: List[Dict[str, Any]] = Field(default_factory=list)
    top_risk_signals: List[str] = Field(default_factory=list)
    shap_feature_attributions: List[Dict[str, Any]] = Field(default_factory=list)
    feature_values: Dict[str, Any]
    explanation: str
    is_legitimate_spike: bool = False
    is_suspicious_spike: bool = False
    latency_ms: int
    dry_run: bool = True


class StoredRiskAssessmentResponse(BaseModel):
    """Historical stored transaction and risk assessment details."""

    transaction_id: str
    event_time: str
    user_id: str
    merchant_id: str
    amount: float
    currency: str
    status: str
    failure_code: Optional[str] = None
    composite_risk_score: float
    risk_tier: str
    fast_action: str
    xgboost_score: Optional[float] = None
    iforest_score: Optional[float] = None
    velocity_score: Optional[float] = None
    graph_score: Optional[float] = None
    primary_rule_triggered: Optional[str] = None
    latency_ms: int
