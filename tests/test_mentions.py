"""Person mentions vs canonical persons (ADR-0006) and their evidence-based resolution (ADR-0007).

The records mirror real source refs and cases from releases 2026-10-tk and 2026-10-tk-m2:
QA seeds, the common-name and same-name cases, the duplicated Stefkovics profile and the
Illésy / Illéssy link.
"""

import random
from datetime import UTC, datetime

import pytest

from szocatlas.canonical.mentions import mention_id
from szocatlas.models import Claim, EntityRef, Evidence, SourceDocument, SourceRecord
from szocatlas.models.enums import (
    EntityType,
    EpistemicStatus,
    ExtractionMethod,
    MentionResolutionStatus,
    SourceType,
)
from szocatlas.pipeline import canonicalize
from szocatlas.registry import REPO_ROOT
from szocatlas.resolution import mentions as R
from szocatlas.resolution.matcher import IdentityMap, Overrides, identity_anchors, resolve
from szocatlas.resolution.review import write_mention_review
from szocatlas.validation.mention_stats import mention_stats
from szocatlas.validation.qa import run_checks

NOW = datetime(2026, 10, 4, tzinfo=UTC)
SZI = "https://szociologia.tk.elte.hu"
RECENS = "https://recens.tk.elte.hu"
KI = "https://kisebbsegkutato.tk.elte.hu"
PTI = "https://politikatudomany.tk.elte.hu"
CONFIG = R.ResolutionConfig.load(REPO_ROOT / "config" / "resolution.yaml")
S = MentionResolutionStatus


class World:
    """A tiny staged dataset: documents, records and claims as the TK adapter emits them."""

    def __init__(self, registry):
        self.registry = registry
        self.docs: dict[str, SourceDocument] = {}
        self.records: list[SourceRecord] = []
        self.claims: list[Claim] = []
        self.hosts = {s.base_url.split("//")[1].rstrip("/"): s.source_id for s in registry.sources if s.base_url}

    def owner(self, url: str) -> str:
        host = url.split("/")[2]
        return self.hosts.get(host, f"external:{host}")

    def doc(self, url: str) -> str:
        did = SourceDocument.make_id(url, "x")
        self.docs.setdefault(did, SourceDocument(
            document_id=did, source_id=self.owner(url), url=url, final_url=url, canonical_url=url,
            retrieved_at=NOW, http_status=200, content_type="text/html", content_sha256="x",
            raw_path="raw", source_type=SourceType.INSTITUTIONAL_PROFILE, fetcher_version="t"))
        return did

    def claim(self, subject: EntityRef, predicate: str, url: str, value=None, obj: EntityRef | None = None,
              **kw) -> None:
        self.claims.append(Claim(
            subject=subject, predicate=predicate, value=value, object=obj, observed_at=NOW,
            evidence=Evidence(document_id=self.doc(url), locator="t", snippet=str(value or predicate)),
            extraction_method=ExtractionMethod.HTML_PARSER, parser="t", parser_version="0",
            epistemic_status=EpistemicStatus.OBSERVED, confidence=0.9, **kw))

    def site(self, base: str) -> EntityRef:
        sid = self.owner(base + "/")
        er = EntityRef(entity_type=EntityType.ORG_UNIT, source_ref=f"{sid}|site")
        if not any(r.ref == er for r in self.records):
            self.records.append(SourceRecord(ref=er, label=sid, document_id=self.doc(base + "/")))
            self.claim(er, "name", base + "/", sid)
        return er

    def profile(self, url: str, name: str, mtmt: str | None = None, also: tuple[str, ...] = (),
                projects: tuple[EntityRef, ...] = ()) -> str:
        """An own profile page: identity anchor, affiliation with its site, listed projects."""
        ref = f"{self.owner(url)}|{url}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(url),
                                         identity_anchor="institutional_profile"))
        self.claim(er, "name", url, name)
        self.claim(er, "profile_url", url, url)
        for other in also:  # e.g. the tk.mta.hu profile the page links as the same person
            self.claim(er, "profile_url", url, other)
        if mtmt:
            self.claim(er, "mtmt_id", url, mtmt)
        self.claim(er, "AFFILIATED_WITH", url, obj=self.site(url.split("/kutato/")[0]))
        for p in projects:
            self.claim(er, "PARTICIPATES_IN", url, obj=p)
        return ref

    def project(self, url: str, title: str | None = None) -> EntityRef:
        er = EntityRef(entity_type=EntityType.PROJECT, source_ref=f"{self.owner(url)}|{url}")
        if not any(r.ref == er for r in self.records):
            title = title or f"Projekt {url.rsplit('/', 1)[-1]}"
            self.records.append(SourceRecord(ref=er, label=title, document_id=self.doc(url)))
            self.claim(er, "title", url, title)
        return er

    def linked(self, page: str, profile_url: str, name: str, project: EntityRef, stated: str | None = None) -> str:
        """A link to a profile URL on another page; ``stated`` is the URL as written before aliasing."""
        ref = f"{self.owner(profile_url)}|{profile_url}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(page),
                                         hints={"profile_url": profile_url, "stated_url": stated or profile_url}))
        self.claim(er, "PARTICIPATES_IN", page, obj=project)
        return ref

    def unlinked(self, page: str, name: str, project: EntityRef, predicate="PARTICIPATES_IN") -> str:
        slug = name.lower().replace(" ", "-")
        ref = f"{self.owner(page)}|name-mention:{slug}@{project.source_ref}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(page),
                                         hints={"unlinked_mention": True}))
        self.claim(er, "name", page, name)
        self.claim(er, predicate, page, obj=project, qualifiers={"role": "résztvevő"})
        return ref

    def build(self, tmp_path, overrides: Overrides | None = None, decisions: list | None = None):
        ids, match = resolve(self.records, self.claims, overrides or Overrides(),
                             IdentityMap(tmp_path / "identity_map.jsonl"))
        anchors = identity_anchors(self.records, self.claims)
        ds = canonicalize(self.records, self.claims, list(self.docs.values()), ids, match, anchors,
                          self.registry, CONFIG, decisions or [])
        return ds, ids


