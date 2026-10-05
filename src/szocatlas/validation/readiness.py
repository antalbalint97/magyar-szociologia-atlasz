"""ANALYSIS READINESS: diagnostic indicators of whether a release is fit for exploratory network analysis (#17).

``quality_report`` says whether a release is consistent and ``coverage`` says how much of the sources it
holds. This module says what the structure of the graph can and cannot carry, so that an analyst knows
which artefacts to expect before computing anything.

It is a diagnostic, not a verdict:

* every indicator states its definition, its denominator and the analysis it threatens (``INDICATORS``);
  a value without them is not reported;
* there are no pass/fail thresholds here. Grades (READY / READY_WITH_RESTRICTIONS / NOT_READY) are a
  reviewed judgement in ``docs/analysis_readiness.md``, made from these numbers and from the sensitivity
  analysis in ``research/analysis/projection_sensitivity.py``, not computed;
* it reads a release directory and nothing else, so any earlier release can be measured with the same
  code and two releases can be compared;
* it writes no timestamp and no person-level ranking: the report of an unchanged release is byte-identical.

Layers: A person-institution/unit, B person-project (bipartite), C person-person co-participation
(a derived projection), D topics and methods, I identity (applies to all layers), T time.
"""

from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from ..normalize.names import name_key, order_free_key
from .coverage import share

PROJECT_EDGES = ("PARTICIPATES_IN", "PRINCIPAL_INVESTIGATOR_OF")
CERTAIN = ("DETERMINISTIC", "MANUAL_CONFIRMED")
AUTO = "HIGH_CONFIDENCE_AUTO"
OUTSIDE_GRAPH = ("REVIEW_REQUIRED", "UNRESOLVED")
ANCHORED = "anchored"  # a claim no PersonMention carries: made on its subject's own profile page, which anchors the Person
_STRONGEST_FIRST = (ANCHORED, "MANUAL_CONFIRMED", "DETERMINISTIC", AUTO, "REVIEW_REQUIRED", "UNRESOLVED")
LARGE_PROJECT_THRESHOLDS = (8, 9, 10)  # thresholds, not "the five largest": the fifth place is tied (#17)
SIZE_BUCKETS = ((1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 5, "4-5"), (6, 7, "6-7"), (8, 9, "8-9"), (10, 10**6, "10+"))

