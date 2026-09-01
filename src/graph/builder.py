"""Heterogeneous Fraud Graph Builder for RazorGuard AI."""

import datetime
import uuid
from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("graph_builder")


class FraudGraphBuilder:
    """Manages an in-memory heterogeneous entity-relationship graph connecting
    Accounts, Devices, IPs, Payment Cards, Transactions, and Merchants."""

    def __init__(self, max_nodes: Optional[int] = None):
        self.graph: nx.Graph = nx.Graph()
        self.max_nodes = max_nodes or settings.RULES.graph.graph_window_max_nodes
        self._creation_times: Dict[str, datetime.datetime] = {}

    def add_event(
        self,
        event: Dict[str, Any],
        transaction_id: str,
        risk_score: Optional[float] = None,
    ) -> None:
        """Incrementally ingests a payment event, adding/updating nodes and connecting relational edges."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Extract Entity Identifiers
        user_id = str(event.get("user_id") or "usr_anonymous")
        merchant_id = str(event.get("merchant_id") or "mer_default")
        amount = float(event.get("amount", 0.0))
        currency = str(event.get("currency", "INR"))
        status = str(event.get("status", "SUCCESS"))

        device_data = event.get("device", {})
        device_id = str(device_data.get("id") or device_data.get("device_id") or f"dev_{uuid.uuid4().hex[:8]}")
        user_agent = device_data.get("user_agent")
        is_headless = bool(device_data.get("is_headless", False))
        is_emulator = bool(device_data.get("is_emulator", False))

        network_data = event.get("network", {})
        ip_address = str(network_data.get("ip") or network_data.get("ip_address") or "127.0.0.1")
        is_proxy = bool(network_data.get("is_datacenter_proxy", False) or network_data.get("vpn_detected", False))
        ip_reputation = float(network_data.get("reputation_score", network_data.get("ip_reputation", 1.0)))

        card_data = event.get("card", {})
        card_bin = card_data.get("bin") or event.get("card_bin")
        card_last4 = card_data.get("last4") or event.get("card_last4")
        card_hash = str(card_data.get("card_hash") or event.get("card_hash") or f"card_{card_bin or '411111'}_{card_last4 or '1111'}")

        # 2. Add / Update Nodes
        # Node: ACCOUNT
        acc_node = f"acc:{user_id}"
        if not self.graph.has_node(acc_node):
            self.graph.add_node(
                acc_node,
                node_type="ACCOUNT",
                entity_id=user_id,
                tx_count=1,
                total_spent=amount,
                first_seen=now,
                last_seen=now,
                risk_tier="LOW",
            )
            self._creation_times[acc_node] = now
        else:
            n_data = self.graph.nodes[acc_node]
            n_data["tx_count"] += 1
            n_data["total_spent"] += amount
            n_data["last_seen"] = now

        # Node: DEVICE
        dev_node = f"dev:{device_id}"
        if not self.graph.has_node(dev_node):
            self.graph.add_node(
                dev_node,
                node_type="DEVICE",
                entity_id=device_id,
                user_agent=user_agent,
                is_headless=is_headless,
                is_emulator=is_emulator,
                first_seen=now,
                last_seen=now,
            )
            self._creation_times[dev_node] = now
        else:
            self.graph.nodes[dev_node]["last_seen"] = now

        # Node: IP
        ip_node = f"ip:{ip_address}"
        if not self.graph.has_node(ip_node):
            self.graph.add_node(
                ip_node,
                node_type="IP",
                entity_id=ip_address,
                is_proxy=is_proxy,
                reputation=ip_reputation,
                first_seen=now,
                last_seen=now,
            )
            self._creation_times[ip_node] = now
        else:
            self.graph.nodes[ip_node]["last_seen"] = now

        # Node: CARD_TOKEN
        card_node = f"card:{card_hash}"
        if not self.graph.has_node(card_node):
            self.graph.add_node(
                card_node,
                node_type="CARD_TOKEN",
                entity_id=card_hash,
                bin=card_bin,
                last4=card_last4,
                first_seen=now,
                last_seen=now,
            )
            self._creation_times[card_node] = now
        else:
            self.graph.nodes[card_node]["last_seen"] = now

        # Node: TRANSACTION
        tx_node = f"tx:{transaction_id}"
        self.graph.add_node(
            tx_node,
            node_type="TRANSACTION",
            entity_id=transaction_id,
            amount=amount,
            currency=currency,
            status=status,
            risk_score=risk_score if risk_score is not None else 0.0,
            timestamp=now,
        )
        self._creation_times[tx_node] = now

        # Node: MERCHANT
        mer_node = f"mer:{merchant_id}"
        if not self.graph.has_node(mer_node):
            self.graph.add_node(
                mer_node,
                node_type="MERCHANT",
                entity_id=merchant_id,
                first_seen=now,
                last_seen=now,
            )
            self._creation_times[mer_node] = now
        else:
            self.graph.nodes[mer_node]["last_seen"] = now

        # 3. Add / Update Edges
        self._add_or_update_edge(acc_node, dev_node, edge_type="USED_DEVICE", now=now)
        self._add_or_update_edge(acc_node, ip_node, edge_type="USED_IP", now=now)
        self._add_or_update_edge(acc_node, card_node, edge_type="LINKED_CARD", now=now)
        self._add_or_update_edge(acc_node, tx_node, edge_type="INITIATED_TRANSACTION", now=now)

        self._add_or_update_edge(dev_node, ip_node, edge_type="OBSERVED_ON_IP", now=now)
        self._add_or_update_edge(dev_node, tx_node, edge_type="TRANSACTED_ON_DEVICE", now=now)

        self._add_or_update_edge(ip_node, tx_node, edge_type="ROUTED_THROUGH_IP", now=now)
        self._add_or_update_edge(card_node, tx_node, edge_type="FUNDED_TRANSACTION", now=now)
        self._add_or_update_edge(tx_node, mer_node, edge_type="PROCESSED_AT_MERCHANT", now=now)

        # 4. Prune if exceeds max nodes
        if len(self.graph) > self.max_nodes:
            self._evict_oldest_nodes(evict_count=100)

    def _add_or_update_edge(
        self,
        u: str,
        v: str,
        edge_type: str,
        now: datetime.datetime,
    ) -> None:
        """Adds or updates an attributed edge between two nodes with frequency and timestamp history."""
        if not self.graph.has_edge(u, v):
            self.graph.add_edge(
                u,
                v,
                edge_type=edge_type,
                weight=1.0,
                count=1,
                first_seen=now,
                last_seen=now,
            )
        else:
            edge_data = self.graph[u][v]
            edge_data["count"] += 1
            edge_data["weight"] += 1.0
            edge_data["last_seen"] = now

    def _evict_oldest_nodes(self, evict_count: int = 100) -> None:
        """Removes oldest transaction nodes to maintain rolling window memory bounded performance."""
        tx_nodes = [
            (node, self._creation_times.get(node, datetime.datetime.min))
            for node in self.graph.nodes
            if self.graph.nodes[node].get("node_type") == "TRANSACTION"
        ]
        tx_nodes.sort(key=lambda x: x[1])
        to_remove = [node for node, _ in tx_nodes[:evict_count]]
        for node in to_remove:
            self.graph.remove_node(node)
            self._creation_times.pop(node, None)

    def get_subgraph_around_entity(self, entity_id: str, radius: int = 2) -> nx.Graph:
        """Extracts ego subgraph around entity within specified hop radius."""
        # Find matching node (handles prefix or raw ID)
        matched_node = None
        for prefix in ("acc:", "dev:", "ip:", "card:", "tx:", "mer:"):
            candidate = f"{prefix}{entity_id}"
            if self.graph.has_node(candidate):
                matched_node = candidate
                break

        if not matched_node:
            if self.graph.has_node(entity_id):
                matched_node = entity_id
            else:
                return nx.Graph()

        nodes = nx.single_source_shortest_path_length(self.graph, matched_node, cutoff=radius).keys()
        return self.graph.subgraph(nodes).copy()

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def clear(self) -> None:
        self.graph.clear()
        self._creation_times.clear()
