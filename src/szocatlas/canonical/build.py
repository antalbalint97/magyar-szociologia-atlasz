"""CLAIMS + IDENTITY  ->  CANONICAL DATASET.

Projection rules:
* every populated entity field lists its supporting claim ids in ``provenance``;
* a single-valued field with disagreeing sources keeps every value in ``conflicts``
  (the displayed value is the best-supported one, never a silent overwrite);
* claims about the same (type, subject, object) become one Relation that keeps all
  claim ids, the union of assertion types and the explicit validity interval if any
  source states one; otherwise the edge is only "observed at" retrieval dates.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..models.entities import ENTITY_CLASSES, CanonicalEntity, ConflictingValue, Relation
from ..models.enums import EntityType, EpistemicStatus, RelationType, TemporalBasis
from ..models.provenance import Claim, SourceDocument, stable_hash

# predicate -> (field, multi-valued?) per entity type
FIELD_MAP: dict[EntityType, dict[str, tuple[str, bool]]] = {
    EntityType.PERSON: {
        "name": ("canonical_name", False),
        "title": ("titles", True),
        "mtmt_id": ("mtmt_id", False),
        "orcid": ("orcid", False),
        "google_scholar_id": ("google_scholar_id", False),
        "profile_url": ("profile_urls", True),
        "cv_url": ("profile_urls", True),
        "biography_excerpt": ("biography_summary", False),
        "stated_research_area": ("stated_research_areas", True),
        "birth_year": ("birth_year", False),
        "death_year": ("death_year", False),
        "academic_rank": ("academic_rank", False),
        "discipline": ("disciplines", True),
        "email_domain": (None, False),  # resolution signal only; not published
    },
    EntityType.INSTITUTION: {
        "name": ("canonical_name", False),
        "english_name": ("english_name", False),
        "alternate_name": ("alternate_names", True),
        "institution_type": ("institution_type", False),
        "city": ("city", False),
        "website": ("website", False),
    },
    EntityType.ORG_UNIT: {
        "name": ("canonical_name", False),
        "english_name": ("english_name", False),
        "unit_type": ("unit_type", False),
        "website": ("website", False),
        "description": ("description", False),
    },
    EntityType.PROJECT: {
        "title": ("title", False),
        "abstract": ("abstract", False),
        "start": ("start", False),
        "end": ("end", False),
        "funding_body": ("funding_body", False),
        "grant_id": ("grant_id", False),
        "website": ("website", False),
        "status_label": ("status_label", False),
    },
    EntityType.TOPIC: {
        "key": ("key", False),
        "name_en": ("name_en", False),
        "name_hu": ("name_hu", False),
        "scope_note": ("scope_note", False),
    },
}
FIELD_MAP[EntityType.RESEARCH_GROUP] = FIELD_MAP[EntityType.ORG_UNIT] | {
    "funding_programme": ("funding_programme", False)
}
FIELD_MAP[EntityType.METHOD] = FIELD_MAP[EntityType.TOPIC]

LABEL_FIELD = {
    EntityType.PERSON: "canonical_name",
    EntityType.INSTITUTION: "canonical_name",
    EntityType.ORG_UNIT: "canonical_name",
    EntityType.RESEARCH_GROUP: "canonical_name",
    EntityType.PROJECT: "title",
    EntityType.TOPIC: "name_en",
    EntityType.METHOD: "name_en",
}

# preference when choosing a displayed value among conflicting ones
LOCATOR_RANK = {"profile.h1": 3, "unit.h1": 3, "project.h1": 3}


@dataclass
class CanonicalDataset:
    entities: dict[str, CanonicalEntity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    documents: dict[str, SourceDocument] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)

    def by_type(self, etype: EntityType) -> list[CanonicalEntity]:
        return [e for e in self.entities.values() if e.entity_type is etype]


def _choose(claims: list[Claim]) -> tuple[Any, list[ConflictingValue]]:
    by_value: dict[str, list[Claim]] = defaultdict(list)
    for c in claims:
        by_value[repr(c.value)].append(c)
    ranked = sorted(
        by_value.values(),
        key=lambda cs: (
            max(LOCATOR_RANK.get(c.evidence.locator, 0) for c in cs),
            len({c.evidence.document_id for c in cs}),
            max(c.confidence for c in cs),
            max(c.observed_at for c in cs),
        ),
        reverse=True,
    )
    chosen = ranked[0][0].value
    conflicts = (
        [ConflictingValue(value=cs[0].value, claim_ids=[c.claim_id for c in cs]) for cs in ranked]
        if len(ranked) > 1
        else []
    )
    return chosen, conflicts


def _cid(ref, ref_to_id: dict[str, str]) -> str | None:
    return ref.canonical_id or ref_to_id.get(ref.source_ref)


def build_canonical(
    claims: list[Claim],
    documents: list[SourceDocument],
    ref_to_id: dict[str, str],
) -> CanonicalDataset:
    ds = CanonicalDataset(claims=claims, documents={d.document_id: d for d in documents})
    literal: dict[tuple[str, EntityType], dict[str, list[Claim]]] = defaultdict(lambda: defaultdict(list))
    edges: dict[tuple[str, str, str], list[Claim]] = defaultdict(list)
    refs_of: dict[str, set[str]] = defaultdict(set)

    for c in claims:
        sid = _cid(c.subject, ref_to_id)
        if sid is None:
            ds.issues.append({"check": "unresolved_subject", "claim_id": c.claim_id})
            continue
        if c.subject.source_ref:
            refs_of[sid].add(c.subject.source_ref)
        if c.object is None:
            literal[(sid, c.subject.entity_type)][c.predicate].append(c)
            continue
        oid = _cid(c.object, ref_to_id)
        if oid is None:
            ds.issues.append({"check": "unresolved_object", "claim_id": c.claim_id})
            continue
        if c.object.source_ref:
            refs_of[oid].add(c.object.source_ref)
        if sid == oid:
            ds.issues.append({"check": "self_loop_after_resolution", "claim_id": c.claim_id})
            continue
        edges[(c.predicate, sid, oid)].append(c)

    # ---------------------------------------------------------------- relations
    position_titles: dict[str, list[tuple[str, Claim]]] = defaultdict(list)
    for (pred, sid, oid), cs in sorted(edges.items()):
        try:
            rtype = RelationType(pred)
        except ValueError:
            ds.issues.append({"check": "unknown_relation_type", "predicate": pred})
            continue
        explicit = [c for c in cs if c.temporal_basis is TemporalBasis.EXPLICIT]
        statuses = {c.epistemic_status for c in cs}
        status = next(s for s in (EpistemicStatus.OBSERVED, EpistemicStatus.DERIVED,
                                  EpistemicStatus.INFERRED, EpistemicStatus.INTERPRETIVE) if s in statuses)
        qualifiers: dict[str, list] = defaultdict(list)
        for c in cs:
            for k, v in c.qualifiers.items():
                if v not in qualifiers[k]:
                    qualifiers[k].append(v)
            if rtype is RelationType.AFFILIATED_WITH and c.qualifiers.get("position_title"):
                position_titles[sid].append((c.qualifiers["position_title"], c))
        froms = sorted(c.valid_from for c in explicit if c.valid_from)
        untils = sorted(c.valid_until for c in explicit if c.valid_until)
        derivations = sorted({c.derivation_method for c in cs if c.derivation_method})
        ds.relations.append(
            Relation(
                relation_id="rel_" + stable_hash(pred, sid, oid),
                type=rtype,
                source_id=sid,
                target_id=oid,
                qualifiers=dict(qualifiers),
                valid_from=froms[0] if froms else None,
                valid_until=untils[-1] if untils and len(untils) == len(explicit) else None,
                temporal_basis=TemporalBasis.EXPLICIT if explicit else (
                    TemporalBasis.OBSERVED_AT if any(c.temporal_basis is TemporalBasis.OBSERVED_AT for c in cs)
                    else TemporalBasis.UNKNOWN),
                first_observed_at=min(c.observed_at for c in cs),
                last_observed_at=max(c.observed_at for c in cs),
                epistemic_status=status,
                assertion_types=sorted({c.assertion_type for c in cs if c.assertion_type}),
                derivation_method="; ".join(derivations) or None,
                confidence=max(c.confidence for c in cs),
                claim_ids=sorted(c.claim_id for c in cs),
                document_ids=sorted({c.evidence.document_id for c in cs}),
            )
        )

    # ---------------------------------------------------------------- entities
    for (cid, etype), by_pred in literal.items():
        cls = ENTITY_CLASSES[etype]
        fmap = FIELD_MAP.get(etype, {})
        values: dict[str, Any] = {}
        provenance: dict[str, list[str]] = {}
        conflicts: dict[str, list[ConflictingValue]] = {}
        for pred, cs in by_pred.items():
            if pred not in fmap:
                ds.issues.append({"check": "unmapped_predicate", "entity": cid, "predicate": pred})
                continue
            fname, multi = fmap[pred]
            if fname is None:
                continue
            if multi:
                vals = values.setdefault(fname, [])
                for c in sorted(cs, key=lambda c: c.observed_at):
                    if c.value not in vals:
                        vals.append(c.value)
            else:
                chosen, conf = _choose(cs)
                values[fname] = chosen
                if conf:
                    conflicts[fname] = conf
            provenance.setdefault(fname, []).extend(c.claim_id for c in cs)
        if etype is EntityType.PERSON:
            pts = position_titles.get(cid, [])
            if pts:
                values["position_titles"] = list(dict.fromkeys(p for p, _ in pts))
                provenance["position_titles"] = [c.claim_id for _, c in pts]
        # Name/title spelling variants are alternates, not conflicts.
        for main_f, alt_f in (("canonical_name", "alternate_names"), ("title", "alternate_titles")):
            if main_f in conflicts and alt_f in cls.model_fields:
                alts = values.setdefault(alt_f, [])
                alts += [cv.value for cv in conflicts.pop(main_f)
                         if cv.value != values[main_f] and cv.value not in alts]
                provenance.setdefault(alt_f, []).extend(provenance.get(main_f, []))
        label_field = LABEL_FIELD.get(etype)
        if not label_field or label_field not in values:
            ds.issues.append({"check": "entity_without_label", "entity": cid, "type": etype.value})
            continue
        observed = [c.observed_at for cs in by_pred.values() for c in cs
                    if ds.documents.get(c.evidence.document_id)
                    and not ds.documents[c.evidence.document_id].url.startswith("repo://")]
        if cid in ds.entities:
            ds.issues.append({"check": "id_type_collision", "entity": cid})
            continue
        ds.entities[cid] = cls(
            canonical_id=cid,
            label=str(values[label_field]),
            provenance={k: sorted(set(v)) for k, v in provenance.items()},
            conflicts=conflicts,
            source_refs=sorted(refs_of.get(cid, ())),
            first_observed_at=min(observed) if observed else None,
            last_verified_at=max(observed) if observed else None,
            **values,
        )

    # relations must point at entities that exist
    known = set(ds.entities)
    kept = []
    for r in ds.relations:
        if r.source_id in known and r.target_id in known:
            kept.append(r)
        else:
            ds.issues.append({"check": "dangling_relation", "relation": r.relation_id,
                              "type": r.type.value, "missing": [x for x in (r.source_id, r.target_id) if x not in known]})
    ds.relations = kept
    return ds


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