# id -> (layer, name, definition, denominator, what it threatens). Every value in the report carries these.
INDICATORS: dict[str, dict[str, str]] = {
    "A1": {"layer": "A", "name": "persons_with_affiliation",
           "definition": "profile-backed Persons with at least one AFFILIATED_WITH relation",
           "denominator": "profile-backed Persons per source (a person with two profiles counts on both sites)",
           "threatens": "any institutional composition or affiliation network"},
    "A2": {"layer": "A", "name": "persons_with_named_unit",
           "definition": "profile-backed Persons with a MEMBER_OF relation to a unit or group, not only to the institute",
           "denominator": "profile-backed Persons per source",
           "threatens": "unit-level composition, cross-unit ties and brokerage between units"},
    "A3": {"layer": "A", "name": "persons_with_position",
           "definition": "profile-backed Persons with at least one stated position title (a raw string, not normalised, #10)",
           "denominator": "profile-backed Persons per source",
           "threatens": "any comparison by position, seniority or staff status (external researchers have profiles too)"},
    "A4": {"layer": "A", "name": "units_in_hierarchy",
           "definition": "units and research groups whose PART_OF chain reaches an Institution",
           "denominator": "OrganisationalUnits and ResearchGroups",
           "threatens": "roll-ups from unit to institute; unit-level counts that double count a nested unit"},
    "B1": {"layer": "B", "name": "persons_with_project_edge",
           "definition": "profile-backed Persons with at least one PARTICIPATES_IN or PRINCIPAL_INVESTIGATOR_OF relation",
           "denominator": "profile-backed Persons per source",
           "threatens": "person-level degree and every projection: a person without an edge is an isolate by coverage"},
    "B2": {"layer": "B", "name": "projects_with_person_edge",
           "definition": "page-backed Projects with at least one / a PI / at least two Persons in the graph",
           "denominator": "canonical Projects per source of their page (the host serving the page URL)",
           "threatens": "project-level analysis; ties exist only where a project has two or more Persons in the graph"},
    "B3": {"layer": "B", "name": "project_participant_subjects",
           "definition": "distinct subjects (a profile link, an external profile link or a name) of lead / participant "
                         "claims about a project page, by how each was identified: anchored (the claim is made on the "
                         "subject's own profile page), certain mention, HIGH_CONFIDENCE_AUTO mention, or outside the "
                         "graph (REVIEW_REQUIRED, UNRESOLVED); a statement seen in several documents counts once, "
                         "with its strongest identification",
           "denominator": "distinct (project page, subject) pairs asserted in claims",
           "threatens": "participant counts and ties of any project whose list is partly outside the graph; "
                        "collaborators without a profile (former staff, outside partners) are missing"},
    "B4": {"layer": "B", "name": "edge_identity_basis",
           "definition": "project edges by how the Person was identified, read from the claims that make the edge "
                         "and the mentions that carry them: only by anchored or certain evidence, anchored plus an "
                         "automatic mention rule, or only by HIGH_CONFIDENCE_AUTO mentions (the relation itself is "
                         "OBSERVED in every case)",
           "denominator": "PARTICIPATES_IN and PRINCIPAL_INVESTIGATOR_OF relations",
           "threatens": "any analysis that treats all edges alike: edges resting on an automatic identity rule "
                        "must be switched on and off to see what depends on them"},
    "C1": {"layer": "C", "name": "co_participation_ties",
           "definition": "person pairs sharing at least one project (unweighted clique projection of the "
                         "bipartite graph; derived, never observed)",
           "denominator": "Persons with a project edge; Projects with at least two Persons",
           "threatens": "density, degree and component measures: a project of n persons adds n(n-1)/2 ties"},
    "C2": {"layer": "C", "name": "large_project_concentration",
           "definition": "for each threshold k: the Projects with k or more Persons, the ties that run through at "
                         "least one of them, the ties that exist only through them, and the Persons whose every tie "
                         "is only through them (they would be isolates without those projects)",
           "denominator": "co-participation ties; Persons with at least one tie",
           "threatens": "every tie-based measure: a few large projects can produce most of the structure"},
    "C3": {"layer": "C", "name": "tie_weights",
           "definition": "ties by the number of shared projects, and the total weight under size-discounted "
                         "weights (each shared project adds 1/(n-1) for n Persons)",
           "denominator": "co-participation ties",
           "threatens": "weighted degree and strength: unweighted and discounted weights rank Persons differently"},
    "C4": {"layer": "C", "name": "cross_institute",
           "definition": "ties between Persons who share no source institute (a Person with profiles on two sites "
                         "belongs to both), the Projects carrying at least one such tie, and the share of those ties "
                         "that run through the one project contributing most of them",
           "denominator": "co-participation ties; Projects with at least two Persons; cross-institute ties",
           "threatens": "claims about cross-institute collaboration or brokerage: the sample is four sites, and one "
                        "large project can be most of the cross-institute structure"},
    "C5": {"layer": "C", "name": "components",
           "definition": "connected components of the co-participation projection (Persons with at least one tie)",
           "denominator": "Persons with at least one tie",
           "threatens": "path-based measures (betweenness, closeness) and community detection"},
    "D1": {"layer": "D", "name": "persons_with_topic_or_method",
           "definition": "profile-backed Persons with a WORKS_ON_TOPIC / USES_METHOD relation",
           "denominator": "profile-backed Persons per source",
           "threatens": "topic or method comparisons between persons, units or institutes"},
    "D2": {"layer": "D", "name": "topic_basis",
           "definition": "topic and method relations by epistemic status and derivation method; topics with a BROADER "
                         "link; Persons that state a research area at all",
           "denominator": "WORKS_ON_TOPIC and USES_METHOD relations; ResearchTopics; profile-backed Persons",
           "threatens": "any substantive topic claim: the relations are keyword-map derivations of free text"},
    "I1": {"layer": "I", "name": "person_mentions",
           "definition": "person mentions by resolution status (a mention is one observation of a person-like record "
                         "in one page, ADR-0006: a name stated on a project page and again in a category listing is two "
                         "mentions; B3 counts statements), and the share of person-like nodes that would exist only as "
                         "an unresolved name (distinct names of UNRESOLVED mentions not equal to a canonical Person's "
                         "name, over canonical Persons plus those names)",
           "denominator": "person mentions per observing source; canonical Persons plus mention-only names",
           "threatens": "a name-based graph (pseudo-nodes), and every count of 'people' that mixes mentions with Persons"},
    "I2": {"layer": "I", "name": "duplicate_persons",
           "definition": "names (accent-folded, and order-free) carried by more than one canonical Person; "
                         "confirmed record merges; person mentions waiting for review and the Persons they are candidates for",
           "denominator": "canonical Persons",
           "threatens": "split identities: one real person appearing as two nodes halves their degree"},
    "I3": {"layer": "I", "name": "project_mentions",
           "definition": "project mentions by resolution status, mentions per canonical Project, and candidate "
                         "duplicate Projects (same grant id, same accent-folded title)",
           "denominator": "project mentions per observing source; canonical Projects",
           "threatens": "pseudo-projects and merged or split projects; a ratio far from 1 is not an error but a "
                        "statement of how much of the project layer is mentions"},
    "I4": {"layer": "I", "name": "activity_classification",
           "definition": "Projects carrying an activity type (research project, survey programme, network, journal...)",
           "denominator": "canonical Projects",
           "threatens": "any project-level analysis: programmes, journals and networks listed as projects are "
                        "counted as research projects (#9)"},
    "I5": {"layer": "I", "name": "edge_provenance",
           "definition": "relations by epistemic status per relation type, and the share supported by claims from "
                         "two or more documents",
           "denominator": "relations per type",
           "threatens": "mixing observed and derived relations in one measure; single-source edges"},
    "I6": {"layer": "I", "name": "orphans",
           "definition": "profile-backed Persons with no relation besides AFFILIATED_WITH / MEMBER_OF / LEADS / PART_OF",
           "denominator": "profile-backed Persons",
           "threatens": "isolates that are coverage gaps, not findings"},
    "T1": {"layer": "T", "name": "temporal_basis",
           "definition": "relations with an explicit start or end (valid_from / valid_until), and Projects with a start "
                         "date, by relation type",
           "denominator": "relations per type; canonical Projects",
           "threatens": "any longitudinal or period-specific claim: most relations are 'observed at crawl time'"},
}


# ------------------------------------------------------------------ loading
def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _status(mention: dict[str, Any]) -> str:
    return (mention.get("resolution") or {}).get("status", "UNKNOWN")


def _stronger(a: str | None, b: str) -> str:
    """The stronger of two identification statuses (a status outside ``_STRONGEST_FIRST`` ranks last)."""
    rank = lambda s: _STRONGEST_FIRST.index(s) if s in _STRONGEST_FIRST else len(_STRONGEST_FIRST)  # noqa: E731
    return b if a is None or rank(b) < rank(a) else a


