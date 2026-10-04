"""ADR-0006 regression tests: person mentions vs canonical persons.

The records mirror real source refs from release 2026-10-tk (QA seeds whose profile
was split across several canonical ids before the mention model).
"""

from datetime import UTC, datetime

import pytest

from szocatlas.canonical.build import build_canonical
from szocatlas.canonical.mentions import build_mentions, mention_id
from szocatlas.models import Claim, EntityRef, Evidence, SourceDocument, SourceRecord
from szocatlas.models.enums import (
    EntityType,
    EpistemicStatus,
    ExtractionMethod,
    MentionResolutionStatus,
    SourceType,
)
from szocatlas.resolution.matcher import IdentityMap, Overrides, identity_anchors, resolve
from szocatlas.validation.qa import run_checks

NOW = datetime(2026, 10, 4, tzinfo=UTC)
SZI = "https://szociologia.tk.elte.hu"
RECENS = "https://recens.tk.elte.hu"
KI = "https://kisebbsegkutato.tk.elte.hu"


class World:
    """A tiny staged dataset: documents, records and claims as adapters emit them."""

    def __init__(self):
        self.docs: dict[str, SourceDocument] = {}
        self.records: list[SourceRecord] = []
        self.claims: list[Claim] = []

    def doc(self, url: str) -> str:
        did = SourceDocument.make_id(url, "x")
        self.docs.setdefault(did, SourceDocument(
            document_id=did, source_id="tk_test", url=url, final_url=url, canonical_url=url,
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

    def profile(self, url: str, name: str, mtmt: str | None = None) -> str:
        ref = f"tk_test|{url}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(url),
                                         identity_anchor="institutional_profile"))
        self.claim(er, "name", url, name)
        if mtmt:
            self.claim(er, "mtmt_id", url, mtmt)
        return ref

    def project(self, url: str, title: str) -> EntityRef:
        er = EntityRef(entity_type=EntityType.PROJECT, source_ref=f"tk_test|{url}")
        self.records.append(SourceRecord(ref=er, label=title, document_id=self.doc(url)))
        self.claim(er, "title", url, title)
        return er

    def linked(self, page: str, profile_url: str, name: str, project: EntityRef) -> str:
        """A link to a profile URL on another page (listing, unit or project page)."""
        ref = f"tk_test|{profile_url}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(page)))
        self.claim(er, "PARTICIPATES_IN", page, obj=project)
        return ref

    def unlinked(self, page: str, name: str, project: EntityRef, predicate="PARTICIPATES_IN") -> str:
        slug = name.lower().replace(" ", "-")
        ref = f"tk_test|name-mention:{slug}@{project.source_ref}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(page),
                                         hints={"unlinked_mention": True}))
        self.claim(er, "name", page, name)
        self.claim(er, predicate, page, obj=project, qualifiers={"role": "résztvevő"})
        return ref

    def build(self, tmp_path, overrides: Overrides | None = None):
        ids, decisions = resolve(self.records, self.claims, overrides or Overrides(),
                                 IdentityMap(tmp_path / "identity_map.jsonl"))
        anchors = identity_anchors(self.records, self.claims)
        evidence: dict[str, set] = {}
        for ref, kinds in anchors.items():
            if ref in ids:
                evidence.setdefault(ids[ref], set()).update(kinds)
        ds = build_canonical(self.claims, list(self.docs.values()), ids, {k: sorted(v) for k, v in evidence.items()})
        ds.anchor_refs = set(anchors)
        ds.mentions = build_mentions(self.records, self.claims, ds.documents, ids, decisions, anchors, NOW)
        return ds, ids


def persons(ds):
    return {p.canonical_id: p for p in ds.by_type(EntityType.PERSON)}


def of(ds, name):
    return [m for m in ds.mentions.values() if m.stated_name == name]


