"""Transparent Rule-Based Behavioural Risk Rules and Evaluator."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.core.config import settings
from src.features.calculator import FeatureVector
from src.core.logging import get_logger

logger = get_logger("rule_engine")


class RuleResult(BaseModel):
    """Execution result of a single behavioural rule."""

    rule_id: str
    rule_name: str
    category: str
    triggered: bool
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL, DISCOUNT
    score_impact: float
    description: str


class RuleEngine:
    """Evaluates behavioural rules against extracted real-time feature vectors."""

    def __init__(self):
        self.rules_config = settings.RULES

    def evaluate_all_rules(self, features: FeatureVector) -> List[RuleResult]:
        """Evaluates all registered behavioural risk rules."""
        results: List[RuleResult] = []

        # -------------------------------------------------------------
        # 1. Velocity Rules
        # -------------------------------------------------------------
        # Rule: IP Velocity Burst (1m)
        if features.ip_requests_per_minute > self.rules_config.velocity.max_ip_requests_per_minute:
            results.append(RuleResult(
                rule_id="R_VEL_IP_BURST",
                rule_name="Abnormal IP Request Velocity",
                category="velocity",
                triggered=True,
                severity="HIGH",
                score_impact=35.0,
                description=(
                    f"IP {features.ip_address} generated {features.ip_requests_per_minute} requests/min "
                    f"(threshold: {self.rules_config.velocity.max_ip_requests_per_minute})."
                )
            ))

        # Rule: User Velocity Burst (1m)
        if features.user_requests_per_minute > self.rules_config.velocity.max_user_requests_per_minute:
            results.append(RuleResult(
                rule_id="R_VEL_USER_BURST",
                rule_name="Abnormal User Account Velocity",
                category="velocity",
                triggered=True,
                severity="MEDIUM",
                score_impact=20.0,
                description=(
                    f"User {features.user_id} made {features.user_requests_per_minute} requests/min "
                    f"(threshold: {self.rules_config.velocity.max_user_requests_per_minute})."
                )
            ))

        # Rule: Sub-Second Inhuman Checkout (Bot signature)
        if features.checkout_duration_sec < self.rules_config.velocity.min_checkout_duration_sec:
            results.append(RuleResult(
                rule_id="R_BOT_SUB_SECOND_CHECKOUT",
                rule_name="Sub-Second Automated Checkout Speed",
                category="velocity",
                triggered=True,
                severity="HIGH",
                score_impact=40.0,
                description=(
                    f"Checkout completed in {features.checkout_duration_sec}s "
                    f"(threshold: < {self.rules_config.velocity.min_checkout_duration_sec}s indicates automated bot script)."
                )
            ))

        # -------------------------------------------------------------
        # 2. Payment Failure & Decline Rules
        # -------------------------------------------------------------
        # Rule: High IP Failure / Decline Burst
        if (
            features.ip_requests_per_5_minutes >= self.rules_config.failure_rates.min_transactions_for_failure_ratio
            and features.payment_failure_rate_5m >= self.rules_config.failure_rates.high_ip_failure_ratio_threshold
        ):
            results.append(RuleResult(
                rule_id="R_FAIL_EXCESSIVE_DECLINES",
                rule_name="Excessive Payment Decline Cluster",
                category="failure_rate",
                triggered=True,
                severity="HIGH",
                score_impact=35.0,
                description=(
                    f"IP {features.ip_address} has {round(features.payment_failure_rate_5m * 100, 1)}% failure rate "
                    f"over {features.ip_requests_per_5_minutes} transactions in 5m."
                )
            ))

        # Rule: Multiple Distinct Accounts on Single IP (Excludes verified campus/corporate diverse NATs)
        if features.unique_accounts_per_ip_1h > self.rules_config.concentration.max_unique_accounts_per_ip_1h:
            is_campus_or_corporate = (
                features.unique_devices_per_ip_1h >= 4 and
                not features.is_datacenter_proxy and
                features.ip_reputation_score >= 0.70 and
                features.payment_failure_rate_5m <= 0.20
            )
            if not is_campus_or_corporate:
                results.append(RuleResult(
                    rule_id="R_CONC_ACCOUNTS_ON_IP",
                    rule_name="Suspicious Multi-Account IP Concentration",
                    category="concentration",
                    triggered=True,
                    severity="HIGH",
                    score_impact=30.0,
                    description=(
                        f"{features.unique_accounts_per_ip_1h} distinct user accounts originated from "
                        f"IP {features.ip_address} in 1h (threshold: {self.rules_config.concentration.max_unique_accounts_per_ip_1h})."
                    )
                ))

        # Rule: Headless Browser / Emulator Signature
        if features.is_headless_device or features.is_emulator_device:
            results.append(RuleResult(
                rule_id="R_THREAT_HEADLESS_BROWSER",
                rule_name="Headless Browser or Emulator Detected",
                category="threat_intel",
                triggered=True,
                severity="HIGH",
                score_impact=35.0,
                description="Transaction originated from a headless browser environment (Puppeteer/Playwright) or emulator."
            ))

        # Rule: Datacenter Proxy or Low Reputation IP
        if features.is_datacenter_proxy or features.ip_reputation_score < 0.40:
            results.append(RuleResult(
                rule_id="R_THREAT_DATACENTER_PROXY",
                rule_name="Datacenter Proxy or High Risk IP",
                category="threat_intel",
                triggered=True,
                severity="MEDIUM",
                score_impact=25.0,
                description=(
                    f"IP {features.ip_address} is associated with a datacenter proxy/VPN "
                    f"(reputation score: {features.ip_reputation_score})."
                )
            ))

        # Rule: High Risk Card Decline Code
        if features.failure_code in ("INCORRECT_CVV", "INVALID_EXPIRY", "DO_NOT_HONOR", "STOLEN_CARD", "CARD_EXPIRED", "INVALID_CARD_NUMBER"):
            results.append(RuleResult(
                rule_id="R_FAIL_HIGH_RISK_CODE",
                rule_name="Suspicious Card Decline Code",
                category="failure_rate",
                triggered=True,
                severity="HIGH",
                score_impact=30.0,
                description=f"Transaction failed with high-risk payment decline code '{features.failure_code}'."
            ))

        # -------------------------------------------------------------
        # 4. Pattern & Abuse Rules (Card Cracking / Micro Testing)
        # -------------------------------------------------------------
        # Rule: Micro-transaction Card Testing Cadence
        if features.is_micro_transaction:
            if (
                features.ip_requests_per_5_minutes >= 2
                or features.payment_failure_rate_5m > 0.0
                or features.failure_code is not None
                or features.checkout_duration_sec < 5.0
            ):
                results.append(RuleResult(
                    rule_id="R_PAT_MICRO_CARD_TESTING",
                    rule_name="Micro-Transaction Card Testing Pattern",
                    category="pattern",
                    triggered=True,
                    severity="HIGH",
                    score_impact=35.0,
                    description=(
                        f"Micro-amount payment (INR {features.amount}) with rapid checkout or failure signals, "
                        f"characteristic of card cracking/testing."
                    )
                ))
            else:
                results.append(RuleResult(
                    rule_id="R_PAT_MICRO_TRANSACTION",
                    rule_name="Micro-Transaction Amount Flag",
                    category="pattern",
                    triggered=True,
                    severity="LOW",
                    score_impact=15.0,
                    description=f"Transaction amount (INR {features.amount}) is below standard threshold."
                ))

        # Rule: High Repeated Amount Ratio
        if (
            features.ip_requests_per_5_minutes >= self.rules_config.patterns.min_repeated_count_threshold
            and features.repeated_transaction_ratio >= self.rules_config.patterns.max_repeated_amount_ratio_5m
        ):
            results.append(RuleResult(
                rule_id="R_PAT_REPEATED_AMOUNTS",
                rule_name="Repeated Transaction Amount Burst",
                category="pattern",
                triggered=True,
                severity="MEDIUM",
                score_impact=20.0,
                description=(
                    f"{round(features.repeated_transaction_ratio * 100, 1)}% of transactions in 5m "
                    f"shared the exact same amount ({features.amount})."
                )
            ))

        # -------------------------------------------------------------
        # 5. Account / Device Relationships
        # -------------------------------------------------------------
        # Rule: Fresh Account + High Ticket Surge
        if features.account_age_hours < 2.0 and features.amount_deviation > self.rules_config.patterns.max_amount_deviation_multiplier:
            results.append(RuleResult(
                rule_id="R_REL_NEW_ACCOUNT_LARGE_AMOUNT",
                rule_name="New Account High Ticket Surge",
                category="concentration",
                triggered=True,
                severity="MEDIUM",
                score_impact=20.0,
                description=(
                    f"Account created only {features.account_age_hours}h ago transacting {features.amount_deviation}x "
                    f"above standard basket size."
                )
            ))

        # -------------------------------------------------------------
        # 6. Merchant Baseline & Spike Context
        # -------------------------------------------------------------
        # Rule: Suspicious Merchant Attack Surge (Low entropy + high volume)
        if features.is_suspicious_spike_candidate:
            results.append(RuleResult(
                rule_id="R_SPIKE_SUSPICIOUS_ATTACK_SURGE",
                rule_name="Suspicious Low-Entropy Volume Surge on Merchant",
                category="merchant_spike",
                triggered=True,
                severity="CRITICAL",
                score_impact=45.0,
                description=(
                    f"Merchant {features.merchant_id} experienced a {features.merchant_volume_multiplier}x volume surge "
                    f"with abnormally low IP entropy ({features.merchant_ip_entropy}) and high failure rate, "
                    f"indicating a distributed botnet attack rather than genuine customers."
                )
            ))

        # Rule: Legitimate Flash Sale Discount (High entropy + high volume -> negative penalty)
        if features.is_legitimate_spike_candidate or (features.declared_flash_sale and features.merchant_ip_entropy >= 0.60):
            results.append(RuleResult(
                rule_id="R_SPIKE_LEGITIMATE_FLASH_SALE_DISCOUNT",
                rule_name="Confirmed Legitimate Flash Sale Traffic Discount",
                category="merchant_spike",
                triggered=True,
                severity="DISCOUNT",
                score_impact=-25.0,  # Mitigates false positives during flash sales
                description=(
                    f"Merchant {features.merchant_id} traffic confirmed as legitimate high-entropy flash sale "
                    f"(IP entropy: {features.merchant_ip_entropy}, Device entropy: {features.merchant_device_entropy}, "
                    f"Success rate: {round(features.payment_success_rate_5m * 100, 1)}%). Velocity thresholds adjusted."
                )
            ))

        return results
