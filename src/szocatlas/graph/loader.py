"""GRAPH IMPORT: canonical release -> Neo4j (idempotent upsert).

The release directory is the source of truth; Neo4j is a disposable projection that
can be rebuilt from it at any time. Loading the same release twice leaves the graph
unchanged: nodes MERGE on canonical_id, relationships MERGE on relation_id, claims on
claim_id, documents on document_id.

What becomes a node vs a property (docs/neo4j.md):
* nodes: things people traverse to or between (Person, Institution, OrgUnit,
  ResearchGroup, Project, Topic, Method, Tradition, Event, Journal, Publication) and
  provenance objects (Claim, SourceDocument), so "why do we believe this edge?" is a
  graph query;
* properties: descriptive attributes (names, ids, titles, dates) and edge
  qualifiers (position title, role, validity interval, epistemic status);
* JSON-string properties: nested structures nobody filters on in Cypher
  (field-level provenance, conflicts).

Person mentions (ADR-0006) are evidence, not entities: they are loaded as
``:PersonMention`` nodes WITHOUT the ``:Entity`` label, with
``(:PersonMention)-[:RESOLVES_TO]->(:Person)`` for resolved ones and
``(:PersonMention)-[:MENTIONED_IN {relation, role}]->(target)`` for the context the page
states. Analytical queries match ``:Person`` / ``:Entity`` and never see them.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

from ..models.enums import EntityType, RelationType
from ..normalize.names import strip_accents

LABELS: dict[str, list[str]] = {
    EntityType.PERSON.value: ["Person"],
    EntityType.INSTITUTION.value: ["Institution"],
    EntityType.ORG_UNIT.value: ["OrgUnit"],
    EntityType.RESEARCH_GROUP.value: ["OrgUnit", "ResearchGroup"],
    EntityType.PROJECT.value: ["Project"],
    EntityType.PUBLICATION.value: ["Publication"],
    EntityType.JOURNAL.value: ["Journal"],
    EntityType.TOPIC.value: ["Topic"],
    EntityType.METHOD.value: ["Method"],
    EntityType.TRADITION.value: ["Tradition"],
    EntityType.EVENT.value: ["Event"],
}
NESTED = {"provenance", "conflicts"}
MENTION_FILE = EntityType.PERSON_MENTION.value
MENTION_REL_TYPES = ("RESOLVES_TO", "MENTIONED_IN")  # evidence layer only, never in relations.jsonl
MENTION_NESTED = NESTED | {"context", "resolution", "stated_identifiers"}
BATCH = 500


def _year(v: str | None) -> int | None:
    return int(v[:4]) if v else None


def _prop(v: Any) -> Any:
    """Neo4j properties are scalars or homogeneous lists of scalars."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
        return v
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def _read_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def node_rows(release: Path) -> dict[tuple[str, ...], list[dict]]:
    """labels -> [{canonical_id, props}] for every entity file in the release."""
    out: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for f in sorted((release / "entities").glob("*.jsonl")):
        etype = f.stem
        if etype == MENTION_FILE:
            continue  # evidence layer, see mention_rows()
        labels = tuple(["Entity", *LABELS[etype]])
        for row in _read_jsonl(f):
            props = {k: _prop(v) for k, v in row.items() if k not in NESTED}
            props["entity_type"] = etype
            props["provenance_json"] = json.dumps(row.get("provenance", {}), ensure_ascii=False, sort_keys=True)
            props["conflicts_json"] = json.dumps(row.get("conflicts", {}), ensure_ascii=False, sort_keys=True)
            props["has_conflicts"] = bool(row.get("conflicts"))
            names = [row.get("label", "")] + list(row.get("alternate_names", []) or [])
            props["search_text"] = " ".join(strip_accents(n).lower() for n in names if n)
            out[labels].append({"canonical_id": row["canonical_id"], "props": props})
    return out