class ReleaseData:
    """The files of one release directory, indexed once."""

    def __init__(self, root: Path, sources: list[str] | None = None, manifest: dict[str, Any] | None = None):
        self.root = root
        self.manifest = manifest if manifest is not None else (
            json.loads((root / "manifest.json").read_text(encoding="utf-8")) if (root / "manifest.json").exists() else {})
        ent = root / "entities"
        by_id = lambda name: {e["canonical_id"]: e for e in _rows(ent / f"{name}.jsonl")}  # noqa: E731
        self.persons, self.projects = by_id("Person"), by_id("Project")
        self.institutions = by_id("Institution")
        self.units = {**by_id("OrganisationalUnit"), **by_id("ResearchGroup")}
        self.topics, self.methods = by_id("ResearchTopic"), by_id("Method")
        self.person_mentions = _rows(ent / "PersonMention.jsonl")
        self.project_mentions = _rows(ent / "ProjectMention.jsonl")
        self.relations = _rows(root / "relations.jsonl")
        self.claims = _rows(root / "claims.jsonl")
        self.matches = _rows(root / "matches.jsonl")
        self.sources = sources or self.manifest.get("sources") or None
        self.by_type: dict[str, list[dict]] = defaultdict(list)
        for r in self.relations:
            self.by_type[r["type"]].append(r)
        # claim id -> the PersonMention that carries it (context[*].claim_ids). A claim no mention carries was made on
        # its subject's own profile page: the page anchors the Person and there is no decision to take. The join is on
        # the claim, never on the subject's source_ref: one ref (a profile link, an external profile) is shared by
        # mentions made in different documents, and their statuses can differ.
        self.claim_mention: dict[str, dict[str, Any]] = {}
        for m in self.person_mentions:
            for ctx in m.get("context", []):
                for cid in ctx.get("claim_ids", []):
                    held = self.claim_mention.get(cid)
                    if held is None or _stronger(_status(held), _status(m)) != _status(held):
                        self.claim_mention[cid] = m
        # the source an entity belongs to is the source whose host serves its page, as in coverage.py
        self.host_source: dict[str, str] = {}
        for d in _rows(root / "documents.jsonl"):
            if d["url"].startswith("repo://") or (self.sources is not None and d["source_id"] not in self.sources):
                continue
            self.host_source.setdefault((urlsplit(d["canonical_url"]).hostname or "").lower(), d["source_id"])
        self.person_sites = {pid: self._sites(p.get("profile_urls", [])) or {"other"} for pid, p in self.persons.items()}
        self.project_sites = {pid: self._sites([p["website"]] if p.get("website") else [])
                              or self._ref_sites(p) for pid, p in self.projects.items()}
        self.profiled = {pid for pid, p in self.persons.items()
                         if "institutional_profile" in p.get("identity_evidence", [])}
        self.source_ids = sorted({s for sites in self.person_sites.values() for s in sites}
                                 | {s for sites in self.project_sites.values() for s in sites})

    def _sites(self, urls: list[str]) -> set[str]:
        return {self.host_source[h] for u in urls if (h := (urlsplit(u).hostname or "").lower()) in self.host_source}

    def _ref_sites(self, entity: dict) -> set[str]:
        """Fallback for a Project without a page URL: the sources of its own references (not a mention's)."""
        out = set()
        for ref in entity.get("source_refs", []):
            sid, _, rest = ref.partition("|")
            if rest and "name-mention:" not in rest and not sid.startswith("external:") \
                    and (self.sources is None or sid in self.sources):
                out.add(sid)
        return out or {"other"}


def _by_source(universe: dict[str, set[str]], hit: set[str]) -> dict[str, Any]:
    """{source: share} plus ``all`` over distinct entities. ``universe`` maps entity id -> its sources."""
    out: dict[str, Any] = {}
    for sid in sorted({s for v in universe.values() for s in v}):
        ids = [i for i, v in universe.items() if sid in v]
        out[sid] = share(sum(1 for i in ids if i in hit), len(ids))
    out["all"] = share(sum(1 for i in universe if i in hit), len(universe))
    return out


# ------------------------------------------------------------------ the graph the measures are about
def _membership(rel: ReleaseData, edges: list[dict]) -> dict[str, set[str]]:
    """project id -> the Persons (ids) in the graph with a lead or participant edge to it."""
    mem: dict[str, set[str]] = defaultdict(set)
    for r in edges:
        if r["source_id"] in rel.persons and r["target_id"] in rel.projects:
            mem[r["target_id"]].add(r["source_id"])
    return dict(mem)


def _page_to_project(rel: ReleaseData) -> dict[str, str]:
    """Project page URL -> canonical Project id (a Project is page-backed: its source_refs are its pages)."""
    return {ref.partition("|")[2]: pid for pid, p in rel.projects.items() for ref in p.get("source_refs", [])}


def _carrier_status(rel: ReleaseData, claim_id: str) -> str:
    """How the subject of a claim was identified: ``anchored`` (the claim was made on the subject's own profile page)
    or the status of the PersonMention that carries it."""
    carrier = rel.claim_mention.get(claim_id)
    return _status(carrier) if carrier else ANCHORED


