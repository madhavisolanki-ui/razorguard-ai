"""Relational Graph Feature Extraction Engine."""

from typing import Dict, Any, List, Optional, Set
import networkx as nx
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("graph_features")


class GraphFeatures(BaseModel):
    """Pydantic model containing relational graph topological and neighborhood features."""
    user_id: str
    device_id: str
    ip_address: str
    card_hash: Optional[str] = None
    
    # Direct degree features
    accounts_per_device: int = 1
    accounts_per_ip: int = 1
    devices_per_account: int = 1
    ips_per_account: int = 1
    shared_card_accounts: int = 1
    
    # Shared entity overlap counts
    shared_device_count: int = 0
    shared_ip_count: int = 0
    
    # Transaction counts on infrastructure
    transactions_per_device: int = 1
    transactions_per_ip: int = 1
    
    # Subgraph neighborhood & cluster metrics
    neighbourhood_size: int = 1
    suspicious_neighbour_count: int = 0
    cluster_size: int = 1
    cluster_density: float = 0.0
    connection_frequency: float = 1.0
    multi_hop_relationship_count: int = 0


class GraphFeatureExtractor:
    """Computes relational multi-hop topological features from the entity graph."""

    def __init__(self, graph: nx.Graph):
        self.graph = graph

    def extract_features(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        card_hash: Optional[str] = None,
    ) -> GraphFeatures:
        """Extracts relational graph metrics around an active payment transaction's entities."""
        acc_node = f"acc:{user_id}"
        dev_node = f"dev:{device_id}"
        ip_node = f"ip:{ip_address}"
        card_node = f"card:{card_hash}" if card_hash else None

        # 1. Direct Neighbor Counts
        accounts_on_dev = self._get_typed_neighbors(dev_node, "ACCOUNT")
        accounts_on_ip = self._get_typed_neighbors(ip_node, "ACCOUNT")
        devices_on_acc = self._get_typed_neighbors(acc_node, "DEVICE")
        ips_on_acc = self._get_typed_neighbors(acc_node, "IP")
        accounts_on_card = self._get_typed_neighbors(card_node, "ACCOUNT") if card_node else []

        acc_per_dev = max(1, len(accounts_on_dev))
        acc_per_ip = max(1, len(accounts_on_ip))
        dev_per_acc = max(1, len(devices_on_acc))
        ip_per_acc = max(1, len(ips_on_acc))
        shared_card = max(1, len(accounts_on_card))

        shared_dev_count = max(0, acc_per_dev - 1)
        shared_ip_count = max(0, acc_per_ip - 1)

        # 2. Transaction Activity on Hardware / Network
        txs_on_dev = len(self._get_typed_neighbors(dev_node, "TRANSACTION"))
        txs_on_ip = len(self._get_typed_neighbors(ip_node, "TRANSACTION"))

        # 3. Neighborhood & Component Metrics
        if self.graph.has_node(acc_node):
            # Connected component
            try:
                component = nx.node_connected_component(self.graph, acc_node)
                cluster_size = len(component)
                subgraph = self.graph.subgraph(component)
                cluster_density = round(float(nx.density(subgraph)), 3)
            except Exception:
                cluster_size = 1
                cluster_density = 0.0

            # 2-hop neighborhood size
            try:
                nbrs_2hop = set(nx.single_source_shortest_path_length(self.graph, acc_node, cutoff=2).keys())
                neighbourhood_size = len(nbrs_2hop)
            except Exception:
                neighbourhood_size = 1

            # Multi-hop relationships (other accounts reachable within 2 hops)
            other_accounts_in_2hop = [
                n for n in nbrs_2hop
                if n.startswith("acc:") and n != acc_node
            ]
            multi_hop_count = len(other_accounts_in_2hop)

            # Suspicious neighbor count (high-risk transactions or proxy IPs in neighborhood)
            suspicious_count = 0
            for n in nbrs_2hop:
                data = self.graph.nodes.get(n, {})
                if data.get("node_type") == "TRANSACTION" and data.get("risk_score", 0.0) >= 65.0:
                    suspicious_count += 1
                elif data.get("node_type") == "IP" and data.get("is_proxy", False):
                    suspicious_count += 1
                elif data.get("node_type") == "DEVICE" and data.get("is_headless", False):
                    suspicious_count += 1
        else:
            cluster_size = 1
            cluster_density = 0.0
            neighbourhood_size = 1
            multi_hop_count = 0
            suspicious_count = 0

        # Connection frequency (average edge count on active user edges)
        conn_freq = 1.0
        if self.graph.has_node(acc_node):
            edges = self.graph.edges(acc_node, data=True)
            if edges:
                weights = [d.get("count", 1) for _, _, d in edges]
                conn_freq = round(float(sum(weights) / len(weights)), 2)

        return GraphFeatures(
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            card_hash=card_hash,
            accounts_per_device=acc_per_dev,
            accounts_per_ip=acc_per_ip,
            devices_per_account=dev_per_acc,
            ips_per_account=ip_per_acc,
            shared_card_accounts=shared_card,
            shared_device_count=shared_dev_count,
            shared_ip_count=shared_ip_count,
            transactions_per_device=max(1, txs_on_dev),
            transactions_per_ip=max(1, txs_on_ip),
            neighbourhood_size=neighbourhood_size,
            suspicious_neighbour_count=suspicious_count,
            cluster_size=cluster_size,
            cluster_density=cluster_density,
            connection_frequency=conn_freq,
            multi_hop_relationship_count=multi_hop_count,
        )

    def _get_typed_neighbors(self, node_id: Optional[str], target_type: str) -> List[str]:
        """Returns neighbor node IDs matching the specified node_type."""
        if not node_id or not self.graph.has_node(node_id):
            return []
        return [
            nbr for nbr in self.graph.neighbors(node_id)
            if self.graph.nodes[nbr].get("node_type") == target_type
        ]
