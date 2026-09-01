import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from src.core.database import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    """User profile record."""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    email = Column(String(255), nullable=True)
    email_domain = Column(String(128), nullable=True, index=True)
    phone_country = Column(String(8), default="IN")
    account_status = Column(String(32), default="ACTIVE")  # ACTIVE, SUSPENDED, FLAGGED
    total_successful_tx = Column(Integer, default=0)
    total_chargebacks = Column(Integer, default=0)
    is_synthetic_bad_actor = Column(Boolean, default=False)

    transactions = relationship("Transaction", back_populates="user")


class Merchant(Base):
    """Merchant entity record."""
    __tablename__ = "merchants"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(128), default="ecommerce")
    risk_category = Column(String(32), default="STANDARD")  # LOW, STANDARD, HIGH
    created_at = Column(DateTime, default=utc_now)

    transactions = relationship("Transaction", back_populates="merchant")


class Device(Base):
    """Device fingerprint record."""
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True, index=True)  # Fingerprint Hash
    user_agent = Column(String(512), nullable=True)
    os = Column(String(64), nullable=True)
    browser = Column(String(64), nullable=True)
    is_headless = Column(Boolean, default=False)
    is_emulator = Column(Boolean, default=False)
    canvas_hash = Column(String(64), nullable=True, index=True)
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)

    transactions = relationship("Transaction", back_populates="device")


class IPAddress(Base):
    """IP Address metadata and reputation record."""
    __tablename__ = "ip_addresses"

    ip = Column(String(45), primary_key=True, index=True)
    subnet_c = Column(String(45), nullable=True, index=True)  # /24 subnet
    country = Column(String(8), default="IN")
    isp = Column(String(128), nullable=True)
    asn = Column(String(64), nullable=True)
    is_datacenter_proxy = Column(Boolean, default=False)
    is_tor = Column(Boolean, default=False)
    reputation_score = Column(Float, default=1.0)  # 1.0 (Clean) to 0.0 (Malicious)
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)

    transactions = relationship("Transaction", back_populates="ip_record")


class Transaction(Base):
    """Payment transaction event record."""
    __tablename__ = "transactions"

    id = Column(String(64), primary_key=True, index=True)
    event_time = Column(DateTime, default=utc_now, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    device_id = Column(String(64), ForeignKey("devices.id"), nullable=True, index=True)
    ip_address = Column(String(45), ForeignKey("ip_addresses.ip"), nullable=True, index=True)

    amount = Column(Float, nullable=False)
    currency = Column(String(8), default="INR")
    payment_method = Column(String(32), default="credit_card")  # credit_card, debit_card, upi, netbanking

    card_bin = Column(String(8), nullable=True, index=True)
    card_last4 = Column(String(4), nullable=True)
    card_hash = Column(String(64), nullable=True, index=True)
    bank_code = Column(String(32), nullable=True)

    status = Column(String(32), default="SUCCESS", index=True)  # SUCCESS, FAILED, BLOCKED
    failure_code = Column(String(64), nullable=True)  # INSUFFICIENT_FUNDS, INCORRECT_CVV, CARD_EXPIRED, etc.
    checkout_duration_sec = Column(Float, default=12.0)
    is_flash_sale = Column(Boolean, default=False, index=True)
    scenario_tag = Column(String(64), nullable=True, index=True)  # normal, flash_sale, bot_abuse, etc.

    # Relationships
    user = relationship("User", back_populates="transactions")
    merchant = relationship("Merchant", back_populates="transactions")
    device = relationship("Device", back_populates="transactions")
    ip_record = relationship("IPAddress", back_populates="transactions")
    risk_assessment = relationship("RiskAssessment", back_populates="transaction", uselist=False)
    investigation_case = relationship("InvestigationCase", back_populates="transaction", uselist=False)

    __table_args__ = (
        Index("ix_tx_event_time_user", "event_time", "user_id"),
        Index("ix_tx_event_time_ip", "event_time", "ip_address"),
        Index("ix_tx_event_time_device", "event_time", "device_id"),
    )


class RiskAssessment(Base):
    """Synchronous fast-path risk assessment result."""
    __tablename__ = "risk_assessments"

    id = Column(String(64), primary_key=True, index=True)
    transaction_id = Column(String(64), ForeignKey("transactions.id"), unique=True, nullable=False, index=True)
    assessed_at = Column(DateTime, default=utc_now, nullable=False)

    composite_risk_score = Column(Float, nullable=False)  # 0.0 to 100.0
    risk_tier = Column(String(32), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL

    xgboost_score = Column(Float, default=0.0)
    iforest_score = Column(Float, default=0.0)
    velocity_score = Column(Float, default=0.0)
    graph_score = Column(Float, default=0.0)

    primary_rule_triggered = Column(String(128), nullable=True)
    fast_action = Column(String(32), nullable=False)  # ALLOW, MONITOR, STEP_UP_VERIFICATION, RATE_LIMIT
    latency_ms = Column(Integer, default=0)

    transaction = relationship("Transaction", back_populates="risk_assessment")


class InvestigationCase(Base):
    """AI Investigation Agent case dossier."""
    __tablename__ = "investigation_cases"

    id = Column(String(64), primary_key=True, index=True)
    transaction_id = Column(String(64), ForeignKey("transactions.id"), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    agent_status = Column(String(32), default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    traffic_scenario_verdict = Column(String(64), nullable=True)
    agent_confidence = Column(Float, default=0.0)
    recommended_action = Column(String(32), default="MONITOR")  # ALLOW, MONITOR, STEP_UP_VERIFICATION, RATE_LIMIT

    evidence_bundle = Column(JSON, nullable=True)
    justification_markdown = Column(Text, nullable=True)
    tool_call_trace = Column(JSON, nullable=True)

    human_override = Column(Boolean, default=False)
    human_verdict = Column(String(32), nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    transaction = relationship("Transaction", back_populates="investigation_case")


class GraphEdge(Base):
    """Relational entity link for fraud ring detection."""
    __tablename__ = "graph_edges"

    id = Column(String(64), primary_key=True, index=True)
    source_entity_id = Column(String(64), nullable=False, index=True)
    source_entity_type = Column(String(32), nullable=False)  # USER, DEVICE, IP, CARD, BANK, MERCHANT
    target_entity_id = Column(String(64), nullable=False, index=True)
    target_entity_type = Column(String(32), nullable=False)
    relation_type = Column(String(32), nullable=False)  # USED_DEVICE, FROM_IP, HAS_CARD, PAYS_MERCHANT, SHARES_BANK
    weight = Column(Float, default=1.0)
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_graph_edge_source_target", "source_entity_id", "target_entity_id"),
    )


class TrafficMetricWindow(Base):
    """Aggregated traffic metrics for Spike vs Attack visualization."""
    __tablename__ = "traffic_metric_windows"

    id = Column(String(64), primary_key=True, index=True)
    timestamp_window = Column(DateTime, nullable=False, index=True)
    window_size_sec = Column(Integer, default=300)  # 5 minutes

    total_transactions = Column(Integer, default=0)
    successful_transactions = Column(Integer, default=0)
    failed_transactions = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)

    ip_entropy = Column(Float, default=1.0)
    device_entropy = Column(Float, default=1.0)
    avg_checkout_duration = Column(Float, default=12.0)

    classified_as_spike = Column(Boolean, default=False)
    classified_as_attack = Column(Boolean, default=False)
    dominant_scenario = Column(String(64), default="normal")