def _edge_basis(rel: ReleaseData) -> dict[str, str]:
    """relation_id -> 'certain' | 'certain+auto' | 'auto_only' | 'other' for the project edges.

    A claim is *certain* when its subject is anchored (made on the subject's own profile page) or its mention is
    DETERMINISTIC / MANUAL_CONFIRMED, *auto* when its mention is HIGH_CONFIDENCE_AUTO. The mention that carries a claim
    is found by the claim, not by the form of the subject's source_ref: a profile link or an external profile link
    can be an automatic identification too (a host alias that cannot be verified, ADR-0007). An edge rests on its
    claims, so one certain claim makes it certain; the relation is OBSERVED either way, the difference is how the
    Person was identified."""
    known = {c["claim_id"] for c in rel.claims}
    out: dict[str, str] = {}
    for r in rel.relations:
        if r["type"] not in PROJECT_EDGES:
            continue
        kinds = set()
        for cid in r["claim_ids"]:
            if cid not in known:
                continue
            st = _carrier_status(rel, cid)
            kinds.add("certain" if st == ANCHORED or st in CERTAIN else "auto" if st == AUTO else "other")
        out[r["relation_id"]] = ("certain+auto" if {"certain", "auto"} <= kinds else "certain" if "certain" in kinds
                                 else "auto_only" if "auto" in kinds else "other")
    return out


def _statements(rel: ReleaseData) -> dict[tuple[str, str], dict[str, Any]]:
    """(Project, subject) -> what the pages state: one entry per distinct lead / participant subject of a project page.

    ``status``: the strongest identification among the claims that state it (``anchored``, or the status of the
    mention carrying the claim; the same name seen in two documents is one statement). ``candidates``: person id ->
    candidate record (signals as recorded) for the viable candidates (not rejected, canonical) of the mentions that
    carry it. The subject is the claim's source_ref: a profile link, an external profile link, or a name on that page."""
    page_to_project = _page_to_project(rel)
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for c in rel.claims:
        if c["predicate"] not in PROJECT_EDGES:
            continue
        pid = page_to_project.get((c["object"].get("source_ref") or "").partition("|")[2])
        if pid is None:
            continue
        carrier = rel.claim_mention.get(c["claim_id"])
        item = out.setdefault((pid, c["subject"].get("source_ref") or ""), {"status": None, "candidates": {}})
        item["status"] = _stronger(item["status"], _status(carrier) if carrier else ANCHORED)
        for x in (carrier or {}).get("candidates", []):
            if not x.get("rejected") and x["person_id"] in rel.persons:
                item["candidates"].setdefault(x["person_id"], x)
    return out


def _complete_projects(rel: ReleaseData) -> set[str]:
    """Projects every stated lead/participant of which is in the graph (none is REVIEW_REQUIRED or UNRESOLVED)."""
    stated = _statements(rel)
    return {pid for pid, _ in stated} - {pid for (pid, _), v in stated.items() if v["status"] in OUTSIDE_GRAPH}


VARIANTS = ("default", "strict_certain_edges_only", "complete_projects_only")


def variant_memberships(rel: ReleaseData) -> dict[str, dict[str, set[str]]]:
    """The project -> Persons table under each identity policy. They answer different questions and never replace
    one another: ``default`` is every project edge in the release (anchored, deterministic, manual and automatic
    identifications side by side); ``strict_certain_edges_only`` drops the edges that rest only on
    HIGH_CONFIDENCE_AUTO mentions; ``complete_projects_only`` keeps the Projects every stated lead and participant
    of which is in the graph (no REVIEW_REQUIRED or UNRESOLVED mention on the page)."""
    graph_edges = [r for r in rel.relations if r["type"] in PROJECT_EDGES]
    mem = _membership(rel, graph_edges)
    basis = _edge_basis(rel)
    certain_edges = [r for r in graph_edges if basis.get(r["relation_id"]) in ("certain", "certain+auto")]
    complete = _complete_projects(rel)
    return {"default": mem,
            "strict_certain_edges_only": _membership(rel, certain_edges),
            "complete_projects_only": {p: ms for p, ms in mem.items() if p in complete}}


def review_candidates_accepted(rel: ReleaseData, accept: Callable[[dict[str, Any]], bool] | None = None
                               ) -> tuple[dict[str, set[str]], dict[str, int]]:
    """The default project -> Persons table plus the Person of every stated subject that is still REVIEW_REQUIRED and
    has exactly one viable candidate (not rejected, a canonical Person of the release). ``accept`` narrows that to the
    candidates it approves (it is given the candidate record, with its recorded signals).

    A counterfactual for the recall side of the identity decisions, the counterpart of the strict policy on the
    precision side: how far could the structure move if the review queue were accepted in the one way that needs no
    choice? It is an upper bound under that rule, not a version of the data and not a forecast. A reviewer rejects
    some of these (a common surname, a name that contradicts the page's own link); a subject with several candidates
    is left out because "accept one of them" has no single answer, and one with none adds nothing. Nothing here is
    written to a release, and ``variant_memberships`` stays the list of versions of the edges.

    Returns the table and the counts behind it. A statement is a distinct (Project, stated subject): the same name seen
    in a project page and in a listing page is one statement, however many mention records the release holds for it."""
    default = _membership(rel, [r for r in rel.relations if r["type"] in PROJECT_EDGES])
    mem = {p: set(ms) for p, ms in default.items()}
    pending = {k: v["candidates"] for k, v in _statements(rel).items() if v["status"] == "REVIEW_REQUIRED"}
    pairs = {(pid, person) for (pid, _), cands in pending.items() if len(cands) == 1
             for person, cand in cands.items() if accept is None or accept(cand)}
    new = {(pid, person) for pid, person in pairs if person not in default.get(pid, set())}
    for pid, person in new:
        mem.setdefault(pid, set()).add(person)
    had_edge = {p for ms in default.values() for p in ms}
    info = {"review_mention_records": sum(1 for m in rel.person_mentions if _status(m) == "REVIEW_REQUIRED"),
            "review_statements": len(pending),
            "with_one_candidate": sum(1 for c in pending.values() if len(c) == 1),
            "with_several_candidates": sum(1 for c in pending.values() if len(c) > 1),
            "with_no_viable_candidate": sum(1 for c in pending.values() if not c),
            "pairs": len(pairs), "new_edges": len(new),
            "persons_gaining_a_first_edge": len({person for _, person in new} - had_edge),
            "projects_gaining_a_person": len({pid for pid, _ in new})}
    return mem, info


