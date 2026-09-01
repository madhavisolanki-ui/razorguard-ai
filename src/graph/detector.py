"""Fraud Ring & Syndicate Detection Algorithm Engine using NetworkX."""

from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx
from pydantic import BaseModel, Field

from src.core.config import settings
from src.graph.features import GraphFeatures
from src.core.logging import get_logger

logger = get_logger("graph_detector")


class RingDetectionResult(BaseModel):
    """Encapsulates fraud ring and syndicate network detection findings."""
    is_fraud_ring: bool = False
    is_legitimate_shared_infra: bool = False
    ring_type: Optional[str] = None
    confidence_score: float = 0.0
    cluster_id: str = "cluster_none"
    cluster_size: int = 1
    cluster_density: float = 0.0
    detected_cycles: List[List[str]] = Field(default_factory=list)
    suspicious_entities: List[str] = Field(default_factory=list)
    triggered_graph_signals: List[str] = Field(default_factory=list)
    mitigating_factors: List[str] = Field(default_factory=list)
    explanation: str = "No suspicious graph syndicate patterns detected."


class FraudRingDetector:
    """Detects multi-entity fraud rings, synthetic identity syndicates, and distinguishes
    them from legitimate shared infrastructure (university NATs, corporate VPNs, family devices)."""

    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.config = settings.RULES.graph

    def detect(self, features: GraphFeatures) -> RingDetectionResult:
        """Executes multi-entity graph algorithms across ego networks and connected components."""
        acc_node = f"acc:{features.user_id}"
        dev_node = f"dev:{features.device_id}"
        ip_node = f"ip:{features.ip_address}"
        card_node = f"card:{features.card_hash}" if features.card_hash else None

        signals = []
        mitigations = []
        suspicious_entities = []
        detected_cycles = []
        is_fraud_ring = False
        is_legitimate_shared = False
        ring_type = None
        confidence = 0.0

        # Extract Connected Component for Cluster ID and Size
        cluster_id = f"cl_{features.user_id[:8]}"
        cluster_size = features.cluster_size
        cluster_density = features.cluster_density

        comp_nodes = []
        if self.graph.has_node(acc_node):
            try:
                comp = nx.node_connected_component(self.graph, acc_node)
                comp_nodes = list(comp)
                sorted_nodes = sorted(comp_nodes)
                cluster_id = f"cl_{hash(tuple(sorted_nodes[:5])) & 0xffffffff:08x}"
                cluster_size = len(comp)
                subgraph = self.graph.subgraph(comp)
                cluster_density = round(float(nx.density(subgraph)), 3)
            except Exception:
                pass

        # -------------------------------------------------------------
        # 1. Pattern: Shared Payment Card Syndicate
        # -------------------------------------------------------------
        if card_node and self.graph.has_node(card_node):
            linked_accounts = [
                n for n in self.graph.neighbors(card_node)
                if self.graph.nodes[n].get("node_type") == "ACCOUNT"
            ]
            if len(linked_accounts) >= self.config.max_shared_card_accounts:
                is_fraud_ring = True
                ring_type = "SHARED_PAYMENT_CARD_SYNDICATE"
                confidence = max(confidence, 0.90)
                signals.append(f"SHARED_CARD_ACROSS_{len(linked_accounts)}_ACCOUNTS")
                suspicious_entities.extend(linked_accounts)
                suspicious_entities.append(card_node)

        # -------------------------------------------------------------
        # 2. Pattern: Device Farm / Hardware Pooling
        # -------------------------------------------------------------
        if self.graph.has_node(dev_node):
            accounts_on_dev = [
                n for n in self.graph.neighbors(dev_node)
                if self.graph.nodes[n].get("node_type") == "ACCOUNT"
            ]
            if len(accounts_on_dev) >= self.config.max_accounts_per_device:
                is_fraud_ring = True
                ring_type = ring_type or "DEVICE_FARM_SYNDICATE"
                confidence = max(confidence, 0.85)
                signals.append(f"DEVICE_FARM_OVER_{len(accounts_on_dev)}_ACCOUNTS")
                suspicious_entities.extend(accounts_on_dev)
                suspicious_entities.append(dev_node)

        # -------------------------------------------------------------
        # 3. Pattern: Shared IP vs. Legitimate Campus/Corporate NAT
        # -------------------------------------------------------------
        if self.graph.has_node(ip_node):
            accounts_on_ip = [
                n for n in self.graph.neighbors(ip_node)
                if self.graph.nodes[n].get("node_type") == "ACCOUNT"
            ]
            devices_on_ip = [
                n for n in self.graph.neighbors(ip_node)
                if self.graph.nodes[n].get("node_type") == "DEVICE"
            ]
            ip_data = self.graph.nodes[ip_node]
            is_proxy = bool(ip_data.get("is_proxy", False))
            reputation = float(ip_data.get("reputation", 1.0))

            if len(accounts_on_ip) >= self.config.max_accounts_per_ip:
                # Distinguish Legitimate Campus/Corporate NAT vs. Botnet Proxy Swarm
                # If high device diversity, clean IP reputation, and NO shared payment cards -> Campus NAT
                is_high_entropy_nat = (
                    len(devices_on_ip) >= 4 and
                    not is_proxy and
                    reputation >= 0.70 and
                    features.shared_card_accounts <= 1
                )

                if is_high_entropy_nat:
                    is_legitimate_shared = True
                    mitigations.append(f"LEGITIMATE_CAMPUS_OR_CORPORATE_NAT ({len(devices_on_ip)} diverse clean devices)")
                else:
                    is_fraud_ring = True
                    ring_type = ring_type or "COORDINATED_PROXY_SWARM"
                    confidence = max(confidence, 0.80)
                    signals.append(f"SUSPICIOUS_IP_CONCENTRATION_{len(accounts_on_ip)}_ACCOUNTS")
                    suspicious_entities.extend(accounts_on_ip)
                    suspicious_entities.append(ip_node)

        # -------------------------------------------------------------
        # 4. Pattern: Multi-Hop Closed Cycle & Bridge Detection (Graph Rings)
        # -------------------------------------------------------------
        if comp_nodes:
            try:
                sub = self.graph.subgraph(comp_nodes)
                cycles = nx.cycle_basis(sub)
                for cyc in cycles:
                    acc_nodes_in_cyc = [n for n in cyc if n.startswith("acc:")]
                    card_or_dev_in_cyc = [n for n in cyc if n.startswith("card:") or n.startswith("dev:")]

                    if len(acc_nodes_in_cyc) >= 2 and len(card_or_dev_in_cyc) >= 1:
                        is_fraud_ring = True
                        ring_type = ring_type or "MULTI_HOP_SYNDICATE_RING"
                        confidence = max(confidence, 0.95)
                        detected_cycles.append(cyc)
                        signals.append(f"CLOSED_SYNDICATE_CYCLE_HOPS_{len(cyc)}")
                        suspicious_entities.extend(cyc)
            except Exception as e:
                logger.debug("Cycle computation error: %s", e)

        # -------------------------------------------------------------
        # 5. Pattern: Dense Suspicious Subgraphs
        # -------------------------------------------------------------
        acc_count = len([n for n in comp_nodes if n.startswith("acc:")])
        if cluster_size >= self.config.suspicious_cluster_min_size and cluster_density >= self.config.suspicious_cluster_density_threshold:
            if not is_legitimate_shared and (len(signals) > 0 or acc_count >= 4):
                signals.append(f"DENSE_SYNDICATE_CLUSTER (size={cluster_size}, accounts={acc_count}, density={cluster_density:.2f})")
                confidence = max(confidence, 0.85)

        # Deduplicate entities
        suspicious_entities = sorted(list(set(suspicious_entities)))

        # Build Explanation
        if is_fraud_ring:
            explanation = (
                f"Fraud Syndicate Detected [{ring_type}]: {', '.join(signals)}. "
                f"Cluster {cluster_id} contains {cluster_size} linked nodes across {len(suspicious_entities)} flagged entities."
            )
        elif is_legitimate_shared:
            explanation = (
                f"Legitimate Shared Infrastructure Verified: {', '.join(mitigations)}. "
                f"Shared IP connects {features.accounts_per_ip} users across diverse devices with zero card overlap."
            )
        else:
            explanation = "Normal isolated graph topology: No coordinated multi-entity relationships detected."

        return RingDetectionResult(
            is_fraud_ring=is_fraud_ring,
            is_legitimate_shared_infra=is_legitimate_shared,
            ring_type=ring_type,
            confidence_score=round(confidence, 2),
            cluster_id=cluster_id,
            cluster_size=cluster_size,
            cluster_density=cluster_density,
            detected_cycles=detected_cycles,
            suspicious_entities=suspicious_entities,
            triggered_graph_signals=signals,
            mitigating_factors=mitigations,
            explanation=explanation,
        )
