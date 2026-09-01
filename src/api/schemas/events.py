"""Pydantic Schemas for Event Ingestion."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CardDetails(BaseModel):
    bin: Optional[str] = Field(default="411111", description="First 6 digits of card BIN")
    last4: Optional[str] = Field(default="1111", description="Last 4 digits of card")
    card_hash: Optional[str] = Field(default=None, description="Anonymized card token")
    network: Optional[str] = Field(default="VISA", description="Card network")
    issuer_bank: Optional[str] = Field(default="HDFC", description="Card issuer bank")


class DeviceDetails(BaseModel):
    id: Optional[str] = Field(default=None, description="Unique device fingerprint hash")
    user_agent: Optional[str] = Field(default="Mozilla/5.0 Chrome/128", description="Browser user agent")
    os: Optional[str] = Field(default="Windows", description="Operating system")
    browser: Optional[str] = Field(default="Chrome", description="Browser name")
    is_headless: Optional[bool] = Field(default=False, description="Headless browser indicator")
    is_emulator: Optional[bool] = Field(default=False, description="Device emulator indicator")
    canvas_hash: Optional[str] = Field(default=None, description="HTML5 Canvas / WebGL hardware hash")


class NetworkDetails(BaseModel):
    ip: Optional[str] = Field(default="103.21.244.2", description="Origin IPv4 / IPv6 address")
    subnet_c: Optional[str] = Field(default=None, description="/24 subnet prefix")
    country: Optional[str] = Field(default="IN", description="ISO country code")
    isp: Optional[str] = Field(default="Jio Fiber", description="Internet Service Provider")
    asn: Optional[str] = Field(default="AS55836", description="Autonomous System Number")
    is_datacenter_proxy: Optional[bool] = Field(default=False, description="Datacenter proxy or VPN flag")
    vpn_detected: Optional[bool] = Field(default=False, description="VPN flag")
    tor_detected: Optional[bool] = Field(default=False, description="Tor exit node flag")
    reputation_score: Optional[float] = Field(default=1.0, description="IP reputation (1.0 clean to 0.0 malicious)")


class EventContext(BaseModel):
    checkout_duration_sec: Optional[float] = Field(default=12.0, description="Seconds spent on checkout page")
    cart_items_count: Optional[int] = Field(default=1, description="Number of items in shopping cart")
    is_flash_sale: Optional[bool] = Field(default=False, description="Active merchant flash sale flag")


class PaymentEventInput(BaseModel):
    """Incoming payment event structure."""

    event_id: Optional[str] = Field(default=None, description="Client-generated unique event ID")
    timestamp: Optional[str] = Field(default=None, description="ISO 8601 event timestamp")
    user_id: str = Field(..., description="Unique customer user account ID")
    merchant_id: str = Field(..., description="Merchant account ID")
    amount: float = Field(..., gt=0, description="Transaction amount")
    currency: Optional[str] = Field(default="INR", description="Three-letter currency code")
    payment_method: Optional[str] = Field(default="credit_card", description="Payment instrument")
    status: Optional[str] = Field(default="SUCCESS", description="Gateway status: SUCCESS, FAILED")
    failure_code: Optional[str] = Field(default=None, description="Decline error code if failed")

    card: Optional[CardDetails] = Field(default_factory=CardDetails)
    device: Optional[DeviceDetails] = Field(default_factory=DeviceDetails)
    network: Optional[NetworkDetails] = Field(default_factory=NetworkDetails)
    context: Optional[EventContext] = Field(default_factory=EventContext)
    scenario: Optional[str] = Field(default="normal", description="Synthetic scenario tag")


class PaymentEventResponse(BaseModel):
    """Synchronous response returned after evaluating and persisting an event."""

    transaction_id: str
    event_id: str
    timestamp: str
    amount: float
    currency: str
    risk_score: float
    risk_level: str
    recommended_action: str
    fraud_probability: Optional[float] = None
    anomaly_score: Optional[float] = None
    model_scores: Optional[Dict[str, float]] = None
    primary_rule_triggered: Optional[str] = None
    triggered_rules: List[Dict[str, Any]] = Field(default_factory=list)
    top_risk_signals: List[str] = Field(default_factory=list)
    shap_feature_attributions: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str
    is_legitimate_spike: bool = False
    is_suspicious_spike: bool = False
    latency_ms: int