def tie_stats(mem: dict[str, set[str]], sites: dict[str, set[str]]) -> dict[str, Any]:
    """Structure of the co-participation projection of a membership table (pure Python, deterministic)."""
    persons = {p for ms in mem.values() for p in ms}
    big = {k: {pid for pid, ms in mem.items() if len(ms) >= k} for k in LARGE_PROJECT_THRESHOLDS}
    shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for pid, ms in mem.items():
        for a, b in itertools.combinations(sorted(ms), 2):
            shared[(a, b)].add(pid)
    ties = len(shared)
    total_weight = sum(1 / (len(mem[p]) - 1) for ps in shared.values() for p in ps)
    parent = {p: p for p in persons}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in shared:
        parent[find(a)] = find(b)
    comp = Counter(find(p) for p in {x for t in shared for x in t})
    cross_ties = {t: ps for t, ps in shared.items() if sites.get(t[0], set()).isdisjoint(sites.get(t[1], set()))}
    cross = len(cross_ties)
    via = Counter(p for ps in cross_ties.values() for p in ps)  # cross-institute ties running through each project
    sizes = Counter(len(ms) for ms in mem.values())
    in_ties = {x for t in shared for x in t}

    def tied_outside(k: int) -> set[str]:
        """Persons with at least one tie that does not run only through projects of k or more persons."""
        return {x for t, ps in shared.items() if not ps <= big[k] for x in t}

    return {
        "projects_with_person": len(mem),
        "projects_with_two_or_more": sum(1 for ms in mem.values() if len(ms) >= 2),
        "persons_with_edge": len(persons),
        "size_distribution": {label: sum(v for k, v in sizes.items() if lo <= k <= hi) for lo, hi, label in SIZE_BUCKETS},
        "ties": ties,
        "persons_in_ties": len({x for t in shared for x in t}),
        "large_projects": {
            f">={k}": {
                "projects": len(big[k]),
                "ties_through": share(sum(1 for ps in shared.values() if ps & big[k]), ties),
                "ties_only_through": share(sum(1 for ps in shared.values() if ps <= big[k]), ties),
                "persons_only_tied_through": share(len(in_ties - tied_outside(k)), len(in_ties)),
                "size_discounted_weight_through": share_float(
                    sum(1 / (len(mem[p]) - 1) for ps in shared.values() for p in ps if p in big[k]), total_weight),
            } for k in LARGE_PROJECT_THRESHOLDS},
        "ties_by_shared_projects": {"1": sum(1 for ps in shared.values() if len(ps) == 1),
                                    "2": sum(1 for ps in shared.values() if len(ps) == 2),
                                    "3+": sum(1 for ps in shared.values() if len(ps) >= 3),
                                    "max": max((len(ps) for ps in shared.values()), default=0)},
        "total_size_discounted_weight": round(total_weight, 3),
        "cross_institute": {"ties": share(cross, ties), "projects_with_a_cross_institute_tie": len(via),
                            "ties_through_the_single_largest_contributor": share(max(via.values(), default=0), cross)},
        "components": {"count": len(comp), "largest": max(comp.values(), default=0),
                       "largest_share": share(max(comp.values(), default=0), len({x for t in shared for x in t})),
                       "singletons_among_edge_persons": len(persons) - len({x for t in shared for x in t})},
    }


def share_float(n: float, of: float) -> dict[str, Any]:
    return {"n": round(n, 3), "of": round(of, 3), "rate": round(n / of, 3) if of else None}


