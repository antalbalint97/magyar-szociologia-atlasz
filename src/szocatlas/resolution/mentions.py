"""PERSON MENTIONS  ->  RESOLVES_TO decisions from explainable evidence (#5, ADR-0007).

Two separate steps:

* candidate generation asks which canonical Persons a mention *might* refer to (name
  keys, initials, profile slugs). A candidate is never a decision.
* the decision asks whether the evidence for exactly one candidate is enough. Every
  automatic decision is a named rule that combines at least two strong signals and is
  blocked by any contradicting signal. Weak signals only rank candidates for review.

Contextual evidence about a candidate (its units, institutes, projects) comes only from
identity-anchored observations and *certain* mention decisions, never from other
automatic decisions, so the outcome does not depend on processing order.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ..models.entities import MentionCandidate, MentionResolution, Person, PersonMention
from ..models.enums import EntityType, MentionResolutionStatus, RelationType
from ..normalize.names import clean_display_name, name_key, order_free_key
from ..registry import Registry

RESOLVER_DOC = "docs/adr/0007-evidence-based-mention-resolution.md"
OVERRIDES = "review/manual_overrides.yaml"

# ---------------------------------------------------------------- signal vocabulary
# certain
PROFILE_URL_EXACT = "PROFILE_URL_EXACT"
HARD_ID_MATCH = "HARD_ID_MATCH"
MANUAL_SAME_AS = "MANUAL_SAME_AS"
# name (candidate generation; a full-name match is one strong signal)
NAME_EXACT = "NAME_EXACT"  # same characters incl. diacritics, titles and spacing aside
SAME_NORMALIZED_NAME = "SAME_NORMALIZED_NAME"  # accent/case/punctuation-insensitive, same token order
ALTERNATE_NAME_MATCH = "ALTERNATE_NAME_MATCH"  # equals a name form the Person is already observed under
NAME_ORDER_VARIANT = "NAME_ORDER_VARIANT"  # weak
NAME_INITIALS_COMPATIBLE = "NAME_INITIALS_COMPATIBLE"  # weak
# strong context
PROFILE_SLUG_INFERRED_ALIAS = "PROFILE_SLUG_INFERRED_ALIAS"
PROFILE_SLUG_FAMILY_HOST = "PROFILE_SLUG_FAMILY_HOST"
OWN_PROFILE_LISTS_PROJECT = "OWN_PROFILE_LISTS_PROJECT"
SOURCE_UNIT_MEMBER = "SOURCE_UNIT_MEMBER"
SAME_INSTITUTE = "SAME_INSTITUTE"
UNIQUE_NAME_IN_FAMILY = "UNIQUE_NAME_IN_FAMILY"
# weak context
SAME_INSTITUTION_FAMILY = "SAME_INSTITUTION_FAMILY"
# negative
LINKS_OTHER_PROFILE = "LINKS_OTHER_PROFILE"
LINK_NAME_MISMATCH = "LINK_NAME_MISMATCH"
MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
SAME_NAME_MULTIPLE_PERSONS = "SAME_NAME_MULTIPLE_PERSONS"
CONFLICTING_HARD_ID = "CONFLICTING_HARD_ID"
MANUAL_NOT_SAME_AS = "MANUAL_NOT_SAME_AS"
COMMON_SURNAME = "COMMON_SURNAME"  # caution only
DIFFERENT_INSTITUTE = "DIFFERENT_INSTITUTE"  # caution only: cross-institute collaboration is normal

FULL_NAME = (NAME_EXACT, SAME_NORMALIZED_NAME, ALTERNATE_NAME_MATCH)
STRONG = {*FULL_NAME, PROFILE_SLUG_INFERRED_ALIAS, PROFILE_SLUG_FAMILY_HOST, OWN_PROFILE_LISTS_PROJECT,
          SOURCE_UNIT_MEMBER, SAME_INSTITUTE, UNIQUE_NAME_IN_FAMILY}
SLUG_SIGNALS = {PROFILE_SLUG_INFERRED_ALIAS, PROFILE_SLUG_FAMILY_HOST}
BLOCKING = {LINKS_OTHER_PROFILE, LINK_NAME_MISMATCH, MULTIPLE_CANDIDATES, SAME_NAME_MULTIPLE_PERSONS,
            CONFLICTING_HARD_ID, MANUAL_NOT_SAME_AS}

# Automatic rules, tried in order. Each needs a full-name match plus the listed signals,
# a single viable candidate and no blocking signal.
RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    # (rule id, required signals besides the full name, signals that switch the rule off)
    ("slug_inferred_alias", (PROFILE_SLUG_INFERRED_ALIAS,), ()),
    ("slug_family_host", (PROFILE_SLUG_FAMILY_HOST,), ()),
    ("own_profile_project", (OWN_PROFILE_LISTS_PROJECT,), ()),
    ("unit_member_unique", (SOURCE_UNIT_MEMBER, UNIQUE_NAME_IN_FAMILY), ()),
    ("institute_unique_name", (SAME_INSTITUTE, UNIQUE_NAME_IN_FAMILY), (COMMON_SURNAME,)),
]

_SLUG_RE = re.compile(r"/kutato/([^/?#]+)")


# ---------------------------------------------------------------- configuration
@dataclass
class Family:
    key: str
    sources: set[str]
    profile_hosts: set[str]
    shared_slugs: bool


@dataclass
class ResolutionConfig:
    resolver_version: str = "person-mention-resolver/0"
    families: list[Family] = field(default_factory=list)
    common_surnames: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> ResolutionConfig:
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        fams = [Family(k, set(v.get("sources") or []), {h.lower() for h in v.get("profile_hosts") or []},
                       bool(v.get("shared_profile_slug_namespace")))
                for k, v in (data.get("institution_families") or {}).items()]
        return cls(data.get("resolver_version", "person-mention-resolver/0"), fams,
                   {s.lower() for s in data.get("common_surnames") or []})

    def family_of_source(self, source_id: str) -> Family | None:
        return next((f for f in self.families if source_id in f.sources), None)


@dataclass
class MentionDecision:
    person_id: str
    decision: str  # same_as | not_same_as
    mention_id: str | None = None
    source_ref: str | None = None
    reviewer: str | None = None
    date: str | None = None
    evidence: str | None = None

    def applies(self, m: PersonMention) -> bool:
        return (self.mention_id == m.canonical_id) or (self.source_ref is not None and self.source_ref == m.source_ref)


def load_mention_decisions(path: Path) -> list[MentionDecision]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for d in data.get("mention_decisions") or []:
        out.append(MentionDecision(person_id=d["person_id"], decision=d["decision"], mention_id=d.get("mention_id"),
                                   source_ref=d.get("source_ref"), reviewer=d.get("reviewer"),
                                   date=str(d["date"]) if d.get("date") else None, evidence=d.get("evidence")))
    return out


# ---------------------------------------------------------------- helpers
def exact_form(name: str) -> str:
    cleaned, _ = clean_display_name(name)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", cleaned).replace(".", ". ")).strip().lower()


def _initials_compatible(a: str, b: str) -> bool:
    """Same family name; every given-name token of the shorter form fits one of the other's
    tokens in order, by full token or by initial ('Papp Z. Attila' ~ 'Papp Attila')."""
    ta, tb = name_key(a).split(), name_key(b).split()
    if len(ta) < 2 or len(tb) < 2 or ta[0] != tb[0] or ta == tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    i = 1
    for t in short[1:]:
        while i < len(long_) and not (long_[i] == t or (len(t) == 1 and long_[i][0] == t)
                                      or (len(long_[i]) == 1 and t[0] == long_[i])):
            i += 1
        if i == len(long_):
            return False
        i += 1
    return True


def title_fold(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slug_of(url: str | None) -> str | None:
    m = _SLUG_RE.search(url or "")
    return m.group(1) if m else None


def host_of(url: str | None) -> str:
    return (urlsplit(url or "").hostname or "").lower()


# ---------------------------------------------------------------- person index
@dataclass
class PersonFacts:
    person: Person
    names: dict[str, str]  # name_key -> "label" | "alternate"
    exact: set[str]
    slugs: set[str]
    profile_hosts: set[str]
    sources: set[str]
    families: set[str]
    units: set[str]
    institutes: set[str]
    projects: set[str]
    project_titles: dict[str, str]  # folded title -> project id


class Index:
    """Everything the rules may know about canonical Persons, from certain evidence only."""

    def __init__(self, ds, registry: Registry, config: ResolutionConfig, ref_to_id: dict[str, str]):
        self.registry, self.config = registry, config
        self.host_source = {host_of(s.base_url): s.source_id for s in registry.sources if s.base_url}
        self.site_unit = {s.source_id: ref_to_id.get(f"{s.source_id}|site") for s in registry.sources}
        self.site_units = {u for u in self.site_unit.values() if u}
        parent: dict[str, set[str]] = defaultdict(set)
        out: dict[str, dict[RelationType, set[str]]] = defaultdict(lambda: defaultdict(set))
        self.hosted_by: dict[str, set[str]] = defaultdict(set)
        for r in ds.relations:
            out[r.source_id][r.type].add(r.target_id)
            if r.type is RelationType.PART_OF:
                parent[r.source_id].add(r.target_id)
            if r.type is RelationType.HOSTED_BY:
                self.hosted_by[r.source_id].add(r.target_id)
        self.parent = parent
        self.entities = ds.entities
        self.persons: dict[str, PersonFacts] = {}
        self.by_key: dict[str, set[str]] = defaultdict(set)
        self.by_order_free: dict[str, set[str]] = defaultdict(set)
        self.by_surname: dict[str, set[str]] = defaultdict(set)
        self.by_slug: dict[str, set[str]] = defaultdict(set)
        for p in ds.by_type(EntityType.PERSON):
            names = {name_key(p.label): "label"}
            for n in p.alternate_names:
                names.setdefault(name_key(n), "alternate")
            profile = [u for u in p.profile_urls if slug_of(u) and host_of(u) in self.host_source]
            sources = {self.host_source[host_of(u)] for u in profile}
            fams = {f.key for s in sources if (f := config.family_of_source(s))}
            units = out[p.canonical_id][RelationType.AFFILIATED_WITH] | out[p.canonical_id][RelationType.MEMBER_OF] \
                | out[p.canonical_id][RelationType.LEADS]
            projects = out[p.canonical_id][RelationType.PARTICIPATES_IN] \
                | out[p.canonical_id][RelationType.PRINCIPAL_INVESTIGATOR_OF]
            facts = PersonFacts(
                p, names, {exact_form(n) for n in [p.label, *p.alternate_names]},
                {slug_of(u) for u in profile}, {host_of(u) for u in profile}, sources, fams, units,
                self.institutes(units), projects,
                {title_fold(t): pid for pid in projects
                 if (e := ds.entities.get(pid)) is not None and len(t := title_fold(e.label)) >= 15},
            )
            self.persons[p.canonical_id] = facts
            for k in names:
                self.by_key[k].add(p.canonical_id)
                self.by_order_free[" ".join(sorted(k.split()))].add(p.canonical_id)
                if k.split():
                    self.by_surname[k.split()[0]].add(p.canonical_id)
            for s in facts.slugs:
                self.by_slug[s].add(p.canonical_id)

    def ancestors(self, unit: str) -> set[str]:
        seen, stack = set(), [unit]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(self.parent.get(u, ()))
        return seen

    def institutes(self, units: set[str]) -> set[str]:
        return {a for u in units for a in self.ancestors(u)} & self.site_units

    def family_hosts(self, fam_key: str) -> set[str]:
        fam = next(f for f in self.config.families if f.key == fam_key)
        hosts = set(fam.profile_hosts)
        for s in self.registry.sources:
            if s.source_id in fam.sources and s.base_url:
                hosts |= {host_of(s.base_url), *(a.lower() for a in s.host_aliases)}
        return hosts


# ---------------------------------------------------------------- the resolver
def resolve_mentions(mentions: dict[str, PersonMention], ds, registry: Registry, config: ResolutionConfig,
                     ref_to_id: dict[str, str], manual: list[MentionDecision]) -> None:
    """Fill ``candidates`` for every mention and decide the pending ones, in place."""
    idx = Index(ds, registry, config, ref_to_id)
    for m in mentions.values():
        _resolve_one(m, idx, config, manual)


def _name_match(m: PersonMention, f: PersonFacts) -> str | None:
    key = m.normalized_name
    if exact_form(m.stated_name) in f.exact:
        return NAME_EXACT if f.names.get(key) == "label" else ALTERNATE_NAME_MATCH
    if f.names.get(key) == "label":
        return SAME_NORMALIZED_NAME
    if key in f.names:
        return ALTERNATE_NAME_MATCH
    if any(order_free_key(m.stated_name) == " ".join(sorted(k.split())) for k in f.names):
        return NAME_ORDER_VARIANT
    if any(_initials_compatible(m.stated_name, k) for k in f.names):
        return NAME_INITIALS_COMPATIBLE
    return None


def _candidates(m: PersonMention, idx: Index) -> set[str]:
    key = m.normalized_name
    out = set(idx.by_key.get(key, ())) | set(idx.by_order_free.get(order_free_key(m.stated_name), ()))
    toks = key.split()
    if toks:
        out |= {p for p in idx.by_surname.get(toks[0], ())
                if any(_initials_compatible(m.stated_name, k) for k in idx.persons[p].names)}
    if (s := slug_of(m.linked_profile_url)):
        out |= idx.by_slug.get(s, set())
    return out


def _context_targets(m: PersonMention) -> tuple[set[str], set[str]]:
    projects, units = set(), set()
    for c in m.context:
        if not c.target_id:
            continue
        if c.relation in (RelationType.PARTICIPATES_IN, RelationType.PRINCIPAL_INVESTIGATOR_OF):
            projects.add(c.target_id)
        elif c.relation in (RelationType.MEMBER_OF, RelationType.LEADS, RelationType.AFFILIATED_WITH):
            units.add(c.target_id)
    return projects, units


def _signals(m: PersonMention, pid: str, idx: Index, config: ResolutionConfig,
             evidence: dict[str, Any]) -> tuple[list[str], list[str], str]:
    f = idx.persons[pid]
    pos, neg = [], []
    match = _name_match(m, f) or "SLUG_ONLY"
    if match != "SLUG_ONLY":
        pos.append(match)
    full = match in FULL_NAME
    fam = config.family_of_source(m.source_id)
    if fam and fam.key in f.families:
        pos.append(SAME_INSTITUTION_FAMILY)

    # profile links as the page wrote them
    link_slug, link_host = slug_of(m.linked_profile_url), host_of(m.linked_profile_url)
    if link_slug and fam and link_host in idx.family_hosts(fam.key):
        if link_slug in f.slugs:
            stated = {host_of(u): idx.registry.alias_status(host_of(u)) for u in m.stated_profile_urls}
            if link_host in f.profile_hosts and stated and all(s == "inferred" for s in stated.values()):
                pos.append(PROFILE_SLUG_INFERRED_ALIAS)
                evidence["stated_hosts"] = stated
            elif fam.shared_slugs and link_host not in f.profile_hosts:
                pos.append(PROFILE_SLUG_FAMILY_HOST)
                evidence["shared_slug_namespace"] = fam.key
            evidence["linked_profile_url"] = m.linked_profile_url
            if not full:
                neg.append(LINK_NAME_MISMATCH)
        elif f.slugs:
            neg.append(LINKS_OTHER_PROFILE)
            evidence["linked_profile_url"] = m.linked_profile_url

    projects, units = _context_targets(m)
    hit = sorted(projects & f.projects)
    titles = sorted({title_fold(idx.entities[p].label) for p in projects if p in idx.entities} & set(f.project_titles))
    if hit or titles:
        pos.append(OWN_PROFILE_LISTS_PROJECT)
        evidence["projects"] = hit + [f.project_titles[t] for t in titles if f.project_titles[t] not in hit]
        evidence["project_match"] = "id" if hit else "title"
    hosts = {u for p in projects for u in idx.hosted_by.get(p, ())} - idx.site_units
    unit_hit = sorted((units | hosts) & f.units)
    if unit_hit:
        pos.append(SOURCE_UNIT_MEMBER)
        evidence["units"] = unit_hit
    page_institute = idx.site_unit.get(m.source_id)
    if page_institute and page_institute in f.institutes:
        pos.append(SAME_INSTITUTE)
        evidence["institute"] = page_institute
    elif page_institute and f.institutes:
        neg.append(DIFFERENT_INSTITUTE)

    if fam:
        same = {p for p in idx.by_key.get(m.normalized_name, ()) if fam.key in idx.persons[p].families}
        if same == {pid}:
            pos.append(UNIQUE_NAME_IN_FAMILY)
            evidence["uniqueness_scope"] = fam.key
        elif len(same) > 1 and pid in same:
            neg.append(SAME_NAME_MULTIPLE_PERSONS)
    for k, v in m.stated_identifiers.items():
        own = getattr(f.person, k, None)
        if own and own != v:
            neg.append(CONFLICTING_HARD_ID)
    if m.normalized_name.split()[:1] and m.normalized_name.split()[0] in config.common_surnames:
        neg.append(COMMON_SURNAME)
    return pos, neg, match


def _resolve_one(m: PersonMention, idx: Index, config: ResolutionConfig, manual: list[MentionDecision]) -> None:
    rejected = {d.person_id for d in manual if d.decision == "not_same_as" and d.applies(m)}
    confirmed = next((d for d in manual if d.decision == "same_as" and d.applies(m)), None)

    cands: list[MentionCandidate] = []
    details: dict[str, dict[str, Any]] = {}
    for pid in sorted(_candidates(m, idx) | ({m.resolution.person_id} if m.resolution.person_id else set())):
        if pid not in idx.persons:
            continue
        ev: dict[str, Any] = {}
        pos, neg, match = _signals(m, pid, idx, config, ev)
        if pid in rejected:
            neg.append(MANUAL_NOT_SAME_AS)
        cands.append(MentionCandidate(person_id=pid, name_match=match, signals=pos, negative_signals=neg,
                                      rejected=pid in rejected))
        details[pid] = ev
    viable = [c for c in cands if not c.rejected and (set(c.signals) & (set(FULL_NAME) | SLUG_SIGNALS)
                                                      or LINK_NAME_MISMATCH in c.negative_signals)]
    if len(viable) > 1:
        for c in viable:
            c.negative_signals.append(MULTIPLE_CANDIDATES)
    cands.sort(key=lambda c: (c.rejected, c not in viable, -len(set(c.signals) & STRONG), -len(c.signals),
                              c.person_id))
    m.candidates = cands
    res = m.resolution

    if confirmed is not None:
        if confirmed.person_id in idx.persons:
            m.resolution = MentionResolution(
                status=MentionResolutionStatus.MANUAL_CONFIRMED, person_id=confirmed.person_id,
                method="manual:mention_same_as", signals=[MANUAL_SAME_AS],
                evidence={k: v for k, v in (("reviewer", confirmed.reviewer), ("evidence", confirmed.evidence)) if v},
                decision_source=OVERRIDES, resolver_version=config.resolver_version,
                decided_at=datetime.fromisoformat(confirmed.date) if confirmed.date else None)
        else:
            m.resolution = MentionResolution(status=MentionResolutionStatus.REVIEW_REQUIRED if cands else
                                             MentionResolutionStatus.UNRESOLVED,
                                             reason=f"manual same_as names a missing Person {confirmed.person_id}",
                                             decision_source=OVERRIDES, resolver_version=config.resolver_version)
        return
    if res.status.resolved:
        if res.person_id in rejected:  # a manual rejection outranks any automatic rule, even a certain one
            m.resolution = MentionResolution(status=MentionResolutionStatus.REVIEW_REQUIRED,
                                             negative_signals=[MANUAL_NOT_SAME_AS],
                                             reason="manual not_same_as contradicts the automatic link",
                                             decision_source=OVERRIDES, resolver_version=config.resolver_version)
        else:
            res.resolver_version = config.resolver_version
        return

    if len(viable) == 1:
        c = viable[0]
        blocking = sorted(set(c.negative_signals) & BLOCKING)
        if not blocking and set(c.signals) & set(FULL_NAME):
            for rule, needs, offs in RULES:
                if all(s in c.signals for s in needs) and not set(offs) & set(c.negative_signals):
                    m.resolution = MentionResolution(
                        status=MentionResolutionStatus.HIGH_CONFIDENCE_AUTO, person_id=c.person_id, method=rule,
                        signals=list(c.signals), negative_signals=list(c.negative_signals),
                        evidence=details[c.person_id], decision_source=f"{RESOLVER_DOC}#{rule.replace('_', '-')}",
                        resolver_version=config.resolver_version)
                    return
    m.resolution = MentionResolution(
        status=MentionResolutionStatus.REVIEW_REQUIRED if any(not c.rejected for c in cands)
        else MentionResolutionStatus.UNRESOLVED,
        reason=_why_not(cands, viable, res.reason), decision_source=RESOLVER_DOC,
        resolver_version=config.resolver_version)


def _why_not(cands: list[MentionCandidate], viable: list[MentionCandidate], prior: str | None) -> str:
    if not cands:
        return "no canonical Person with a compatible name or the linked profile slug"
    if all(c.rejected for c in cands):
        return "every candidate was rejected manually"
    if not viable:
        return "only weak name evidence (order variant or initials)"
    if len(viable) > 1:
        return f"{len(viable)} viable candidates"
    c = viable[0]
    if blocking := sorted(set(c.negative_signals) & BLOCKING):
        return "blocked: " + ", ".join(blocking)
    have = sorted(set(c.signals) & STRONG)
    why = f"no rule satisfied (strong signals: {', '.join(have) or 'none'})"
    if COMMON_SURNAME in c.negative_signals and SAME_INSTITUTE in c.signals:
        why += "; common surname needs more than institute + unique name"
    if prior and prior.startswith("profile link only through an inferred"):
        why += "; " + prior
    return why


def claim_persons(mentions: dict[str, PersonMention], claim_mention: dict[tuple[str, str], str],
                  own_claims: dict[tuple[str, str], str], *, certain_only: bool = False) -> dict[tuple[str, str], str]:
    """Person side of each claim -> canonical id: own-profile observations plus resolved mentions."""
    ok = {MentionResolutionStatus.DETERMINISTIC, MentionResolutionStatus.MANUAL_CONFIRMED}
    if not certain_only:
        ok.add(MentionResolutionStatus.HIGH_CONFIDENCE_AUTO)
    out = dict(own_claims)
    for side, mid in claim_mention.items():
        r = mentions[mid].resolution
        if r.status in ok and r.person_id:
            out[side] = r.person_id
    return out
