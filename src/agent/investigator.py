"""High-Level Risk Investigation Service Coordinating LangGraph Execution."""

import time
import uuid
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.database.repository import Repository
from src.graph.builder import FraudGraphBuilder
from src.engine.service import get_global_graph_builder
from src.agent.tools import InvestigationTools
from src.agent.llm import GeminiLLMClient, get_llm_client
from src.agent.graph import create_investigation_graph
from src.agent.state import InvestigationState
from src.agent.schemas import InvestigationReport, ToolCallRecord
from src.agent.audit import get_global_audit_logger
from src.core.logging import get_logger

logger = get_logger("risk_investigator")


class RiskInvestigationService:
    """Service orchestrating AI investigations on evaluated payment transactions."""

    def __init__(
        self,
        db_session: Session,
        graph_builder: Optional[FraudGraphBuilder] = None,
        llm_client: Optional[GeminiLLMClient] = None,
    ):
        self.repo = Repository(db_session)
        self.graph_builder = graph_builder or get_global_graph_builder()
        self.llm_client = llm_client or get_llm_client()
        self.tools = InvestigationTools(self.repo, self.graph_builder)
        self.audit_logger = get_global_audit_logger()
        self.compiled_graph = create_investigation_graph(self.tools, self.llm_client)

    def investigate_transaction(
        self,
        transaction_id: str,
        analyst_notes: Optional[str] = None,
    ) -> InvestigationReport:
        """Runs the LangGraph investigation workflow on an existing stored transaction."""
        t0 = time.perf_counter()
        investigation_id = f"inv_{uuid.uuid4().hex[:12]}"

        # 1. Retrieve Stored Transaction & Risk Assessment
        tx = self.repo.get_transaction(transaction_id)
        if not tx:
            raise ValueError(f"Transaction with ID '{transaction_id}' not found in database.")

        assessment = self.repo.get_risk_assessment(transaction_id)
        if not assessment:
            raise ValueError(f"Risk assessment for transaction '{transaction_id}' not found.")

        # 2. Extract Graph & Topology Context
        user_id = tx.user_id
        acc_node = f"acc:{user_id}"
        dev_id = tx.device_id or "dev_unknown"
        ip_addr = tx.ip_address or "127.0.0.1"
        card_hash = tx.card_hash

        cluster_id = "cluster_none"
        cluster_size = 1
        cluster_density = 0.0
        suspicious_entities = []
        graph_signals = []
        is_fraud_ring = False
        is_legitimate_shared = False

        if self.graph_builder.graph.has_node(acc_node):
            try:
                import networkx as nx
                comp = nx.node_connected_component(self.graph_builder.graph, acc_node)
                sorted_nodes = sorted(list(comp))
                cluster_id = f"cl_{hash(tuple(sorted_nodes[:5])) & 0xffffffff:08x}"
                cluster_size = len(comp)
                sub = self.graph_builder.graph.subgraph(comp)
                cluster_density = round(float(nx.density(sub)), 3)

                # Check if card/device sharing exists
                if card_hash:
                    card_node = f"card:{card_hash}"
                    if self.graph_builder.graph.has_node(card_node):
                        card_accs = [
                            n for n in self.graph_builder.graph.neighbors(card_node)
                            if self.graph_builder.graph.nodes[n].get("node_type") == "ACCOUNT"
                        ]
                        if len(card_accs) >= 2:
                            is_fraud_ring = True
                            graph_signals.append(f"SHARED_CARD_ACROSS_{len(card_accs)}_ACCOUNTS")
                            suspicious_entities.extend(card_accs)
                            suspicious_entities.append(card_node)

                dev_node = f"dev:{dev_id}"
                if self.graph_builder.graph.has_node(dev_node):
                    dev_accs = [
                        n for n in self.graph_builder.graph.neighbors(dev_node)
                        if self.graph_builder.graph.nodes[n].get("node_type") == "ACCOUNT"
                    ]
                    if len(dev_accs) >= 3:
                        is_fraud_ring = True
                        graph_signals.append(f"DEVICE_FARM_OVER_{len(dev_accs)}_ACCOUNTS")
                        suspicious_entities.extend(dev_accs)
                        suspicious_entities.append(dev_node)
            except Exception as e:
                logger.debug("Graph extraction warning during investigation: %s", e)

        # 3. Assemble Initial LangGraph State
        initial_state: InvestigationState = {
            "transaction_id": tx.id,
            "user_id": tx.user_id,
            "merchant_id": tx.merchant_id,
            "device_id": dev_id,
            "ip_address": ip_addr,
            "card_hash": card_hash,
            "amount": tx.amount,
            "currency": tx.currency,
            "payment_method": tx.payment_method or "credit_card",
            "event_time": tx.event_time.isoformat() if tx.event_time else "",
            "status": tx.status,
            "failure_code": tx.failure_code,
            "individual_risk_score": assessment.composite_risk_score,
            "graph_risk_score": assessment.graph_score or 0.0,
            "unified_risk_score": assessment.composite_risk_score,
            "risk_level": assessment.risk_tier,
            "fraud_probability": assessment.xgboost_score or 0.0,
            "anomaly_score": assessment.iforest_score or 0.0,
            "velocity_score": assessment.velocity_score or 0.0,
            "fast_action": assessment.fast_action,
            "primary_rule_triggered": assessment.primary_rule_triggered,
            "triggered_rules": [],
            "shap_signals": [],
            "top_risk_signals": [assessment.primary_rule_triggered] if assessment.primary_rule_triggered else [],
            "graph_signals": graph_signals,
            "suspicious_entities": sorted(list(set(suspicious_entities))),
            "cluster_id": cluster_id,
            "cluster_size": cluster_size,
            "cluster_density": cluster_density,
            "is_fraud_ring": is_fraud_ring or (assessment.graph_score or 0.0) >= 50.0,
            "is_legitimate_shared_infra": is_legitimate_shared,
            "relationship_explanation": "Investigation initiated.",
            "investigation_id": investigation_id,
            "risk_category": "LOW_RISK",
            "planned_tools": [],
            "tool_calls_executed": [],
            "tool_results": {},
            "key_evidence": [],
            "investigation_findings": [],
            "related_entities": [],
            "hypothesis_verdict": "UNEVALUATED",
            "recommended_action": assessment.fast_action,
            "confidence": 0.90,
            "explanation": "",
            "investigation_status": "PENDING",
            "investigation_path": [],
            "is_fallback": False,
            "analyst_notes": analyst_notes,
        }

        # 4. Invoke LangGraph Execution
        final_state = self.compiled_graph.invoke(initial_state)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # 5. Format Executed Tool Calls
        tool_records = [
            ToolCallRecord(
                tool_name=tc["tool_name"],
                arguments=tc.get("arguments", {}),
                result_summary=tc.get("result_summary", ""),
                execution_time_ms=tc.get("execution_time_ms", 0.0),
            )
            for tc in final_state.get("tool_calls_executed", [])
        ]
        tools_used = [tc["tool_name"] for tc in final_state.get("tool_calls_executed", [])]

        # 6. Audit Trail Recording
        self.audit_logger.record_investigation(
            investigation_id=investigation_id,
            transaction_id=tx.id,
            deterministic_inputs={
                "risk_score": assessment.composite_risk_score,
                "risk_tier": assessment.risk_tier,
                "fast_action": assessment.fast_action,
                "xgboost_score": assessment.xgboost_score,
                "iforest_score": assessment.iforest_score,
                "graph_score": assessment.graph_score,
            },
            tools_executed=tool_records,
            investigation_path=final_state.get("investigation_path", []),
            final_verdict={
                "recommended_action": final_state.get("recommended_action", assessment.fast_action),
                "confidence": final_state.get("confidence", 0.90),
                "explanation": final_state.get("explanation", ""),
            },
            fallback_invoked=final_state.get("is_fallback", False),
        )

        return InvestigationReport(
            investigation_id=investigation_id,
            transaction_id=tx.id,
            investigation_status="COMPLETED" if not final_state.get("is_fallback") else "FALLBACK_DETERMINISTIC",
            risk_score=assessment.composite_risk_score,
            risk_level=assessment.risk_tier,
            fraud_probability=assessment.xgboost_score,
            anomaly_score=assessment.iforest_score,
            graph_risk_score=assessment.graph_score,
            key_evidence=final_state.get("key_evidence", []),
            investigation_findings=final_state.get("investigation_findings", []),
            related_entities=final_state.get("related_entities", []),
            fraud_ring_detected=final_state.get("is_fraud_ring", False),
            cluster_id=cluster_id,
            cluster_size=cluster_size,
            recommended_action=final_state.get("recommended_action", assessment.fast_action),
            confidence=final_state.get("confidence", 0.90),
            explanation=final_state.get("explanation", ""),
            tools_used=tools_used,
            tool_calls=tool_records,
            investigation_path=final_state.get("investigation_path", []),
            latency_ms=elapsed_ms,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
