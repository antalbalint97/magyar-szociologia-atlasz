"""CLAIMS + IDENTITY  ->  PROJECT MENTIONS (ADR-0008).

A ProjectMention is one project-like source record observed in one page other than the
project's own page: an article on a category listing, a line in a researcher profile's
"Projektek" section, a link to a project page that was never fetched. It carries what
the page said (title as written, the profile owner's role, a stated period, raw funder
and grant strings) and the identity decision that ties it, or does not tie it, to an
anchored Project.

Mention ids are ``pjm_`` + a hash of (source record ref, observing page URL).

This module makes only the *certain* decisions: the mention names the Project's own
page URL, or a reviewer joined its record to an anchored one. Everything else leaves
here pending for the project resolver (resolution/projects.py).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ..models.entities import ID_PREFIX, MentionContext, ProjectMention, ProjectMentionResolution
from ..models.enums import EntityType, IdentityAnchor, MentionResolutionStatus, RelationType
from ..models.provenance import Claim, SourceDocument, SourceRecord, stable_hash
from ..resolution.projects import PROJECT_RESOLVER_DOC, activity_cues, grant_keys, registry_grant_keys, title_key

OVERRIDES = "review/manual_overrides.yaml"
Side = tuple[str, str]  # (claim_id, "subject" | "object")
_PERSON_SIDE_RELATIONS = {RelationType.PARTICIPATES_IN.value, RelationType.PRINCIPAL_INVESTIGATOR_OF.value}


def project_mention_id(source_ref: str, page_url: str) -> str:
    return f"{ID_PREFIX[EntityType.PROJECT_MENTION]}_{stable_hash(source_ref, page_url, length=10)}"


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


@dataclass
class ProjectMentionBuild:
    mentions: dict[str, ProjectMention]
    claim_mention: dict[Side, str]  # project side of a claim -> the mention it was observed as
    own_claims: dict[Side, str]  # project side observed on the project's own page -> project id


def build_project_mentions(
    records: list[SourceRecord],
    claims: list[Claim],
    documents: dict[str, SourceDocument],
    ref_to_id: dict[str, str],
    anchors: dict[str, set[IdentityAnchor]],
    person_sides: dict[Side, str],
) -> ProjectMentionBuild:
    """``person_sides``: person side of a claim -> Person id, for observations on the person's
    own profile (the profile owner who lists a project)."""
    own: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if r.ref.entity_type is EntityType.PROJECT and r.identity_anchor and r.document_id in documents:
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

    any_label: dict[str, str] = {}
    for r in records:
        if r.ref.entity_type is EntityType.PROJECT and r.ref.source_ref:
            any_label.setdefault(r.ref.source_ref, r.label)
            if (o := observe(r.ref.source_ref, r.document_id)) and r.label not in o.labels:
                o.labels.append(r.label)
    claim_obs: dict[Side, tuple[str, str]] = {}
    for c in claims:
        for side, pos, ref in (("out", "subject", c.subject), ("in", "object", c.object)):
            if ref is None or ref.entity_type is not EntityType.PROJECT or not ref.source_ref:
                continue
            if o := observe(ref.source_ref, c.evidence.document_id):
                o.claims.append((c, side))
                claim_obs[(c.claim_id, pos)] = (o.ref, o.url)
            elif ref.source_ref in ref_to_id:
                own_claims[(c.claim_id, pos)] = ref_to_id[ref.source_ref]

    out: dict[str, ProjectMention] = {}
    key_to_id: dict[tuple[str, str], str] = {}
    for (ref, url), o in sorted(obs.items()):
        lit: dict[str, list[Claim]] = defaultdict(list)
        rels: list[Claim] = []
        for c, side in o.claims:
            if side == "out" and c.object is None:
                lit[c.predicate].append(c)
            else:
                rels.append(c)
        titles = lit.get("title", [])
        # a page that links a project without naming it (rare) is still an observation of it
        stated = Counter(str(c.value) for c in titles).most_common(1)[0][0] if titles else \
            (o.labels or [any_label.get(ref, "")])[0]
        if not stated:
            continue
        owner_claims = [c for c in rels if c.predicate in _PERSON_SIDE_RELATIONS
                        and (c.claim_id, "subject") in person_sides]
        owners = sorted({person_sides[(c.claim_id, "subject")] for c in owner_claims})
        froms = sorted({str(c.value) for c in lit.get("start", [])} | {c.valid_from for c in owner_claims if c.valid_from})
        untils = sorted({str(c.value) for c in lit.get("end", [])} | {c.valid_until for c in owner_claims if c.valid_until})
        grants = list(dict.fromkeys(str(c.value) for c in lit.get("grant_id", [])))
        funders = list(dict.fromkeys(str(c.value) for c in lit.get("funding_body", [])))
        roles = list(dict.fromkeys(str(c.qualifiers["role"]) for c in owner_claims if c.qualifiers.get("role")))
        leads = list(dict.fromkeys(str(c.qualifiers["stated_lead"]) for c in owner_claims
                                   if c.qualifiers.get("stated_lead")))
        status = list(dict.fromkeys(str(c.value) for c in lit.get("status_label", [])))
        locators = [c.evidence.locator for c, _ in o.claims]
        kind = "profile_list" if any(loc.startswith("profile.section.projektek") for loc in locators) else \
            "project_listing" if any(loc.startswith("listing.article") for loc in locators) else "other"
        context = _context(o, rels, ref_to_id, person_sides)
        provenance: dict[str, list[str]] = {}
        for fname, cs in (("stated_title", titles), ("stated_grant_ids", lit.get("grant_id", [])),
                          ("stated_funders", lit.get("funding_body", [])),
                          ("stated_period", lit.get("start", []) + lit.get("end", [])),
                          ("stated_status", lit.get("status_label", [])),
                          ("stated_roles", [c for c in owner_claims if c.qualifiers.get("role")]),
                          ("context", rels)):
            if cs:
                provenance[fname] = sorted({c.claim_id for c in cs})
        retrieved = sorted(documents[d].retrieved_at for d in o.document_ids)
        mid = project_mention_id(ref, url)
        key_to_id[(ref, url)] = mid
        out[mid] = ProjectMention(
            canonical_id=mid,
            label=stated,
            provenance=provenance,
            source_refs=[ref],
            first_observed_at=retrieved[0],
            last_verified_at=retrieved[-1],
            stated_title=stated,
            title_key=title_key(stated),
            observation=kind,
            source_ref=ref,
            source_id=documents[sorted(o.document_ids)[0]].source_id,
            source_url=url,
            document_ids=sorted(o.document_ids),
            linked_url=_ref_url(ref),
            observed_on_profile_of=owners[0] if len(owners) == 1 else None,
            stated_period_from=froms[0] if froms else None,
            stated_period_until=untils[-1] if untils else None,
            stated_funders=funders,
            stated_grant_ids=grants,
            grant_keys=list(dict.fromkeys(grant_keys(*grants, stated) + registry_grant_keys(_ref_url(ref)))),
            stated_roles=roles,
            stated_leads=leads,
            stated_status=status,
            context=context,
            activity_cues=activity_cues(stated),
            resolution=_certain(ref, ref_to_id.get(ref), anchors),
        )
    claim_mention = {side: key_to_id[k] for side, k in claim_obs.items() if k in key_to_id}
    return ProjectMentionBuild(out, claim_mention, own_claims)


def _context(o: _Obs, rels: list[Claim], ref_to_id: dict[str, str],
             person_sides: dict[Side, str]) -> list[MentionContext]:
    grouped: dict[tuple, list[Claim]] = defaultdict(list)
    sides = {c.claim_id: side for c, side in o.claims}
    for c in rels:
        side = sides[c.claim_id]
        other, pos = (c.object, "object") if side == "out" else (c.subject, "subject")
        if other is None:
            continue
        if other.entity_type is EntityType.PERSON:
            # only the profile owner is a resolved target here; other people are person mentions
            tid = person_sides.get((c.claim_id, pos))
        else:
            tid = other.canonical_id or ref_to_id.get(other.source_ref or "")
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


def _certain(ref: str, pid: str | None, anchors: dict[str, set[IdentityAnchor]]) -> ProjectMentionResolution:
    if pid is None:
        return ProjectMentionResolution(status=MentionResolutionStatus.UNRESOLVED,
                                        reason="pending evidence resolution", decision_source=PROJECT_RESOLVER_DOC)
    kinds = anchors.get(ref, set())
    if IdentityAnchor.PROJECT_PAGE in kinds:
        # the observation names the project's own page (after host aliasing; no project link
        # in the snapshot is written on an inferred alias host, see ADR-0008)
        return ProjectMentionResolution(status=MentionResolutionStatus.DETERMINISTIC, project_id=pid,
                                        method="project_url", signals=["PROJECT_URL_EXACT"],
                                        evidence={"project_url": _ref_url(ref)},
                                        decision_source=f"{PROJECT_RESOLVER_DOC}#candidates-are-not-decisions")
    return ProjectMentionResolution(status=MentionResolutionStatus.MANUAL_CONFIRMED, project_id=pid,
                                    method="manual:same_as", signals=["MANUAL_SAME_AS"],
                                    evidence={"source_ref": ref}, decision_source=OVERRIDES)
