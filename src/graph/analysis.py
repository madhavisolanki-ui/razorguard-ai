"""Graph Risk Scoring and Network Analysis Service."""

from typing import Dict, Any, List, Optional
import networkx as nx
from pydantic import BaseModel, Field

from src.core.config import settings
from src.graph.features import GraphFeatures, GraphFeatureExtractor
from src.graph.detector import FraudRingDetector, RingDetectionResult
from src.core.logging import get_logger

logger = get_logger("graph_analyzer")


class GraphRiskResult(BaseModel):
    """Complete graph risk assessment containing numerical score, tier, and explainable cluster signals."""
    graph_risk_score: float = 0.0
    graph_risk_level: str = "LOW"
    cluster_id: str = "cluster_none"
    cluster_size: int = 1
    cluster_density: float = 0.0
    is_fraud_ring: bool = False
    is_legitimate_shared_infra: bool = False
    ring_type: Optional[str] = None
    suspicious_entities: List[str] = Field(default_factory=list)
    graph_signals: List[str] = Field(default_factory=list)
    mitigating_factors: List[str] = Field(default_factory=list)
    relationship_explanation: str = "Clean network topology."


class GraphRiskAnalyzer:
    """Calculates deterministic relational graph risk score and syndicate breakdown without double-counting."""

    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.feature_extractor = GraphFeatureExtractor(graph)
        self.detector = FraudRingDetector(graph)

    def analyze(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        card_hash: Optional[str] = None,
    ) -> GraphRiskResult:
        """Extracts relational features, detects fraud rings, and calculates calibrated 0-100 graph risk score."""
        features = self.feature_extractor.extract_features(
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            card_hash=card_hash,
        )

        detection = self.detector.detect(features)

        # -------------------------------------------------------------
        # Deterministic, Non-Redundant Graph Risk Scoring Formula
        # -------------------------------------------------------------
        # 1. Primary Syndicate Pattern Score (Max-pooled across pattern types)
        pattern_score = 0.0
        if detection.is_fraud_ring:
            if detection.ring_type == "MULTI_HOP_SYNDICATE_RING":
                pattern_score = 70.0
            elif detection.ring_type == "SHARED_PAYMENT_CARD_SYNDICATE":
                pattern_score = 65.0
            elif detection.ring_type == "DEVICE_FARM_SYNDICATE":
                pattern_score = 60.0
            elif detection.ring_type == "COORDINATED_PROXY_SWARM":
                pattern_score = 50.0
            else:
                pattern_score = 50.0

        # 2. Cluster Scale & Density Modifiers (Bounded: [0.0, 20.0])
        cluster_modifier = 0.0
        if detection.is_fraud_ring:
            if detection.cluster_size >= 6:
                cluster_modifier += 10.0
            elif detection.cluster_size >= 4:
                cluster_modifier += 5.0

            if detection.cluster_density >= 0.40:
                cluster_modifier += 10.0
            cluster_modifier = min(20.0, cluster_modifier)

        # 3. Non-Syndicate Topological Anomalies (Only if not already flagged as a full syndicate ring)
        anomaly_score = 0.0
        if not detection.is_fraud_ring:
            if features.shared_card_accounts > 1:
                anomaly_score += 20.0
            if features.shared_device_count >= 2:
                anomaly_score += 15.0
            if features.shared_ip_count >= 4 and not detection.is_legitimate_shared_infra:
                anomaly_score += 10.0
            if features.suspicious_neighbour_count >= 2:
                anomaly_score += 10.0
            anomaly_score = min(35.0, anomaly_score)

        # 4. Legitimate Shared Infrastructure Discount
        discount = 0.0
        if detection.is_legitimate_shared_infra:
            discount = 30.0

        # 5. Bounded Aggregation: Score = min(100.0, max(0.0, S_pattern + S_cluster + S_anomaly - S_discount))
        raw_score = pattern_score + cluster_modifier + anomaly_score - discount
        final_graph_score = round(max(0.0, min(100.0, raw_score)), 1)

        # Assign Risk Tier
        if final_graph_score <= settings.THRESHOLD_ALLOW_MAX:
            graph_risk_level = "LOW"
        elif final_graph_score <= settings.THRESHOLD_MONITOR_MAX:
            graph_risk_level = "MEDIUM"
        elif final_graph_score <= settings.THRESHOLD_STEP_UP_MAX:
            graph_risk_level = "HIGH"
        else:
            graph_risk_level = "CRITICAL"

        return GraphRiskResult(
            graph_risk_score=final_graph_score,
            graph_risk_level=graph_risk_level,
            cluster_id=detection.cluster_id,
            cluster_size=detection.cluster_size,
            cluster_density=detection.cluster_density,
            is_fraud_ring=detection.is_fraud_ring,
            is_legitimate_shared_infra=detection.is_legitimate_shared_infra,
            ring_type=detection.ring_type,
            suspicious_entities=detection.suspicious_entities,
            graph_signals=detection.triggered_graph_signals,
            mitigating_factors=detection.mitigating_factors,
            relationship_explanation=detection.explanation,
        )
