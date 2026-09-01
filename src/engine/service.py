"""Real-Time Event Processing Service with ML, Behavioural Fusion, and Graph Syndicates."""

import datetime
import time
import uuid
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from src.database.models import Transaction, RiskAssessment
from src.database.repository import Repository
from src.features.calculator import FeatureCalculator, FeatureVector
from src.ml.composite_scorer import UnifiedRiskScorer, UnifiedRiskDecision
from src.graph.builder import FraudGraphBuilder
from src.graph.analysis import GraphRiskAnalyzer
from src.core.logging import get_logger

logger = get_logger("event_service")

# Global singleton in-memory graph builder & analyzer for continuous stream ingestion
_GLOBAL_GRAPH_BUILDER = FraudGraphBuilder()
_GLOBAL_GRAPH_ANALYZER = GraphRiskAnalyzer(_GLOBAL_GRAPH_BUILDER.graph)


def get_global_graph_builder() -> FraudGraphBuilder:
    return _GLOBAL_GRAPH_BUILDER


def get_global_graph_analyzer() -> GraphRiskAnalyzer:
    return _GLOBAL_GRAPH_ANALYZER


class EventProcessingService:
    """Orchestrates real-time event ingestion, feature extraction, ML inference,
    multi-entity graph syndicate detection, rules, and persistence."""

    def __init__(
        self,
        db: Session,
        graph_builder: Optional[FraudGraphBuilder] = None,
        graph_analyzer: Optional[GraphRiskAnalyzer] = None,
    ):
        self.db = db
        self.repo = Repository(db)
        self.calculator = FeatureCalculator(self.repo)
        self.unified_scorer = UnifiedRiskScorer()
        self.graph_builder = graph_builder or _GLOBAL_GRAPH_BUILDER
        self.graph_analyzer = graph_analyzer or GraphRiskAnalyzer(self.graph_builder.graph)

    def process_event(
        self,
        event: Dict[str, Any],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Processes an incoming payment event through features, ML, graph syndicates, rules, and scoring."""
        start_time = time.perf_counter()

        event_id = event.get("event_id") or f"evt_{uuid.uuid4().hex[:16]}"
        user_id = event.get("user_id", "usr_anonymous")
        merchant_id = event.get("merchant_id", "mer_electronics_hub")
        amount = float(event.get("amount", 0.0))
        currency = event.get("currency", "INR")
        payment_method = event.get("payment_method", "credit_card")
        status = event.get("status", "SUCCESS")
        failure_code = event.get("failure_code")

        # Extract nested structures
        device_data = event.get("device", {})
        device_id = device_data.get("id") or device_data.get("device_id") or f"dev_{uuid.uuid4().hex[:8]}"
        user_agent = device_data.get("user_agent")
        device_os = device_data.get("os") or device_data.get("device_os")
        browser = device_data.get("browser") or device_data.get("device_browser")
        is_headless = bool(device_data.get("is_headless", False))
        is_emulator = bool(device_data.get("is_emulator", False))
        canvas_hash = device_data.get("canvas_hash")

        network_data = event.get("network", {})
        ip_address = network_data.get("ip") or network_data.get("ip_address") or "127.0.0.1"
        country = network_data.get("country") or network_data.get("ip_country") or "IN"
        isp = network_data.get("isp") or network_data.get("ip_isp")
        asn = network_data.get("asn") or network_data.get("ip_asn")
        is_proxy = bool(network_data.get("is_datacenter_proxy", False) or network_data.get("vpn_detected", False))
        reputation = float(network_data.get("reputation_score", network_data.get("ip_reputation", 1.0)))

        card_data = event.get("card", {})
        card_bin = card_data.get("bin") or event.get("card_bin")
        card_last4 = card_data.get("last4") or event.get("card_last4")
        card_hash = card_data.get("card_hash") or event.get("card_hash")
        bank_code = card_data.get("issuer_bank") or event.get("bank_code")

        context_data = event.get("context", {})
        checkout_duration = float(context_data.get("checkout_duration_sec", 12.0))
        is_flash_sale = bool(context_data.get("is_flash_sale", False))
        scenario_tag = event.get("scenario", "normal")

        # -------------------------------------------------------------
        # 1. Register / Update Entity Records (if not dry_run)
        # -------------------------------------------------------------
        if not dry_run:
            self.repo.get_or_create_user(user_id=user_id)
            self.repo.get_or_create_merchant(merchant_id=merchant_id)
            self.repo.get_or_create_device(
                device_id=device_id,
                user_agent=user_agent,
                os_name=device_os,
                browser=browser,
                is_headless=is_headless,
                is_emulator=is_emulator,
                canvas_hash=canvas_hash,
            )
            self.repo.get_or_create_ip(
                ip=ip_address,
                country=country,
                isp=isp,
                asn=asn,
                is_datacenter_proxy=is_proxy,
                reputation_score=reputation,
            )

        # -------------------------------------------------------------
        # 2. Real-Time Feature Calculation & Unified ML + Graph Evaluation
        # -------------------------------------------------------------
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"

        # Incrementally register entities into graph for real-time neighborhood analysis
        self.graph_builder.add_event(
            event=event,
            transaction_id=tx_id,
            risk_score=0.0,
        )

        features: FeatureVector = self.calculator.calculate_features(event)
        decision: UnifiedRiskDecision = self.unified_scorer.evaluate(
            features=features,
            graph_analyzer=self.graph_analyzer,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # -------------------------------------------------------------
        # 3. Persistence (if not dry_run)
        # -------------------------------------------------------------
        if not dry_run:

            tx = self.repo.create_transaction({
                "id": tx_id,
                "event_time": datetime.datetime.now(datetime.timezone.utc),
                "user_id": user_id,
                "merchant_id": merchant_id,
                "device_id": device_id,
                "ip_address": ip_address,
                "amount": amount,
                "currency": currency,
                "payment_method": payment_method,
                "card_bin": card_bin,
                "card_last4": card_last4,
                "card_hash": card_hash,
                "bank_code": bank_code,
                "status": status,
                "failure_code": failure_code,
                "checkout_duration_sec": checkout_duration,
                "is_flash_sale": is_flash_sale,
                "scenario_tag": scenario_tag,
            })

            self.repo.create_risk_assessment({
                "id": f"risk_{uuid.uuid4().hex[:12]}",
                "transaction_id": tx.id,
                "assessed_at": datetime.datetime.now(datetime.timezone.utc),
                "composite_risk_score": decision.risk_score,
                "risk_tier": decision.risk_level,
                "xgboost_score": decision.fraud_probability,
                "iforest_score": decision.anomaly_score,
                "velocity_score": decision.velocity_anomaly_score,
                "graph_score": decision.graph_risk_score,
                "primary_rule_triggered": decision.primary_rule_triggered,
                "fast_action": decision.recommended_action,
                "latency_ms": elapsed_ms,
            })

        logger.debug(
            "Processed event %s (tx: %s): score=%.1f, level=%s, action=%s, graph_score=%.1f in %dms",
            event_id, tx_id, decision.risk_score, decision.risk_level, decision.recommended_action, decision.graph_risk_score, elapsed_ms
        )

        return {
            "transaction_id": tx_id,
            "event_id": event_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "amount": amount,
            "currency": currency,
            "risk_score": decision.risk_score,
            "risk_level": decision.risk_level,
            "recommended_action": decision.recommended_action,
            "fraud_probability": decision.fraud_probability,
            "anomaly_score": decision.anomaly_score,
            "graph_risk_score": decision.graph_risk_score,
            "graph_risk_level": decision.graph_risk_level,
            "cluster_id": decision.cluster_id,
            "cluster_size": decision.cluster_size,
            "suspicious_entities": decision.suspicious_entities,
            "graph_signals": decision.graph_signals,
            "is_fraud_ring": decision.is_fraud_ring,
            "is_legitimate_shared_infra": decision.is_legitimate_shared_infra,
            "model_scores": decision.model_scores,
            "primary_rule_triggered": decision.primary_rule_triggered,
            "triggered_rules": decision.triggered_rules,
            "top_risk_signals": decision.top_risk_signals,
            "shap_feature_attributions": decision.shap_feature_attributions,
            "feature_values": features.model_dump(),
            "explanation": decision.explanation,
            "is_legitimate_spike": decision.is_legitimate_spike,
            "is_suspicious_spike": decision.is_suspicious_spike,
            "latency_ms": elapsed_ms,
            "dry_run": dry_run,
        }
