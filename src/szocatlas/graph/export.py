"""Portable exports of a release for the analysis layer (no database needed)."""

from __future__ import annotations

from pathlib import Path

from .loader import edge_rows, node_rows


def to_networkx(release: Path, *, observed_only: bool = True, relation_types: set[str] | None = None):
    """MultiDiGraph with node attrs (label, entity_type, ...) and edge attrs (type, status, ...).

    ``observed_only`` drops DERIVED/INFERRED/INTERPRETIVE edges so that structural
    metrics are computed on documented relations unless an analysis opts in.
    """
    import networkx as nx

    g = nx.MultiDiGraph(release=release.name)
    for _labels, rows in node_rows(release).items():
        for r in rows:
            g.add_node(r["canonical_id"], **{k: v for k, v in r["props"].items()
                                             if k in ("label", "entity_type", "key", "unit_type")})
    for rtype, rows in edge_rows(release).items():
        if relation_types and rtype not in relation_types:
            continue
        for r in rows:
            if observed_only and not r["props"]["observed"]:
                continue
            g.add_edge(r["source"], r["target"], key=r["relation_id"], type=rtype,
                       epistemic_status=r["props"]["epistemic_status"],
                       confidence=r["props"]["confidence"])
    return g