SEEDS = [
    # (name, profile url, mtmt, [(project page, linked profile url | None)])
    ("Koltai Júlia", f"{RECENS}/kutato/koltai-julia", "10031086",
     [(f"{RECENS}/ds4", f"{RECENS}/kutato/koltai-julia"),
      (f"{SZI}/egy-projekt", f"{SZI}/kutato/koltai-julia"),      # same slug, other host: not exact
      ("https://tk.mta.hu/valami", "https://tk.mta.hu/kutato/koltai-julia")]),
    ("Ságvári Bence", f"{RECENS}/kutato/sagvari-bence", "10017827",
     [(f"{SZI}/a-kultura-es-az-ertekek-kapcsolata", None), (f"{SZI}/sogreen-social-aspects-of-the-green-transition", None),
      (f"{SZI}/infra4nextgen", None), (f"{SZI}/european-social-survey-ess", None),
      (f"{SZI}/egy-online-kozossegi-halozat-eletciklusa-big-data-elemzes", None),
      (f"{RECENS}/digitalis-politikai-labnyomok", f"{RECENS}/kutato/sagvari-bence")]),
    ("Messing Vera", f"{SZI}/kutato/messing-vera", "10017824",
     [(f"{SZI}/infra4nextgen", None), (f"{SZI}/european-social-survey-ess", None), (f"{SZI}/essmagyarorszag", None),
      (f"{SZI}/a-roma-mediakep-1988-2015", None), (f"{SZI}/unit-page", f"{SZI}/kutato/messing-vera")]),
    ("Kovách Imre", f"{SZI}/kutato/kovach-imre", "10002912",
     [(f"{SZI}/cpra-agrieva", None), (f"{SZI}/cpra-control-post", None), (f"{SZI}/living-from-their-land", None)]),
    ("Gerő Márton", f"{SZI}/kutato/gero-marton", None,
     [(f"{SZI}/valsagok-kihivasok-es-adaptacio", None), ("https://politikatudomany.tk.elte.hu/strudel", None)]),
    ("Papp Z. Attila", f"{KI}/kutato/papp-z-attila", "10014839", [(f"{SZI}/valsagok-kihivasok-es-adaptacio", None)]),
    ("Durst Judit", f"{KI}/kutato/durst-judit", "10058589",
     [(f"{SZI}/a-tarsadalmi-egyenlotlensegek-ujratermelodese-az-osztalyszerkezet-tetejen", None)]),
]


@pytest.fixture
def seeded(tmp_path):
    w = World()
    refs = {}
    for name, url, mtmt, pages in SEEDS:
        refs[name] = w.profile(url, name, mtmt)
        for page, link in pages:
            proj = w.project(page, f"Projekt {page.rsplit('/', 1)[-1]}")
            if link:
                w.linked(page, link, name, proj)
            else:
                w.unlinked(page, name, proj)
    ds, ids = w.build(tmp_path)
    return ds, ids, refs


@pytest.mark.parametrize("name", [s[0] for s in SEEDS])
def test_each_seed_profile_is_exactly_one_person(seeded, name):
    ds, ids, refs = seeded
    same = [p for p in persons(ds).values() if p.canonical_name == name]
    assert len(same) == 1
    p = same[0]
    assert p.canonical_id == ids[refs[name]]
    assert "institutional_profile" in p.identity_evidence


@pytest.mark.parametrize("name", [s[0] for s in SEEDS])
def test_unlinked_same_name_mentions_stay_unresolved_evidence(seeded, name):
    ds, _, _ = seeded
    pid = next(p.canonical_id for p in persons(ds).values() if p.canonical_name == name)
    unlinked = [m for m in of(ds, name) if m.linked_profile_url is None]
    for m in unlinked:
        assert m.resolution.status is MentionResolutionStatus.UNRESOLVED and m.resolution.person_id is None
        assert pid in m.candidate_person_ids  # offered for review, never merged on the name alone
        assert m.context and m.context[0].qualifiers["role"] == ["résztvevő"]
    # no project edge is attributed to the person from an unresolved mention
    assert not [r for r in ds.relations if r.source_id == pid and r.type.value == "PARTICIPATES_IN"
                and any(r.target_id == cx.target_id for m in unlinked for cx in m.context)]


def test_link_to_exact_profile_url_resolves_deterministically(seeded):
    ds, ids, refs = seeded
    m = next(m for m in of(ds, "Koltai Júlia") if m.source_url == f"{RECENS}/ds4")
    assert m.resolution.status is MentionResolutionStatus.DETERMINISTIC
    assert m.resolution.person_id == ids[refs["Koltai Júlia"]]
    assert m.resolution.method == "profile_url"
    # and the observed participation reaches the canonical graph through the resolution
    assert any(r.source_id == m.resolution.person_id and r.type.value == "PARTICIPATES_IN" for r in ds.relations)


