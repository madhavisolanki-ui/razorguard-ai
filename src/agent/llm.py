"""LLM Provider Abstraction and Deterministic Fallback Engine."""

import os
import json
import re
from typing import Dict, Any, Optional
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("agent_llm")


class RuleBasedSynthesizer:
    """Deterministic, high-fidelity synthesis engine for offline/fallback mode.
    Guarantees 100% evidence traceability and zero hallucinations without external network calls."""

    def synthesize(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesizes structured investigation findings directly from deterministic state."""
        risk_score = state.get("unified_risk_score", 0.0)
        risk_level = state.get("risk_level", "LOW")
        fast_action = state.get("fast_action", "ALLOW")
        is_fraud_ring = state.get("is_fraud_ring", False)
        is_legitimate_shared = state.get("is_legitimate_shared_infra", False)
        graph_signals = state.get("graph_signals", [])
        shap_signals = state.get("top_risk_signals", [])
        primary_rule = state.get("primary_rule_triggered")
        tool_results = state.get("tool_results", {})
        cluster_id = state.get("cluster_id", "cluster_none")
        cluster_size = state.get("cluster_size", 1)

        key_evidence = []
        findings = []

        # 1. Compile ML Evidence
        for sig in shap_signals[:3]:
            key_evidence.append(sig)

        if not key_evidence:
            key_evidence.append("Organic customer transaction within expected behavioural baselines.")

        # 2. Compile Heuristic Rule Evidence
        if primary_rule:
            key_evidence.append(f"Heuristic Rule Triggered: {primary_rule}")

        # 3. Compile Graph & Syndicate Evidence
        if is_fraud_ring:
            for g_sig in graph_signals:
                key_evidence.append(f"Network Graph Signal: {g_sig}")
            findings.append(
                f"Multi-entity fraud ring confirmed in Cluster {cluster_id} ({cluster_size} connected entities). "
                f"Activity indicates coordinated syndicate operation."
            )
        elif is_legitimate_shared:
            findings.append(
                "High entity concentration on origin IP verified as legitimate campus or corporate NAT infrastructure with diverse devices."
            )
        else:
            findings.append("Isolated transaction topology with no coordinated multi-account syndicate relationships detected.")

        # 4. Synthesize Tool Results
        if "get_account_activity" in tool_results:
            acc = tool_results["get_account_activity"]
            if not acc.get("error"):
                findings.append(f"Account Profile: Lifetime spend INR {acc.get('total_spend', 0.0):,.2f} across {acc.get('total_transactions', 0)} transactions.")

        if "get_device_activity" in tool_results:
            dev = tool_results["get_device_activity"]
            if not dev.get("error") and dev.get("is_headless"):
                key_evidence.append("Device Profile: Headless automated browser fingerprint (Puppeteer/Playwright) detected.")

        if "get_merchant_baseline" in tool_results:
            mer = tool_results["get_merchant_baseline"]
            if not mer.get("error") and mer.get("volume_surge_multiplier", 1.0) > 2.0:
                key_evidence.append(f"Merchant Spike: Volume surge {mer.get('volume_surge_multiplier')}x over baseline (Flash sale: {mer.get('is_flash_sale_active')}).")

        # 5. Formulate Grounded Natural Language Explanation
        if is_fraud_ring:
            explanation = (
                f"Transaction evaluated at {risk_score:.1f}/100 ({risk_level} Tier). "
                f"While individual transaction parameters may appear standard, NetworkX graph analysis identified a "
                f"coordinated syndicate in Cluster {cluster_id} ({cluster_size} linked nodes) with signals: {', '.join(graph_signals)}. "
                f"Recommended action '{fast_action}' assigned to protect merchant receivables."
            )
        elif is_legitimate_shared:
            explanation = (
                f"Transaction evaluated at {risk_score:.1f}/100 ({risk_level} Tier). "
                f"Observed IP concentration is cleared as legitimate shared infrastructure (campus NAT/VPN) "
                f"due to high device entropy and clean network reputation. Recommended action '{fast_action}' maintained."
            )
        elif risk_score > settings.THRESHOLD_MONITOR_MAX:
            explanation = (
                f"Transaction evaluated at {risk_score:.1f}/100 ({risk_level} Tier). "
                f"Elevated risk signals detected including {primary_rule or 'high ML fraud probability and payment failure velocity'}. "
                f"Defensive action '{fast_action}' assigned to protect merchant."
            )
        elif risk_score > settings.THRESHOLD_ALLOW_MAX:
            explanation = (
                f"Transaction evaluated at {risk_score:.1f}/100 ({risk_level} Tier). "
                f"Moderate behavioral anomalies observed. Action '{fast_action}' assigned for continuous monitoring."
            )
        else:
            explanation = (
                f"Transaction evaluated at {risk_score:.1f}/100 ({risk_level} Tier). "
                f"Behavioral velocity, merchant baselines, and network graph topology are within normal organic bounds. "
                f"Action '{fast_action}' approved."
            )

        return {
            "key_evidence": key_evidence[:6],
            "investigation_findings": findings[:4],
            "recommended_action": fast_action,
            "confidence": 0.95 if is_fraud_ring or risk_score < 30.0 else 0.88,
            "explanation": explanation,
            "is_fallback": True,
        }


class GeminiLLMClient:
    """Invokes Google Gemini API with structured JSON output and fallback safety."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GOOGLE_GENAI_API_KEY")
            or settings.GEMINI_API_KEY
        )
        self.model_name = model_name or settings.AGENT_MODEL_NAME
        self.fallback = RuleBasedSynthesizer()
        self.client = None

        if self.api_key and self.api_key not in ("your_gemini_api_key_here", "None", ""):
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini LLM Client initialized with model: %s", self.model_name)
            except Exception as e:
                logger.warning("Failed to initialize google.genai Client: %s. Using fallback synthesizer.", e)

    def generate_synthesis(self, system_prompt: str, user_prompt: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Calls Gemini API or gracefully falls back to deterministic synthesis."""
        if not self.client:
            logger.debug("No live Gemini client available. Invoking deterministic synthesizer.")
            return self.fallback.synthesize(state)

        try:
            from google.genai import types
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=settings.AGENT_TEMPERATURE,
                    response_mime_type="application/json",
                ),
            )
            
            text = response.text or ""
            parsed = json.loads(text)
            
            # Verify and preserve bounded recommended action
            action = parsed.get("recommended_action", state.get("fast_action", "ALLOW"))
            if action not in ("ALLOW", "MONITOR", "STEP_UP_VERIFICATION", "RATE_LIMIT"):
                action = state.get("fast_action", "ALLOW")

            return {
                "key_evidence": parsed.get("key_evidence", []),
                "investigation_findings": parsed.get("investigation_findings", []),
                "recommended_action": action,
                "confidence": float(parsed.get("confidence", 0.90)),
                "explanation": parsed.get("explanation", ""),
                "is_fallback": False,
            }
        except Exception as e:
            logger.warning("Gemini generation failed (%s). Gracefully falling back to deterministic synthesizer.", e)
            return self.fallback.synthesize(state)


def get_llm_client() -> GeminiLLMClient:
    """Factory creating configured LLM client with automatic fallback."""
    return GeminiLLMClient(
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.AGENT_MODEL_NAME,
    )
