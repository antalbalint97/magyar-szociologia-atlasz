"""A second, independent count of how the project edges of a release were identified (#17, #37).

validation/readiness.py decides, for every Person-Project edge, whether the Person was identified by evidence
that stands on its own or only by an automatic rule, and builds three versions of the edges from that. A join
on the wrong key there once understated the edges that rest on an automatic rule. This script recounts the
same figures from the files of a release with its own code and no import from szocatlas, so that the two can
disagree. It is a check, not a second source of truth.

    python research/analysis/identity_basis_recount.py data/releases/<release> [--json]

The rule is the one of docs/methodology.md section 9, applied to the claims:

* a claim made on a page is carried by at most one person mention record (``context[*].claim_ids``); a claim no
  mention carries was made on the subject's own profile page and is *anchored*;
* an edge (one PARTICIPATES_IN or PRINCIPAL_INVESTIGATOR_OF relation) is *certain* when one of its claims is
  anchored or carried by a deterministic or manually confirmed mention, and *automatic* when one is carried by a
  high-confidence automatic mention; ``auto_only`` is automatic and not certain;
* a *statement* is a distinct (Project, subject reference) and takes the strongest identification among its
  claims, in the order anchored, manually confirmed, deterministic, automatic, review, unresolved;
* versions of the edges: default (every edge), strict (every edge but ``auto_only``), complete (only Projects
  whose statements are all anchored, certain or automatic);
* a Person's institutes are the targets of its AFFILIATED_WITH relations; a tie is across institutes when the
  two sets are disjoint.

Every figure is an aggregate; no person is named.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_EDGES = ("PARTICIPATES_IN", "PRINCIPAL_INVESTIGATOR_OF")
STRONGEST_FIRST = ("anchored", "MANUAL_CONFIRMED", "DETERMINISTIC", "HIGH_CONFIDENCE_AUTO", "REVIEW_REQUIRED",
                   "UNRESOLVED")
CERTAIN = {"anchored", "MANUAL_CONFIRMED", "DETERMINISTIC"}
IN_GRAPH = CERTAIN | {"HIGH_CONFIDENCE_AUTO"}


def read(root: Path, name: str) -> list[dict]:
    path = root / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def strongest(statuses) -> str:
    return min(statuses, key=STRONGEST_FIRST.index)


def ties_of(edges: list[dict], institutes: dict[str, set[str]]) -> dict[str, int]:
    persons_by_project: dict[str, set[str]] = defaultdict(set)
    for r in edges:
        persons_by_project[r["target_id"]].add(r["source_id"])
    pairs = {frozenset(p) for ps in persons_by_project.values() for p in itertools.combinations(sorted(ps), 2)}
    across = sum(1 for p in pairs if institutes[min(p)].isdisjoint(institutes[max(p)]))
    return {"projects_with_person": len(persons_by_project),
            "projects_with_two_or_more": sum(1 for ps in persons_by_project.values() if len(ps) >= 2),
            "persons_with_edge": len({r["source_id"] for r in edges}), "ties": len(pairs),
            "persons_in_ties": len(set().union(*pairs)) if pairs else 0, "ties_across_institutes": across}


def recount(root: Path) -> dict:
    claims = {c["claim_id"]: c for c in read(root, "claims.jsonl")}
    persons = {p["canonical_id"] for p in read(root, "entities/Person.jsonl")}
    projects = {p["canonical_id"]: p for p in read(root, "entities/Project.jsonl")}
    relations = read(root, "relations.jsonl")
    edges = [r for r in relations if r["type"] in PROJECT_EDGES and r["source_id"] in persons]
    institutes: dict[str, set[str]] = defaultdict(set)
    for r in relations:
        if r["type"] == "AFFILIATED_WITH" and r["source_id"] in persons:
            institutes[r["source_id"]].add(r["target_id"])

    carried_by: dict[str, list[str]] = defaultdict(list)  # claim id -> statuses of the mention records carrying it
    for m in read(root, "entities/PersonMention.jsonl"):
        ids = {cid for ctx in m.get("context", []) for cid in ctx.get("claim_ids", [])}
        ids |= set((m.get("provenance") or {}).get("context", []))
        for cid in ids:
            carried_by[cid].append(m["resolution"]["status"])

    def basis(claim_id: str) -> str:
        return strongest(carried_by[claim_id]) if carried_by.get(claim_id) else "anchored"

    edge_basis: dict[str, str] = {}
    for r in edges:
        bases = {basis(cid) for cid in r["claim_ids"] if cid in claims}
        certain, auto = bool(bases & CERTAIN), "HIGH_CONFIDENCE_AUTO" in bases
        edge_basis[r["relation_id"]] = ("certain+auto" if certain and auto else "certain" if certain
                                        else "auto_only" if auto else "other")

    page_to_project = {ref: pid for pid, p in projects.items() for ref in p.get("source_refs", [])}
    statements: dict[tuple[str, str], list[str]] = defaultdict(list)
    for c in claims.values():
        if c["predicate"] not in PROJECT_EDGES:
            continue
        project = page_to_project.get((c.get("object") or {}).get("source_ref"))
        if project is not None:
            statements[(project, c["subject"]["source_ref"])].append(basis(c["claim_id"]))
    status = {key: strongest(v) for key, v in statements.items()}
    by_status = Counter(status.values())
    in_graph = sum(n for k, n in by_status.items() if k in IN_GRAPH)
    complete = {p for p in projects if any(k[0] == p for k in status)
                and all(s in IN_GRAPH for k, s in status.items() if k[0] == p)}

    return {
        "edges": len(edges),
        "edges_by_basis": dict(sorted(Counter(edge_basis.values()).items())),
        "statements": {"total": len(status), "by_status": dict(sorted(by_status.items())), "in_graph": in_graph,
                       "outside_graph": len(status) - in_graph},
        "versions": {
            "default": ties_of(edges, institutes),
            "strict_certain_edges_only": ties_of([r for r in edges if edge_basis[r["relation_id"]] != "auto_only"],
                                                 institutes),
            "complete_projects_only": ties_of([r for r in edges if r["target_id"] in complete], institutes),
        },
        "complete_projects": len(complete),
    }


def render(result: dict) -> str:
    st = result["statements"]
    lines = [f"edges {result['edges']}: " + ", ".join(f"{k} {n}" for k, n in result["edges_by_basis"].items()),
             f"statements {st['total']}: " + ", ".join(f"{k} {n}" for k, n in st["by_status"].items())
             + f"; in the graph {st['in_graph']}, outside {st['outside_graph']}",
             f"complete projects {result['complete_projects']}"]
    for name, v in result["versions"].items():
        lines.append(f"{name}: " + ", ".join(f"{k} {n}" for k, n in v.items()))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("release", type=Path, help="a release directory (data/releases/<id>)")
    ap.add_argument("--json", action="store_true", help="print the figures as JSON")
    args = ap.parse_args(argv)
    result = recount(args.release)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n" if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
