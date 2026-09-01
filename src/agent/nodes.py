"""LangGraph Node Implementations for AI Risk Investigation."""

from typing import Dict, Any, List, Optional
import time
from src.agent.state import InvestigationState
from src.agent.tools import InvestigationTools
from src.agent.llm import GeminiLLMClient
from src.agent.prompts import INVESTIGATION_SYSTEM_PROMPT, INVESTIGATION_USER_PROMPT_TEMPLATE
from src.core.logging import get_logger

logger = get_logger("agent_nodes")


def observe_node(state: InvestigationState) -> Dict[str, Any]:
    """OBSERVE: Reads the deterministic Phase 2-4 assessment and classifies initial risk profile."""
    risk_score = state.get("unified_risk_score", 0.0)
    is_fraud_ring = state.get("is_fraud_ring", False)
    is_legitimate_shared = state.get("is_legitimate_shared_infra", False)
    primary_rule = state.get("primary_rule_triggered") or ""

    if is_fraud_ring:
        category = "NETWORK_SYNDICATE"
    elif "SPIKE" in primary_rule or "FLASH_SALE" in primary_rule:
        category = "MERCHANT_SPIKE"
    elif risk_score >= 65.0 or "VELOCITY" in primary_rule or "MICRO" in primary_rule or "HEADLESS" in primary_rule:
        category = "BEHAVIOURAL_ABUSE"
    elif risk_score <= 30.0:
        category = "LOW_RISK"
    else:
        category = "AMBIGUOUS_ANOMALY"

    return {
        "risk_category": category,
        "investigation_path": ["OBSERVE"],
        "investigation_status": "OBSERVING",
    }


def analyze_node(state: InvestigationState) -> Dict[str, Any]:
    """ANALYZE: Determines which targeted investigation tools are required based on the risk profile."""
    category = state.get("risk_category", "LOW_RISK")
    planned_tools: List[str] = []

    if category == "NETWORK_SYNDICATE":
        planned_tools = ["get_related_entities", "get_graph_signals", "get_device_activity", "get_ip_activity"]
    elif category == "BEHAVIOURAL_ABUSE":
        planned_tools = ["get_transaction_history", "get_account_activity", "get_device_activity"]
    elif category == "MERCHANT_SPIKE":
        planned_tools = ["get_merchant_baseline", "get_ip_activity"]
    elif category == "AMBIGUOUS_ANOMALY":
        planned_tools = ["get_transaction_history", "get_account_activity", "get_device_activity", "get_ip_activity"]
    else:  # LOW_RISK
        planned_tools = ["get_account_activity"]

    return {
        "planned_tools": planned_tools,
        "investigation_path": ["ANALYZE"],
        "investigation_status": "ANALYZING",
    }


def create_investigate_node(tools: InvestigationTools):
    """Factory creating the INVESTIGATE node with bound investigation tools."""

    def investigate_node(state: InvestigationState) -> Dict[str, Any]:
        """INVESTIGATE: Executes planned read-only investigation tools."""
        user_id = state.get("user_id", "")
        device_id = state.get("device_id", "")
        ip_address = state.get("ip_address", "")
        merchant_id = state.get("merchant_id", "")
        transaction_id = state.get("transaction_id", "")
        planned = state.get("planned_tools", [])

        tool_results: Dict[str, Any] = {}
        tool_records: List[Dict[str, Any]] = []

        for tool_name in planned:
            t0 = time.perf_counter()
            res = {}
            if tool_name == "get_transaction_history":
                res = tools.get_transaction_history(user_id)
            elif tool_name == "get_account_activity":
                res = tools.get_account_activity(user_id)
            elif tool_name == "get_device_activity":
                res = tools.get_device_activity(device_id)
            elif tool_name == "get_ip_activity":
                res = tools.get_ip_activity(ip_address)
            elif tool_name == "get_merchant_baseline":
                res = tools.get_merchant_baseline(merchant_id)
            elif tool_name == "get_related_entities":
                res = tools.get_related_entities(user_id)
            elif tool_name == "get_graph_signals":
                res = tools.get_graph_signals(user_id)
            elif tool_name == "get_risk_signals":
                res = tools.get_risk_signals(transaction_id)

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            tool_results[tool_name] = res
            tool_records.append({
                "tool_name": tool_name,
                "arguments": {"user_id": user_id, "device_id": device_id, "ip": ip_address},
                "result_summary": str(res)[:200],
                "execution_time_ms": elapsed_ms,
            })

        return {
            "tool_results": tool_results,
            "tool_calls_executed": tool_records,
            "investigation_path": ["INVESTIGATE"],
            "investigation_status": "INVESTIGATED",
        }

    return investigate_node


def correlate_node(state: InvestigationState) -> Dict[str, Any]:
    """CORRELATE: Synthesizes evidence across multi-modal deterministic signals and tool outputs."""
    tool_results = state.get("tool_results", {})
    key_evidence: List[str] = []
    findings: List[str] = []
    related_entities: List[str] = []

    # Correlate ML SHAP drivers
    for s in state.get("top_risk_signals", [])[:3]:
        key_evidence.append(s)

    # Correlate Graph Signals
    if state.get("is_fraud_ring"):
        for g_sig in state.get("graph_signals", []):
            key_evidence.append(f"Network Graph: {g_sig}")
        findings.append(
            f"Multi-entity syndicate detected in Cluster {state.get('cluster_id')} "
            f"({state.get('cluster_size')} entities connected)."
        )

    # Correlate Related Entities Tool
    if "get_related_entities" in tool_results:
        ent = tool_results["get_related_entities"]
        if not ent.get("error"):
            accounts = ent.get("linked_accounts", [])
            devices = ent.get("linked_devices", [])
            cards = ent.get("linked_card_tokens", [])
            for a in accounts:
                related_entities.append(f"acc:{a}")
            for d in devices:
                related_entities.append(f"dev:{d}")
            for c in cards:
                related_entities.append(f"card:{c}")

    # Correlate Device Profile Tool
    if "get_device_activity" in tool_results:
        dev = tool_results["get_device_activity"]
        if dev.get("is_headless"):
            findings.append("Device Profile: Headless automation runtime detected.")

    # Correlate Merchant Baseline Tool
    if "get_merchant_baseline" in tool_results:
        mer = tool_results["get_merchant_baseline"]
        if mer.get("volume_surge_multiplier", 1.0) > 2.0:
            findings.append(f"Merchant Spike: {mer.get('volume_surge_multiplier')}x volume surge observed.")

    return {
        "key_evidence": key_evidence,
        "investigation_findings": findings,
        "related_entities": related_entities[:15],
        "investigation_path": ["CORRELATE"],
        "investigation_status": "CORRELATED",
    }