def edge_rows(release: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in _read_jsonl(release / "relations.jsonl"):
        rtype = RelationType(row["type"]).value  # validates: only enum values reach Cypher
        props = {k: _prop(v) for k, v in row.items() if k not in ("qualifiers", "source_id", "target_id", "type")}
        for k, v in (row.get("qualifiers") or {}).items():
            props[k] = _prop(v)
        props["from_year"] = _year(row.get("valid_from"))
        props["until_year"] = _year(row.get("valid_until"))
        props["first_observed_year"] = _year(row.get("first_observed_at"))
        props["last_observed_year"] = _year(row.get("last_observed_at"))
        props["observed"] = row["epistemic_status"] == "OBSERVED"
        out[rtype].append({"source": row["source_id"], "target": row["target_id"],
                           "relation_id": row["relation_id"], "props": props})
    return out


def mention_rows(release: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """(mention nodes, RESOLVES_TO rows, MENTIONED_IN rows) from entities/PersonMention.jsonl."""
    nodes, resolves, contexts = [], [], []
    for row in _read_jsonl(release / "entities" / f"{MENTION_FILE}.jsonl"):
        res = row["resolution"]
        props = {k: _prop(v) for k, v in row.items() if k not in MENTION_NESTED}
        props["resolution_status"] = res["status"]
        props["resolved_to"] = res.get("person_id")
        props["provenance_json"] = json.dumps(row.get("provenance", {}), ensure_ascii=False, sort_keys=True)
        props["context_json"] = json.dumps(row.get("context", []), ensure_ascii=False, sort_keys=True)
        props["resolution_json"] = json.dumps(res, ensure_ascii=False, sort_keys=True, default=str)
        props["entity_type"] = MENTION_FILE
        props["search_text"] = strip_accents(row.get("stated_name", "")).lower()
        nodes.append({"canonical_id": row["canonical_id"], "props": props})
        if res.get("person_id"):
            resolves.append({"source": row["canonical_id"], "target": res["person_id"],
                             "props": {"status": res["status"], "method": res.get("method"),
                                       "decision_source": res.get("decision_source"),
                                       "decided_at": _prop(res.get("decided_at")),
                                       "signals_json": json.dumps(res.get("signals", {}), ensure_ascii=False,
                                                                  sort_keys=True)}})
        for cx in row.get("context", []):
            if not cx.get("target_id"):
                continue
            q = cx.get("qualifiers") or {}
            contexts.append({"source": row["canonical_id"], "target": cx["target_id"],
                             "relation": RelationType(cx["relation"]).value,
                             "props": {"relation": cx["relation"], "direction": cx.get("direction", "out"),
                                       "role": _prop(q.get("role")), "snippet": cx.get("snippet", ""),
                                       "claim_ids": cx.get("claim_ids", [])}})
    return nodes, resolves, contexts


def claim_rows(release: Path) -> tuple[list[dict], list[dict]]:
    docs = [{"document_id": d["document_id"], "props": {k: _prop(v) for k, v in d.items()}}
            for d in _read_jsonl(release / "documents.jsonl")]
    claims = []
    for c in _read_jsonl(release / "claims.jsonl"):
        ev = c["evidence"]
        claims.append({
            "claim_id": c["claim_id"],
            "document_id": ev["document_id"],
            "props": {
                "predicate": c["predicate"],
                "value": _prop(c.get("value")),
                "snippet": ev["snippet"],
                "locator": ev["locator"],
                "confidence": c["confidence"],
                "epistemic_status": c["epistemic_status"],
                "assertion_type": c.get("assertion_type"),
                "extraction_method": c["extraction_method"],
                "parser": c["parser"],
                "parser_version": c["parser_version"],
                "derivation_method": c.get("derivation_method"),
                "review_status": c["review_status"],
                "observed_at": c["observed_at"],
            },
        })
    return docs, claims


def claim_subjects(release: Path) -> list[dict]:
    """claim -> canonical entity it is about (via the entities' provenance maps)."""
    rows = []
    for f in sorted((release / "entities").glob("*.jsonl")):
        for e in _read_jsonl(f):
            for fieldname, ids in (e.get("provenance") or {}).items():
                rows += [{"claim_id": i, "canonical_id": e["canonical_id"], "field": fieldname} for i in ids]
    return rows


class Session(Protocol):
    def run(self, query: str, **params: Any) -> Any: ...


def _batches(rows: list[dict]):
    for i in range(0, len(rows), BATCH):
        yield rows[i : i + BATCH]


def load_release(session: Session, release: Path, *, prune: bool = False) -> dict[str, int]:
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    rid = manifest["release_id"]
    stats: dict[str, int] = defaultdict(int)

    for stmt in resources.files("szocatlas.graph").joinpath("cypher/constraints.cypher").read_text().split(";"):
        lines = [ln for ln in stmt.splitlines() if ln.strip() and not ln.strip().startswith("//")]
        if lines:
            session.run("\n".join(lines))

    for labels, rows in node_rows(release).items():
        label_str = ":".join(labels)  # from LABELS constant, never from data
        for b in _batches(rows):
            session.run(
                f"UNWIND $rows AS row MERGE (n:Entity {{canonical_id: row.canonical_id}}) "
                f"SET n:{label_str} SET n += row.props SET n.release_id = $rid",
                rows=b, rid=rid,
            )
            stats["nodes"] += len(b)

    for rtype, rows in edge_rows(release).items():
        for b in _batches(rows):
            session.run(
                "UNWIND $rows AS row "
                "MATCH (a:Entity {canonical_id: row.source}), (b:Entity {canonical_id: row.target}) "
                f"MERGE (a)-[r:{rtype} {{relation_id: row.relation_id}}]->(b) "
                "SET r += row.props SET r.release_id = $rid",
                rows=b, rid=rid,
            )
            stats["relationships"] += len(b)

    m_nodes, m_resolves, m_contexts = mention_rows(release)
    for b in _batches(m_nodes):
        session.run("UNWIND $rows AS row MERGE (m:PersonMention {canonical_id: row.canonical_id}) "
                    "SET m += row.props SET m.release_id = $rid", rows=b, rid=rid)
        stats["mentions"] += len(b)
    for b in _batches(m_resolves):
        session.run("UNWIND $rows AS row MATCH (m:PersonMention {canonical_id: row.source}), "
                    "(p:Person {canonical_id: row.target}) MERGE (m)-[r:RESOLVES_TO]->(p) "
                    "SET r += row.props SET r.release_id = $rid", rows=b, rid=rid)
        stats["resolves_to"] += len(b)
    for b in _batches(m_contexts):
        session.run("UNWIND $rows AS row MATCH (m:PersonMention {canonical_id: row.source}), "
                    "(t:Entity {canonical_id: row.target}) "
                    "MERGE (m)-[r:MENTIONED_IN {relation: row.relation}]->(t) "
                    "SET r += row.props SET r.release_id = $rid", rows=b, rid=rid)
        stats["mentioned_in"] += len(b)

    docs, claims = claim_rows(release)
    for b in _batches(docs):
        session.run("UNWIND $rows AS row MERGE (s:SourceDocument {document_id: row.document_id}) "
                    "SET s += row.props SET s.release_id = $rid", rows=b, rid=rid)
        stats["documents"] += len(b)
    for b in _batches(claims):
        session.run(
            "UNWIND $rows AS row MERGE (c:Claim {claim_id: row.claim_id}) SET c += row.props "
            "SET c.release_id = $rid WITH c, row "
            "MATCH (s:SourceDocument {document_id: row.document_id}) MERGE (c)-[:SUPPORTED_BY]->(s)",
            rows=b, rid=rid,
        )
        stats["claims"] += len(b)
    for b in _batches(claim_subjects(release)):
        session.run(
            "UNWIND $rows AS row MATCH (c:Claim {claim_id: row.claim_id}), "
            "(n:Entity {canonical_id: row.canonical_id}) MERGE (c)-[a:ABOUT]->(n) SET a.field = row.field",
            rows=b,
        )
    if prune:
        session.run("MATCH ()-[r]->() WHERE r.release_id IS NOT NULL AND r.release_id <> $rid DELETE r", rid=rid)
        session.run("MATCH (n) WHERE (n:Entity OR n:PersonMention OR n:Claim OR n:SourceDocument) "
                    "AND n.release_id <> $rid "
                    "DETACH DELETE n", rid=rid)
    session.run("MERGE (m:ReleaseInfo {key: 'current'}) SET m += $m",
                m={k: _prop(v) for k, v in manifest.items()})
    return dict(stats)


def load_release_from_env(release: Path, *, prune: bool = False) -> dict[str, int]:
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
        database=os.environ.get("NEO4J_DATABASE", "neo4j")
    ) as session:
        return load_release(session, release, prune=prune)