def persons(ds):
    return {p.canonical_id: p for p in ds.by_type(EntityType.PERSON)}


def of(ds, name):
    return sorted((m for m in ds.mentions.values() if m.stated_name == name), key=lambda m: m.source_url)


def one(ds, name):
    (m,) = of(ds, name)
    return m


def edges(ds, pid, rel="PARTICIPATES_IN"):
    return {r.target_id for r in ds.relations if r.source_id == pid and r.type.value == rel}


# ------------------------------------------------------------------ the QA seeds

SEEDS = [
    # (name, own profile, mtmt, [(page, linked profile url | None, expected status)])
    ("Koltai Júlia", f"{RECENS}/kutato/koltai-julia", "10031086",
     [(f"{RECENS}/ds4", f"{RECENS}/kutato/koltai-julia", S.DETERMINISTIC),
      (f"{SZI}/egy-projekt", f"{SZI}/kutato/koltai-julia", S.HIGH_CONFIDENCE_AUTO),  # shared slug namespace
      (f"{KI}/valami", "https://tk.mta.hu/kutato/koltai-julia", S.HIGH_CONFIDENCE_AUTO)]),  # former umbrella host
    ("Ságvári Bence", f"{RECENS}/kutato/sagvari-bence", "10017827",
     [(f"{SZI}/a-kultura-es-az-ertekek-kapcsolata", None, S.REVIEW_REQUIRED),  # name only, other institute
      (f"{SZI}/infra4nextgen", None, S.REVIEW_REQUIRED),
      (f"{RECENS}/digitalis-politikai-labnyomok", f"{RECENS}/kutato/sagvari-bence", S.DETERMINISTIC)]),
    ("Messing Vera", f"{SZI}/kutato/messing-vera", "10017824",
     [(f"{SZI}/infra4nextgen", None, S.HIGH_CONFIDENCE_AUTO),  # own institute, name unique in TK
      (f"{SZI}/a-roma-mediakep-1988-2015", None, S.HIGH_CONFIDENCE_AUTO),
      (f"{SZI}/unit-page", f"{SZI}/kutato/messing-vera", S.DETERMINISTIC)]),
    ("Kovách Imre", f"{SZI}/kutato/kovach-imre", "10002912",
     [(f"{SZI}/cpra-agrieva", None, S.HIGH_CONFIDENCE_AUTO), (f"{SZI}/living-from-their-land", None,
                                                               S.HIGH_CONFIDENCE_AUTO)]),
    ("Gerő Márton", f"{SZI}/kutato/gero-marton", None,
     [(f"{SZI}/valsagok-kihivasok-es-adaptacio", None, S.HIGH_CONFIDENCE_AUTO),
      (f"{PTI}/strudel", None, S.REVIEW_REQUIRED)]),
    ("Papp Z. Attila", f"{KI}/kutato/papp-z-attila", "10014839",
     [(f"{SZI}/valsagok-kihivasok-es-adaptacio", None, S.REVIEW_REQUIRED)]),
    ("Durst Judit", f"{KI}/kutato/durst-judit", "10058589",
     [(f"{SZI}/a-tarsadalmi-egyenlotlensegek-ujratermelodese", None, S.REVIEW_REQUIRED)]),
]