def decide_node(state: InvestigationState) -> Dict[str, Any]:
    """DECIDE: Evaluates findings against investigation hypotheses."""
    is_fraud_ring = state.get("is_fraud_ring", False)
    is_legitimate_shared = state.get("is_legitimate_shared_infra", False)
    risk_score = state.get("unified_risk_score", 0.0)

    if is_fraud_ring:
        verdict = "COORDINATED_SYNDICATE"
    elif is_legitimate_shared:
        verdict = "BENIGN_SHARED_INFRASTRUCTURE"
    elif risk_score >= 65.0:
        verdict = "SUSPICIOUS_BEHAVIOUR"
    else:
        verdict = "LEGITIMATE_ACTIVITY"

    return {
        "hypothesis_verdict": verdict,
        "investigation_path": ["DECIDE"],
        "investigation_status": "DECIDED",
    }


def recommend_node(state: InvestigationState) -> Dict[str, Any]:
    """RECOMMEND: Preserves and enforces the bounded defensive action."""
    fast_action = state.get("fast_action", "ALLOW")
    # Action must remain bounded: ALLOW, MONITOR, STEP_UP_VERIFICATION, RATE_LIMIT
    recommended_action = fast_action if fast_action in ("ALLOW", "MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT") else "ALLOW"

    return {
        "recommended_action": recommended_action,
        "investigation_path": ["RECOMMEND"],
        "investigation_status": "RECOMMENDED",
    }


def create_explain_node(llm_client: GeminiLLMClient):
    """Factory creating the EXPLAIN node with bound LLM provider."""

    def explain_node(state: InvestigationState) -> Dict[str, Any]:
        """EXPLAIN: Formulates evidence-grounded natural language explanation with anti-injection defense."""
        # Sanitize untrusted fields to neutralize prompt injections
        def _sanitize(val: Any) -> str:
            s = str(val or "")
            return s.replace("\n", " ").replace("\r", " ").strip()[:200]

        top_signals_str = "\n".join(f"- {s}" for s in state.get("top_risk_signals", [])) or "- Normal organic baseline"
        graph_signals_str = ", ".join(state.get("graph_signals", [])) or "None"
        suspicious_entities_str = ", ".join(state.get("suspicious_entities", [])) or "None"

        # Format tool results
        tool_lines = []
        for t_name, t_val in state.get("tool_results", {}).items():
            tool_lines.append(f"[{t_name}]: {str(t_val)[:250]}")
        tool_evidence_str = "\n".join(tool_lines) or "No additional tool calls required."

        user_prompt = INVESTIGATION_USER_PROMPT_TEMPLATE.format(
            transaction_id=_sanitize(state.get("transaction_id")),
            user_id=_sanitize(state.get("user_id")),
            merchant_id=_sanitize(state.get("merchant_id")),
            amount=state.get("amount", 0.0),
            currency=_sanitize(state.get("currency", "INR")),
            payment_method=_sanitize(state.get("payment_method", "credit_card")),
            event_time=_sanitize(state.get("event_time", "")),
            failure_code=_sanitize(state.get("failure_code")),
            unified_risk_score=state.get("unified_risk_score", 0.0),
            risk_level=state.get("risk_level", "LOW"),
            fast_action=state.get("fast_action", "ALLOW"),
            fraud_probability=state.get("fraud_probability", 0.0),
            anomaly_score=state.get("anomaly_score", 0.0),
            graph_risk_score=state.get("graph_risk_score", 0.0),
            primary_rule_triggered=_sanitize(state.get("primary_rule_triggered") or "None"),
            top_risk_signals=top_signals_str,
            is_fraud_ring=state.get("is_fraud_ring", False),
            is_legitimate_shared_infra=state.get("is_legitimate_shared_infra", False),
            cluster_id=_sanitize(state.get("cluster_id")),
            cluster_size=state.get("cluster_size", 1),
            graph_signals=graph_signals_str,
            suspicious_entities=suspicious_entities_str,
            tool_evidence=tool_evidence_str,
        )

        synthesis = llm_client.generate_synthesis(
            system_prompt=INVESTIGATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            state=dict(state),
        )

        return {
            "key_evidence": synthesis.get("key_evidence", state.get("key_evidence", [])),
            "investigation_findings": synthesis.get("investigation_findings", state.get("investigation_findings", [])),
            "recommended_action": synthesis.get("recommended_action", state.get("recommended_action", "ALLOW")),
            "confidence": synthesis.get("confidence", 0.90),
            "explanation": synthesis.get("explanation", ""),
            "is_fallback": synthesis.get("is_fallback", False),
            "investigation_path": ["EXPLAIN"],
            "investigation_status": "COMPLETED",
        }

    return explain_node
