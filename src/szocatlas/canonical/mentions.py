"""CLAIMS + IDENTITY  ->  PERSON MENTIONS (ADR-0006).

A PersonMention is one person-like source record observed in one page other than the
person's own profile: a linked name on a listing, unit or project page, or an unlinked
name in a participant list. It carries what the page said (stated name, linked profile
URL as written, the relations the page asserts) and the identity decision that ties it,
or does not tie it, to a canonical Person.

Mention ids are ``pmn_`` + a hash of (source record ref, observing page URL), so the
same observation keeps its id across re-crawls and rebuilds.

This module makes only the *certain* decisions (ADR-0006): exact profile URL on the
canonical host or a verified alias, a stated hard id, a manual decision. Everything else
leaves here as pending (UNRESOLVED) for the evidence resolver (resolution/mentions.py, #5).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ..models.entities import ID_PREFIX, MentionContext, MentionResolution, PersonMention
from ..models.enums import EntityType, IdentityAnchor, MatchStatus, MentionResolutionStatus, RelationType
from ..models.provenance import Claim, SourceDocument, SourceRecord, stable_hash
from ..normalize.names import name_key
from ..registry import Registry
from ..resolution.matcher import HARD_IDS, MatchDecision

RULE_DOC = "docs/adr/0006-person-mentions-vs-canonical-persons.md"
RESOLVER_DOC = "docs/adr/0007-evidence-based-mention-resolution.md"
OVERRIDES = "review/manual_overrides.yaml"
Side = tuple[str, str]  # (claim_id, "subject" | "object")


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
    stated_urls: set[str] = field(default_factory=set)
    document_ids: set[str] = field(default_factory=set)
    claims: list[tuple[Claim, str]] = field(default_factory=list)  # (claim, "out" | "in")


@dataclass
class MentionBuild:
    mentions: dict[str, PersonMention]
    claim_mention: dict[Side, str]  # person side of a claim -> the mention it was observed as
    own_claims: dict[Side, str]  # person side observed on the person's own profile -> person id


def build_mentions(
    records: list[SourceRecord],
    claims: list[Claim],
    documents: dict[str, SourceDocument],
    ref_to_id: dict[str, str],
    decisions: list[MatchDecision],
    anchors: dict[str, set[IdentityAnchor]],
    registry: Registry | None = None,
) -> MentionBuild:
    # pages that are a person's own profile: observations there are the identity, not mentions
    own: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if r.ref.entity_type is EntityType.PERSON and r.identity_anchor and r.document_id in documents:
            own[r.ref.source_ref].add(documents[r.document_id].canonical_url)

    obs: dict[tuple[str, str], _Obs] = {}
    own_claims: dict[Side, str] = {}

    def observe(ref: str, document_id: str) -> _Obs | None:
        doc = documents.get(document_id)
        if doc is None or doc.url.startswith("repo://") or doc.canonical_url in own.get(ref, ()):
            return None
        o = obs.setdefault((ref, doc.canonical_url), _Obs(ref, doc.canonical_url))
        o.document_ids.add(document_id)
        return o

    for r in records:
        if r.ref.entity_type is EntityType.PERSON and r.ref.source_ref:
            if o := observe(r.ref.source_ref, r.document_id):
                if r.label not in o.labels:
                    o.labels.append(r.label)
                if r.hints.get("stated_url"):
                    o.stated_urls.add(str(r.hints["stated_url"]))
    claim_obs: dict[Side, tuple[str, str]] = {}
    for c in claims:
        for side, pos, ref in (("out", "subject", c.subject), ("in", "object", c.object)):
            if ref is None or ref.entity_type is not EntityType.PERSON:
                continue
            if not ref.source_ref:
                continue  # curated claim naming a canonical id directly
            if o := observe(ref.source_ref, c.evidence.document_id):
                o.claims.append((c, side))
                claim_obs[(c.claim_id, pos)] = (o.ref, o.url)
            elif ref.source_ref in ref_to_id:
                own_claims[(c.claim_id, pos)] = ref_to_id[ref.source_ref]

    confirmed: dict[str, list[MatchDecision]] = defaultdict(list)
    for d in decisions:
        if d.entity_type is EntityType.PERSON and d.status is MatchStatus.CONFIRMED:
            confirmed[d.left].append(d)
            confirmed[d.right].append(d)

    out: dict[str, PersonMention] = {}
    key_to_id: dict[tuple[str, str], str] = {}
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
        out_id = mention_id(ref, url)
        key_to_id[(ref, url)] = out_id
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
            stated_profile_urls=sorted(o.stated_urls),
            stated_identifiers=ids,
            context=context,
            resolution=_certain(ref, sorted(o.stated_urls), ref_to_id.get(ref), anchors, confirmed, registry),
        )
    claim_mention = {side: key_to_id[k] for side, k in claim_obs.items() if k in key_to_id}
    return MentionBuild(out, claim_mention, own_claims)


def _context(o: _Obs, ref_to_id: dict[str, str]) -> list[MentionContext]:
    grouped: dict[tuple, list[Claim]] = defaultdict(list)
    for c, side in o.claims:
        if c.object is None:
            continue
        other = c.object if side == "out" else c.subject
        tid = other.canonical_id or ref_to_id.get(other.source_ref or "")
        # another person-like record is never a resolved target here: it is a mention itself
        if other.entity_type is EntityType.PERSON:
            tid = None
        grouped[(c.predicate, side, tid, None if tid else other.source_ref)].append(c)
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


def pending(reason: str = "pending evidence resolution") -> MentionResolution:
    return MentionResolution(status=MentionResolutionStatus.UNRESOLVED, reason=reason, decision_source=RESOLVER_DOC)


def _certain(ref: str, stated_urls: list[str], pid: str | None, anchors: dict[str, set[IdentityAnchor]],
             confirmed: dict[str, list[MatchDecision]], registry: Registry | None) -> MentionResolution:
    if pid is None:
        return pending()
    ds = confirmed.get(ref, [])
    manual = next((d for d in ds if d.method.startswith("manual")), None)
    if manual is not None:
        return MentionResolution(status=MentionResolutionStatus.MANUAL_CONFIRMED, person_id=pid,
                                 method=manual.method, signals=["MANUAL_SAME_AS"],
                                 evidence={"pair": [manual.left, manual.right]}, decision_source=OVERRIDES)
    url = _ref_url(ref)
    if url and ref in anchors:
        # the page links the person's own canonical profile; how it wrote the link matters (#14)
        hosts = {(urlsplit(u).hostname or "").lower() for u in stated_urls}
        status = {h: registry.alias_status(h) for h in sorted(hosts)} if registry else {}
        if not stated_urls or any(s in ("canonical", "verified") for s in status.values()):
            signal = "PROFILE_URL_EXACT" if not status or "canonical" in status.values() \
                else "PROFILE_URL_VERIFIED_ALIAS"
            return MentionResolution(
                status=MentionResolutionStatus.DETERMINISTIC, person_id=pid, method="profile_url",
                signals=[signal], evidence={"linked_profile_url": url, "stated_urls": stated_urls,
                                            "host_alias_status": status},
                decision_source=f"{RULE_DOC}#resolution-decision")
        return pending("profile link only through an inferred host alias")
    if ref in anchors and anchors[ref] & {IdentityAnchor.MTMT, IdentityAnchor.ORCID}:
        return MentionResolution(status=MentionResolutionStatus.DETERMINISTIC, person_id=pid, method="hard_id",
                                 signals=["HARD_ID_MATCH"], evidence={"anchors": sorted(anchors[ref])},
                                 decision_source=f"{RULE_DOC}#resolution-decision")
    hard = next((d for d in ds if d.method == "auto:hard_id+name"), None)
    if hard is not None:
        return MentionResolution(status=MentionResolutionStatus.DETERMINISTIC, person_id=pid,
                                 method=hard.method, signals=["HARD_ID_MATCH"], evidence=dict(hard.signals),
                                 decision_source=f"{RULE_DOC}#resolution-decision")
    return pending("clustered without a certain rule")
