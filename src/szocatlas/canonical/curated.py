"""Claims from version-controlled curated files: the source registry and the taxonomies.

These files are themselves sources. Each becomes a SourceDocument (source_type MANUAL
or TAXONOMY, identified by its content hash), so a curated fact is as traceable as a
scraped one: you can see which commit of config/sources.yaml asserted it.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..models.enums import (
    AssertionType,
    EntityType,
    EpistemicStatus,
    ExtractionMethod,
    SourceType,
    TemporalBasis,
)
from ..models.provenance import Claim, EntityRef, Evidence, SourceDocument, SourceRecord
from ..normalize.names import strip_accents
from ..registry import Registry
from ..sources.base import ParseResult, local_ref

CURATED_PARSER_VERSION = "curated/0.1.0"


def file_document(path: Path, source_type: SourceType) -> SourceDocument:
    body = path.read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    parts = path.resolve().parts
    # repo-relative path from the config/ directory down, wherever the repo is checked out
    rel = "/".join(parts[len(parts) - 1 - parts[::-1].index("config"):]) if "config" in parts \
        else path.name
    return SourceDocument(
        document_id="doc_" + sha[:16],
        source_id="curated",
        url=f"repo://{rel}",
        final_url=f"repo://{rel}",
        canonical_url=f"repo://{rel}",
        retrieved_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
        http_status=200,
        content_type="application/yaml",
        content_sha256=sha,
        raw_path=f"repo://{rel}",
        page_title=rel,
        source_type=source_type,
        fetcher_version=CURATED_PARSER_VERSION,
    )


def _claim(doc, subject, predicate, *, value=None, obj=None, snippet, locator, conf=0.9, **kw):
    return Claim(
        subject=subject,
        predicate=predicate,
        value=value,
        object=obj,
        observed_at=doc.retrieved_at,
        temporal_basis=kw.pop("temporal_basis", TemporalBasis.UNKNOWN),
        evidence=Evidence(document_id=doc.document_id, locator=locator, snippet=snippet),
        extraction_method=ExtractionMethod.MANUAL_ENTRY,
        parser="curated",
        parser_version=CURATED_PARSER_VERSION,
        epistemic_status=EpistemicStatus.OBSERVED,
        assertion_type=kw.pop("assertion_type", AssertionType.INSTITUTIONAL),
        confidence=conf,
        **kw,
    )


def institution_ref(key: str) -> EntityRef:
    return EntityRef(entity_type=EntityType.INSTITUTION, source_ref=f"registry|institution:{key}")


def registry_claims(registry: Registry, path: Path) -> ParseResult:
    doc = file_document(path, SourceType.MANUAL)
    out = ParseResult(documents=[doc])
    for inst in registry.institutions:
        ref = institution_ref(inst.key)
        loc = f"institutions[{inst.key}]"
        out.records.append(SourceRecord(ref=ref, label=inst.canonical_name, document_id=doc.document_id,
                                        hints={"registry_key": inst.key}))
        c = out.claims
        c.append(_claim(doc, ref, "name", value=inst.canonical_name, snippet=inst.canonical_name, locator=loc))
        if inst.english_name:
            c.append(_claim(doc, ref, "english_name", value=inst.english_name, snippet=inst.english_name, locator=loc))
        for alt in inst.alternate_names:
            c.append(_claim(doc, ref, "alternate_name", value=alt, snippet=alt, locator=loc))
        c.append(_claim(doc, ref, "institution_type", value=inst.institution_type.value,
                        snippet=inst.institution_type.value, locator=loc))
        if inst.city:
            c.append(_claim(doc, ref, "city", value=inst.city, snippet=inst.city, locator=loc))
        if inst.website:
            c.append(_claim(doc, ref, "website", value=inst.website, snippet=inst.website, locator=loc))
        if inst.parent:
            c.append(_claim(doc, ref, "PART_OF", obj=institution_ref(inst.parent),
                            snippet=f"parent: {inst.parent}", locator=loc, temporal_basis=TemporalBasis.OBSERVED_AT))
    for s in registry.sources:
        # Only institutional websites describe an organisational unit; journals,
        # registries and archives get their own entity types when their adapters exist.
        if not s.unit_name or not s.institution or s.source_type != "institutional_website":
            continue
        ref = local_ref(s.source_id, EntityType.ORG_UNIT, "site")
        if s.unit_type == "research_group":
            ref = EntityRef(entity_type=EntityType.RESEARCH_GROUP, source_ref=ref.source_ref)
        loc = f"sources[{s.source_id}]"
        out.records.append(SourceRecord(ref=ref, label=s.unit_name, document_id=doc.document_id,
                                        hints={"registry_source": s.source_id}))
        c = out.claims
        c.append(_claim(doc, ref, "name", value=s.unit_name, snippet=s.unit_name, locator=loc))
        if s.unit_english_name:
            c.append(_claim(doc, ref, "english_name", value=s.unit_english_name, snippet=s.unit_english_name, locator=loc))
        if s.unit_type:
            c.append(_claim(doc, ref, "unit_type", value=s.unit_type, snippet=s.unit_type, locator=loc))
        if s.base_url:
            c.append(_claim(doc, ref, "website", value=s.base_url, snippet=s.base_url, locator=loc))
        c.append(_claim(doc, ref, "PART_OF", obj=institution_ref(s.institution),
                        snippet=f"institution: {s.institution}", locator=loc,
                        temporal_basis=TemporalBasis.OBSERVED_AT))
    return out


# ------------------------------------------------------------------ taxonomy


class Taxonomy:
    def __init__(self, topics_path: Path, methods_path: Path):
        self.topics_path, self.methods_path = topics_path, methods_path
        self.topics = yaml.safe_load(topics_path.read_text(encoding="utf-8"))["topics"]
        self.methods = yaml.safe_load(methods_path.read_text(encoding="utf-8"))["methods"]
        self._compiled = [
            (EntityType.TOPIC, t, [re.compile(p) for p in t.get("patterns", [])]) for t in self.topics
        ] + [
            (EntityType.METHOD, m, [re.compile(p) for p in m.get("patterns", [])]) for m in self.methods
        ]

    @staticmethod
    def ref(etype: EntityType, key: str) -> EntityRef:
        return EntityRef(entity_type=etype, source_ref=f"taxonomy|{key}")

    def match(self, text: str) -> list[tuple[EntityType, str, str]]:
        """-> [(type, key, matched pattern)] on accent-folded lower-case text."""
        folded = strip_accents(text).lower()
        hits = []
        for etype, item, pats in self._compiled:
            for p in pats:
                if p.search(folded):
                    hits.append((etype, item["key"], p.pattern))
                    break
        return hits

    def claims(self) -> ParseResult:
        out = ParseResult()
        for path, etype, items in (
            (self.topics_path, EntityType.TOPIC, self.topics),
            (self.methods_path, EntityType.METHOD, self.methods),
        ):
            doc = file_document(path, SourceType.TAXONOMY)
            out.documents.append(doc)
            for it in items:
                ref = self.ref(etype, it["key"])
                loc = f"{etype.value}[{it['key']}]"
                out.records.append(SourceRecord(ref=ref, label=it["en"], document_id=doc.document_id,
                                                hints={"taxonomy_key": it["key"]}))
                kw = dict(locator=loc, assertion_type=None, conf=1.0)
                out.claims += [
                    _claim(doc, ref, "key", value=it["key"], snippet=it["key"], **kw),
                    _claim(doc, ref, "name_en", value=it["en"], snippet=it["en"], **kw),
                    _claim(doc, ref, "name_hu", value=it["hu"], snippet=it["hu"], **kw),
                ]
                if it.get("scope"):
                    out.claims.append(_claim(doc, ref, "scope_note", value=it["scope"], snippet=it["scope"], **kw))
                if it.get("broader"):
                    out.claims.append(_claim(doc, ref, "BROADER", obj=self.ref(etype, it["broader"]),
                                             snippet=f"broader: {it['broader']}", **kw))
        return out


DERIVATION = "taxonomy_keyword_map/0.1.0"


def derive_classifications(claims: list[Claim], taxonomy: Taxonomy) -> list[Claim]:
    """stated_research_area / project title  ->  DERIVED WORKS_ON_TOPIC / USES_METHOD.

    The derived claim points at the observed claim it came from; its confidence is
    capped below the observed claim's, and the matched pattern is kept as evidence.
    """
    out: list[Claim] = []
    for c in claims:
        if c.predicate == "stated_research_area":
            text, base_conf = str(c.value), 0.75
        elif c.predicate == "title" and c.subject.entity_type is EntityType.PROJECT:
            text, base_conf = str(c.value), 0.6
        else:
            continue
        for etype, key, pattern in taxonomy.match(text):
            out.append(
                Claim(
                    subject=c.subject,
                    predicate="WORKS_ON_TOPIC" if etype is EntityType.TOPIC else "USES_METHOD",
                    object=taxonomy.ref(etype, key),
                    qualifiers={"matched_pattern": pattern, "stated_text": text},
                    observed_at=c.observed_at,
                    temporal_basis=TemporalBasis.OBSERVED_AT,
                    evidence=c.evidence,
                    extraction_method=ExtractionMethod.TAXONOMY_KEYWORD_MAP,
                    parser="derive.taxonomy",
                    parser_version=DERIVATION,
                    epistemic_status=EpistemicStatus.DERIVED,
                    assertion_type=c.assertion_type,
                    derivation_method=DERIVATION,
                    derived_from=[c.claim_id],
                    confidence=round(min(base_conf, c.confidence), 2),
                )
            )
    return out
