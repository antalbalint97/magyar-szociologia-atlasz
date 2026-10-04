"""CLAIMS + IDENTITY  ->  PERSON MENTIONS (ADR-0006).

A PersonMention is one person-like source record observed in one page other than the
person's own profile: a linked name on a listing, unit or project page, or an unlinked
name in a participant list. It carries what the page said (stated name, linked profile
URL, the relations the page asserts) and the identity decision that ties it, or does
not tie it, to a canonical Person.

Mention ids are ``pmn_`` + a hash of (source record ref, observing page URL), so the
same observation keeps its id across re-crawls and rebuilds.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit

from ..models.entities import ID_PREFIX, MentionContext, MentionResolution, PersonMention
from ..models.enums import EntityType, IdentityAnchor, MatchStatus, MentionResolutionStatus, RelationType
from ..models.provenance import Claim, SourceDocument, SourceRecord, stable_hash
from ..normalize.names import name_key
from ..resolution.matcher import HARD_IDS, MatchDecision

RULE_DOC = "docs/adr/0006-person-mentions-vs-canonical-persons.md"
OVERRIDES = "review/manual_overrides.yaml"


def mention_id(source_ref: str, page_url: str) -> str:
    return f"{ID_PREFIX[EntityType.PERSON_MENTION]}_{stable_hash(source_ref, page_url, length=10)}"


def _ref_url(ref: str) -> str | None:
    loc = ref.split("|", 1)[1] if "|" in ref else ""
    return loc if urlsplit(loc).scheme in ("http", "https") else None


@dataclass
class _Obs:
    ref: str
    url: str
    labels: list[str] = field(default_factory=list)
    document_ids: set[str] = field(default_factory=set)
    claims: list[tuple[Claim, str]] = field(default_factory=list)  # (claim, "out" | "in")


def build_mentions(
    records: list[SourceRecord],
    claims: list[Claim],
    documents: dict[str, SourceDocument],
    ref_to_id: dict[str, str],
    decisions: list[MatchDecision],
    anchors: dict[str, set[IdentityAnchor]],
    decided_at: datetime,
) -> dict[str, PersonMention]:
    # pages that are a person's own profile: observations there are the identity, not mentions
    own: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if r.ref.entity_type is EntityType.PERSON and r.identity_anchor and r.document_id in documents:
            own[r.ref.source_ref].add(documents[r.document_id].canonical_url)

    obs: dict[tuple[str, str], _Obs] = {}

    def observe(ref: str, document_id: str) -> _Obs | None:
        doc = documents.get(document_id)
        if doc is None or doc.url.startswith("repo://") or doc.canonical_url in own.get(ref, ()):
            return None
        o = obs.setdefault((ref, doc.canonical_url), _Obs(ref, doc.canonical_url))
        o.document_ids.add(document_id)
        return o

    for r in records:
        if r.ref.entity_type is EntityType.PERSON and r.ref.source_ref:
            if (o := observe(r.ref.source_ref, r.document_id)) and r.label not in o.labels:
                o.labels.append(r.label)
    for c in claims:
        for side, ref in (("out", c.subject), ("in", c.object)):
            if ref is not None and ref.entity_type is EntityType.PERSON and ref.source_ref:
                if o := observe(ref.source_ref, c.evidence.document_id):
                    o.claims.append((c, side))

    confirmed: dict[str, list[MatchDecision]] = defaultdict(list)
    possible: dict[str, list[MatchDecision]] = defaultdict(list)
    for d in decisions:
        if d.entity_type is not EntityType.PERSON:
            continue
        bucket = confirmed if d.status is MatchStatus.CONFIRMED else possible if d.status is MatchStatus.POSSIBLE else None
        if bucket is not None:
            bucket[d.left].append(d)
            bucket[d.right].append(d)

    out: dict[str, PersonMention] = {}
    for (ref, url), o in sorted(obs.items()):
        names = [c for c, side in o.claims if side == "out" and c.object is None and c.predicate == "name"]
        stated = Counter(str(c.value) for c in names).most_common(1)[0][0] if names else (o.labels or [""])[0]
        if not stated:
            continue
        context = _context(o, ref_to_id)
        ids = {c.predicate: str(c.value) for c, side in o.claims
               if side == "out" and c.object is None and c.predicate in HARD_IDS and c.value}
        retrieved = sorted(documents[d].retrieved_at for d in o.document_ids)
        provenance = {"stated_name": sorted({c.claim_id for c in names})} if names else {}
        if context:
            provenance["context"] = sorted({i for cx in context for i in cx.claim_ids})
        if ids:
            provenance["stated_identifiers"] = sorted({c.claim_id for c, side in o.claims
                                                       if side == "out" and c.predicate in ids})
        pid = ref_to_id.get(ref)
        out_id = mention_id(ref, url)
        out[out_id] = PersonMention(
            canonical_id=out_id,
            label=stated,
            provenance=provenance,
            source_refs=[ref],
            first_observed_at=retrieved[0],
            last_verified_at=retrieved[-1],
            stated_name=stated,
            normalized_name=name_key(stated),
            source_ref=ref,
            source_id=documents[sorted(o.document_ids)[0]].source_id,
            source_url=url,
            document_ids=sorted(o.document_ids),
            linked_profile_url=_ref_url(ref),
            stated_identifiers=ids,
            context=context,
            resolution=_resolution(ref, pid, anchors, confirmed, decided_at),
            candidate_person_ids=sorted({ref_to_id[x] for d in possible.get(ref, [])
                                         for x in (d.left, d.right) if x != ref and x in ref_to_id} - {pid}),
        )
    return out


def _context(o: _Obs, ref_to_id: dict[str, str]) -> list[MentionContext]:
    grouped: dict[tuple, list[Claim]] = defaultdict(list)
    for c, side in o.claims:
        if c.object is None:
            continue
        other = c.object if side == "out" else c.subject
        grouped[(c.predicate, side, other.canonical_id or ref_to_id.get(other.source_ref or ""),
                 None if (other.canonical_id or ref_to_id.get(other.source_ref or "")) else other.source_ref)
                ].append(c)
    out = []
    for (pred, side, tid, tref), cs in sorted(grouped.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        try:
            rtype = RelationType(pred)
        except ValueError:
            continue
        quals: dict[str, list] = defaultdict(list)
        for c in cs:
            for k, v in c.qualifiers.items():
                if v not in quals[k]:
                    quals[k].append(v)
        froms = sorted(c.valid_from for c in cs if c.valid_from)
        untils = sorted(c.valid_until for c in cs if c.valid_until)
        out.append(MentionContext(relation=rtype, direction=side, target_id=tid, target_ref=tref,
                                  qualifiers=dict(quals), valid_from=froms[0] if froms else None,
                                  valid_until=untils[-1] if untils else None, snippet=cs[0].evidence.snippet,
                                  claim_ids=sorted(c.claim_id for c in cs)))
    return out


def _resolution(ref: str, pid: str | None, anchors: dict[str, set[IdentityAnchor]],
                confirmed: dict[str, list[MatchDecision]], decided_at: datetime) -> MentionResolution:
    if pid is None:
        return MentionResolution(status=MentionResolutionStatus.UNRESOLVED, decided_at=decided_at,
                                 decision_source=RULE_DOC)
    if ref in anchors:
        # the page links to the person's own canonical profile URL (or states a hard id)
        url = _ref_url(ref)
        return MentionResolution(
            status=MentionResolutionStatus.DETERMINISTIC, person_id=pid, decided_at=decided_at,
            method="profile_url" if url else "hard_id",
            signals={"linked_profile_url": url} if url else {"anchors": sorted(anchors[ref])},
            decision_source=f"{RULE_DOC}#resolution-decision",
        )
    ds = confirmed.get(ref, [])
    manual = next((d for d in ds if d.method.startswith("manual")), None)
    if manual is not None:
        return MentionResolution(status=MentionResolutionStatus.MANUAL_CONFIRMED, person_id=pid,
                                 method=manual.method, signals={"pair": [manual.left, manual.right]},
                                 decision_source=OVERRIDES, decided_at=decided_at)
    hard = next((d for d in ds if d.method == "auto:hard_id+name"), None)
    if hard is not None:
        return MentionResolution(status=MentionResolutionStatus.DETERMINISTIC, person_id=pid,
                                 method=hard.method, signals=dict(hard.signals),
                                 decision_source=f"{RULE_DOC}#resolution-decision", decided_at=decided_at)
    d = ds[0] if ds else None
    return MentionResolution(status=MentionResolutionStatus.HIGH_CONFIDENCE_AUTO, person_id=pid,
                             method=d.method if d else "cluster", signals=dict(d.signals) if d else {},
                             decision_source="szocatlas.resolution.matcher", decided_at=decided_at)