def seed_world(registry) -> tuple[World, dict[str, str]]:
    w, refs = World(registry), {}
    for name, url, mtmt, pages in SEEDS:
        refs[name] = w.profile(url, name, mtmt)
        for page, link, _ in pages:
            proj = w.project(page)
            w.linked(page, link, name, proj) if link else w.unlinked(page, name, proj)
    return w, refs


@pytest.fixture
def seeded(tmp_path, registry):
    w, refs = seed_world(registry)
    ds, ids = w.build(tmp_path)
    return ds, ids, refs


@pytest.mark.parametrize("name", [s[0] for s in SEEDS])
def test_each_seed_profile_is_exactly_one_person(seeded, name):
    ds, ids, refs = seeded
    same = [p for p in persons(ds).values() if p.canonical_name == name]
    assert len(same) == 1
    assert same[0].canonical_id == ids[refs[name]]
    assert "institutional_profile" in same[0].identity_evidence


@pytest.mark.parametrize("name", [s[0] for s in SEEDS])
def test_seed_mentions_get_the_expected_decision(seeded, name):
    ds, _, _ = seeded
    pid = next(p.canonical_id for p in persons(ds).values() if p.canonical_name == name)
    expected = {page: st for n, _, _, pages in SEEDS if n == name for page, _, st in pages}
    for m in of(ds, name):
        assert m.resolution.status is expected[m.source_url], (m.source_url, m.resolution)
        assert pid in [c.person_id for c in m.candidates]
        if m.resolution.status.resolved:
            assert m.resolution.person_id == pid
            assert m.resolution.resolver_version == CONFIG.resolver_version
        else:
            assert m.resolution.person_id is None and m.resolution.reason


def test_unresolved_mentions_project_no_edges(seeded):
    ds, _, _ = seeded
    pid = next(p.canonical_id for p in persons(ds).values() if p.canonical_name == "Ságvári Bence")
    review = [m for m in of(ds, "Ságvári Bence") if m.resolution.status is S.REVIEW_REQUIRED]
    assert review
    assert not edges(ds, pid) & {cx.target_id for m in review for cx in m.context}


def test_resolved_mentions_project_their_claims_onto_the_person(seeded):
    ds, _, _ = seeded
    m = next(m for m in of(ds, "Kovách Imre") if m.source_url.endswith("cpra-agrieva"))
    assert m.resolution.method == "institute_unique_name"
    assert {cx.target_id for cx in m.context} <= edges(ds, m.resolution.person_id)


def test_every_automatic_decision_is_explained(seeded):
    ds, _, _ = seeded
    for m in ds.mentions.values():
        r = m.resolution
        if r.status is S.HIGH_CONFIDENCE_AUTO:
            strong = set(r.signals) & R.STRONG
            assert len(strong) >= 2 and set(r.signals) & set(R.FULL_NAME), r
            assert not set(r.negative_signals) & R.BLOCKING
            assert r.method in {rule for rule, *_ in R.RULES}
            assert r.decision_source.startswith(R.RESOLVER_DOC) and r.decided_at is None


def test_mention_ids_are_stable_and_per_observation(seeded):
    ds, _, _ = seeded
    for m in ds.mentions.values():
        assert m.canonical_id == mention_id(m.source_ref, m.source_url)
    # Ságvári and Messing are both named on infra4nextgen: two mentions, never one
    page = f"{SZI}/infra4nextgen"
    assert {m.stated_name for m in ds.mentions.values() if m.source_url == page} == {"Ságvári Bence", "Messing Vera"}


def test_counts_separate_people_from_mentions(seeded):
    ds, _, _ = seeded
    assert len(persons(ds)) == len(SEEDS)
    assert len(ds.mentions) == sum(len(pages) for *_, pages in SEEDS)
    stats = mention_stats(ds)
    assert stats["resolved"] + stats["not_resolved"] == stats["total"] == len(ds.mentions)
    assert stats["by_source"]["tk_szociologia"]["total"] == sum(
        1 for m in ds.mentions.values() if m.source_id == "tk_szociologia")


# ------------------------------------------------------------------ build stability


def _snapshot(ds):
    return sorted(m.model_dump_json() for m in ds.mentions.values()), sorted(
        (r.source_id, r.type.value, r.target_id) for r in ds.relations)


def test_rebuild_is_idempotent(tmp_path, registry):
    w, _ = seed_world(registry)
    a, ids_a = w.build(tmp_path)
    b, ids_b = w.build(tmp_path)
    assert ids_a == ids_b and _snapshot(a) == _snapshot(b)


def test_input_order_does_not_change_decisions(tmp_path, registry):
    w, _ = seed_world(registry)
    a, _ = w.build(tmp_path / "a")
    rnd = random.Random(7)
    rnd.shuffle(w.records)
    rnd.shuffle(w.claims)
    b, _ = w.build(tmp_path / "b")
    assert _snapshot(a) == _snapshot(b)


