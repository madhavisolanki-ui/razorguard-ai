"""Scenario-specific Synthetic Payment Event Generators."""

import datetime
import random
import uuid
from typing import Dict, Any, Optional
from src.generator.profiles import SyntheticProfilePool


class ScenarioGenerator:
    """Generates synthetic payment events for each of the 6 canonical risk scenarios."""

    def __init__(self, profile_pool: Optional[SyntheticProfilePool] = None, seed: int = 42):
        self.pool = profile_pool or SyntheticProfilePool(pool_size=1000, seed=seed)
        random.seed(seed)

        # Persistent clusters for coordinated abuse & fraud ring scenarios
        self.bot_subnets = ["185.220.101.0/24", "193.56.28.0/24", "45.154.255.0/24"]
        self.farm_canvas_hashes = [f"cnv_farm_{uuid.uuid4().hex[:8]}" for _ in range(3)]
        self.fraud_ring_bank = self.pool.bank_accounts[0]["account_hash"]
        self.fraud_ring_cards = [c["card_hash"] for c in self.pool.cards[:3]]
        self.fraud_ring_users = [u["id"] for u in self.pool.users[:10]]

    def _base_event_scaffold(self, timestamp: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc)
        return {
            "event_id": f"evt_{uuid.uuid4().hex[:16]}",
            "timestamp": ts.isoformat(),
            "currency": "INR",
        }

    # -------------------------------------------------------------
    # Scenario 1: Normal Organic Traffic
    # -------------------------------------------------------------
    def generate_normal_event(self, timestamp: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        event = self._base_event_scaffold(timestamp)
        user = self.pool.get_random_normal_user()
        merchant = self.pool.get_random_merchant()
        device = user["assigned_device"]
        ip = user["assigned_ip"]
        card = user["assigned_card"]

        is_success = random.random() < 0.94
        failure_code = None if is_success else random.choice(["INSUFFICIENT_FUNDS", "BANK_SERVER_DOWN", "AUTH_TIMEOUT"])

        event.update({
            "scenario": "normal",
            "user_id": user["id"],
            "merchant_id": merchant["id"],
            "amount": round(random.choice([
                random.uniform(199, 999),
                random.uniform(1200, 4999),
                random.uniform(5000, 15000)
            ]), 2),
            "payment_method": card["type"] + "_card",
            "card": card,
            "device": device,
            "network": ip,
            "status": "SUCCESS" if is_success else "FAILED",
            "failure_code": failure_code,
            "context": {
                "checkout_duration_sec": round(random.uniform(8.0, 35.0), 1),
                "cart_items_count": random.randint(1, 4),
                "is_flash_sale": False,
            }
        })
        return event

    # -------------------------------------------------------------
    # Scenario 2: Legitimate Traffic Spike (Flash Sale / Festival)
    # -------------------------------------------------------------
    def generate_legitimate_spike_event(
        self,
        timestamp: Optional[datetime.datetime] = None,
        target_merchant_id: str = "mer_electronics_hub"
    ) -> Dict[str, Any]:
        event = self._base_event_scaffold(timestamp)
        user = self.pool.get_random_normal_user()
        # In flash sales, distinct organic users converge on a specific merchant
        device = user["assigned_device"]
        ip = user["assigned_ip"]
        card = user["assigned_card"]

        # High success rate (slight bank congestion, but genuine)
        is_success = random.random() < 0.88
        failure_code = None if is_success else random.choice(["GATEWAY_TIMEOUT", "INSUFFICIENT_FUNDS", "NETWORK_ERROR"])

        event.update({
            "scenario": "legitimate_spike",
            "user_id": user["id"],
            "merchant_id": target_merchant_id,
            "amount": round(random.choice([
                19999.00, 24999.00, 49999.00, 79999.00, random.uniform(15000, 65000)
            ]), 2),
            "payment_method": "credit_card",
            "card": card,
            "device": device,
            "network": ip,
            "status": "SUCCESS" if is_success else "FAILED",
            "failure_code": failure_code,
            "context": {
                "checkout_duration_sec": round(random.uniform(6.0, 22.0), 1),
                "cart_items_count": 1,
                "is_flash_sale": True,
            }
        })
        return event

    # -------------------------------------------------------------
    # Scenario 3: Automated Bot Abuse (Credential Stuffing / Scripted Checkouts)
    # -------------------------------------------------------------
    def generate_bot_abuse_event(self, timestamp: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        event = self._base_event_scaffold(timestamp)
        # Bots use headless browsers, proxies, and rapid micro-second checkouts
        subnet = random.choice(self.bot_subnets)
        bot_ip_str = f"{subnet.split('/')[0][:-1]}{random.randint(2, 254)}"
        bot_ua = random.choice(SyntheticProfilePool.USER_AGENTS[5:])  # Headless agents

        bot_device = {
            "id": f"dev_bot_{uuid.uuid4().hex[:8]}",
            "user_agent": bot_ua[0],
            "os": bot_ua[1],
            "browser": bot_ua[2],
            "is_headless": True,
            "is_emulator": random.choice([True, False]),
            "canvas_hash": "cnv_null_headless_0000",
        }

        bot_ip = {
            "ip": bot_ip_str,
            "subnet_c": subnet,
            "country": "IN",
            "isp": "DigitalOcean Datacenter",
            "asn": "AS14061",
            "is_datacenter_proxy": True,
            "is_tor": False,
            "reputation_score": 0.20,
        }

        is_success = random.random() < 0.15  # Low success rate
        failure_code = None if is_success else random.choice(["INCORRECT_CVV", "CARD_EXPIRED", "DO_NOT_HONOR", "CAPTCHA_FAILED"])

        event.update({
            "scenario": "bot_abuse",
            "user_id": f"usr_bot_{random.randint(100, 999)}",
            "merchant_id": "mer_electronics_hub",
            "amount": round(random.uniform(500, 2500), 2),
            "payment_method": "credit_card",
            "card": random.choice(self.pool.cards),
            "device": bot_device,
            "network": bot_ip,
            "status": "SUCCESS" if is_success else "FAILED",
            "failure_code": failure_code,
            "context": {
                "checkout_duration_sec": round(random.uniform(0.1, 1.2), 2),  # Inhuman speed
                "cart_items_count": 1,
                "is_flash_sale": False,
            }
        })
        return event

    # -------------------------------------------------------------
    # Scenario 4: Payment Abuse (Card Cracking / Micro Testing)
    # -------------------------------------------------------------
    def generate_payment_abuse_event(
        self,
        timestamp: Optional[datetime.datetime] = None,
        attacker_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        event = self._base_event_scaffold(timestamp)
        uid = attacker_user_id or f"usr_carder_{random.randint(1, 10)}"
        merchant = self.pool.MERCHANTS[3]  # Digital goods merchant

        is_success = random.random() < 0.10
        failure_code = None if is_success else random.choice(["INCORRECT_CVV", "INVALID_EXPIRY", "DO_NOT_HONOR", "STOLEN_CARD"])

        event.update({
            "scenario": "payment_abuse",
            "user_id": uid,
            "merchant_id": merchant["id"],
            "amount": round(random.uniform(1.00, 49.00), 2),  # Micro amounts ($0.10 - $1.00)
            "payment_method": "credit_card",
            "card": random.choice(self.pool.cards),
            "device": random.choice(self.pool.devices),
            "network": random.choice(self.pool.ip_addresses),
            "status": "SUCCESS" if is_success else "FAILED",
            "failure_code": failure_code,
            "context": {
                "checkout_duration_sec": round(random.uniform(1.5, 4.0), 1),
                "cart_items_count": 1,
                "is_flash_sale": False,
            }
        })
        return event

    # -------------------------------------------------------------
    # Scenario 5: Coordinated Abuse (Multi-Account Device/Subnet Farm)
    # -------------------------------------------------------------
    def generate_coordinated_abuse_event(self, timestamp: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        event = self._base_event_scaffold(timestamp)
        # Shared canvas hash across multiple fresh user accounts
        canvas_hash = random.choice(self.farm_canvas_hashes)
        farm_subnet = "194.26.29.0/24"
        farm_ip_str = f"194.26.29.{random.randint(10, 240)}"

        shared_device = {
            "id": f"dev_{canvas_hash[:12]}",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0",
            "os": "Windows",
            "browser": "Chrome",
            "is_headless": False,
            "is_emulator": False,
            "canvas_hash": canvas_hash,
        }

        shared_ip = {
            "ip": farm_ip_str,
            "subnet_c": farm_subnet,
            "country": "IN",
            "isp": "NordVPN Proxy Gateway",
            "asn": "AS9009",
            "is_datacenter_proxy": True,
            "is_tor": False,
            "reputation_score": 0.45,
        }

        is_success = random.random() < 0.75

        event.update({
            "scenario": "coordinated_abuse",
            "user_id": f"usr_farm_{uuid.uuid4().hex[:8]}",  # Fresh account every time
            "merchant_id": "mer_fashion_trends",
            "amount": round(random.uniform(299, 899), 2),  # Promo code target amount
            "payment_method": "credit_card",
            "card": random.choice(self.pool.cards),
            "device": shared_device,
            "network": shared_ip,
            "status": "SUCCESS" if is_success else "FAILED",
            "failure_code": None if is_success else "PROMO_LIMIT_EXCEEDED",
            "context": {
                "checkout_duration_sec": round(random.uniform(3.0, 7.0), 1),
                "cart_items_count": 1,
                "is_flash_sale": False,
            }
        })
        return event

    # -------------------------------------------------------------
    # Scenario 6: Fraud Ring (Graph Syndicate)
    # -------------------------------------------------------------
    def generate_fraud_ring_event(self, timestamp: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        event = self._base_event_scaffold(timestamp)
        # Ring members share bank accounts, cards, and cross-transact
        ring_user = random.choice(self.fraud_ring_users)
        ring_card = random.choice(self.pool.cards[:3])
        ring_card["card_hash"] = random.choice(self.fraud_ring_cards)

        merchant = random.choice(self.pool.MERCHANTS)

        event.update({
            "scenario": "fraud_ring",
            "user_id": ring_user,
            "merchant_id": merchant["id"],
            "amount": round(random.uniform(25000, 95000), 2),  # High-ticket money laundering / bust-out
            "payment_method": "credit_card",
            "card": ring_card,
            "bank_account_hash": self.fraud_ring_bank,  # Shared withdrawal hub
            "device": random.choice(self.pool.devices[:5]),
            "network": random.choice(self.pool.ip_addresses[:5]),
            "status": "SUCCESS",
            "failure_code": None,
            "context": {
                "checkout_duration_sec": round(random.uniform(10.0, 30.0), 1),
                "cart_items_count": random.randint(1, 3),
                "is_flash_sale": False,
            }
        })
        return event

    def generate_by_scenario_name(self, scenario_name: str, timestamp: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        """Dispatch helper to generate an event for a specific scenario."""
        dispatch = {
            "normal": self.generate_normal_event,
            "legitimate_spike": self.generate_legitimate_spike_event,
            "bot_abuse": self.generate_bot_abuse_event,
            "payment_abuse": self.generate_payment_abuse_event,
            "coordinated_abuse": self.generate_coordinated_abuse_event,
            "fraud_ring": self.generate_fraud_ring_event,
        }
        gen_func = dispatch.get(scenario_name, self.generate_normal_event)
        return gen_func(timestamp)
