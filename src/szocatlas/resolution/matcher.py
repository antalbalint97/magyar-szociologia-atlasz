"""ENTITY RESOLUTION: conservative identity matching with manual overrides.

Rules (people), in priority order:

1. manual ``not_same_as``  -> rejected_match (always wins)
2. manual ``same_as``      -> confirmed_match
3. conflicting hard identifiers (two different MTMT ids or ORCIDs) -> rejected_match
4. shared hard identifier (MTMT id, ORCID) AND compatible names -> confirmed_match
5. shared hard identifier but incompatible names -> possible_match (review)
6. same accent-folded name, different source record -> possible_match (review), scored
   with soft signals (same institution family, same profile slug, e-mail domain)

A same-name pair is never merged automatically, however strong the soft signals are.
Possible matches are written to review/unresolved_people.yaml for a human decision,
which is then recorded in review/manual_overrides.yaml (version-controlled).

Canonical ids are minted once and persisted in review/identity_map.jsonl; a re-run
reuses them, so ids stay stable as sources are added.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field

from ..models.entities import ID_PREFIX
from ..models.enums import EntityType, IdentityAnchor, MatchStatus
from ..models.provenance import Claim, SourceRecord
from ..normalize.names import name_key, order_free_key

HARD_IDS = ("mtmt_id", "orcid")
HARD_ID_ANCHOR = {"mtmt_id": IdentityAnchor.MTMT, "orcid": IdentityAnchor.ORCID}
ANCHORED_TYPES = (EntityType.PERSON, EntityType.PROJECT)  # canonical only with identity evidence


class MatchDecision(BaseModel):
    left: str
    right: str
    entity_type: EntityType
    status: MatchStatus
    method: str
    score: float = 0.0
    signals: dict[str, object] = Field(default_factory=dict)
    left_label: str = ""
    right_label: str = ""


@dataclass
class Overrides:
    same_as: list[tuple[str, str]] = field(default_factory=list)
    not_same_as: list[tuple[str, str]] = field(default_factory=list)
    # canonical ids a reviewer chose to keep when a same_as joins records that already
    # had different ids (ADR-0003: otherwise the oldest id survives)
    survivors: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> Overrides:
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        def pairs(key):
            out = []
            for item in data.get(key) or []:
                refs = item["refs"]
                out += [(refs[0], r) for r in refs[1:]]
            return out

        survivors = {str(item["survivor"]) for item in data.get("same_as") or [] if item.get("survivor")}
        return cls(pairs("same_as"), pairs("not_same_as"), survivors)


class _UF:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


@dataclass
class SourceEntity:
    ref: str
    entity_type: EntityType
    labels: list[str]
    hints: dict[str, set[str]]


def collect(records: list[SourceRecord], claims: list[Claim]) -> dict[str, SourceEntity]:
    ents: dict[str, SourceEntity] = {}
    for r in records:
        key = r.ref.source_ref or r.ref.canonical_id
        e = ents.setdefault(key, SourceEntity(key, r.ref.entity_type, [], defaultdict(set)))
        if r.label not in e.labels:
            e.labels.append(r.label)
        for k, v in r.hints.items():
            if v is not None:
                e.hints[k].add(str(v))
    # hard ids asserted by claims count even when no record carried them as a hint
    for c in claims:
        if c.predicate in HARD_IDS and c.subject.source_ref in ents:
            ents[c.subject.source_ref].hints[c.predicate].add(str(c.value))
    return ents


def _site_family(ref: str) -> str:
    src = ref.split("|", 1)[0]
    return src.split("_", 1)[0]  # tk_recens -> tk


def _slug(ref: str) -> str | None:
    url = ref.split("|", 1)[1] if "|" in ref else ""
    path = urlsplit(url).path
    return path.rsplit("/", 1)[-1] if "/kutato/" in path else None


def _names_compatible(a: SourceEntity, b: SourceEntity) -> bool:
    ka = {name_key(x) for x in a.labels} | {order_free_key(x) for x in a.labels}
    kb = {name_key(x) for x in b.labels} | {order_free_key(x) for x in b.labels}
    return bool(ka & kb)


def match_people(ents: dict[str, SourceEntity], overrides: Overrides) -> list[MatchDecision]:
    people = [e for e in ents.values() if e.entity_type is EntityType.PERSON]
    decisions: dict[tuple[str, str], MatchDecision] = {}

    def put(a: SourceEntity, b: SourceEntity, status, method, score=0.0, **signals):
        left, right = sorted((a.ref, b.ref))
        la, lb = (a, b) if a.ref == left else (b, a)
        prev = decisions.get((left, right))
        if prev and prev.method.startswith("manual"):
            return
        decisions[(left, right)] = MatchDecision(
            left=left, right=right, entity_type=EntityType.PERSON, status=status, method=method,
            score=score, signals=signals, left_label=la.labels[0], right_label=lb.labels[0],
        )

    # candidate pairs: blocking on hard ids and on order-free name key
    blocks: dict[str, list[SourceEntity]] = defaultdict(list)
    for e in people:
        for hid in HARD_IDS:
            for v in e.hints.get(hid, ()):
                blocks[f"{hid}:{v}"].append(e)
        for lab in e.labels:
            blocks[f"name:{order_free_key(lab)}"].append(e)
    seen = set()
    for members in blocks.values():
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                if a.ref == b.ref or (a.ref, b.ref) in seen:
                    continue
                seen.add((a.ref, b.ref))
                seen.add((b.ref, a.ref))
                shared = {h: a.hints[h] & b.hints[h] for h in HARD_IDS if a.hints.get(h) and b.hints.get(h)}
                conflicting = [h for h, s in shared.items() if not s]
                agreeing = [h for h, s in shared.items() if s]
                compatible = _names_compatible(a, b)
                if conflicting:
                    put(a, b, MatchStatus.REJECTED, "auto:conflicting_hard_id", conflicting=conflicting)
                elif agreeing and compatible:
                    put(a, b, MatchStatus.CONFIRMED, "auto:hard_id+name", 1.0, shared=agreeing)
                elif agreeing:
                    put(a, b, MatchStatus.POSSIBLE, "auto:hard_id_name_mismatch", 0.6, shared=agreeing)
                elif compatible:
                    signals = {
                        "same_institution_family": _site_family(a.ref) == _site_family(b.ref),
                        "same_profile_slug": bool(_slug(a.ref)) and _slug(a.ref) == _slug(b.ref),
                        "same_email_domain": bool(a.hints.get("email_domain") & b.hints.get("email_domain"))
                        if a.hints.get("email_domain") and b.hints.get("email_domain") else False,
                        "unlinked_mention": bool(a.hints.get("unlinked_mention") or b.hints.get("unlinked_mention")),
                    }
                    score = 0.4 + 0.15 * sum(bool(v) for k, v in signals.items() if k != "unlinked_mention")
                    put(a, b, MatchStatus.POSSIBLE, "auto:same_name", round(min(score, 0.85), 2), **signals)

    by_ref = {e.ref: e for e in people}
    for a, b in overrides.same_as:
        if a in by_ref and b in by_ref:
            put(by_ref[a], by_ref[b], MatchStatus.CONFIRMED, "manual:same_as", 1.0)
    for a, b in overrides.not_same_as:
        if a in by_ref and b in by_ref:
            put(by_ref[a], by_ref[b], MatchStatus.REJECTED, "manual:not_same_as", 0.0)
    return list(decisions.values())


def match_structural(ents: dict[str, SourceEntity]) -> list[MatchDecision]:
    """Units and research groups: the same name within one site is the same thing.

    Projects are excluded (ADR-0008): editions share titles, so a same-title pair is a
    candidate for the project resolver, never an automatic merge."""
    out = []
    groups: dict[tuple, list[SourceEntity]] = defaultdict(list)
    for e in ents.values():
        if e.entity_type in (EntityType.ORG_UNIT, EntityType.RESEARCH_GROUP):
            site = e.ref.split("|", 1)[0]
            for lab in e.labels:
                groups[(e.entity_type, site, name_key(lab))].append(e)
    for (etype, _site, _k), members in groups.items():
        uniq = list({m.ref: m for m in members}.values())
        for b in uniq[1:]:
            a = uniq[0]
            left, right = sorted((a.ref, b.ref))
            out.append(MatchDecision(left=left, right=right, entity_type=etype, status=MatchStatus.CONFIRMED,
                                     method="auto:same_site_same_name", score=0.95,
                                     left_label=a.labels[0], right_label=b.labels[0]))
    return out


def match_manual(ents: dict[str, SourceEntity], overrides: Overrides) -> list[MatchDecision]:
    """Reviewer same_as / not_same_as between records of other types (projects, ADR-0008)."""
    out = []
    for pairs, status, method in ((overrides.same_as, MatchStatus.CONFIRMED, "manual:same_as"),
                                  (overrides.not_same_as, MatchStatus.REJECTED, "manual:not_same_as")):
        for a, b in pairs:
            ea, eb = ents.get(a), ents.get(b)
            if ea is None or eb is None or ea.entity_type is EntityType.PERSON or ea.entity_type is not eb.entity_type:
                continue
            left, right = sorted((a, b))
            la, lb = (ea, eb) if a == left else (eb, ea)
            out.append(MatchDecision(left=left, right=right, entity_type=ea.entity_type, status=status,
                                     method=method, score=1.0 if status is MatchStatus.CONFIRMED else 0.0,
                                     left_label=la.labels[0], right_label=lb.labels[0]))
    return out


class IdentityMap:
    """Persistent source_ref -> canonical_id assignments (review/identity_map.jsonl)."""

    def __init__(self, path: Path):
        self.path = path
        self.rows: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.rows[row["source_ref"]] = row

    @staticmethod
    def mint(etype: EntityType, seed: str) -> str:
        return f"{ID_PREFIX[etype]}_{hashlib.sha1(seed.encode()).hexdigest()[:10]}"

    def assign(self, clusters: dict[str, list[SourceEntity]], survivors: set[str] = frozenset(),
               strength: dict[str, int] | None = None) -> dict[str, str]:
        """Give every cluster a canonical id. When a merge joins records that already carry
        different ids, the survivor is, in order: the id a reviewer named (``survivors``),
        the oldest assignment, the id whose records carry the stronger identity anchor
        (``strength`` per source ref), the lowest id. The other ids are recorded as
        ``previous_id`` on the rows that move (ADR-0003)."""
        strength = strength or {}
        now = datetime.now(UTC).isoformat(timespec="seconds")
        ref_to_id: dict[str, str] = {}
        used: set[str] = set()
        # clusters whose members already have ids keep the oldest one
        ordered = sorted(clusters.values(), key=lambda ms: (min(
            (self.rows[m.ref]["assigned_at"] for m in ms if m.ref in self.rows), default="~"),
            min(m.ref for m in ms)))
        for members in ordered:
            etype = members[0].entity_type
            ids: dict[str, list[str]] = defaultdict(list)
            for m in members:
                row = self.rows.get(m.ref)
                if row and row["canonical_id"].startswith(ID_PREFIX[etype] + "_"):
                    ids[row["canonical_id"]].append(m.ref)
            known = sorted(ids, key=lambda c: (
                c not in survivors,
                min(self.rows[r]["assigned_at"] for r in ids[c]),
                -max(strength.get(r, 0) for r in ids[c]),
                c,
            ))
            cid = next((c for c in known if c not in used), None)
            if cid is None:
                cid = self.mint(etype, min(m.ref for m in members))
                while cid in used:
                    cid = self.mint(etype, cid)
            used.add(cid)
            for m in members:
                ref_to_id[m.ref] = cid
                row = self.rows.get(m.ref)
                if row is None or row["canonical_id"] != cid:
                    self.rows[m.ref] = {
                        "source_ref": m.ref, "entity_type": etype.value, "canonical_id": cid,
                        "assigned_at": row["assigned_at"] if row and row["canonical_id"] == cid else now,
                        **({"previous_id": row["canonical_id"]} if row and row["canonical_id"] != cid else {}),
                    }
        return ref_to_id

    def retire(self, refs: list[str]) -> None:
        """Forget assignments of records that no longer map to a canonical entity."""
        for ref in refs:
            self.rows.pop(ref, None)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            for ref in sorted(self.rows):
                fh.write(json.dumps(self.rows[ref], ensure_ascii=False, sort_keys=True) + "\n")


def resolve(
    records: list[SourceRecord],
    claims: list[Claim],
    overrides: Overrides,
    identity: IdentityMap,
) -> tuple[dict[str, str], list[MatchDecision]]:
    ents = collect(records, claims)
    decisions = match_people(ents, overrides) + match_structural(ents) + match_manual(ents, overrides)
    uf = _UF()
    for e in ents:
        uf.find(e)
    rejected = {(d.left, d.right) for d in decisions if d.status is MatchStatus.REJECTED}
    for d in decisions:
        if d.status is MatchStatus.CONFIRMED and (d.left, d.right) not in rejected:
            # do not let transitivity join two records that were explicitly kept apart
            ra, rb = uf.find(d.left), uf.find(d.right)
            members_a = [x for x in ents if uf.find(x) == ra]
            members_b = [x for x in ents if uf.find(x) == rb]
            if any(tuple(sorted((x, y))) in rejected for x in members_a for y in members_b):
                d.status = MatchStatus.POSSIBLE
                d.method += "+blocked_by_rejection"
                continue
            uf.union(d.left, d.right)
    clusters: dict[str, list[SourceEntity]] = defaultdict(list)
    for ref, e in ents.items():
        clusters[uf.find(ref)].append(e)
    # A person or project cluster becomes a canonical entity only with identity evidence;
    # its other records are mentions of it. Clusters without evidence stay mentions
    # (ADR-0006, ADR-0008).
    anchors = identity_anchors(records, claims, overrides)
    keep = {k: ms for k, ms in clusters.items()
            if ms[0].entity_type not in ANCHORED_TYPES or any(m.ref in anchors for m in ms)}
    identity.retire([m.ref for k, ms in clusters.items() if k not in keep for m in ms])
    strength = {ref: len(kinds & {IdentityAnchor.MTMT, IdentityAnchor.ORCID}) for ref, kinds in anchors.items()}
    return identity.assign(keep, overrides.survivors, strength), decisions


def identity_anchors(records: list[SourceRecord], claims: list[Claim],
                     overrides: Overrides | None = None) -> dict[str, set[IdentityAnchor]]:
    """Person / project source ref -> the identity evidence it carries (ADR-0006, ADR-0008).

    A record from the entity's own page (``identity_anchor``: a researcher's profile, a
    project's page) or a stated hard identifier anchors an identity. A name or title on
    someone else's page does not. A project record a reviewer joined to another with
    ``same_as`` is anchored by that decision.
    """
    out: dict[str, set[IdentityAnchor]] = defaultdict(set)
    projects = set()
    for r in records:
        if r.ref.entity_type in ANCHORED_TYPES and r.ref.source_ref and r.identity_anchor:
            out[r.ref.source_ref].add(IdentityAnchor(r.identity_anchor))
        if r.ref.entity_type is EntityType.PROJECT and r.ref.source_ref:
            projects.add(r.ref.source_ref)
    for c in claims:
        if (c.subject.entity_type is EntityType.PERSON and c.subject.source_ref and c.object is None
                and c.predicate in HARD_ID_ANCHOR and c.value):
            out[c.subject.source_ref].add(HARD_ID_ANCHOR[c.predicate])
    for a, b in (overrides.same_as if overrides else []):
        if a in projects and b in projects:
            out[a].add(IdentityAnchor.MANUAL)
            out[b].add(IdentityAnchor.MANUAL)
    return out


def write_review_queue(decisions: list[MatchDecision], path: Path, only_refs: set[str] | None = None) -> int:
    """Possible person-person matches. With ``only_refs``, only pairs of identity-anchored
    records (two profiles that may be one person); name mentions are reviewed per mention
    in review/mention_review.yaml instead (#5)."""
    pending = [d for d in decisions if d.status is MatchStatus.POSSIBLE and d.entity_type is EntityType.PERSON
               and (only_refs is None or (d.left in only_refs and d.right in only_refs))]
    payload = {
        "_comment": (
            "Generated. Do not edit: record decisions in review/manual_overrides.yaml "
            "under same_as / not_same_as with reviewer and date."
        ),
        "possible_matches": [
            {"refs": [d.left, d.right], "labels": [d.left_label, d.right_label],
             "method": d.method, "score": d.score, "signals": d.signals}
            for d in sorted(pending, key=lambda d: (-d.score, d.left, d.right))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return len(pending)
