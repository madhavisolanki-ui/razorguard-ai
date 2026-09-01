"""Synthetic Profile Generator for Users, Devices, IPs, Cards, and Merchants."""

import hashlib
import random
import uuid
from typing import List, Dict, Any, Optional

try:
    from faker import Faker
    fake = Faker("en_IN")
except ImportError:
    fake = None


class SyntheticProfilePool:
    """Manages reusable synthetic entity pools to maintain coherent entity graphs."""

    CARD_BINS = [
        {"bin": "411111", "network": "VISA", "issuer_bank": "HDFC", "type": "credit"},
        {"bin": "422222", "network": "VISA", "issuer_bank": "ICICI", "type": "debit"},
        {"bin": "510510", "network": "MASTERCARD", "issuer_bank": "SBI", "type": "credit"},
        {"bin": "520082", "network": "MASTERCARD", "issuer_bank": "AXIS", "type": "credit"},
        {"bin": "607189", "network": "RUPAY", "issuer_bank": "KOTAK", "type": "debit"},
        {"bin": "652150", "network": "RUPAY", "issuer_bank": "PNB", "type": "debit"},
    ]

    USER_AGENTS = [
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36", "Windows", "Chrome", False),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36", "macOS", "Chrome", False),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1", "iOS", "Safari", False),
        ("Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.88 Mobile Safari/537.36", "Android", "Chrome", False),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0", "Windows", "Firefox", False),
        # Headless bot signatures
        ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/128.0.6613.88 Safari/537.36", "Linux", "HeadlessChrome", True),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Playwright/1.46.0 Chrome/128.0.6613.18 Safari/537.36", "Windows", "Playwright", True),
        ("Python-urllib/3.11", "Linux", "PythonScript", True),
    ]

    INDIAN_ISPS = [
        ("Jio Fiber", "AS55836", False),
        ("Airtel Broadband", "AS24560", False),
        ("ACT Fibernet", "AS24309", False),
        ("Tata Teleservices", "AS4755", False),
        ("DigitalOcean Datacenter", "AS14061", True),
        ("AWS EC2 Datacenter", "AS16509", True),
        ("NordVPN Proxy Gateway", "AS9009", True),
        ("TOR Exit Node", "AS60729", True),
    ]

    MERCHANTS = [
        {"id": "mer_electronics_hub", "name": "Apex Electronics India", "category": "electronics", "risk_category": "STANDARD"},
        {"id": "mer_fashion_trends", "name": "Vogue Apparel", "category": "fashion", "risk_category": "LOW"},
        {"id": "mer_quick_groceries", "name": "BlinkKart Supermarket", "category": "grocery", "risk_category": "LOW"},
        {"id": "mer_digital_gaming", "name": "PixelPlay Gaming Keys", "category": "digital_goods", "risk_category": "HIGH"},
        {"id": "mer_luxury_watches", "name": "Chronos Luxury Timepieces", "category": "jewelry_luxury", "risk_category": "HIGH"},
    ]

    def __init__(self, pool_size: int = 1000, seed: int = 42):
        random.seed(seed)
        self.users: List[Dict[str, Any]] = []
        self.devices: List[Dict[str, Any]] = []
        self.ip_addresses: List[Dict[str, Any]] = []
        self.cards: List[Dict[str, Any]] = []
        self.bank_accounts: List[Dict[str, Any]] = []

        self._initialize_pools(pool_size)

    def _hash_token(self, val: str) -> str:
        return hashlib.sha256(val.encode()).hexdigest()[:16]

    def _initialize_pools(self, size: int) -> None:
        """Pre-generates pools of entities for consistent cross-referencing."""
        # Generate Cards
        for i in range(size * 2):
            bin_info = random.choice(self.CARD_BINS)
            last4 = f"{random.randint(1000, 9999)}"
            raw_card = f"{bin_info['bin']}{random.randint(100000, 999999)}{last4}"
            card_hash = self._hash_token(raw_card)
            self.cards.append({
                "bin": bin_info["bin"],
                "last4": last4,
                "card_hash": f"crd_{card_hash}",
                "network": bin_info["network"],
                "issuer_bank": bin_info["issuer_bank"],
                "type": bin_info["type"],
            })

        # Generate Bank Accounts
        for i in range(max(50, size // 10)):
            bank_code = random.choice(["HDFC", "ICICI", "SBI", "AXIS", "KOTAK"])
            acct_no = f"{bank_code}_{random.randint(1000000000, 9999999999)}"
            self.bank_accounts.append({
                "bank_code": bank_code,
                "account_hash": self._hash_token(acct_no),
            })

        # Generate Devices
        for i in range(size):
            ua_tuple = random.choice(self.USER_AGENTS[:5])  # Mostly clean devices
            canvas_seed = f"canvas_hw_{i}_{random.randint(1000, 9999)}"
            self.devices.append({
                "id": f"dev_{self._hash_token(canvas_seed)}",
                "user_agent": ua_tuple[0],
                "os": ua_tuple[1],
                "browser": ua_tuple[2],
                "is_headless": ua_tuple[3],
                "is_emulator": False,
                "canvas_hash": f"cnv_{self._hash_token(canvas_seed + '_render')}",
            })

        # Generate IP Addresses
        for i in range(size):
            isp_info = random.choice(self.INDIAN_ISPS[:4])  # Mostly residential
            subnet_prefix = f"{random.randint(11, 223)}.{random.randint(10, 200)}.{random.randint(1, 250)}"
            ip_str = f"{subnet_prefix}.{random.randint(2, 254)}"
            self.ip_addresses.append({
                "ip": ip_str,
                "subnet_c": f"{subnet_prefix}.0/24",
                "country": "IN",
                "isp": isp_info[0],
                "asn": isp_info[1],
                "is_datacenter_proxy": isp_info[2],
                "is_tor": False,
                "reputation_score": round(random.uniform(0.85, 1.0), 2),
            })

        # Generate Users
        for i in range(size):
            user_id = f"usr_{uuid.uuid4().hex[:10]}"
            if fake:
                name = fake.name()
                email = f"{name.lower().replace(' ', '')}{random.randint(10, 99)}@gmail.com"
            else:
                email = f"user_{i}_{random.randint(100, 999)}@example.com"

            self.users.append({
                "id": user_id,
                "email": email,
                "phone_country": "IN",
                "total_successful_tx": random.randint(1, 50),
                "total_chargebacks": 0,
                "assigned_device": random.choice(self.devices),
                "assigned_ip": random.choice(self.ip_addresses),
                "assigned_card": random.choice(self.cards),
            })

    def get_random_normal_user(self) -> Dict[str, Any]:
        return random.choice(self.users)

    def get_random_merchant(self) -> Dict[str, Any]:
        return random.choice(self.MERCHANTS)