# ------------------------------------------------------------------ the report
def readiness_report(release: Path, *, manifest: dict[str, Any] | None = None, sources: list[str] | None = None,
                     labels: dict[str, str] | None = None) -> dict[str, Any]:
    """The ``analysis_readiness`` section of a release: indicator definitions, values, and the sensitivity of the
    structure to the identity decisions it rests on. ``manifest`` defaults to the release's own manifest.json;
    ``labels`` maps a source id to its institute code."""
    rel = ReleaseData(release, sources, manifest)
    values: dict[str, Any] = {}
    profiled = {pid: rel.person_sites[pid] for pid in rel.profiled}

    # ---- A
    aff = {r["source_id"] for r in rel.by_type["AFFILIATED_WITH"]}
    member = {r["source_id"] for r in rel.by_type["MEMBER_OF"]}
    values["A1"] = _by_source(profiled, aff)
    values["A2"] = _by_source(profiled, member)
    values["A3"] = _by_source(profiled, {pid for pid in rel.profiled if rel.persons[pid].get("position_titles")})
    parent: dict[str, set[str]] = defaultdict(set)
    for r in rel.by_type["PART_OF"]:
        parent[r["source_id"]].add(r["target_id"])

    def reaches_institute(uid: str, seen: frozenset = frozenset()) -> bool:
        return any(t in rel.institutions or (t not in seen and reaches_institute(t, seen | {uid}))
                   for t in parent.get(uid, ()))

    values["A4"] = share(sum(1 for u in rel.units if reaches_institute(u)), len(rel.units))

    # ---- B
    graph_edges = [r for r in rel.relations if r["type"] in PROJECT_EDGES]
    mem = _membership(rel, graph_edges)
    with_edge = {p for ms in mem.values() for p in ms}
    values["B1"] = _by_source(profiled, with_edge)
    pi_projects = {r["target_id"] for r in rel.by_type["PRINCIPAL_INVESTIGATOR_OF"] if r["target_id"] in rel.projects}
    values["B2"] = {"with_person": _by_source(rel.project_sites, set(mem)),
                    "with_pi": _by_source(rel.project_sites, pi_projects),
                    "with_two_or_more_persons": _by_source(rel.project_sites, {p for p, ms in mem.items() if len(ms) >= 2})}
    values["B3"] = _participant_subjects(rel)
    basis = _edge_basis(rel)
    bc = Counter(basis.values())
    values["B4"] = {"edges": len(basis), "by_basis": dict(sorted(bc.items())),
                    "auto_only_share": share(bc["auto_only"], len(basis))}

    # ---- C, with the identity-decision sensitivity (strict = certain edges only; complete = projects whose
    # stated participants are all in the graph). Each variant is a different question; none replaces the others.
    variants = {name: tie_stats(m, rel.person_sites) for name, m in variant_memberships(rel).items()}
    default = variants["default"]
    values["C1"] = {"ties": default["ties"], "persons_with_edge": default["persons_with_edge"],
                    "persons_in_ties": default["persons_in_ties"],
                    "projects_with_two_or_more": default["projects_with_two_or_more"],
                    "size_distribution": default["size_distribution"]}
    values["C2"] = default["large_projects"]
    values["C3"] = {"ties_by_shared_projects": default["ties_by_shared_projects"],
                    "total_size_discounted_weight": default["total_size_discounted_weight"]}
    values["C4"] = default["cross_institute"]
    values["C5"] = default["components"]
    values["sensitivity"] = {
        "definition": "the same measures on three versions of the project edges. default: every project edge in "
                      "the release; strict: only edges with an anchored or certain claim; complete: only Projects "
                      "whose stated leads and participants are all in the graph",
        "variants": {k: {"projects_with_two_or_more": v["projects_with_two_or_more"], "persons_with_edge": v["persons_with_edge"],
                         "ties": v["ties"], "large_projects": {k2: v2["ties_through"] for k2, v2 in v["large_projects"].items()},
                         "cross_institute_ties": v["cross_institute"]["ties"],
                         "components": v["components"]["count"], "largest_component": v["components"]["largest"]}
                     for k, v in variants.items()},
    }

    # ---- D
    topic_p = {r["source_id"] for r in rel.by_type["WORKS_ON_TOPIC"]}
    method_p = {r["source_id"] for r in rel.by_type["USES_METHOD"]}
    values["D1"] = {"topic": _by_source(profiled, topic_p), "method": _by_source(profiled, method_p)}
    ref_to_person = {ref: pid for pid, p in rel.persons.items() for ref in p.get("source_refs", [])}
    stated = {ref_to_person[c["subject"]["source_ref"]] for c in rel.claims
              if c["predicate"] == "stated_research_area" and c["subject"].get("source_ref") in ref_to_person}
    td = rel.by_type["WORKS_ON_TOPIC"] + rel.by_type["USES_METHOD"]
    values["D2"] = {
        "relations_by_epistemic_status": dict(sorted(Counter(r["epistemic_status"] for r in td).items())),
        "derivation_methods": dict(sorted(Counter(r["derivation_method"] for r in td).items(), key=lambda kv: str(kv[0]))),
        "topics_used": share(len({r["target_id"] for r in rel.by_type["WORKS_ON_TOPIC"]}), len(rel.topics)),
        "topics_with_broader_link": share(len({r["source_id"] for r in rel.by_type["BROADER"]}), len(rel.topics)),
        "persons_stating_a_research_area": _by_source(profiled, stated),
    }

    # ---- I
    values["I1"] = _person_mentions(rel)
    values["I2"] = _duplicates(rel)
    values["I3"] = _project_mentions(rel)
    classified = [p for p in rel.projects.values() if p.get("activity_type") or p.get("project_type")]
    values["I4"] = {"classified": share(len(classified), len(rel.projects)),
                    "note": "no activity type is modelled yet (#9)" if not classified else None}
    values["I5"] = _edge_provenance(rel)
    structural = {"AFFILIATED_WITH", "MEMBER_OF", "LEADS", "PART_OF"}
    touched = defaultdict(set)
    for r in rel.relations:
        touched[r["source_id"]].add(r["type"])
        touched[r["target_id"]].add(r["type"])
    values["I6"] = share(sum(1 for pid in rel.profiled if touched.get(pid, set()) <= structural), len(rel.profiled))

    # ---- T
    start = sum(1 for p in rel.projects.values() if p.get("start"))
    values["T1"] = {
        "relations_with_explicit_dates": {t: share(sum(1 for r in rs if r.get("valid_from") or r.get("valid_until")), len(rs))
                                          for t, rs in sorted(rel.by_type.items())
                                          if t in PROJECT_EDGES + ("AFFILIATED_WITH", "MEMBER_OF")},
        "projects_with_start": share(start, len(rel.projects)),
    }

    return {
        "release_id": rel.manifest.get("release_id") or release.name,
        "basis": {"source_set_digest": (rel.manifest.get("source_set") or {}).get("digest"),
                  "canonical_persons": len(rel.persons), "profile_backed_persons": len(rel.profiled),
                  "canonical_projects": len(rel.projects), "person_mentions": len(rel.person_mentions),
                  "project_mentions": len(rel.project_mentions), "relations": len(rel.relations)},
        "labels": labels or {sid: sid for sid in rel.source_ids},
        "indicators": {i: {**spec, "values": values[i]} for i, spec in INDICATORS.items()},
        "sensitivity": values["sensitivity"],
        "not_measured": NOT_MEASURED,
    }