def test_automatic_decisions_do_not_chain(tmp_path, registry):
    # Kovách's SZI mention resolves automatically; that edge must not become the context
    # that resolves his name on a KI page of the same project (own_profile_project)
    w = World(registry)
    w.profile(f"{SZI}/kutato/kovach-imre", "Kovách Imre")
    proj = w.project(f"{SZI}/cpra-agrieva")
    w.unlinked(f"{SZI}/cpra-agrieva", "Kovách Imre", proj)
    w.unlinked(f"{KI}/hirek/cpra", "Kovách Imre", proj)
    ds, _ = w.build(tmp_path)
    by_site = {m.source_id: m for m in of(ds, "Kovách Imre")}
    szi, ki = by_site["tk_szociologia"], by_site["tk_kisebbsegkutato"]
    assert szi.resolution.status is S.HIGH_CONFIDENCE_AUTO
    assert ki.resolution.status is S.REVIEW_REQUIRED
    assert R.OWN_PROFILE_LISTS_PROJECT not in ki.candidates[0].signals


# ------------------------------------------------------------------ profile links and aliases


def test_verified_alias_link_is_deterministic(tmp_path, registry):
    w = World(registry)
    w.profile(f"{SZI}/kutato/messing-vera", "Messing Vera")
    proj = w.project(f"{RECENS}/p")
    w.linked(f"{RECENS}/p", f"{SZI}/kutato/messing-vera", "Messing Vera", proj,
             stated="https://szociologia.tk.mta.hu/kutato/messing-vera")  # 301 checked (#14)
    ds, _ = w.build(tmp_path)
    r = one(ds, "Messing Vera").resolution
    assert r.status is S.DETERMINISTIC and r.signals == ["PROFILE_URL_VERIFIED_ALIAS"]
    assert r.evidence["host_alias_status"] == {"szociologia.tk.mta.hu": "verified"}


def test_inferred_alias_link_is_never_deterministic(tmp_path, registry):
    w = World(registry)
    w.profile(f"{PTI}/kutato/ujlaki-anna", "Ujlaki Anna")
    proj = w.project(f"{PTI}/politikai-normativitas")
    w.linked(f"{PTI}/politikai-normativitas", f"{PTI}/kutato/ujlaki-anna", "Ujlaki Anna", proj,
             stated="https://politikatudomany.tk.hun-ren.hu/kutato/ujlaki-anna")  # alias never verified
    ds, _ = w.build(tmp_path)
    r = one(ds, "Ujlaki Anna").resolution
    assert r.status is S.HIGH_CONFIDENCE_AUTO and r.method == "slug_inferred_alias"
    assert R.PROFILE_SLUG_INFERRED_ALIAS in r.signals and R.NAME_EXACT in r.signals


def test_inferred_alias_with_a_different_name_is_not_resolved(tmp_path, registry):
    w = World(registry)
    w.profile(f"{PTI}/kutato/ujlaki-anna", "Ujlaki Anna")
    proj = w.project(f"{PTI}/p")
    w.linked(f"{PTI}/p", f"{PTI}/kutato/ujlaki-anna", "Kiss Anna", proj,
             stated="https://politikatudomany.tk.hun-ren.hu/kutato/ujlaki-anna")
    ds, _ = w.build(tmp_path)
    m = one(ds, "Kiss Anna")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert R.LINK_NAME_MISMATCH in m.candidates[0].negative_signals


