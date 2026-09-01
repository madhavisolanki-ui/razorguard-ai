"""LangGraph Investigation State Definition for RazorGuard AI."""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
import operator


class InvestigationState(TypedDict):
    """Mutable typed state passed between LangGraph nodes during an AI investigation."""

    # 1. Target Transaction & Entity Identification
    transaction_id: str
    user_id: str
    merchant_id: str
    device_id: str
    ip_address: str
    card_hash: Optional[str]
    amount: float
    currency: str
    payment_method: str
    event_time: str
    status: str
    failure_code: Optional[str]

    # 2. Immutable Deterministic Assessment Inputs (Phase 2-4 Truth)
    individual_risk_score: float
    graph_risk_score: float
    unified_risk_score: float
    risk_level: str
    fraud_probability: float
    anomaly_score: float
    velocity_score: float
    fast_action: str
    primary_rule_triggered: Optional[str]
    triggered_rules: List[Dict[str, Any]]
    shap_signals: List[Dict[str, Any]]
    top_risk_signals: List[str]

    # 3. Graph & Syndicate Deterministic Inputs
    graph_signals: List[str]
    suspicious_entities: List[str]
    cluster_id: Optional[str]
    cluster_size: Optional[int]
    cluster_density: Optional[float]
    is_fraud_ring: bool
    is_legitimate_shared_infra: bool
    relationship_explanation: Optional[str]

    # 4. Agent Dynamic Investigation Workspace
    investigation_id: str
    risk_category: str  # "LOW_RISK", "BEHAVIOURAL_ABUSE", "NETWORK_SYNDICATE", "AMBIGUOUS_SPIKE"
    planned_tools: List[str]
    tool_calls_executed: Annotated[List[Dict[str, Any]], operator.add]
    tool_results: Dict[str, Any]
    
    # 5. Synthesis & Findings
    key_evidence: List[str]
    investigation_findings: List[str]
    related_entities: List[str]
    hypothesis_verdict: str  # "LEGITIMATE_ACTIVITY", "SUSPICIOUS_BEHAVIOUR", "COORDINATED_SYNDICATE", "BENIGN_SPIKE"
    
    # 6. Final Decision & Explanation
    recommended_action: str  # Bounded: ALLOW, MONITOR, STEP_UP_VERIFICATION, RATE_LIMIT
    confidence: float
    explanation: str
    investigation_status: str  # "COMPLETED", "FALLBACK_DETERMINISTIC", "FAILED"
    investigation_path: Annotated[List[str], operator.add]
    is_fallback: bool
    analyst_notes: Optional[str]