def test_same_slug_on_another_host_is_not_an_exact_profile_match(seeded):
    # szociologia.tk.elte.hu/kutato/koltai-julia and tk.mta.hu/kutato/koltai-julia are not her
    # canonical profile URL; equating them needs alias evidence (#14) or a rule from #5
    ds, _, _ = seeded
    other = [m for m in of(ds, "Koltai Júlia") if m.linked_profile_url and "recens" not in m.linked_profile_url]
    assert len(other) == 2
    assert all(m.resolution.status is MentionResolutionStatus.UNRESOLVED for m in other)


def test_counts_separate_people_from_mentions(seeded):
    ds, _, _ = seeded
    assert len(persons(ds)) == len(SEEDS)
    n_obs = sum(len(pages) for *_, pages in SEEDS)
    assert len(ds.mentions) == n_obs
    resolved = [m for m in ds.mentions.values() if m.resolution.person_id]
    assert len(resolved) == 3  # Koltai on DS4, Ságvári on the recens project, Messing on the unit page


def test_mention_ids_are_stable_and_per_observation(seeded, tmp_path):
    ds, _, _ = seeded
    for m in ds.mentions.values():
        assert m.canonical_id == mention_id(m.source_ref, m.source_url)
    # Ságvári and Messing are both named on infra4nextgen: two mentions, never one
    page = f"{SZI}/infra4nextgen"
    assert {m.stated_name for m in ds.mentions.values() if m.source_url == page} == {"Ságvári Bence", "Messing Vera"}


def test_manual_override_resolves_a_mention(tmp_path):
    w = World()
    prof = w.profile(f"{SZI}/kutato/kovach-imre", "Kovách Imre", "10002912")
    proj = w.project(f"{SZI}/cpra-agrieva", "CPRA AgriEVA")
    ment = w.unlinked(f"{SZI}/cpra-agrieva", "Kovách Imre", proj)
    ds, ids = w.build(tmp_path, Overrides(same_as=[(prof, ment)]))
    (m,) = ds.mentions.values()
    assert m.resolution.status is MentionResolutionStatus.MANUAL_CONFIRMED
    assert m.resolution.person_id == ids[prof]
    assert m.resolution.decision_source == "review/manual_overrides.yaml"


def test_two_people_with_one_name_are_not_merged(tmp_path):
    # Szabó Sára x4 in 2026-10-tk: two profiled people with one name stay two identities
    w = World()
    a = w.profile(f"{SZI}/kutato/szabo-sara", "Szabó Sára")
    b = w.profile("https://politikatudomany.tk.elte.hu/kutato/szabo-sara", "Szabó Sára")
    proj = w.project(f"{SZI}/p", "P")
    w.unlinked(f"{SZI}/p", "Szabó Sára", proj)
    ds, ids = w.build(tmp_path)
    assert ids[a] != ids[b]
    (m,) = ds.mentions.values()
    assert m.resolution.person_id is None and set(m.candidate_person_ids) == {ids[a], ids[b]}


def test_qa_reports_mentions_and_no_identity_errors(seeded):
    ds, _, _ = seeded
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert not [f for f in found.values() if f.severity == "error"]
    assert "identity.unresolved_mentions" in found
    assert "structure.orphan_person" in found  # canonical people only: no affiliation edges in this world
    assert len(found["structure.orphan_person"].subjects) == len(SEEDS)


def test_qa_flags_a_person_without_identity_evidence(seeded):
    ds, _, _ = seeded
    p = next(iter(persons(ds).values()))
    p.identity_evidence = []
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert found["identity.person_without_evidence"].severity == "error"


def test_label_variants_of_one_profile_are_not_a_suspicious_merge(tmp_path):
    # Nyírő Zsanna / Nyírő Zsanna Jozefa: one profile, two observed name forms
    w = World()
    url = f"{KI}/kutato/nyiro-zsanna-jozefa"
    ref = w.profile(url, "Nyírő Zsanna Jozefa", "10064218")
    w.claim(EntityRef(entity_type=EntityType.PERSON, source_ref=ref), "name", f"{KI}/kutatok", "Nyírő Zsanna")
    ds, _ = w.build(tmp_path)
    found = {f.check: f for f in run_checks(ds, [], None)}
    assert "identity.suspicious_merge" not in found
    assert "identity.name_variants" in found
