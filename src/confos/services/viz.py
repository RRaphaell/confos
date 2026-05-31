"""Co-authorship graph for a topic (``viz network``).

Builds an undirected co-authorship graph over the authors of topic-matching papers, caps
it to the most-connected nodes so it stays legible, and returns a source-neutral
dict the command renders as terminal / mermaid / html.
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from ..aliases import load_topic_aliases
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import papers as papers_repo
from ..fts import topic_query
from ..paths import Paths

_MATCH_CAP = 5000


def build_coauthor_graph(
    paths: Paths, topic: str, *, venue: str | None = None, max_nodes: int = 30
) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        fts = topic_query(topic, load_topic_aliases(paths))
        rows = papers_repo.search(conn, fts, venue=venue, limit=_MATCH_CAP)
        authors_by_paper = papers_repo.authors_for_papers(conn, [r["id"] for r in rows])
    finally:
        conn.close()

    graph: nx.Graph[str] = nx.Graph()
    labels: dict[str, str] = {}
    for briefs in authors_by_paper.values():
        ids = [b["author_id"] for b in briefs]
        for brief in briefs:
            labels[brief["author_id"]] = brief["raw_name"]
            graph.add_node(brief["author_id"])
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                graph.add_edge(ids[i], ids[j])

    truncated = graph.number_of_nodes() > max_nodes
    if truncated:
        kept = {n for n, _ in sorted(graph.degree, key=lambda d: (-d[1], d[0]))[:max_nodes]}
        graph = graph.subgraph(kept).copy()

    by_degree = sorted(graph.degree, key=lambda d: (-d[1], d[0]))  # (node, degree), deterministic
    nodes = [{"id": n, "label": labels.get(n, n), "degree": deg} for n, deg in by_degree]
    edges = sorted([sorted((a, b)) for a, b in graph.edges])
    return {
        "topic": topic,
        "venue": venue,
        "matched_papers": len(rows),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "truncated": truncated,
        "nodes": nodes,
        "edges": edges,
    }
