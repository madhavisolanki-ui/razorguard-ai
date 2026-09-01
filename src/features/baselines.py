"""Merchant and User Baseline Estimations and Traffic Spike Evaluators."""

import math
from typing import Dict, Any, List, Optional
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("baselines")


class BaselineEvaluator:
    """Computes entity baselines and evaluates legitimate flash sales vs attack surges."""

    # Default fallback baselines by merchant category
    CATEGORY_DEFAULTS = {
        "electronics": {"avg_tps_5m": 30, "avg_amount": 15000.0, "success_rate": 0.90},
        "fashion": {"avg_tps_5m": 25, "avg_amount": 1800.0, "success_rate": 0.94},
        "grocery": {"avg_tps_5m": 50, "avg_amount": 650.0, "success_rate": 0.96},
        "digital_goods": {"avg_tps_5m": 20, "avg_amount": 500.0, "success_rate": 0.85},
        "jewelry_luxury": {"avg_tps_5m": 10, "avg_amount": 45000.0, "success_rate": 0.88},
    }

    @staticmethod
    def calculate_shannon_entropy(items: List[str]) -> float:
        """Calculates normalized Shannon entropy (0.0 to 1.0) of a categorical distribution.
        
        High entropy (~1.0) means high diversity (many distinct users/IPs) -> Legitimate flash sale.
        Low entropy (~0.0) means concentration (single IP/device repeating) -> Bot attack.
        """
        if not items:
            return 1.0
        n = len(items)
        if n <= 1:
            return 1.0

        counts: Dict[str, int] = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1

        k = len(counts)
        if k <= 1:
            return 0.0

        entropy = 0.0
        for count in counts.values():
            p = count / n
            entropy -= p * math.log2(p)

        # Normalize by log2(n)
        max_entropy = math.log2(n)
        if max_entropy <= 0.0:
            return 1.0
        return round(min(1.0, entropy / max_entropy), 3)

    @classmethod
    def evaluate_merchant_spike(
        cls,
        merchant_id: str,
        merchant_category: str,
        current_5m_count: int,
        current_success_rate: float,
        ip_list_5m: List[str],
        device_list_5m: List[str],
        declared_flash_sale: bool = False,
    ) -> Dict[str, Any]:
        """Evaluates whether current traffic represents a legitimate spike or an automated attack surge."""
        defaults = cls.CATEGORY_DEFAULTS.get(merchant_category, {"avg_tps_5m": 25, "avg_amount": 2000.0, "success_rate": 0.92})
        baseline_5m = defaults["avg_tps_5m"]

        spike_multiplier = round(float(current_5m_count) / max(1, baseline_5m), 2)
        ip_entropy = cls.calculate_shannon_entropy(ip_list_5m)
        device_entropy = cls.calculate_shannon_entropy(device_list_5m)

        is_volume_surge = spike_multiplier >= settings.RULES.merchant_spike.spike_volume_multiplier

        # Legitimate Spike Criteria:
        # High volume surge + High IP diversity + High Device diversity + Healthy success rate
        is_legitimate_spike = False
        is_suspicious_attack_surge = False
        spike_verdict = "NORMAL_VOLUME"

        if is_volume_surge or declared_flash_sale:
            has_high_entropy = (ip_entropy >= settings.RULES.merchant_spike.flash_sale_min_entropy and
                                device_entropy >= settings.RULES.merchant_spike.flash_sale_min_entropy)
            has_healthy_success = current_success_rate >= settings.RULES.merchant_spike.flash_sale_min_success_rate

            if has_high_entropy and has_healthy_success:
                is_legitimate_spike = True
                spike_verdict = "LEGITIMATE_FLASH_SALE_SPIKE"
            elif (not has_high_entropy) or (current_success_rate < 0.50):
                is_suspicious_attack_surge = True
                spike_verdict = "SUSPICIOUS_ATTACK_SURGE"
            else:
                spike_verdict = "MODERATE_SPIKE_MONITORING"

        return {
            "merchant_id": merchant_id,
            "current_5m_volume": current_5m_count,
            "baseline_5m_volume": baseline_5m,
            "volume_multiplier": spike_multiplier,
            "ip_entropy": ip_entropy,
            "device_entropy": device_entropy,
            "current_success_rate": current_success_rate,
            "is_volume_surge": is_volume_surge,
            "is_legitimate_spike": is_legitimate_spike,
            "is_suspicious_attack_surge": is_suspicious_attack_surge,
            "spike_verdict": spike_verdict,
        }
