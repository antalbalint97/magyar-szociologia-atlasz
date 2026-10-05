"""PROJECT MENTIONS  ->  RESOLVES_TO decisions from explainable evidence (#7, ADR-0008).

Same two steps as for people (ADR-0007), with project-specific evidence:

* candidate generation asks which anchored Projects a mention *might* be: a shared grant
  key, an equal title key, or one title key a long prefix of the other. Being a
  candidate says nothing about identity.
* the decision asks whether the evidence for exactly one candidate satisfies a named
  rule. Title evidence never decides alone; every rule pairs it (or a grant key) with an
  independent observation, and any contradiction (other grant, disjoint period, a link
  to another page, a second candidate, a manual rejection) blocks it.

Project rules read anchored Projects built from certain decisions and the *name
observations* on project pages; they never read an automatic person decision, so person
rules may use project decisions without circularity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ..models.entities import ProjectCandidate, ProjectMention, ProjectMentionResolution
from ..models.enums import EntityType, MentionResolutionStatus, RelationType
from ..normalize.names import name_key
from .mentions import title_fold

PROJECT_RESOLVER_DOC = "docs/adr/0008-project-mentions-vs-canonical-projects.md"
OVERRIDES = "review/manual_overrides.yaml"

# ---------------------------------------------------------------- signal vocabulary
PROJECT_URL_EXACT = "PROJECT_URL_EXACT"
MANUAL_SAME_AS = "MANUAL_SAME_AS"
GRANT_ID_MATCH = "GRANT_ID_MATCH"
TITLE_EXACT = "TITLE_EXACT"
TITLE_EQUAL_AFTER_AFFIXES = "TITLE_EQUAL_AFTER_AFFIXES"
TITLE_PREFIX = "TITLE_PREFIX"
PAGE_LINKS_OWNER = "PAGE_LINKS_OWNER"
PAGE_NAMES_OWNER = "PAGE_NAMES_OWNER"
SAME_SITE = "SAME_SITE"  # weak
GRANT_ID_CONFLICT = "GRANT_ID_CONFLICT"
PERIOD_CONFLICT = "PERIOD_CONFLICT"
LINKS_OTHER_PAGE = "LINKS_OTHER_PAGE"
MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
MANUAL_NOT_SAME_AS = "MANUAL_NOT_SAME_AS"
ACTIVITY_CUE = "ACTIVITY_CUE"  # caution only

TITLE_SIGNALS = (TITLE_EXACT, TITLE_EQUAL_AFTER_AFFIXES, TITLE_PREFIX)
OWNER_SIGNALS = (PAGE_LINKS_OWNER, PAGE_NAMES_OWNER)
BLOCKING = {GRANT_ID_CONFLICT, PERIOD_CONFLICT, LINKS_OTHER_PAGE, MULTIPLE_CANDIDATES, MANUAL_NOT_SAME_AS}
MIN_PREFIX = 20  # folded characters of the shorter title in a prefix match

# (rule id, alternatives: the candidate needs every signal of one alternative)
RULES: list[tuple[str, list[tuple[tuple[str, ...], tuple[str, ...]]]]] = [
    # each alternative: (needs one of these, and one of these)
    ("grant_and_title", [((GRANT_ID_MATCH,), TITLE_SIGNALS)]),
    ("grant_and_owner", [((GRANT_ID_MATCH,), OWNER_SIGNALS)]),
    ("title_and_owner", [(TITLE_SIGNALS, OWNER_SIGNALS)]),
]

# ---------------------------------------------------------------- titles, grants, cues
_FUNDER = r"(?:NKFIH|NKFI|OTKA)"
_ROLE = (r"(?:vezető kutató|kutatásvezető|projektvezető|témavezető|szakmai vezető|résztvevő(?: kutató)?|"
         r"kutató|részvétel|participating researcher|researcher|principal investigator|koordinátor)")
_AFFIXES = [
    re.compile(r"^\s*\d{4}\s*[-–]\s*(?:\d{4}|jelenleg|folyamatban)?\s*[-–—:.]?\s+"),  # "2023-2027 – Title"
    re.compile(rf"^\s*(?:[A-Z]{{1,4}}\s+)?(?:{_FUNDER}\s*)?[A-Z]{{0,4}}[\s_-]*\d{{5,6}}\s*[-–—:.,]\s+"),  # "OTKA K 143593 - "
    re.compile(r"\s*\([^()]*(?:\d|NKFI|OTKA|PI:|ERC|H2020|Horizon|kutató|vezető|résztvevő|program)[^()]*\)\s*\.?$",
               re.I),
    re.compile(rf"\s*[,;]\s*(?:{_FUNDER}\b|(?:PD|FK|KKP|K)[\s_-]*\d{{5,6}}).*$"),
    re.compile(rf"\s*[-–—,]\s*{_ROLE}\.?\s*$", re.I),
    re.compile(r"\s+című\s+(?:kutatás|projekt|program)\.?\s*$", re.I),
    re.compile(r"\s*\|.*$"),
    re.compile(r"\s+(?:19|20)\d{2}\.?$"),  # "Éghajlatváltozás és egészség 2021": an edition year
    re.compile(r"\s*(?:https?://|www\.)\S+\s*$", re.I),
]
_GRANT_RE = re.compile(
    rf"(?:\b{_FUNDER}\b[\s.:_-]*(?:[A-Z]{{1,4}}[\s_:-]*)?|\b(?:PD|FK|KKP|KH|NN|SNN|ANN|K)[\s_:-]*)(\d{{5,6}})\b"
    r"|\b(\d{5,6})\s+jelű"
)
_CUES = [
    ("journal", re.compile(r"\bJournal\b|folyóirat", re.I)),
    ("network", re.compile(r"\bNetwork\b|kutatóhálózat")),
    ("programme", re.compile(r"\bProgram(?:me)?\b|Kiválósági Program|Nemzeti Laboratórium")),
    ("infrastructure", re.compile(r"infrastruktúr|infrastructure", re.I)),
    ("consortium", re.compile(r"konzorci|consorti", re.I)),
    ("newsletter", re.compile(r"hírlevél|newsletter", re.I)),
    ("research_group", re.compile(r"kutatócsoport|research group|Lendület", re.I)),
    ("database", re.compile(r"adatbázis|database|adatrepozitórium", re.I)),
]


def strip_affixes(title: str) -> str:
    t = title.strip().strip("„”\"'").strip()
    for _ in range(4):
        before = t
        for rx in _AFFIXES:
            t = rx.sub("", t).strip().strip("„”\"'").strip()
        if t == before:
            break
    return t or title


def title_key(title: str) -> str:
    """Matching key: folded title without grant, role, period, funder and URL affixes."""
    return title_fold(strip_affixes(title))


def grant_keys(*texts: str | None) -> list[str]:
    """Hungarian OTKA / NKFI / NKFIH grant numbers ("OTKA K 143593", "K_143593", "108836 jelű").

    The programmes share one numbering, so the key is the number only; funder labels and
    programme letters stay raw on the mention (#11 normalises funders)."""
    out = []
    for t in texts:
        for m in _GRANT_RE.finditer(t or ""):
            k = f"nkfih:{m.group(1) or m.group(2)}"
            if k not in out:
                out.append(k)
    return out


# public grant registries: a link to a grant record states the grant, it is not another project page
GRANT_REGISTRY_HOSTS = {"nyilvanos.otka-palyazat.hu": "num"}


def registry_grant_keys(url: str | None) -> list[str]:
    """'https://nyilvanos.otka-palyazat.hu/index.php?...&num=137755...' -> ['nkfih:137755']."""
    parts = urlsplit(url or "")
    param = GRANT_REGISTRY_HOSTS.get((parts.hostname or "").lower())
    if not param:
        return []
    m = re.search(rf"(?:^|&){param}=(\d{{5,6}})(?!\d)", parts.query)
    return [f"nkfih:{m.group(1)}"] if m else []


def activity_cues(*texts: str | None) -> list[str]:
    """Words suggesting a journal, network, programme, ... (#9 decides; never used for resolution)."""
    return sorted({cue for t in texts if t for cue, rx in _CUES if rx.search(t)})


def _years(start: str | None, end: str | None) -> tuple[int | None, int | None]:
    def y(v):
        return int(v[:4]) if v and re.match(r"\d{4}", v) else None
    return y(start), y(end)


def periods_conflict(a: tuple[int | None, int | None], b: tuple[int | None, int | None]) -> bool:
    """Disjoint at year precision ('2023' and '2023-01-01' agree; open ends never conflict)."""
    (af, au), (bf, bu) = a, b
    if af is None and au is None or bf is None and bu is None:
        return False
    lo_a, hi_a = af if af is not None else au, au if au is not None else None
    lo_b, hi_b = bf if bf is not None else bu, bu if bu is not None else None
    return (hi_a is not None and lo_b is not None and hi_a < lo_b) or \
        (hi_b is not None and lo_a is not None and hi_b < lo_a)


# ---------------------------------------------------------------- manual decisions
@dataclass
class ProjectDecision:
    """A reviewer's decision about one mention (or every page of one source record).

    same_as / not_same_as name the Project. `defer` names no identity: it records that the
    mention is not decided yet because another issue (blocked_by) must settle what kind of
    canonical entity it would resolve to (#9 for activities that may not be Projects)."""

    project_id: str | None  # None only for defer
    decision: str  # same_as | not_same_as | defer
    mention_id: str | None = None
    source_ref: str | None = None
    reviewer: str | None = None
    date: str | None = None
    evidence: str | None = None
    blocked_by: str | None = None  # defer only: the issue that has to decide first, e.g. "#9"

    def applies(self, m: ProjectMention) -> bool:
        return self.mention_id == m.canonical_id or (self.source_ref is not None and self.source_ref == m.source_ref)


def load_project_decisions(path: Path) -> list[ProjectDecision]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for d in data.get("project_decisions") or []:
        if d["decision"] not in ("same_as", "not_same_as", "defer"):
            raise ValueError(f"project_decisions: unknown decision {d['decision']!r}")
        if d["decision"] != "defer" and not d.get("project_id"):
            raise ValueError(f"project_decisions: {d['decision']} needs project_id ({d.get('mention_id')})")
        if d["decision"] == "defer" and not d.get("blocked_by"):
            raise ValueError(f"project_decisions: defer needs blocked_by ({d.get('mention_id')})")
        out.append(ProjectDecision(
            project_id=d.get("project_id"), decision=d["decision"], mention_id=d.get("mention_id"),
            source_ref=d.get("source_ref"), reviewer=d.get("reviewer"),
            date=str(d["date"]) if d.get("date") else None, evidence=d.get("evidence"),
            blocked_by=d.get("blocked_by")))
    return out


# ---------------------------------------------------------------- project index
@dataclass
class ProjectFacts:
    project_id: str
    label: str
    keys: dict[str, str]  # title key -> the title it came from
    folded: set[str]
    grant_keys: set[str]
    years: tuple[int | None, int | None]
    urls: set[str]
    site: str
    people: list[tuple[str, str | None]]  # (name key, anchored person id it links or None)


class ProjectIndex:
    """What the project rules may know about anchored Projects: certain evidence only."""

    def __init__(self, ds, records, claims, project_sides: dict[tuple[str, str], str], ref_to_id: dict[str, str]):
        label_at = {(r.ref.source_ref, r.document_id): r.label for r in records
                    if r.ref.entity_type is EntityType.PERSON and r.ref.source_ref}
        people: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        for c in claims:
            if c.predicate not in (RelationType.PARTICIPATES_IN.value, RelationType.PRINCIPAL_INVESTIGATOR_OF.value):
                continue
            if c.object is None or c.object.entity_type is not EntityType.PROJECT:
                continue
            pid = project_sides.get((c.claim_id, "object"))
            if pid is None or c.subject.entity_type is not EntityType.PERSON or not c.subject.source_ref:
                continue
            if c.evidence.locator.startswith("profile."):
                continue  # the profile owner's own statement is the mention side, not the page's naming
            name = label_at.get((c.subject.source_ref, c.evidence.document_id))
            if name:
                entry = (name_key(name), ref_to_id.get(c.subject.source_ref))
                if entry not in people[pid]:
                    people[pid].append(entry)
        self.projects: dict[str, ProjectFacts] = {}
        self.by_key: dict[str, set[str]] = defaultdict(set)
        self.by_grant: dict[str, set[str]] = defaultdict(set)
        for p in ds.by_type(EntityType.PROJECT):
            titles = [p.title, *p.alternate_titles]
            grants = [p.grant_id] + [cv.value for cv in p.conflicts.get("grant_id", [])]
            starts = [p.start] + [cv.value for cv in p.conflicts.get("start", [])]
            ends = [p.end] + [cv.value for cv in p.conflicts.get("end", [])]
            ys = [y for y in (_years(s, None)[0] for s in starts) if y is not None]
            ye = [y for y in (_years(e, None)[0] for e in ends) if y is not None]
            facts = ProjectFacts(
                p.canonical_id, p.label, {title_key(t): t for t in titles if title_key(t)},
                {title_fold(t) for t in titles}, set(grant_keys(*[g for g in grants if g], *titles)),
                (min(ys) if ys else None, max(ye) if ye else None),
                {u for u in [p.website] + [cv.value for cv in p.conflicts.get("website", [])] if u},
                (p.source_refs[0].split("|", 1)[0] if p.source_refs else ""), people.get(p.canonical_id, []))
            self.projects[p.canonical_id] = facts
            for k in facts.keys:
                self.by_key[k].add(p.canonical_id)
            for g in facts.grant_keys:
                self.by_grant[g].add(p.canonical_id)
        self.persons = {p.canonical_id: p for p in ds.by_type(EntityType.PERSON)}

    def candidates(self, m: ProjectMention) -> set[str]:
        out = set(self.by_key.get(m.title_key, ()))
        for g in m.grant_keys:
            out |= self.by_grant.get(g, set())
        if len(m.title_key) >= MIN_PREFIX:
            for pid, f in self.projects.items():
                if any(_prefix(m.title_key, k) for k in f.keys):
                    out.add(pid)
        return out


def _prefix(a: str, b: str) -> bool:
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= MIN_PREFIX and short != long_ and long_.startswith(short) and long_[len(short)] == " "


# ---------------------------------------------------------------- the resolver
def resolve_project_mentions(mentions: dict[str, ProjectMention], idx: ProjectIndex, resolver_version: str,
                             manual: list[ProjectDecision], links: dict[str, dict[str, Any]] | None = None) -> None:
    """``links``: the crawl frontier by URL (discovery.merge_frontier); it only explains *why* a linked
    page has no anchor, it never resolves anything."""
    for m in mentions.values():
        _resolve_one(m, idx, resolver_version, manual, links or {})


def _signals(m: ProjectMention, f: ProjectFacts, idx: ProjectIndex, evidence: dict[str, Any]) -> tuple[list, list, str | None]:
    pos, neg = [], []
    match = None
    if title_fold(m.stated_title) in f.folded:
        match = TITLE_EXACT
    elif m.title_key in f.keys:
        match = TITLE_EQUAL_AFTER_AFFIXES
    elif any(_prefix(m.title_key, k) for k in f.keys):
        match = TITLE_PREFIX
    if match:
        pos.append(match)
        evidence["title_match"] = {"mention": m.stated_title, "project": f.label, "key": m.title_key}
    shared = sorted(set(m.grant_keys) & f.grant_keys)
    if shared:
        pos.append(GRANT_ID_MATCH)
        evidence["grant_keys"] = shared
    elif m.grant_keys and f.grant_keys:
        neg.append(GRANT_ID_CONFLICT)
        evidence["grant_conflict"] = {"mention": m.grant_keys, "project": sorted(f.grant_keys)}
    owner = m.observed_on_profile_of
    if owner:
        person = idx.persons.get(owner)
        keys = {name_key(n) for n in ([person.label, *person.alternate_names] if person else [])}
        if any(pid == owner for _, pid in f.people):
            pos.append(PAGE_LINKS_OWNER)
            evidence["owner"] = owner
        elif any(k in keys and (pid is None or pid == owner) for k, pid in f.people):
            pos.append(PAGE_NAMES_OWNER)
            evidence["owner"] = owner
            evidence["owner_named_as"] = sorted({k for k, pid in f.people if k in keys})
    m_years = _years(m.stated_period_from, m.stated_period_until)
    if periods_conflict(m_years, f.years):
        neg.append(PERIOD_CONFLICT)
        evidence["period_conflict"] = {"mention": list(m_years), "project": list(f.years)}
    if m.linked_url and m.linked_url not in f.urls and not registry_grant_keys(m.linked_url):
        neg.append(LINKS_OTHER_PAGE)
        evidence["linked_url"] = m.linked_url
    if m.source_id == f.site:
        pos.append(SAME_SITE)
    if m.activity_cues:
        neg.append(ACTIVITY_CUE)
    return pos, neg, match


def _resolve_one(m: ProjectMention, idx: ProjectIndex, version: str, manual: list[ProjectDecision],
                 links: dict[str, dict[str, Any]]) -> None:
    rejected = {d.project_id for d in manual if d.decision == "not_same_as" and d.applies(m)}
    confirmed = next((d for d in manual if d.decision == "same_as" and d.applies(m)), None)
    deferred = next((d for d in manual if d.decision == "defer" and d.applies(m)), None)
    res = m.resolution
    if confirmed is not None:
        if confirmed.project_id in idx.projects:
            # what the automatic rules saw is kept next to the reviewer's evidence: a manual decision
            # is allowed to overrule a blocking signal, and the record shows which one it overruled
            seen: dict[str, Any] = {}
            pos, neg, _ = _signals(m, idx.projects[confirmed.project_id], idx, seen)
            m.resolution = ProjectMentionResolution(
                status=MentionResolutionStatus.MANUAL_CONFIRMED, project_id=confirmed.project_id,
                method="manual:project_same_as", signals=[MANUAL_SAME_AS],
                evidence={k: v for k, v in (("reviewer", confirmed.reviewer), ("evidence", confirmed.evidence)) if v}
                | {"signals_seen": {"positive": pos, "negative": neg, **seen}},
                decision_source=OVERRIDES, resolver_version=version,
                decided_at=datetime.fromisoformat(confirmed.date) if confirmed.date else None)
        else:
            m.resolution = ProjectMentionResolution(
                status=MentionResolutionStatus.UNRESOLVED,
                reason=f"manual same_as names a missing Project {confirmed.project_id}",
                decision_source=OVERRIDES, resolver_version=version)
        return
    if res.status.resolved:
        if res.project_id in rejected:
            m.resolution = ProjectMentionResolution(
                status=MentionResolutionStatus.REVIEW_REQUIRED, negative_signals=[MANUAL_NOT_SAME_AS],
                reason="manual not_same_as contradicts the automatic link", decision_source=OVERRIDES,
                resolver_version=version)
        else:
            res.resolver_version = version
        return

    cands: list[ProjectCandidate] = []
    details: dict[str, dict[str, Any]] = {}
    for pid in sorted(idx.candidates(m)):
        ev: dict[str, Any] = {}
        pos, neg, match = _signals(m, idx.projects[pid], idx, ev)
        if pid in rejected:
            neg.append(MANUAL_NOT_SAME_AS)
        cands.append(ProjectCandidate(project_id=pid, title_match=match, signals=pos, negative_signals=neg,
                                      rejected=pid in rejected))
        details[pid] = ev
    viable = [c for c in cands if not c.rejected and not set(c.negative_signals) & BLOCKING
              and (set(c.signals) & {*TITLE_SIGNALS, GRANT_ID_MATCH})]
    if len(viable) > 1:
        for c in viable:
            c.negative_signals.append(MULTIPLE_CANDIDATES)
    cands.sort(key=lambda c: (c.rejected, c not in viable, -len(c.signals), c.project_id))
    m.candidates = cands
    if deferred is not None:
        # the reviewer holds the identity back until another issue has decided what kind of entity this
        # is; candidates stay visible, nothing is resolved and no automatic rule may fire
        m.resolution = ProjectMentionResolution(
            status=MentionResolutionStatus.REVIEW_REQUIRED if any(not c.rejected for c in cands)
            else MentionResolutionStatus.UNRESOLVED,
            method="manual:project_deferred",
            reason=f"deferred, blocked by {deferred.blocked_by}: the canonical entity type is undecided",
            evidence={k: v for k, v in (("reviewer", deferred.reviewer), ("evidence", deferred.evidence),
                                        ("blocked_by", deferred.blocked_by)) if v},
            decision_source=OVERRIDES, resolver_version=version,
            decided_at=datetime.fromisoformat(deferred.date) if deferred.date else None)
        return
    if len(viable) == 1:
        c = viable[0]
        for rule, alternatives in RULES:
            if any(set(a) & set(c.signals) and set(b) & set(c.signals) for a, b in alternatives):
                m.resolution = ProjectMentionResolution(
                    status=MentionResolutionStatus.HIGH_CONFIDENCE_AUTO, project_id=c.project_id, method=rule,
                    signals=list(c.signals), negative_signals=list(c.negative_signals),
                    evidence=details[c.project_id],
                    decision_source=f"{PROJECT_RESOLVER_DOC}#rules", resolver_version=version)
                return
    m.resolution = ProjectMentionResolution(
        status=MentionResolutionStatus.REVIEW_REQUIRED if any(not c.rejected for c in cands)
        else MentionResolutionStatus.UNRESOLVED,
        reason=_why_not(m, cands, viable, res.reason, links), decision_source=PROJECT_RESOLVER_DOC,
        resolver_version=version)


def link_reason(url: str, links: dict[str, dict[str, Any]]) -> str:
    """Why a linked page has no anchored Project, from the crawl frontier (#16). Nothing is inferred from the URL."""
    row = links.get(url)
    if row is None:
        return "linked page was not on the crawl frontier"
    fetch = row.get("fetch") or {}
    if row["decision"] == "skipped":
        return f"linked project page not followed ({row['reason']})"
    if fetch.get("attempted") and fetch.get("error"):
        return f"linked project page fetch failed ({fetch['error']})"
    if fetch.get("redirected"):
        return f"linked project page redirected to {fetch.get('final_url')}"
    return "linked project page fetched, no Project anchored"


def _why_not(m: ProjectMention, cands: list[ProjectCandidate], viable: list[ProjectCandidate],
             prior: str | None, links: dict[str, dict[str, Any]]) -> str:
    if not cands:
        if m.linked_url and not registry_grant_keys(m.linked_url):
            return link_reason(m.linked_url, links) + "; no anchored Project with a compatible title or grant id"
        return "no anchored Project with a compatible title or grant id"
    if all(c.rejected for c in cands):
        return "every candidate was rejected manually"
    if not viable:
        blocks = sorted({s for c in cands for s in c.negative_signals if s in BLOCKING})
        return "blocked: " + ", ".join(blocks)
    if len(viable) > 1:
        return f"{len(viable)} viable candidates (same or compatible title)"
    c = viable[0]
    have = sorted(set(c.signals) - {SAME_SITE})
    if set(have) <= set(TITLE_SIGNALS):
        return f"title evidence only ({', '.join(have)}); the page does not name the profile owner and no grant id agrees"
    return f"no rule satisfied (signals: {', '.join(have) or 'none'})"


def claim_projects(mentions: dict[str, ProjectMention], claim_mention: dict[tuple[str, str], str],
                   own_claims: dict[tuple[str, str], str], *, certain_only: bool = False) -> dict[tuple[str, str], str]:
    """Project side of each claim -> canonical id: own-page observations plus resolved mentions."""
    ok = {MentionResolutionStatus.DETERMINISTIC, MentionResolutionStatus.MANUAL_CONFIRMED}
    if not certain_only:
        ok.add(MentionResolutionStatus.HIGH_CONFIDENCE_AUTO)
    out = dict(own_claims)
    for side, mid in claim_mention.items():
        r = mentions[mid].resolution
        if r.status in ok and r.project_id:
            out[side] = r.project_id
    return out
