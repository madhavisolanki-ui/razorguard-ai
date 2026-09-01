"""Interactive NetworkX Fraud Graph Visualizer Component (Plotly)."""

import streamlit as st
import networkx as nx
import plotly.graph_objects as go
from src.graph.builder import FraudGraphBuilder


def render_graph_view():
    """Renders interactive 2D entity fraud graph for the active transaction or cluster."""
    txs = st.session_state.get("transactions", [])
    selected_id = st.session_state.get("selected_tx_id")
    builder: FraudGraphBuilder = st.session_state.get("graph_builder")

    st.subheader("🕸️ Multi-Entity Fraud Graph & Syndicate Analysis")
    st.caption("Visualizes relational topologies across Accounts, Payment Cards, Devices, IP Subnets, and Merchants to detect coordinated syndicates.")

    if not builder or builder.node_count == 0:
        st.info("The in-memory fraud graph is currently empty. Ingest events or run a syndicate scenario.")
        return

    # Extract ego subgraph around the selected transaction's account
    selected_record = next((t for t in txs if t["transaction_id"] == selected_id), None) if selected_id else None
    
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 2])
    with col_ctrl1:
        view_mode = st.radio("Graph View Scope:", ["Ego Subgraph (Selected Tx)", "Full Global Entity Graph"], horizontal=True)
    with col_ctrl2:
        hop_radius = st.slider("Hop Neighborhood Radius:", 1, 3, 2)
    with col_ctrl3:
        st.metric(label="Global Graph Scale", value=f"{builder.node_count} Nodes", delta=f"{builder.edge_count} Edges")

    # Determine graph to display
    if view_mode == "Ego Subgraph (Selected Tx)" and selected_record:
        user_id = selected_record["user_id"]
        graph_to_plot = builder.get_subgraph_around_entity(user_id, radius=hop_radius)
        if graph_to_plot.number_of_nodes() == 0:
            graph_to_plot = builder.graph
    else:
        # Sample or display full graph
        if builder.node_count > 60:
            # Take largest connected component for clear layout
            components = sorted(nx.connected_components(builder.graph), key=len, reverse=True)
            graph_to_plot = builder.graph.subgraph(components[0]).copy()
        else:
            graph_to_plot = builder.graph

    if graph_to_plot.number_of_nodes() == 0:
        st.warning("No nodes found for the selected entity.")
        return

    # 1. Compute Spring Layout
    pos = nx.spring_layout(graph_to_plot, k=0.45, iterations=40, seed=42)

    # 2. Extract Edges for Plotly
    edge_x = []
    edge_y = []
    for u, v in graph_to_plot.edges():
        if u in pos and v in pos:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1.5, color="#64748B"),
        hoverinfo="none",
        mode="lines",
    )

    # 3. Extract Nodes by Type
    node_colors = {
        "ACCOUNT": "#38BDF8",      # Sky Blue
        "CARD_TOKEN": "#F59E0B",   # Orange
        "DEVICE": "#A855F7",       # Purple
        "IP_ADDRESS": "#06B6D4",   # Cyan
        "TRANSACTION": "#EF4444",  # Red
        "MERCHANT": "#EAB308",     # Yellow
    }

    node_x = []
    node_y = []
    node_color_list = []
    node_text_list = []
    node_hover_list = []
    node_size_list = []

    for node in graph_to_plot.nodes():
        if node in pos:
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            data = graph_to_plot.nodes[node]
            ntype = data.get("node_type", "UNKNOWN")
            
            color = node_colors.get(ntype, "#94A3B8")
            if ntype == "TRANSACTION" and data.get("risk_score", 0) < 50:
                color = "#10B981"  # Green for safe transaction

            node_color_list.append(color)
            
            # Short label for display
            label = node.split(":")[-1][:8]
            node_text_list.append(f"{ntype[:3]}:{label}")
            
            # Detailed hover
            hover = f"<b>{ntype}</b><br>ID: {node}<br>Degree: {graph_to_plot.degree(node)}"
            if ntype == "TRANSACTION":
                hover += f"<br>Risk Score: {data.get('risk_score', 0)}/100<br>Amount: ₹{data.get('amount', 0):,.2f}"
            node_hover_list.append(hover)
            
            # Size
            size = 20 if ntype in ("ACCOUNT", "CARD_TOKEN", "DEVICE") else 15
            node_size_list.append(size)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text_list,
        textposition="top center",
        textfont=dict(size=9, color="#E2E8F0"),
        hoverinfo="text",
        hovertext=node_hover_list,
        marker=dict(
            showscale=False,
            color=node_color_list,
            size=node_size_list,
            line=dict(width=2, color="#0F172A"),
        ),
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title=f"<b>Relational Entity Topology ({graph_to_plot.number_of_nodes()} Entities, {graph_to_plot.number_of_edges()} Relations)</b>",
            title_font_size=15,
            showlegend=False,
            hovermode="closest",
            margin=dict(b=10, l=10, r=10, t=35),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=420,
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Graph Legend & Cluster Summary Metrics
    c_leg, c_stat = st.columns([3, 2])
    with c_leg:
        st.markdown(
            """
            **Legend:** 
            🔵 `Account` | 🟠 `Card Token` | 🟣 `Device Hardware` | 🔷 `IP Subnet` | 🟡 `Merchant` | 🔴 `Suspicious Tx` | 🟢 `Safe Tx`
            """
        )
    with c_stat:
        # Check if fraud ring is present in graph
        report = st.session_state.get("latest_investigation")
        if report and report.fraud_ring_detected:
            st.error(f"🚨 **Fraud Ring Detected:** Cluster `{report.cluster_id}` ({report.cluster_size} entities linked across shared payment credentials).")
        else:
            st.success("✅ **Graph Verdict:** No high-density syndicate ring detected for this entity.")