# What these indicators cannot see. Stated in every release so a value is never read as more than it is.
NOT_MEASURED = [
    "Who is missing: the Person universe is each site's current staff listing, so collaborators and former staff "
    "are mentions at best. No indicator estimates their number.",
    "Whether a project's participant list is complete: B3 counts only what the pages state.",
    "Whether a tie is a collaboration: sharing a project page is co-listing, which can mean working together, "
    "belonging to the same grant or sitting in the same consortium.",
    "Role semantics: 'Projektvezető' (project lead), 'Kutatásvezető' and 'Koordinátor' are not distinguished (#10).",
    "Anything about other institutions: the release holds four institutes of one research centre (Milestone 3 "
    "adds more).",
    "Grades. READY / READY_WITH_RESTRICTIONS / NOT_READY are a reviewed judgement (docs/analysis_readiness.md), "
    "not a computed result.",
]


def _participant_subjects(rel: ReleaseData) -> dict[str, Any]:
    """B3: distinct (project page, subject) statements of lead/participant claims, by how the subject was identified."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for (pid, _), v in _statements(rel).items():
        for key in sorted(rel.project_sites[pid]) + ["all"]:
            counts[key][v["status"]] += 1
    out = {}
    for key in sorted(counts, key=lambda k: (k == "all", k)):
        c = counts[key]
        total = sum(c.values())
        inside = c[ANCHORED] + sum(c[k] for k in CERTAIN) + c[AUTO]
        out[key] = {"subjects": total, "by_status": dict(sorted(c.items())), "in_graph": share(inside, total),
                    "outside_graph": share(sum(c[k] for k in OUTSIDE_GRAPH), total)}
    return out


def _person_mentions(rel: ReleaseData) -> dict[str, Any]:
    by: dict[str, Counter] = defaultdict(Counter)
    for m in rel.person_mentions:
        st = (m.get("resolution") or {}).get("status", "UNKNOWN")
        for key in (m.get("source_id", "?"), "all"):
            by[key]["total"] += 1
            by[key][st] += 1
    by.setdefault("all", Counter())  # a release with no person mention still has the row
    table = {}
    for key in sorted(by, key=lambda k: (k == "all", k)):
        c = by[key]
        certain = sum(c[k] for k in CERTAIN)
        table[key] = {"total": c["total"], "by_status": {k: v for k, v in sorted(c.items()) if k != "total"},
                      "resolved_certain": share(certain, c["total"]),
                      "resolved_incl_auto": share(certain + c[AUTO], c["total"]),
                      "outside_graph": share(sum(c[k] for k in OUTSIDE_GRAPH), c["total"])}
    canonical = {name_key(p.get("canonical_name") or p["label"]) for p in rel.persons.values()}
    names = {m["normalized_name"] for m in rel.person_mentions
             if (m.get("resolution") or {}).get("status") == "UNRESOLVED"} - canonical
    return {"by_source": table, "canonical_persons": len(rel.persons),
            "mention_only_names": len(names),
            "mention_only_share": share(len(names), len(rel.persons) + len(names))}


def _duplicates(rel: ReleaseData) -> dict[str, Any]:
    def groups(key) -> int:
        g: dict[str, set[str]] = defaultdict(set)
        for pid, p in rel.persons.items():
            g[key(p.get("canonical_name") or p["label"])].add(pid)
        return sum(1 for v in g.values() if len(v) > 1)

    review = [m for m in rel.person_mentions if (m.get("resolution") or {}).get("status") == "REVIEW_REQUIRED"]
    return {"canonical_persons": len(rel.persons), "names_with_more_than_one_person": groups(name_key),
            "order_free_names_with_more_than_one_person": groups(order_free_key),
            "record_merges_confirmed": sum(1 for m in rel.matches if m["status"] == "confirmed_match"),
            "person_mentions_waiting_for_review": len(review),
            "candidate_persons_with_a_review_item": len({c["person_id"] for m in review
                                                         for c in m.get("candidates", [])})}


def _project_mentions(rel: ReleaseData) -> dict[str, Any]:
    by: dict[str, Counter] = defaultdict(Counter)
    for m in rel.project_mentions:
        st = (m.get("resolution") or {}).get("status", "UNKNOWN")
        for key in (m.get("source_id", "?"), "all"):
            by[key]["total"] += 1
            by[key][st] += 1
    by.setdefault("all", Counter())   # a release from before ProjectMention (#7) has none: say so, do not omit the row
    table = {key: {"total": c["total"], "by_status": {k: v for k, v in sorted(c.items()) if k != "total"},
                   "resolved": share(c["total"] - c["UNRESOLVED"] - c["REVIEW_REQUIRED"], c["total"])}
             for key, c in sorted(by.items(), key=lambda kv: (kv[0] == "all", kv[0]))}
    grants: dict[str, int] = Counter(p["grant_id"] for p in rel.projects.values() if p.get("grant_id"))
    titles: dict[str, int] = Counter(name_key(p["title"]) for p in rel.projects.values() if p.get("title"))
    return {"by_source": table, "canonical_projects": len(rel.projects),
            "project_mentions_in_release": bool(rel.project_mentions),
            "mentions_per_project": (round(len(rel.project_mentions) / len(rel.projects), 2)
                                     if rel.projects and rel.project_mentions else None),
            "candidate_duplicates": {"grant_ids_on_more_than_one_project": sum(1 for v in grants.values() if v > 1),
                                     "titles_on_more_than_one_project": sum(1 for v in titles.values() if v > 1)}}


def _edge_provenance(rel: ReleaseData) -> dict[str, Any]:
    out = {}
    for t, rs in sorted(rel.by_type.items()):
        status = Counter(r["epistemic_status"] for r in rs)
        out[t] = {"relations": len(rs), "by_epistemic_status": dict(sorted(status.items())),
                  "two_or_more_documents": share(sum(1 for r in rs if len(set(r.get("document_ids", []))) >= 2), len(rs))}
    return out


# ------------------------------------------------------------------ rendering and the manifest
def readiness_summary(report: dict[str, Any]) -> dict[str, Any]:
    """The few figures worth keeping in the manifest; everything else is in analysis_readiness.json."""
    ind = report["indicators"]
    return {
        "report": "analysis_readiness.md",
        "co_participation_ties": ind["C1"]["values"]["ties"],
        "projects_with_two_or_more_persons": ind["C1"]["values"]["projects_with_two_or_more"],
        "edges_resting_only_on_automatic_identity_rules": ind["B4"]["values"]["auto_only_share"],
        "ties_only_through_projects_with_10_or_more_persons": ind["C2"]["values"][">=10"]["ties_only_through"],
        "person_mentions_outside_the_graph": ind["I1"]["values"]["by_source"]["all"]["outside_graph"],
        "mention_only_share_of_person_like_nodes": ind["I1"]["values"]["mention_only_share"],
        "grades": "not computed; see docs/analysis_readiness.md",
    }


def _is_share(v: Any) -> bool:
    return isinstance(v, dict) and {"n", "of"} <= set(v)


def _scalar(v: Any) -> str:
    if _is_share(v):
        # whole percent, half up, from the counts (as coverage.md): the stored 3-decimal rate would round twice
        pct = f" ({int((200 * v['n'] + v['of']) // (2 * v['of']))}%)" if v["of"] else ""
        return f"{v['n']}/{v['of']}{pct}"
    return "-" if v is None else str(v)


def _flat(v: Any) -> bool:
    return isinstance(v, dict) and not _is_share(v) and all(not isinstance(x, (dict, list)) or _is_share(x)
                                                           for x in v.values())


def _bullets(v: Any, labels: dict[str, str], depth: int = 0) -> list[str]:
    """A nested value as a bullet list: a flat dict is one line, a dict of dicts is one bullet per key."""
    pad = "  " * depth
    inline = lambda d: " · ".join(f"{labels.get(k, k)} {_scalar(x)}" for k, x in d.items())  # noqa: E731
    if not isinstance(v, dict) or _is_share(v):
        return [f"{pad}- {_scalar(v)}"]
    if _flat(v):
        return [f"{pad}- {inline(v)}"]
    out = []
    for k, x in v.items():
        if not isinstance(x, dict) or _is_share(x):
            out.append(f"{pad}- {labels.get(k, k)}: {_scalar(x)}")
        elif _flat(x):
            out.append(f"{pad}- {labels.get(k, k)}: {inline(x)}")
        else:
            out.append(f"{pad}- {labels.get(k, k)}:")
            out += _bullets(x, labels, depth + 1)
    return out


def render_readiness_markdown(report: dict[str, Any]) -> str:
    labels = report["labels"]
    b = report["basis"]
    lines = [
        f"# Analysis readiness: `{report['release_id']}`",
        "",
        "Diagnostic indicators for exploratory network analysis (#17). **This is not a verdict**: there are no "
        "thresholds here, and the grades (READY / READY_WITH_RESTRICTIONS / NOT_READY) are a reviewed judgement in "
        "`docs/analysis_readiness.md`. Every indicator names its denominator and the analysis it threatens.",
        "",
        f"Basis: {b['canonical_persons']} canonical Persons ({b['profile_backed_persons']} profile-backed), "
        f"{b['canonical_projects']} Projects, {b['person_mentions']} person mentions, {b['project_mentions']} "
        f"project mentions, {b['relations']} relations; source-set digest `{b['source_set_digest']}`.",
        "",
    ]
    layers = {"A": "Person - institution / unit", "B": "Person - project (bipartite, the observed layer)",
              "C": "Person - person co-participation (a derived projection)", "D": "Topics and methods",
              "I": "Identity (applies to every layer)", "T": "Time"}
    for layer, title in layers.items():
        lines += [f"## {layer}. {title}", ""]
        for i, spec in report["indicators"].items():
            if spec["layer"] != layer:
                continue
            lines += [f"### {i} {spec['name']}", "", spec["definition"] + ".", "",
                      f"*Denominator:* {spec['denominator']}. *Threatens:* {spec['threatens']}.", ""]
            lines += _bullets(spec["values"], labels) + [""]
    s = report["sensitivity"]
    lines += ["## Sensitivity of the structure to identity decisions", "", s["definition"] + ".", "",
              "| variant | projects with 2+ Persons | Persons with an edge | ties | ties through projects of 8+ | "
              "cross-institute ties | components | largest component |", "|---|---|---|---|---|---|---|---|"]
    for k, v in s["variants"].items():
        lines.append(f"| {k} | {v['projects_with_two_or_more']} | {v['persons_with_edge']} | {v['ties']} | "
                     f"{_scalar(v['large_projects']['>=8'])} | {_scalar(v['cross_institute_ties'])} | "
                     f"{v['components']} | {v['largest_component']} |")
    lines += ["", "## What no indicator can see", ""] + [f"* {x}" for x in report["not_measured"]]
    return "\n".join(lines) + "\n"


def write_readiness(release: Path, report: dict[str, Any]) -> None:
    """Write ``analysis_readiness.json`` / ``.md`` into the release directory."""
    (release / "analysis_readiness.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (release / "analysis_readiness.md").write_text(render_readiness_markdown(report), encoding="utf-8")
