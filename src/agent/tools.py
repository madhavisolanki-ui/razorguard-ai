"""Bounded, Read-Only Investigation Tools for LangGraph Agent."""

from typing import Dict, Any, List, Optional
import time
import networkx as nx
from src.database.repository import Repository
from src.graph.builder import FraudGraphBuilder
from src.core.logging import get_logger

logger = get_logger("agent_tools")


class InvestigationTools:
    """Safe, read-only investigation tools querying local database and in-memory entity graph."""

    def __init__(self, repository: Repository, graph_builder: FraudGraphBuilder):
        self.repo = repository
        self.graph_builder = graph_builder
        self.graph = graph_builder.graph

    def get_transaction_history(self, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """Retrieves recent transaction history for the customer account."""
        t0 = time.perf_counter()
        try:
            txs = self.repo.get_user_transactions(user_id, limit=limit)
            history = [
                {
                    "transaction_id": t.id,
                    "event_time": t.event_time.isoformat() if t.event_time else "",
                    "amount": t.amount,
                    "currency": t.currency,
                    "merchant_id": t.merchant_id,
                    "status": t.status,
                    "failure_code": t.failure_code,
                }
                for t in txs
            ]
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "user_id": user_id,
                "history_count": len(history),
                "transactions": history,
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_transaction_history error for %s: %s", user_id, e)
            return {"user_id": user_id, "error": str(e), "transactions": []}

    def get_account_activity(self, user_id: str) -> Dict[str, Any]:
        """Retrieves user profile velocity, cumulative metrics, and account age."""
        t0 = time.perf_counter()
        try:
            user = self.repo.get_user(user_id)
            user_stats = self.repo.get_user_statistics(user_id)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "user_id": user_id,
                "total_transactions": user_stats.get("total_transactions", 0),
                "total_spend": user_stats.get("total_spend", 0.0),
                "avg_ticket_size": user_stats.get("avg_amount", 0.0),
                "created_at": user.created_at.isoformat() if user and user.created_at else "unknown",
                "account_status": user.account_status if user else "ACTIVE",
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_account_activity error for %s: %s", user_id, e)
            return {"user_id": user_id, "error": str(e)}

    def get_device_activity(self, device_id: str) -> Dict[str, Any]:
        """Inspects hardware profile, distinct accounts seen, and emulator/headless flags."""
        t0 = time.perf_counter()
        try:
            dev_node = f"dev:{device_id}"
            accounts_on_dev = []
            if self.graph.has_node(dev_node):
                accounts_on_dev = [
                    n.replace("acc:", "") for n in self.graph.neighbors(dev_node)
                    if self.graph.nodes[n].get("node_type") == "ACCOUNT"
                ]
            
            # Fetch device metadata from database
            device_record = self.repo.get_device(device_id)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "device_id": device_id,
                "distinct_accounts_count": len(accounts_on_dev),
                "associated_accounts": accounts_on_dev[:10],
                "os": device_record.os if device_record else "Unknown",
                "browser": device_record.browser if device_record else "Unknown",
                "is_headless": bool(device_record.is_headless) if device_record else False,
                "is_emulator": bool(device_record.is_emulator) if device_record else False,
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_device_activity error for %s: %s", device_id, e)
            return {"device_id": device_id, "error": str(e)}

    def get_ip_activity(self, ip_address: str) -> Dict[str, Any]:
        """Inspects origin IP threat intelligence, network concentration, and proxy flags."""
        t0 = time.perf_counter()
        try:
            ip_node = f"ip:{ip_address}"
            accounts_on_ip = []
            devices_on_ip = []
            if self.graph.has_node(ip_node):
                accounts_on_ip = [
                    n.replace("acc:", "") for n in self.graph.neighbors(ip_node)
                    if self.graph.nodes[n].get("node_type") == "ACCOUNT"
                ]
                devices_on_ip = [
                    n.replace("dev:", "") for n in self.graph.neighbors(ip_node)
                    if self.graph.nodes[n].get("node_type") == "DEVICE"
                ]

            ip_record = self.repo.get_ip_address(ip_address)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "ip_address": ip_address,
                "distinct_accounts_count": len(accounts_on_ip),
                "distinct_devices_count": len(devices_on_ip),
                "is_datacenter_proxy": bool(ip_record.is_datacenter_proxy) if ip_record else False,
                "reputation_score": float(ip_record.reputation_score) if ip_record else 1.0,
                "country": ip_record.country if ip_record else "IN",
                "isp": ip_record.isp if ip_record else "Unknown",
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_ip_activity error for %s: %s", ip_address, e)
            return {"ip_address": ip_address, "error": str(e)}

    def get_merchant_baseline(self, merchant_id: str) -> Dict[str, Any]:
        """Retrieves merchant traffic volume multipliers, entropy diversity, and flash sale status."""
        t0 = time.perf_counter()
        try:
            merchant = self.repo.get_merchant(merchant_id)
            stats = self.repo.get_merchant_recent_stats(merchant_id, window_seconds=300)
            baseline_vol = getattr(merchant, "baseline_velocity_5m", 10) if merchant else 10
            is_flash = getattr(merchant, "is_flash_sale_active", False) if merchant else False
            recent_count = stats.get("count", 0)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "merchant_id": merchant_id,
                "name": merchant.name if merchant else "Unknown",
                "category": merchant.category if merchant else "general",
                "recent_5m_volume": recent_count,
                "baseline_volume_5m": baseline_vol,
                "volume_surge_multiplier": round(recent_count / max(1, baseline_vol), 2),
                "is_flash_sale_active": bool(is_flash),
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_merchant_baseline error for %s: %s", merchant_id, e)
            return {"merchant_id": merchant_id, "error": str(e)}

    def get_related_entities(self, user_id: str) -> Dict[str, Any]:
        """Retrieves the full multi-hop connected component of entities linked to this account."""
        t0 = time.perf_counter()
        try:
            acc_node = f"acc:{user_id}"
            if not self.graph.has_node(acc_node):
                return {"user_id": user_id, "cluster_size": 1, "entities": [acc_node]}

            comp = nx.node_connected_component(self.graph, acc_node)
            subgraph = self.graph.subgraph(comp)
            
            entities_by_type: Dict[str, List[str]] = {
                "accounts": [], "devices": [], "ips": [], "cards": [], "merchants": []
            }
            for n in comp:
                ntype = self.graph.nodes[n].get("node_type", "")
                if ntype == "ACCOUNT":
                    entities_by_type["accounts"].append(n.replace("acc:", ""))
                elif ntype == "DEVICE":
                    entities_by_type["devices"].append(n.replace("dev:", ""))
                elif ntype == "IP":
                    entities_by_type["ips"].append(n.replace("ip:", ""))
                elif ntype == "CARD_TOKEN":
                    entities_by_type["cards"].append(n.replace("card:", ""))
                elif ntype == "MERCHANT":
                    entities_by_type["merchants"].append(n.replace("mer:", ""))

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "user_id": user_id,
                "cluster_size": len(comp),
                "cluster_density": round(float(nx.density(subgraph)), 3),
                "linked_accounts": entities_by_type["accounts"],
                "linked_devices": entities_by_type["devices"],
                "linked_ips": entities_by_type["ips"],
                "linked_card_tokens": entities_by_type["cards"],
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_related_entities error for %s: %s", user_id, e)
            return {"user_id": user_id, "error": str(e)}

    def get_graph_signals(self, user_id: str) -> Dict[str, Any]:
        """Extracts topological cycles and graph syndicate indicators for the account."""
        t0 = time.perf_counter()
        try:
            acc_node = f"acc:{user_id}"
            cycles_detected = []
            if self.graph.has_node(acc_node):
                comp = nx.node_connected_component(self.graph, acc_node)
                sub = self.graph.subgraph(comp)
                basis = nx.cycle_basis(sub)
                for cyc in basis:
                    accs = [n for n in cyc if n.startswith("acc:")]
                    bridges = [n for n in cyc if n.startswith("card:") or n.startswith("dev:")]
                    if len(accs) >= 2 and len(bridges) >= 1:
                        cycles_detected.append(cyc)

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "user_id": user_id,
                "cycles_count": len(cycles_detected),
                "syndicate_cycles": cycles_detected[:5],
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_graph_signals error for %s: %s", user_id, e)
            return {"user_id": user_id, "error": str(e)}

    def get_risk_signals(self, transaction_id: str) -> Dict[str, Any]:
        """Retrieves stored ML feature attributions, SHAP drivers, and heuristic rule breakdowns."""
        t0 = time.perf_counter()
        try:
            assessment = self.repo.get_risk_assessment(transaction_id)
            if not assessment:
                return {"transaction_id": transaction_id, "error": "Assessment not found"}

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "transaction_id": transaction_id,
                "composite_risk_score": assessment.composite_risk_score,
                "risk_tier": assessment.risk_tier,
                "xgboost_score": assessment.xgboost_score,
                "iforest_score": assessment.iforest_score,
                "velocity_score": assessment.velocity_score,
                "graph_score": assessment.graph_score,
                "primary_rule": assessment.primary_rule_triggered,
                "fast_action": assessment.fast_action,
                "execution_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning("get_risk_signals error for %s: %s", transaction_id, e)
            return {"transaction_id": transaction_id, "error": str(e)}