def test_page_outside_the_family_gets_no_family_assumption(tmp_path, registry):
    w = World(registry)
    w.profile(f"{RECENS}/kutato/koltai-julia", "Koltai Júlia")
    proj = w.project("https://tk.mta.hu/valami")
    w.linked("https://tk.mta.hu/valami", "https://tk.mta.hu/kutato/koltai-julia", "Koltai Júlia", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Koltai Júlia")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert m.candidates[0].signals == [R.NAME_EXACT]


def test_slug_outside_the_family_is_no_evidence(tmp_path, registry):
    w = World(registry)
    w.profile(f"{RECENS}/kutato/koltai-julia", "Koltai Júlia")
    proj = w.project(f"{SZI}/p")
    w.linked(f"{SZI}/p", "https://tatk.elte.hu/kutato/koltai-julia", "Koltai Júlia", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Koltai Júlia")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert not set(m.candidates[0].signals) & R.SLUG_SIGNALS


def test_link_name_mismatch_blocks(tmp_path, registry):
    # 2026-10-tk-m2: "Illésy Miklós" linked to tk.mta.hu/kutato/illessy-miklos (Person "Illéssy Miklós")
    w = World(registry)
    w.profile(f"{SZI}/kutato/illessy-miklos", "Illéssy Miklós")
    proj = w.project(f"{SZI}/p")
    w.linked(f"{SZI}/p", "https://tk.mta.hu/kutato/illessy-miklos", "Illésy Miklós", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Illésy Miklós")
    assert m.resolution.status is S.REVIEW_REQUIRED and "LINK_NAME_MISMATCH" in m.resolution.reason
    assert m.candidates[0].name_match == "SLUG_ONLY"


def test_link_to_another_profile_blocks_a_name_match(tmp_path, registry):
    w = World(registry)
    w.profile(f"{SZI}/kutato/szabo-andrea", "Szabó Andrea")
    proj = w.project(f"{SZI}/p")
    w.linked(f"{SZI}/p", "https://tk.mta.hu/kutato/szabo-andrea-2", "Szabó Andrea", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Szabó Andrea")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert R.LINKS_OTHER_PROFILE in m.candidates[0].negative_signals


# ------------------------------------------------------------------ ambiguity regressions


def test_two_people_with_one_name_are_not_merged(tmp_path, registry):
    # Szabó Sára: two profiled people with one name stay two identities; mentions go to review
    w = World(registry)
    a = w.profile(f"{SZI}/kutato/szabo-sara", "Szabó Sára")
    b = w.profile(f"{PTI}/kutato/szabo-sara", "Szabó Sára")
    proj = w.project(f"{SZI}/p")
    w.unlinked(f"{SZI}/p", "Szabó Sára", proj)
    ds, ids = w.build(tmp_path)
    assert ids[a] != ids[b]
    m = one(ds, "Szabó Sára")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert {c.person_id for c in m.candidates} == {ids[a], ids[b]}
    for c in m.candidates:
        assert {R.MULTIPLE_CANDIDATES, R.SAME_NAME_MULTIPLE_PERSONS} <= set(c.negative_signals)


@pytest.mark.parametrize("name,slug", [("Kovács Éva", "kovacs-eva"), ("Szabó Andrea", "szabo-andrea")])
def test_common_surname_needs_more_than_institute_and_unique_name(tmp_path, registry, name, slug):
    w = World(registry)
    w.profile(f"{SZI}/kutato/{slug}", name)
    proj = w.project(f"{SZI}/p")
    w.unlinked(f"{SZI}/p", name, proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, name)
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert "common surname" in m.resolution.reason
    assert {R.SAME_INSTITUTE, R.UNIQUE_NAME_IN_FAMILY} <= set(m.candidates[0].signals)


def test_common_surname_resolves_with_direct_evidence(tmp_path, registry):
    # Szabó Andrea's own PTI profile lists the SZI project she is named on
    w = World(registry)
    w.site(SZI)
    proj = w.project(f"{SZI}/integracios-es-dezintegracios-folyamatok", "Integrációs és dezintegrációs folyamatok")
    w.profile(f"{PTI}/kutato/szabo-andrea", "Szabó Andrea", projects=(proj,))
    w.unlinked(f"{SZI}/integracios-es-dezintegracios-folyamatok", "Szabó Andrea", proj)
    ds, _ = w.build(tmp_path)
    r = one(ds, "Szabó Andrea").resolution
    assert r.status is S.HIGH_CONFIDENCE_AUTO and r.method == "own_profile_project"
    assert R.COMMON_SURNAME in r.negative_signals and R.DIFFERENT_INSTITUTE in r.negative_signals


def test_duplicated_profile_is_not_collapsed(tmp_path, registry):
    # Stefkovics Ádám has a recens and a szociologia profile (one CMS record): two Persons
    # until a reviewer decides; the tk.mta.hu link must not pick one of them
    w = World(registry)
    a = w.profile(f"{RECENS}/kutato/stefkovics-adam", "Stefkovics Ádám")
    b = w.profile(f"{SZI}/kutato/stefkovics-adam", "Stefkovics Ádám")
    proj = w.project(f"{SZI}/p")
    w.linked(f"{SZI}/p", "https://tk.mta.hu/kutato/stefkovics-adam", "Stefkovics Ádám", proj)
    ds, ids = w.build(tmp_path)
    assert ids[a] != ids[b]
    m = one(ds, "Stefkovics Ádám")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert len([c for c in m.candidates if R.MULTIPLE_CANDIDATES in c.negative_signals]) == 2


def test_initials_only_never_resolves(tmp_path, registry):
    w = World(registry)
    w.profile(f"{KI}/kutato/papp-z-attila", "Papp Z. Attila")
    proj = w.project(f"{KI}/p")
    w.unlinked(f"{KI}/p", "Papp Attila", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Papp Attila")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert m.candidates[0].name_match == R.NAME_INITIALS_COMPATIBLE
    assert m.resolution.reason == "only weak name evidence (order variant or initials)"


def test_unique_name_and_family_alone_are_not_enough(tmp_path, registry):
    # same family, other institute, no project or link evidence: review, not a merge
    w = World(registry)
    w.profile(f"{KI}/kutato/durst-judit", "Durst Judit")
    proj = w.project(f"{SZI}/p")
    w.unlinked(f"{SZI}/p", "Durst Judit", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Durst Judit")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert {R.SAME_INSTITUTION_FAMILY, R.UNIQUE_NAME_IN_FAMILY} <= set(m.candidates[0].signals)


def test_name_without_any_candidate_is_unresolved(tmp_path, registry):
    w = World(registry)
    w.profile(f"{SZI}/kutato/messing-vera", "Messing Vera")
    proj = w.project(f"{SZI}/p")
    w.unlinked(f"{SZI}/p", "Virág Tünde", proj)
    ds, _ = w.build(tmp_path)
    m = one(ds, "Virág Tünde")
    assert m.resolution.status is S.UNRESOLVED and not m.candidates


# ------------------------------------------------------------------ manual decisions


def test_cluster_override_resolves_a_mention(tmp_path, registry):
    w = World(registry)
    prof = w.profile(f"{RECENS}/kutato/sagvari-bence", "Ságvári Bence")
    proj = w.project(f"{SZI}/infra4nextgen")
    ment = w.unlinked(f"{SZI}/infra4nextgen", "Ságvári Bence", proj)
    ds, ids = w.build(tmp_path, Overrides(same_as=[(prof, ment)]))
    r = one(ds, "Ságvári Bence").resolution
    assert r.status is S.MANUAL_CONFIRMED and r.person_id == ids[prof]
    assert r.decision_source == "review/manual_overrides.yaml"


def test_mention_same_as_is_authoritative(tmp_path, registry):
    w = World(registry)
    prof = w.profile(f"{RECENS}/kutato/sagvari-bence", "Ságvári Bence")
    proj = w.project(f"{SZI}/infra4nextgen")
    w.unlinked(f"{SZI}/infra4nextgen", "Ságvári Bence", proj)
    ds, ids = w.build(tmp_path)
    mid = one(ds, "Ságvári Bence").canonical_id
    assert one(ds, "Ságvári Bence").resolution.status is S.REVIEW_REQUIRED
    d = R.MentionDecision(person_id=ids[prof], decision="same_as", mention_id=mid, reviewer="t", date="2026-10-04",
                          evidence="co-PI listed on the ESS page")
    ds, _ = w.build(tmp_path, decisions=[d])
    r = one(ds, "Ságvári Bence").resolution
    assert r.status is S.MANUAL_CONFIRMED and r.person_id == ids[prof] and r.method == "manual:mention_same_as"
    assert r.decided_at is not None and r.evidence["evidence"] == "co-PI listed on the ESS page"
    assert proj_id(ds, proj) in edges(ds, ids[prof])


def proj_id(ds, ref: EntityRef) -> str:
    return next(e.canonical_id for e in ds.entities.values() if ref.source_ref in e.source_refs)


def test_not_same_as_overrides_a_certain_link(tmp_path, registry):
    w = World(registry)
    prof = w.profile(f"{RECENS}/kutato/koltai-julia", "Koltai Júlia")
    proj = w.project(f"{RECENS}/ds4")
    w.linked(f"{RECENS}/ds4", f"{RECENS}/kutato/koltai-julia", "Koltai Júlia", proj)
    ds, ids = w.build(tmp_path)
    m = one(ds, "Koltai Júlia")
    assert m.resolution.status is S.DETERMINISTIC
    d = R.MentionDecision(person_id=ids[prof], decision="not_same_as", source_ref=m.source_ref)
    ds, _ = w.build(tmp_path, decisions=[d])
    m = one(ds, "Koltai Júlia")
    assert m.resolution.status is S.REVIEW_REQUIRED and m.resolution.person_id is None
    assert m.candidates[0].rejected and R.MANUAL_NOT_SAME_AS in m.candidates[0].negative_signals
    assert proj_id(ds, proj) not in edges(ds, ids[prof])


def test_not_same_as_blocks_an_automatic_rule(tmp_path, registry):
    w = World(registry)
    prof = w.profile(f"{SZI}/kutato/kovach-imre", "Kovách Imre")
    proj = w.project(f"{SZI}/cpra-agrieva")
    w.unlinked(f"{SZI}/cpra-agrieva", "Kovách Imre", proj)
    ds, ids = w.build(tmp_path)
    m = one(ds, "Kovách Imre")
    assert m.resolution.status is S.HIGH_CONFIDENCE_AUTO
    d = R.MentionDecision(person_id=ids[prof], decision="not_same_as", mention_id=m.canonical_id)
    ds, _ = w.build(tmp_path, decisions=[d])
    m = one(ds, "Kovách Imre")
    assert not m.resolution.status.resolved
    assert m.resolution.reason == "every candidate was rejected manually"


def test_mention_decisions_load_from_overrides(tmp_path):
    p = tmp_path / "manual_overrides.yaml"
    p.write_text("mention_decisions:\n  - {mention_id: pmn_x, person_id: per_y, decision: same_as,"
                 " reviewer: B, date: 2026-10-04, evidence: e}\n", encoding="utf-8")
    (d,) = R.load_mention_decisions(p)
    assert (d.mention_id, d.person_id, d.decision, d.date) == ("pmn_x", "per_y", "same_as", "2026-10-04")


# ------------------------------------------------------------------ review queue, QA


def test_review_queue_lists_only_real_ambiguity(seeded, tmp_path):
    import yaml

    ds, _, _ = seeded
    n = write_mention_review(ds, tmp_path / "mention_review.yaml")
    data = yaml.safe_load((tmp_path / "mention_review.yaml").read_text(encoding="utf-8"))
    listed = [e for g in data["by_candidate"] for e in g["mentions"]]
    assert n == len(listed) == sum(1 for m in ds.mentions.values() if m.resolution.status is S.REVIEW_REQUIRED)
    for e in listed:
        assert e["why_not_automatic"] and e["candidates"] and e["page"] and e["context"]


def test_qa_reports_mentions_and_no_identity_errors(seeded):
    ds, _, _ = seeded
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert not [f for f in found.values() if f.severity == "error"]
    assert "identity.unresolved_mentions" in found and "identity.mention_resolution" in found


def test_qa_rejects_an_unexplained_automatic_decision(seeded):
    ds, _, _ = seeded
    m = next(m for m in ds.mentions.values() if m.resolution.status is S.HIGH_CONFIDENCE_AUTO)
    m.resolution.signals = [R.NAME_EXACT]
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert found["identity.auto_resolution_unexplained"].severity == "error"


def test_qa_flags_a_person_without_identity_evidence(seeded):
    ds, _, _ = seeded
    p = next(iter(persons(ds).values()))
    p.identity_evidence = []
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert found["identity.person_without_evidence"].severity == "error"


def test_label_variants_of_one_profile_are_not_a_suspicious_merge(tmp_path, registry):
    # Nyírő Zsanna / Nyírő Zsanna Jozefa: one profile, two observed name forms
    w = World(registry)
    url = f"{KI}/kutato/nyiro-zsanna-jozefa"
    ref = w.profile(url, "Nyírő Zsanna Jozefa", "10064218")
    w.claim(EntityRef(entity_type=EntityType.PERSON, source_ref=ref), "name", f"{KI}/kutatok", "Nyírő Zsanna")
    ds, _ = w.build(tmp_path)
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert "identity.suspicious_merge" not in found
    assert "identity.name_variants" in found


# ------------------------------------------------------------------ #27: manual canonicalisation of two profiles


def _two_profile_world(registry):
    w = World(registry)
    a = w.profile(f"{RECENS}/kutato/stefkovics-adam", "Stefkovics Ádám", also=(f"{RECENS}/kutato/pdf/615",))
    b = w.profile(f"{SZI}/kutato/stefkovics-adam", "Stefkovics Ádám", also=(f"{SZI}/kutato/pdf/615",))
    proj = w.project(f"{SZI}/infra4nextgen")
    w.linked(f"{SZI}/kutatok/s", f"{SZI}/kutato/stefkovics-adam", "Stefkovics Ádám", w.project(f"{SZI}/p"))
    w.unlinked(f"{SZI}/infra4nextgen", "Stefkovics Ádám", proj)
    return w, a, b


def _seed_ids(tmp_path, rows):
    import json

    (tmp_path / "identity_map.jsonl").write_text("".join(
        json.dumps({"source_ref": ref, "entity_type": "Person", "canonical_id": cid, "assigned_at": at}) + "\n"
        for ref, cid, at in rows), encoding="utf-8")


def test_manual_same_as_canonicalises_two_profiles_into_one_person(tmp_path, registry):
    w, a, b = _two_profile_world(registry)
    _seed_ids(tmp_path, [(a, "per_bbbbbbbbbb", "2026-10-04T14:29:22+00:00"),
                         (b, "per_aaaaaaaaaa", "2026-10-04T14:29:22+00:00")])
    ov = Overrides(same_as=[(a, b)], survivors={"per_bbbbbbbbbb"})
    ds, ids = w.build(tmp_path, ov)
    (p,) = persons(ds).values()  # no duplicate Person survives, no SAME_AS edge
    assert p.canonical_id == ids[a] == ids[b] == "per_bbbbbbbbbb"  # the reviewer's survivor, not the lowest id
    assert {f"{RECENS}/kutato/stefkovics-adam", f"{SZI}/kutato/stefkovics-adam", f"{RECENS}/kutato/pdf/615",
            f"{SZI}/kutato/pdf/615"} <= set(p.profile_urls)
    assert {a, b} <= set(p.source_refs) and not [r for r in ds.relations if r.type.value == "SAME_AS"]
    # the profile link is still decided by the link; the merge is about the Person
    linked = next(m for m in of(ds, "Stefkovics Ádám") if m.linked_profile_url)
    assert linked.resolution.status is S.DETERMINISTIC and linked.resolution.person_id == p.canonical_id
    # the name-only SZI mention now has one viable candidate with an SZI affiliation
    unlinked = next(m for m in of(ds, "Stefkovics Ádám") if not m.linked_profile_url)
    assert unlinked.resolution.person_id == p.canonical_id
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert found["identity.multi_record_persons"].subjects == [p.canonical_id]


def test_survivor_is_stable_across_rebuilds_and_input_order(tmp_path, registry):
    w, a, b = _two_profile_world(registry)
    rows = [(a, "per_bbbbbbbbbb", "2026-10-04T14:29:22+00:00"), (b, "per_aaaaaaaaaa", "2026-10-04T14:29:22+00:00")]
    ov = Overrides(same_as=[(a, b)], survivors={"per_bbbbbbbbbb"})
    (tmp_path / "x").mkdir()
    _seed_ids(tmp_path / "x", rows)
    first, ids1 = w.build(tmp_path / "x", ov)
    again, ids2 = w.build(tmp_path / "x", ov)
    rnd = random.Random(3)
    rnd.shuffle(w.records)
    rnd.shuffle(w.claims)
    (tmp_path / "y").mkdir()
    _seed_ids(tmp_path / "y", rows[::-1])
    shuffled, ids3 = w.build(tmp_path / "y", ov)
    assert ids1 == ids2 == ids3
    assert _snapshot(first) == _snapshot(again) == _snapshot(shuffled)


@pytest.mark.parametrize("rows,expected", [
    # no reviewer choice: the older assignment survives (ADR-0003)
    ([("a", "per_bbbbbbbbbb", "2026-10-01T00:00:00+00:00"), ("b", "per_aaaaaaaaaa", "2026-10-04T00:00:00+00:00")],
     "per_bbbbbbbbbb"),
    # same age: the lowest id, deterministically
    ([("a", "per_bbbbbbbbbb", "2026-10-04T00:00:00+00:00"), ("b", "per_aaaaaaaaaa", "2026-10-04T00:00:00+00:00")],
     "per_aaaaaaaaaa"),
])
def test_default_survivor_rule(tmp_path, registry, rows, expected):
    w, a, b = _two_profile_world(registry)
    refs = {"a": a, "b": b}
    _seed_ids(tmp_path, [(refs[k], cid, at) for k, cid, at in rows])
    _, ids = w.build(tmp_path, Overrides(same_as=[(a, b)]))
    assert ids[a] == ids[b] == expected


def test_stronger_anchor_survives_a_tie(tmp_path, registry):
    w = World(registry)
    a = w.profile(f"{RECENS}/kutato/x-y", "X Y")
    b = w.profile(f"{SZI}/kutato/x-y", "X Y", mtmt="10000001")
    _seed_ids(tmp_path, [(a, "per_aaaaaaaaaa", "2026-10-04T00:00:00+00:00"),
                         (b, "per_bbbbbbbbbb", "2026-10-04T00:00:00+00:00")])
    _, ids = w.build(tmp_path, Overrides(same_as=[(a, b)]))
    assert ids[a] == ids[b] == "per_bbbbbbbbbb"


def test_survivor_is_read_from_the_override_file(tmp_path):
    p = tmp_path / "manual_overrides.yaml"
    p.write_text("same_as:\n  - refs: [r1, r2]\n    survivor: per_x\n    reviewer: B\n    date: 2026-10-04\n"
                 "not_same_as: []\n", encoding="utf-8")
    ov = Overrides.load(p)
    assert ov.same_as == [("r1", "r2")] and ov.survivors == {"per_x"} and ov.not_same_as == []


def test_committed_override_keeps_one_stefkovics():
    # the real decision for #27 stays in the override file with its evidence
    import yaml

    data = yaml.safe_load((REPO_ROOT / "review" / "manual_overrides.yaml").read_text(encoding="utf-8"))
    (item,) = [i for i in data["same_as"] if any("stefkovics-adam" in r for r in i["refs"])]
    assert item["survivor"] == "per_07c6bb757b" and "/kutato/pdf/615" in item["evidence"]
    assert item["reviewer"] and item["date"]
