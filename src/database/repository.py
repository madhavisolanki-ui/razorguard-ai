"""Repository Layer for Database CRUD and Query Optimizations."""

import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, distinct, case
from src.database.models import (
    User,
    Merchant,
    Device,
    IPAddress,
    Transaction,
    RiskAssessment,
    InvestigationCase,
    GraphEdge,
    TrafficMetricWindow,
)


class Repository:
    """Data access and repository operations."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------
    # Users
    # -------------------------------------------------------------
    def get_or_create_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        phone_country: str = "IN",
        is_synthetic_bad_actor: bool = False,
    ) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            email_domain = email.split("@")[-1] if email and "@" in email else "example.com"
            user = User(
                id=user_id,
                email=email,
                email_domain=email_domain,
                phone_country=phone_country,
                is_synthetic_bad_actor=is_synthetic_bad_actor,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    # -------------------------------------------------------------
    # Merchants
    # -------------------------------------------------------------
    def get_or_create_merchant(
        self,
        merchant_id: str,
        name: str = "Demo Merchant",
        category: str = "ecommerce",
        risk_category: str = "STANDARD",
    ) -> Merchant:
        merchant = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            merchant = Merchant(
                id=merchant_id,
                name=name,
                category=category,
                risk_category=risk_category,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            self.db.add(merchant)
            self.db.commit()
            self.db.refresh(merchant)
        return merchant

    def get_merchant(self, merchant_id: str) -> Optional[Merchant]:
        return self.db.query(Merchant).filter(Merchant.id == merchant_id).first()

    # -------------------------------------------------------------
    # Devices
    # -------------------------------------------------------------
    def get_or_create_device(
        self,
        device_id: str,
        user_agent: Optional[str] = None,
        os_name: Optional[str] = None,
        browser: Optional[str] = None,
        is_headless: bool = False,
        is_emulator: bool = False,
        canvas_hash: Optional[str] = None,
    ) -> Device:
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            device = Device(
                id=device_id,
                user_agent=user_agent,
                os=os_name,
                browser=browser,
                is_headless=is_headless,
                is_emulator=is_emulator,
                canvas_hash=canvas_hash or device_id,
                first_seen=datetime.datetime.now(datetime.timezone.utc),
                last_seen=datetime.datetime.now(datetime.timezone.utc),
            )
            self.db.add(device)
            self.db.commit()
            self.db.refresh(device)
        else:
            device.last_seen = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
        return device

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.db.query(Device).filter(Device.id == device_id).first()

    # -------------------------------------------------------------
    # IP Addresses
    # -------------------------------------------------------------
    def get_or_create_ip(
        self,
        ip: str,
        subnet_c: Optional[str] = None,
        country: str = "IN",
        isp: Optional[str] = None,
        asn: Optional[str] = None,
        is_datacenter_proxy: bool = False,
        is_tor: bool = False,
        reputation_score: float = 1.0,
    ) -> IPAddress:
        ip_record = self.db.query(IPAddress).filter(IPAddress.ip == ip).first()
        if not ip_record:
            if not subnet_c and "." in ip:
                subnet_c = ".".join(ip.split(".")[:3]) + ".0/24"
            ip_record = IPAddress(
                ip=ip,
                subnet_c=subnet_c,
                country=country,
                isp=isp or "Generic Telecom",
                asn=asn or "AS1337",
                is_datacenter_proxy=is_datacenter_proxy,
                is_tor=is_tor,
                reputation_score=reputation_score,
                first_seen=datetime.datetime.now(datetime.timezone.utc),
                last_seen=datetime.datetime.now(datetime.timezone.utc),
            )
            self.db.add(ip_record)
            self.db.commit()
            self.db.refresh(ip_record)
        else:
            ip_record.last_seen = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
        return ip_record

    def get_ip(self, ip: str) -> Optional[IPAddress]:
        return self.db.query(IPAddress).filter(IPAddress.ip == ip).first()

    # -------------------------------------------------------------
    # Transactions
    # -------------------------------------------------------------
    def create_transaction(self, tx_data: Dict[str, Any]) -> Transaction:
        tx = Transaction(**tx_data)
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        return self.db.query(Transaction).filter(Transaction.id == tx_id).first()

    def get_recent_transactions(self, limit: int = 50) -> List[Transaction]:
        return (
            self.db.query(Transaction)
            .order_by(desc(Transaction.event_time))
            .limit(limit)
            .all()
        )

    def get_previous_user_transaction(self, user_id: str, before_time: Optional[datetime.datetime] = None) -> Optional[Transaction]:
        query = self.db.query(Transaction).filter(Transaction.user_id == user_id)
        if before_time:
            query = query.filter(Transaction.event_time < before_time)
        return query.order_by(desc(Transaction.event_time)).first()

    def get_user_transactions(self, user_id: str, limit: int = 20) -> List[Transaction]:
        return (
            self.db.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(desc(Transaction.event_time))
            .limit(limit)
            .all()
        )

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        txs = self.db.query(Transaction).filter(Transaction.user_id == user_id).all()
        total_tx = len(txs)
        total_amt = sum(t.amount for t in txs)
        avg_amt = (total_amt / total_tx) if total_tx > 0 else 0.0
        return {
            "total_transactions": total_tx,
            "total_spend": round(total_amt, 2),
            "avg_amount": round(avg_amt, 2),
        }

    def get_merchant_recent_stats(self, merchant_id: str, window_seconds: int = 300) -> Dict[str, Any]:
        count = self.get_merchant_tx_count_in_window(merchant_id, window_seconds)
        return {"count": count}

    def get_ip_address(self, ip: str) -> Optional[IPAddress]:
        return self.get_ip(ip)

    # -------------------------------------------------------------
    # Sliding Window Queries
    # -------------------------------------------------------------
    def get_user_tx_count_in_window(self, user_id: str, window_seconds: int = 300) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.user_id == user_id, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_merchant_tx_count_in_window(self, merchant_id: str, window_seconds: int = 300) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.merchant_id == merchant_id, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_ip_tx_count_in_window(self, ip: str, window_seconds: int = 300) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.ip_address == ip, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_device_tx_count_in_window(self, device_id: str, window_seconds: int = 300) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.device_id == device_id, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_merchant_txs_in_window(self, merchant_id: str, window_seconds: int = 300) -> List[Transaction]:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(Transaction)
            .filter(Transaction.merchant_id == merchant_id, Transaction.event_time >= cutoff)
            .all()
        )

    def get_ip_txs_in_window(self, ip: str, window_seconds: int = 300) -> List[Transaction]:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(Transaction)
            .filter(Transaction.ip_address == ip, Transaction.event_time >= cutoff)
            .all()
        )

    def get_user_txs_in_window(self, user_id: str, window_seconds: int = 300) -> List[Transaction]:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.event_time >= cutoff)
            .all()
        )

    def get_unique_accounts_per_ip(self, ip: str, window_seconds: int = 3600) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(distinct(Transaction.user_id)))
            .filter(Transaction.ip_address == ip, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_unique_devices_per_ip(self, ip: str, window_seconds: int = 3600) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(distinct(Transaction.device_id)))
            .filter(Transaction.ip_address == ip, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_unique_ips_per_account(self, user_id: str, window_seconds: int = 86400) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(distinct(Transaction.ip_address)))
            .filter(Transaction.user_id == user_id, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_unique_accounts_per_device(self, device_id: str, window_seconds: int = 86400) -> int:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(distinct(Transaction.user_id)))
            .filter(Transaction.device_id == device_id, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )

    def get_ip_failed_tx_ratio_in_window(self, ip: str, window_seconds: int = 300) -> float:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=window_seconds)
        total = (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.ip_address == ip, Transaction.event_time >= cutoff)
            .scalar()
            or 0
        )
        if total == 0:
            return 0.0
        failed = (
            self.db.query(func.count(Transaction.id))
            .filter(
                Transaction.ip_address == ip,
                Transaction.event_time >= cutoff,
                Transaction.status != "SUCCESS",
            )
            .scalar()
            or 0
        )
        return float(failed / total)

    def get_user_historical_stats(self, user_id: str) -> Dict[str, float]:
        stats = (
            self.db.query(
                func.count(Transaction.id).label("total_tx"),
                func.avg(Transaction.amount).label("avg_amount"),
                func.sum(case((Transaction.status == "SUCCESS", 1), else_=0)).label("successful_tx"),
            )
            .filter(Transaction.user_id == user_id)
            .first()
        )
        total = stats.total_tx if stats and stats.total_tx else 0
        avg_amt = float(stats.avg_amount) if stats and stats.avg_amount else 0.0
        success = stats.successful_tx if stats and stats.successful_tx else 0
        return {
            "total_transactions": total,
            "average_amount": avg_amt,
            "success_rate": float(success / total) if total > 0 else 1.0,
        }

    def get_merchant_historical_stats(self, merchant_id: str) -> Dict[str, float]:
        stats = (
            self.db.query(
                func.count(Transaction.id).label("total_tx"),
                func.avg(Transaction.amount).label("avg_amount"),
                func.sum(case((Transaction.status == "SUCCESS", 1), else_=0)).label("successful_tx"),
            )
            .filter(Transaction.merchant_id == merchant_id)
            .first()
        )
        total = stats.total_tx if stats and stats.total_tx else 0
        avg_amt = float(stats.avg_amount) if stats and stats.avg_amount else 2500.0
        success = stats.successful_tx if stats and stats.successful_tx else 0
        return {
            "total_transactions": total,
            "average_amount": avg_amt,
            "success_rate": float(success / total) if total > 0 else 0.92,
        }

    # -------------------------------------------------------------
    # Risk Assessments & Cases
    # -------------------------------------------------------------
    def create_risk_assessment(self, assessment_data: Dict[str, Any]) -> RiskAssessment:
        assessment = RiskAssessment(**assessment_data)
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    def get_risk_assessment(self, tx_id: str) -> Optional[RiskAssessment]:
        return self.db.query(RiskAssessment).filter(RiskAssessment.transaction_id == tx_id).first()

    def create_investigation_case(self, case_data: Dict[str, Any]) -> InvestigationCase:
        case = InvestigationCase(**case_data)
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def get_investigation_case(self, case_id: str) -> Optional[InvestigationCase]:
        return self.db.query(InvestigationCase).filter(InvestigationCase.id == case_id).first()

    def get_investigation_case_by_tx(self, tx_id: str) -> Optional[InvestigationCase]:
        return self.db.query(InvestigationCase).filter(InvestigationCase.transaction_id == tx_id).first()

    # -------------------------------------------------------------
    # Graph Edges
    # -------------------------------------------------------------
    def add_or_update_edge(
        self,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relation_type: str,
        weight: float = 1.0,
    ) -> GraphEdge:
        edge = (
            self.db.query(GraphEdge)
            .filter(
                GraphEdge.source_entity_id == source_id,
                GraphEdge.target_entity_id == target_id,
                GraphEdge.relation_type == relation_type,
            )
            .first()
        )
        if not edge:
            import uuid
            edge = GraphEdge(
                id=f"edge_{uuid.uuid4().hex[:12]}",
                source_entity_id=source_id,
                source_entity_type=source_type,
                target_entity_id=target_id,
                target_entity_type=target_type,
                relation_type=relation_type,
                weight=weight,
                first_seen=datetime.datetime.now(datetime.timezone.utc),
                last_seen=datetime.datetime.now(datetime.timezone.utc),
            )
            self.db.add(edge)
        else:
            edge.weight += weight
            edge.last_seen = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def get_edges_for_entity(self, entity_id: str) -> List[GraphEdge]:
        return (
            self.db.query(GraphEdge)
            .filter(
                (GraphEdge.source_entity_id == entity_id)
                | (GraphEdge.target_entity_id == entity_id)
            )
            .all()
        )
