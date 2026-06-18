import networkx as nx
from collections import defaultdict
from datetime import datetime, timezone, timedelta


def build_fraud_graph(flagged_transactions: list[dict]) -> dict:
    """
    Builds a NetworkX directed graph from flagged transactions.

    Edges form when two flagged users share suspicious co-patterns:
      - Same ring_id (explicit ring scenario)
      - Similar amount (within $200) AND same location within 5 minutes
      - Transactions within 3 minutes of each other regardless of location

    Returns a dict with:
      nodes  → list of {id, txn_count, total_amount}
      edges  → list of {source, target, reason}
      rings  → list of detected triangles (3-node cycles)
    """
    G = nx.DiGraph()

    if not flagged_transactions:
        return {"nodes": [], "edges": [], "rings": []}

    user_txns: dict[str, list[dict]] = defaultdict(list)
    for txn in flagged_transactions:
        uid = txn.get("user_id")
        if uid:
            user_txns[uid].append(txn)

    for uid, txns in user_txns.items():
        total = sum(t.get("amount_usd", 0) for t in txns)
        G.add_node(uid, txn_count=len(txns), total_amount=round(total, 2))

    users = list(user_txns.keys())

    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            u1, u2 = users[i], users[j]
            reason = _find_connection(user_txns[u1], user_txns[u2])
            if reason:
                G.add_edge(u1, u2, reason=reason)
                G.add_edge(u2, u1, reason=reason)

    rings = _detect_rings(G)

    return {
        "nodes": [
            {
                "id":           n,
                "txn_count":    G.nodes[n].get("txn_count", 0),
                "total_amount": G.nodes[n].get("total_amount", 0),
            }
            for n in G.nodes
        ],
        "edges": [
            {
                "source": u,
                "target": v,
                "reason": G[u][v].get("reason", ""),
            }
            for u, v in G.edges
        ],
        "rings": rings,
    }


def _parse_time(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _find_connection(txns1: list[dict], txns2: list[dict]) -> str | None:
    for t1 in txns1:
        for t2 in txns2:

            if t1.get("ring_id") and t1.get("ring_id") == t2.get("ring_id"):
                return f"Same ring ID: {t1['ring_id']}"

            a1 = t1.get("amount_usd", 0)
            a2 = t2.get("amount_usd", 0)
            same_loc = t1.get("location") == t2.get("location")

            tm1 = _parse_time(t1.get("timestamp"))
            tm2 = _parse_time(t2.get("timestamp"))

            if tm1 and tm2:
                diff_minutes = abs((tm1 - tm2).total_seconds()) / 60

                if abs(a1 - a2) <= 200 and same_loc and diff_minutes <= 5:
                    return (
                        f"Similar amounts (${a1:,.0f} / ${a2:,.0f}), "
                        f"same location ({t1.get('location')}), "
                        f"{diff_minutes:.1f} min apart"
                    )

                if diff_minutes <= 3:
                    return f"Transactions {diff_minutes:.1f} min apart — coordinated timing"

    return None


def _detect_rings(G: nx.DiGraph) -> list[list[str]]:
    """Returns list of 3-node cycles (money rings)."""
    undirected = G.to_undirected()
    rings = []
    for cycle in nx.simple_cycles(undirected):
        if len(cycle) == 3:
            rings.append(sorted(cycle))

    unique = [list(r) for r in {tuple(r) for r in rings}]
    return unique


def graph_to_pyvis_html(graph_data: dict) -> str:
    """Renders the NetworkX graph as a PyVis interactive HTML string."""
    try:
        from pyvis.network import Network

        net = Network(height="400px", width="100%", bgcolor="transparent",
                      font_color="#444441", directed=True)
        net.barnes_hut()

        ring_users: set[str] = set()
        for ring in graph_data.get("rings", []):
            ring_users.update(ring)

        for node in graph_data.get("nodes", []):
            uid   = node["id"]
            label = f"{uid}\n${node['total_amount']:,.0f}"
            color = "#E24B4A" if uid in ring_users else "#534AB7"
            net.add_node(uid, label=label, color=color,
                         title=f"Transactions: {node['txn_count']}\nTotal: ${node['total_amount']:,.2f}")

        for edge in graph_data.get("edges", []):
            net.add_edge(edge["source"], edge["target"],
                         title=edge["reason"], color="#888780")

        return net.generate_html()

    except ImportError:
        return "<p>PyVis not installed. Run: pip install pyvis</p>"