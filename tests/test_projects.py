"""Project mentions vs canonical Projects and their conservative resolution (#7, ADR-0008).

The records mirror the TK adapter's refs and locators and real cases from release
2026-10-tk-m2-s27: the Éghajlat 2020 / 2021 editions, listing + page pairs, profile titles
carrying grant and role affixes, links to the NKFIH registry, activities for #9.
"""

import random
from datetime import UTC, datetime

import pytest

from szocatlas.canonical.project_mentions import project_mention_id
from szocatlas.models import Claim, EntityRef, Evidence, SourceDocument, SourceRecord
from szocatlas.models.enums import (
    EntityType,
    EpistemicStatus,
    ExtractionMethod,
    IdentityAnchor,
    MentionResolutionStatus,
    SourceType,
    TemporalBasis,
)
from szocatlas.models.entities import ProjectMentionResolution
from szocatlas.pipeline import Paths, canonicalize, ingest_fixtures, read_staged
from szocatlas.registry import REPO_ROOT
from szocatlas.resolution import mentions as R
from szocatlas.resolution import projects as PR
from szocatlas.resolution.matcher import IdentityMap, Overrides, identity_anchors, resolve
from szocatlas.validation.qa import run_checks

NOW = datetime(2026, 10, 4, tzinfo=UTC)
SZI = "https://szociologia.tk.elte.hu"
PTI = "https://politikatudomany.tk.elte.hu"
KI = "https://kisebbsegkutato.tk.elte.hu"
CONFIG = R.ResolutionConfig.load(REPO_ROOT / "config" / "resolution.yaml")
S = MentionResolutionStatus
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tk"


class World:
    """A tiny staged dataset with the TK adapter's project refs and locators."""

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
            raw_path="raw", source_type=SourceType.PROJECT_PAGE, fetcher_version="t"))
        return did

    def claim(self, subject, predicate, url, locator, value=None, obj=None, **kw):
        self.claims.append(Claim(
            subject=subject, predicate=predicate, value=value, object=obj, observed_at=NOW,
            evidence=Evidence(document_id=self.doc(url), locator=locator, snippet=str(value or predicate)),
            extraction_method=ExtractionMethod.HTML_PARSER, parser="t", parser_version="0",
            epistemic_status=EpistemicStatus.OBSERVED, confidence=0.9, **kw))

    def site(self, base: str) -> EntityRef:
        er = EntityRef(entity_type=EntityType.ORG_UNIT, source_ref=f"{self.owner(base + '/')}|site")
        if not any(r.ref == er for r in self.records):
            self.records.append(SourceRecord(ref=er, label=er.source_ref, document_id=self.doc(base + "/")))
            self.claim(er, "name", base + "/", "t", er.source_ref)
        return er

    def project_ref(self, url: str | None, title: str, page: str) -> EntityRef:
        src = f"{self.owner(url)}|{url}" if url else f"{self.owner(page)}|project-title:{R.title_fold(title).replace(' ', '-')}"
        return EntityRef(entity_type=EntityType.PROJECT, source_ref=src)

    def page(self, url: str, title: str, *, start=None, end=None, grant=None,
             people: tuple[tuple[str, str | None], ...] = ()) -> EntityRef:
        """A project's own page (anchor) naming people: (name, profile url or None)."""
        er = self.project_ref(url, title, url)
        self.records.append(SourceRecord(ref=er, label=title, document_id=self.doc(url),
                                         identity_anchor=IdentityAnchor.PROJECT_PAGE.value))
        self.claim(er, "title", url, "project.h1", title)
        self.claim(er, "website", url, "document.url", url)
        for pred, v in (("start", start), ("end", end), ("grant_id", grant)):
            if v:
                self.claim(er, pred, url, f"project.field.{pred}", v)
        self.claim(er, "HOSTED_BY", url, "project.site", obj=self.site("/".join(url.split("/")[:3])))
        for name, profile in people:
            if profile:
                pref = EntityRef(entity_type=EntityType.PERSON, source_ref=f"{self.owner(profile)}|{profile}")
            else:
                pref = EntityRef(entity_type=EntityType.PERSON,
                                 source_ref=f"{self.owner(url)}|name-mention:{name}@{er.source_ref}")
            self.records.append(SourceRecord(ref=pref, label=name, document_id=self.doc(url)))
            self.claim(pref, "name", url, "project.field.resztvevok", name)
            self.claim(pref, "PARTICIPATES_IN", url, "project.field.resztvevok", obj=er)
        return er

    def listing(self, listing_url: str, project_url: str | None, title: str, **fields) -> EntityRef:
        er = self.project_ref(project_url, title, listing_url)
        self.records.append(SourceRecord(ref=er, label=title, document_id=self.doc(listing_url)))
        self.claim(er, "title", listing_url, "listing.article.title", title)
        for pred, v in fields.items():
            self.claim(er, pred, listing_url, f"listing.article.field.{pred}", v)
        return er

    def profile(self, url: str, name: str, projects=()) -> str:
        """An own profile listing projects: (title, url | None, period_from, role)."""
        ref = f"{self.owner(url)}|{url}"
        er = EntityRef(entity_type=EntityType.PERSON, source_ref=ref)
        self.records.append(SourceRecord(ref=er, label=name, document_id=self.doc(url),
                                         identity_anchor="institutional_profile"))
        self.claim(er, "name", url, "profile.h1", name)
        self.claim(er, "profile_url", url, "document.url", url)
        self.claim(er, "AFFILIATED_WITH", url, "profile.position", obj=self.site(url.split("/kutato/")[0]))
        for title, purl, period, role in projects:
            pref = self.project_ref(purl, title, url)
            self.records.append(SourceRecord(ref=pref, label=title, document_id=self.doc(url)))
            self.claim(pref, "title", url, "profile.section.projektek", title)
            kw = dict(valid_from=period, temporal_basis=TemporalBasis.EXPLICIT) if period else {}
            self.claim(er, "PARTICIPATES_IN", url, "profile.section.projektek", obj=pref,
                       qualifiers={"role": role} if role else {}, **kw)
        return ref

    def build(self, tmp_path, overrides: Overrides | None = None, decisions=None, shuffle: int | None = None):
        records, claims = list(self.records), list(self.claims)
        if shuffle is not None:
            random.Random(shuffle).shuffle(records)
            random.Random(shuffle).shuffle(claims)
        overrides = overrides or Overrides()
        ids, match = resolve(records, claims, overrides, IdentityMap(tmp_path / "identity_map.jsonl"))
        anchors = identity_anchors(records, claims, overrides)
        ds = canonicalize(records, claims, list(self.docs.values()), ids, match, anchors, self.registry, CONFIG,
                          [], decisions or [])
        return ds, ids


def projects(ds):
    return {p.canonical_id: p for p in ds.by_type(EntityType.PROJECT)}


def pm_on(ds, page_url):
    (m,) = [m for m in ds.project_mentions.values() if m.source_url == page_url]
    return m


def participates(ds, pid=None):
    return {(r.source_id, r.target_id) for r in ds.relations
            if r.type.value == "PARTICIPATES_IN" and (pid is None or r.target_id == pid)}


# ---------------------------------------------------------------- normalisation helpers
@pytest.mark.parametrize("title,key", [
    ("OTKA K 143593 - Gyermekvédelem az iskolában – Kutatásvezető", "gyermekvedelem az iskolaban"),
    ("PD OTKA 146375 - Közép-Európa választási földrajza - Vezető kutató", "kozep europa valasztasi foldrajza"),
    ("Válságok, kihívások és adaptáció, NKFIH K147304 (kutatásvezető: Kovách Imre)", "valsagok kihivasok es adaptacio"),
    ("Integrációs és dezintegrációs folyamatok a magyar társadalomban című kutatás",
     "integracios es dezintegracios folyamatok a magyar tarsadalomban"),
    ("Magyarország az energiaválságban | TK Politikatudományi Intézet", "magyarorszag az energiavalsagban"),
    ("Éghajlatváltozás és egészség 2021", "eghajlatvaltozas es egeszseg"),
    ("Németek, helyi társadalom és hatalom (Harta, 1920–1989)", "nemetek helyi tarsadalom es hatalom"),
])
def test_title_key_strips_grant_role_period_and_funder_affixes(title, key):
    assert PR.title_key(title) == key


def test_grant_keys_ignore_funder_labels_and_programme_letters():
    for text in ("OTKA K 143593 - X", "NKFIH K_143593", "K-143593", "(NKFI, K: 143593)", "143593 jelű"):
        assert PR.grant_keys(text) == ["nkfih:143593"], text
    assert PR.grant_keys("2012-09-01 - 2015-12-31", "H2020. G-ID: 785125", "16,099 M Ft") == []
    assert PR.registry_grant_keys(
        "https://nyilvanos.otka-palyazat.hu/index.php?lang=HU&menuid=930&num=137755keyword%3D137755") == \
        ["nkfih:137755"]


def test_year_and_full_date_are_not_contradictory():
    assert not PR.periods_conflict(PR._years("2023", None), PR._years("2023-01-01", "2024-06-30"))
    assert not PR.periods_conflict(PR._years("2019", None), PR._years("2021-06-25", "2021-12-25"))  # open end
    assert PR.periods_conflict(PR._years("2012", "2016"), PR._years("2020-04-01", "2020-12-31"))


# ---------------------------------------------------------------- identity
def test_eghajlat_editions_are_two_projects(tmp_path, registry):
    w = World(registry)
    a = w.page(f"{SZI}/eghajlatvaltozas-es-egeszseg", "Éghajlatváltozás és egészség",
               start="2020-04-01", end="2020-12-31")
    b = w.page(f"{SZI}/eghajlatvaltozas-es-egeszseg-2021", "Éghajlatváltozás és egészség 2021",
               start="2021-06-25", end="2021-12-25")
    w.profile(f"{SZI}/kutato/x-y", "X Y", [("Éghajlatváltozás és egészség", None, None, None)])
    ds, ids = w.build(tmp_path)
    p20, p21 = projects(ds)[ids[a.source_ref]], projects(ds)[ids[b.source_ref]]
    assert p20.canonical_id != p21.canonical_id
    # each edition keeps its own values: nothing is "solved" by choosing one
    assert (p20.start, p20.end, p21.start, p21.end) == ("2020-04-01", "2020-12-31", "2021-06-25", "2021-12-25")
    assert not p20.conflicts and not p21.conflicts
    # a bare title on a profile is ambiguous between the editions
    m = pm_on(ds, f"{SZI}/kutato/x-y")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert {c.project_id for c in m.candidates if PR.MULTIPLE_CANDIDATES in c.negative_signals} == {p20.canonical_id,
                                                                                                    p21.canonical_id}
    # no edition relation without a stated one
    assert not [r for r in ds.relations if r.type.value in ("PREDECESSOR_OF", "SUCCESSOR_OF")]
    same = next(f for f in run_checks(ds, [], None) if f.check == "project.same_title_distinct")
    assert set(same.subjects) == {p20.canonical_id, p21.canonical_id}


def test_previously_merged_editions_split_with_previous_id(tmp_path, registry):
    w = World(registry)
    a = w.page(f"{SZI}/eghajlatvaltozas-es-egeszseg", "Éghajlatváltozás és egészség")
    b = w.page(f"{SZI}/eghajlatvaltozas-es-egeszseg-2021", "Éghajlatváltozás és egészség 2021")
    ident = IdentityMap(tmp_path / "identity_map.jsonl")
    for ref in (a.source_ref, b.source_ref):  # what auto:same_site_same_name assigned in 2026-10-tk-m2-s27
        ident.rows[ref] = {"source_ref": ref, "entity_type": "Project", "canonical_id": "prj_2c4d005975",
                           "assigned_at": "2026-10-04T14:29:22+00:00"}
    ident.save()
    ids, _ = resolve(w.records, w.claims, Overrides(), ident)
    assert ids[a.source_ref] == "prj_2c4d005975" and ids[b.source_ref] != "prj_2c4d005975"
    assert ident.rows[b.source_ref]["previous_id"] == "prj_2c4d005975"
    assert "previous_id" not in ident.rows[a.source_ref]
    ident.save()
    again, _ = resolve(w.records, w.claims, Overrides(), IdentityMap(tmp_path / "identity_map.jsonl"))
    assert again == ids


def test_listing_and_page_are_one_project(tmp_path, registry):
    w = World(registry)
    url = f"{SZI}/vakcinacio"
    p = w.page(url, "Vakcinációs hajlandóság", start="2021-01-01")
    w.listing(f"{SZI}/futo-kutatasok", url, "Vakcinációs hajlandóság Magyarországon", start="2021")
    ds, ids = w.build(tmp_path)
    (proj,) = projects(ds).values()
    assert proj.canonical_id == ids[p.source_ref]
    m = pm_on(ds, f"{SZI}/futo-kutatasok")
    assert m.observation == "project_listing" and m.resolution.status is S.DETERMINISTIC
    assert m.resolution.signals == ["PROJECT_URL_EXACT"]
    # the listing's wording is an alternate title; '2021' and '2021-01-01' are not a conflict to choose between
    assert proj.title == "Vakcinációs hajlandóság" and "Vakcinációs hajlandóság Magyarországon" in proj.alternate_titles


def test_project_on_several_profiles(tmp_path, registry):
    w = World(registry)
    url = f"{KI}/az-iskola-nem-sziget"
    w.page(url, "Az iskola nem sziget")
    a = w.profile(f"{KI}/kutato/a-a", "A A", [("Az iskola nem sziget", url, "2022", "kutató")])
    b = w.profile(f"{KI}/kutato/b-b", "B B", [("Az iskola nem sziget (NKFIH)", url, None, None)])
    ds, ids = w.build(tmp_path)
    pid = next(iter(projects(ds)))
    assert participates(ds, pid) == {(ids[a], pid), (ids[b], pid)}
    for page in (a, b):
        m = pm_on(ds, page.split("|", 1)[1])
        assert m.resolution.status is S.DETERMINISTIC and m.observed_on_profile_of == ids[page]
    edge = next(r for r in ds.relations if r.source_id == ids[a] and r.target_id == pid)
    assert edge.qualifiers["role"] == ["kutató"] and edge.valid_from == "2022"  # the person's role stays on the edge


def test_title_only_on_several_profiles_is_never_merged(tmp_path, registry):
    w = World(registry)
    a = w.profile(f"{KI}/kutato/a-a", "A A", [("Kisebbségi magyar közösségek a 20. században", None, None, None)])
    b = w.profile(f"{KI}/kutato/b-b", "B B", [("Kisebbségi magyar közösségek a 20. században", None, None, None)])
    ds, ids = w.build(tmp_path)
    assert not projects(ds)  # no anchor: no Project, hence no invented co-participation tie
    assert not participates(ds)
    ms = [pm_on(ds, r.split("|", 1)[1]) for r in (a, b)]
    assert {m.resolution.status for m in ms} == {S.UNRESOLVED}
    assert ms[0].source_ref == ms[1].source_ref and ms[0].canonical_id != ms[1].canonical_id
    assert ds.project_mention_claims_skipped >= 2  # the participation claims stay on the mentions
    dup = next(f for f in run_checks(ds, [], None) if f.check == "project.duplicate_title_groups")
    assert "kisebbsegi magyar kozossegek a 20 szazadban" in dup.detail["groups"]


# ---------------------------------------------------------------- the rules
def test_title_with_grant_and_role_suffix_resolves_when_the_page_names_the_owner(tmp_path, registry):
    w = World(registry)
    url = f"{PTI}/kozep-europa-valasztasi-foldrajza"
    prof = f"{PTI}/kutato/kovalcsik-tamas"
    p = w.page(url, "Közép-Európa választási földrajza", start="2024", people=(("Kovalcsik Tamás", prof),))
    owner = w.profile(prof, "Kovalcsik Tamás",
                      [("PD OTKA 146375 - Közép-Európa választási földrajza - Vezető kutató", None, None,
                        "Vezető kutató")])
    ds, ids = w.build(tmp_path)
    m = pm_on(ds, prof)
    r = m.resolution
    assert r.status is S.HIGH_CONFIDENCE_AUTO and r.method == "title_and_owner"
    assert r.project_id == ids[p.source_ref]
    assert {"TITLE_EQUAL_AFTER_AFFIXES", "PAGE_LINKS_OWNER"} <= set(r.signals)
    assert m.grant_keys == ["nkfih:146375"] and m.stated_roles == ["Vezető kutató"]
    assert (ids[owner], ids[p.source_ref]) in participates(ds)
    proj = projects(ds)[ids[p.source_ref]]
    assert proj.title == "Közép-Európa választási földrajza"  # the page's title wins; the profile's is an alternate


def test_title_alone_never_resolves(tmp_path, registry):
    # 'ESS Magyarország': the same title, but the page does not name the profile owner
    w = World(registry)
    w.page(f"{SZI}/ess-magyarorszag", "ESS Magyarország")
    w.profile(f"{PTI}/kutato/szabo-andrea", "Szabó Andrea", [("ESS Magyarország", None, None, None)])
    ds, _ = w.build(tmp_path)
    m = pm_on(ds, f"{PTI}/kutato/szabo-andrea")
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert m.candidates[0].signals == ["TITLE_EXACT"]
    assert "title evidence only" in m.resolution.reason


def test_same_title_with_a_different_grant_is_blocked(tmp_path, registry):
    w = World(registry)
    prof = f"{SZI}/kutato/x-y"
    w.page(f"{SZI}/egyenlotlensegek", "Társadalmi egyenlőtlenségek", grant="NKFIH K 128965", people=(("X Y", prof),))
    w.profile(prof, "X Y", [("Társadalmi egyenlőtlenségek (OTKA K 105976)", None, None, None)])
    ds, _ = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.resolution.status is S.REVIEW_REQUIRED
    assert PR.GRANT_ID_CONFLICT in m.candidates[0].negative_signals


def test_same_grant_with_a_title_variant_resolves(tmp_path, registry):
    w = World(registry)
    p = w.page(f"{SZI}/fenntarthato-fogyasztas", "Fenntartható fogyasztási mintázatok és tudáshasználat",
               grant="NKFIH K 134900")
    w.profile(f"{SZI}/kutato/kristof-luca", "Kristóf Luca",
              [("Fenntartható fogyasztási mintázatok és tudáshasználat a magyar társadalomban (K134900)",
                None, None, None)])
    ds, ids = w.build(tmp_path)
    r = pm_on(ds, f"{SZI}/kutato/kristof-luca").resolution
    assert r.status is S.HIGH_CONFIDENCE_AUTO and r.method == "grant_and_title"
    assert r.project_id == ids[p.source_ref] and r.evidence["grant_keys"] == ["nkfih:134900"]


def test_disjoint_period_blocks(tmp_path, registry):
    w = World(registry)
    prof = f"{SZI}/kutato/x-y"
    w.page(f"{SZI}/eghajlat", "Éghajlatváltozás és egészség", start="2020-04-01", end="2020-12-31",
           people=(("X Y", prof),))
    w.profile(prof, "X Y", [("Éghajlatváltozás és egészség", None, "2023", None)])
    ds, _ = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.resolution.status is S.REVIEW_REQUIRED and PR.PERIOD_CONFLICT in m.candidates[0].negative_signals


def test_registry_link_is_a_grant_statement_not_another_page(tmp_path, registry):
    w = World(registry)
    prof = f"{PTI}/kutato/plesz-bendeguz"
    reg = "https://nyilvanos.otka-palyazat.hu/index.php?lang=HU&menuid=930&num=137755"
    p = w.page(f"{PTI}/polarizacio", "A polarizáció szerepe a nemkívánt társadalmi kimenetelek létrejöttében",
               people=(("Plesz Bendegúz", prof),))
    w.profile(prof, "Plesz Bendegúz",
              [("A polarizáció szerepe a nemkívánt társadalmi kimenetelek létrejöttében", reg, "2021", None)])
    ds, ids = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.grant_keys == ["nkfih:137755"] and m.linked_url == reg
    assert m.resolution.status is S.HIGH_CONFIDENCE_AUTO and m.resolution.project_id == ids[p.source_ref]
    assert PR.LINKS_OTHER_PAGE not in m.resolution.negative_signals


def test_link_to_another_site_blocks(tmp_path, registry):
    # 'reprosoc.tk.hu' is a research group's site: not the project page, so not decided automatically
    w = World(registry)
    prof = f"{SZI}/kutato/herke-boglarka"
    w.page(f"{SZI}/a-reprodukcioval-kapcsolatos-dontesek", "A reprodukcióval kapcsolatos döntések vizsgálata",
           people=(("Herke Boglárka", prof),))
    w.profile(prof, "Herke Boglárka",
              [("A reprodukcióval kapcsolatos döntések vizsgálata", "https://reprosoc.tk.hu/", None, None)])
    ds, _ = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.resolution.status is S.REVIEW_REQUIRED and PR.LINKS_OTHER_PAGE in m.candidates[0].negative_signals


def test_uncertain_activity_is_preserved_for_issue_9(tmp_path, registry):
    w = World(registry)
    w.profile(f"{RECENS_HOST}/kutato/x-y", "X Y", [
        ("Intersections. East European Journal of Society and Politics", None, None, "szerkesztő"),
        ("Hírlevél (2)", None, None, None),
        ("ENTAN - European Non-Territorial Autonomy Network", "https://entan.org/", None, None)])
    ds, _ = w.build(tmp_path)
    cues = {m.stated_title: m.activity_cues for m in ds.project_mentions.values()}
    assert cues == {"Intersections. East European Journal of Society and Politics": ["journal"],
                    "Hírlevél (2)": ["newsletter"],
                    "ENTAN - European Non-Territorial Autonomy Network": ["network"]}
    # kept as observed, not dropped and not reclassified here
    assert all(m.observation == "profile_list" for m in ds.project_mentions.values())


RECENS_HOST = "https://recens.tk.elte.hu"


# ---------------------------------------------------------------- decisions: authority, order, no chaining
def test_manual_project_decisions_are_authoritative(tmp_path, registry):
    w = World(registry)
    url = f"{SZI}/diszkontinuitasok"
    p = w.page(url, "Diszkontinuitások - a magyar szociológia 1960 és 2010 között", grant="OTKA 115644")
    w.profile(f"{SZI}/kutato/tibori-timea", "Tibori Tímea",
              [("Diszkontinuitás – a magyar szociológia 1960 és 2010 között (OTKA 115644, 2016–2019)",
                None, None, None)])
    w.listing(f"{SZI}/lezart-kutatasok", url, "Diszkontinuitások")
    ds, ids = w.build(tmp_path)
    m = pm_on(ds, f"{SZI}/kutato/tibori-timea")
    assert m.resolution.status is S.REVIEW_REQUIRED  # grant only: one signal
    pid = ids[p.source_ref]
    lst = pm_on(ds, f"{SZI}/lezart-kutatasok")
    decisions = [PR.ProjectDecision(project_id=pid, decision="same_as", mention_id=m.canonical_id,
                                    reviewer="t", date="2026-10-04", evidence="same grant number"),
                 PR.ProjectDecision(project_id=pid, decision="not_same_as", mention_id=lst.canonical_id,
                                    reviewer="t", date="2026-10-04", evidence="test")]
    ds, _ = w.build(tmp_path, decisions=decisions)
    assert pm_on(ds, f"{SZI}/kutato/tibori-timea").resolution.status is S.MANUAL_CONFIRMED
    r = pm_on(ds, f"{SZI}/lezart-kutatasok").resolution  # a rejection outranks even a certain link
    assert r.status is S.REVIEW_REQUIRED and r.negative_signals == ["MANUAL_NOT_SAME_AS"]


def test_manual_same_as_joins_two_project_pages(tmp_path, registry):
    w = World(registry)
    a = w.page(f"{SZI}/projekt-regi", "Projekt")
    b = w.page(f"{PTI}/projekt-uj", "Projekt (új oldal)")
    ov = Overrides(same_as=[(a.source_ref, b.source_ref)])
    ds, ids = w.build(tmp_path, overrides=ov)
    assert ids[a.source_ref] == ids[b.source_ref]
    (p,) = projects(ds).values()
    assert set(p.identity_evidence) == {IdentityAnchor.PROJECT_PAGE, IdentityAnchor.MANUAL}
    assert any(f.check == "project.multiple_urls" for f in run_checks(ds, [], None))
    ds, ids = w.build(tmp_path, overrides=Overrides(not_same_as=[(a.source_ref, b.source_ref)]))
    assert ids[a.source_ref] != ids[b.source_ref]


def test_manual_same_as_overrules_a_block_and_records_what_the_rules_saw(tmp_path, registry):
    # #7 review: the profile item links the activity's own site (reprosoc.tk.hu); the reviewer decides
    # same_as. The identity decision does not touch the activity cue (#9) and the record keeps the
    # blocking signal that was overruled.
    w = World(registry)
    prof = f"{SZI}/kutato/galantai-julia"
    title = "A reprodukcióval kapcsolatos döntések többszempontú vizsgálata európai összehasonlításban"
    p = w.page(f"{SZI}/a-reprodukcioval-kapcsolatos-dontesek", title)
    w.profile(prof, "Galántai Júlia", [(f"{title} (MTA Lendület)", "https://reprosoc.tk.hu/", None, None)])
    ds, ids = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.resolution.status is S.REVIEW_REQUIRED and not participates(ds, ids[p.source_ref])
    d = PR.ProjectDecision(project_id=ids[p.source_ref], decision="same_as", mention_id=m.canonical_id,
                           reviewer="t", date="2026-10-05", evidence="the activity's own site")
    ds, ids2 = w.build(tmp_path, decisions=[d])
    r = pm_on(ds, prof).resolution
    assert ids2 == ids  # a decision never mints or moves a project id
    assert r.status is S.MANUAL_CONFIRMED and r.project_id == ids[p.source_ref] and r.signals == [PR.MANUAL_SAME_AS]
    assert PR.LINKS_OTHER_PAGE in r.evidence["signals_seen"]["negative"]
    assert r.evidence["signals_seen"]["positive"] and r.evidence["reviewer"] == "t"
    assert pm_on(ds, prof).activity_cues == ["research_group"]  # not pre-empted
    assert len(participates(ds, ids[p.source_ref])) == 1


def test_manual_decision_is_per_mention_and_the_generic_rule_stays_conservative(tmp_path, registry):
    # the same short title on two profiles: deciding one does not decide the other, and without a
    # decision a title prefix never resolves
    w = World(registry)
    p = w.page(f"{SZI}/joleti", "Jóléti attitűdök magyarázata: általános morális elvek, téma-keretezés és dizájn")
    a, b = f"{RECENS_HOST}/kutato/kmetty-zoltan", f"{SZI}/kutato/janky-bela"
    w.profile(a, "Kmetty Zoltán", [("Jóléti attitűdök magyarázata", None, "2016", None)])
    w.profile(b, "Janky Béla", [("Jóléti attitűdök magyarázata", None, "2016", None)])
    ds, ids = w.build(tmp_path)
    assert {pm_on(ds, a).resolution.status, pm_on(ds, b).resolution.status} == {S.REVIEW_REQUIRED}
    d = PR.ProjectDecision(project_id=ids[p.source_ref], decision="same_as", mention_id=pm_on(ds, a).canonical_id)
    ds, _ = w.build(tmp_path, decisions=[d])
    assert pm_on(ds, a).resolution.status is S.MANUAL_CONFIRMED
    assert pm_on(ds, b).resolution.status is S.REVIEW_REQUIRED


def test_defer_holds_a_mention_back_without_naming_a_project(tmp_path, registry):
    # #7 review, ESS Magyarország: the identity is plausible, the entity type is #9's to decide
    w = World(registry)
    page = f"{SZI}/essmagyarorszag"
    p = w.page(page, "ESS Magyarország")
    prof = f"{PTI}/kutato/szabo-andrea"
    w.profile(prof, "Szabó Andrea", [("ESS Magyarország", None, None, "résztvevő kutató")])
    ds, ids = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.resolution.status is S.REVIEW_REQUIRED  # exact title only: not automatic
    d = PR.ProjectDecision(project_id=ids[p.source_ref], decision="defer", mention_id=m.canonical_id,
                           blocked_by="#9", reviewer="t", date="2026-10-05", evidence="recurring survey")
    ds, _ = w.build(tmp_path, decisions=[d])
    r = pm_on(ds, prof).resolution
    assert r.status is S.REVIEW_REQUIRED and r.project_id is None and r.method == "manual:project_deferred"
    assert r.evidence["blocked_by"] == "#9" and "#9" in r.reason
    assert pm_on(ds, prof).candidates[0].project_id == ids[p.source_ref]  # candidate stays visible
    assert not participates(ds, ids[p.source_ref])  # no Project relation is fabricated
    assert not [rel for rel in ds.relations if rel.type.value == "RESOLVES_TO"
                and rel.source_id == m.canonical_id]
    # the review file lists it separately from the open review items
    import yaml

    from szocatlas.resolution.review import write_project_review
    out = tmp_path / "project_review.yaml"
    assert write_project_review(ds, out) == 0
    review = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert review["summary"]["mentions_deferred"] == 1 and review["review_required"] == []
    assert review["deferred"][0]["deferred"]["blocked_by"] == "#9"


def test_defer_never_overrules_a_certain_link(tmp_path, registry):
    w = World(registry)
    page = f"{SZI}/essmagyarorszag"
    w.page(page, "ESS Magyarország")
    prof = f"{PTI}/kutato/szabo-andrea"
    w.profile(prof, "Szabó Andrea", [("ESS Magyarország", page, None, None)])
    ds, ids = w.build(tmp_path)
    m = pm_on(ds, prof)
    assert m.resolution.status is S.DETERMINISTIC
    d = PR.ProjectDecision(project_id=None, decision="defer", mention_id=m.canonical_id, blocked_by="#9")
    ds, _ = w.build(tmp_path, decisions=[d])
    assert pm_on(ds, prof).resolution.status is S.DETERMINISTIC


def test_project_decisions_are_validated_on_load(tmp_path):
    f = tmp_path / "o.yaml"
    for body in ("- {mention_id: pjm_1, decision: defer}",  # no blocked_by
                 "- {mention_id: pjm_1, decision: same_as}",  # no project_id
                 "- {mention_id: pjm_1, project_id: prj_1, decision: maybe}"):
        f.write_text("project_decisions:\n  " + body + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            PR.load_project_decisions(f)
    f.write_text("project_decisions:\n  - {mention_id: pjm_1, decision: defer, blocked_by: '#9'}\n", encoding="utf-8")
    assert PR.load_project_decisions(f)[0].project_id is None


def _rich_world(registry) -> World:
    w = World(registry)
    prof = f"{PTI}/kutato/kopasz-marianna"
    w.page(f"{PTI}/gyermekvedelem-az-iskolaban", "Gyermekvedelem az iskolában: jelzési magatartás",
           people=(("Kopasz Marianna", prof), ("Balogh Karolina", None)))
    w.page(f"{SZI}/eghajlatvaltozas-es-egeszseg", "Éghajlatváltozás és egészség")
    w.page(f"{SZI}/eghajlatvaltozas-es-egeszseg-2021", "Éghajlatváltozás és egészség 2021")
    w.listing(f"{PTI}/futo", f"{PTI}/gyermekvedelem-az-iskolaban", "Gyermekvedelem az iskolában")
    w.profile(prof, "Kopasz Marianna",
              [("OTKA K 143593 - Gyermekvedelem az iskolában: jelzési magatartás – Kutatásvezető", None, None, None),
               ("Éghajlatváltozás és egészség", None, None, None)])
    w.profile(f"{PTI}/kutato/balogh-karolina", "Balogh Karolina",
              [("Gyermekvedelem az iskolában: jelzési magatartás", None, None, None)])
    return w


def test_resolution_is_idempotent_and_order_independent(tmp_path, registry):
    w = _rich_world(registry)
    base, ids = w.build(tmp_path)

    def snapshot(ds):
        return {k: (m.resolution.model_dump(), [c.model_dump() for c in m.candidates])
                for k, m in ds.project_mentions.items()}, sorted(r.relation_id for r in ds.relations)

    for seed in (1, 2, 3):
        ds, again = w.build(tmp_path, shuffle=seed)
        assert again == ids and snapshot(ds) == snapshot(base)


def test_title_edit_does_not_churn_the_project_id(tmp_path, registry):
    w = World(registry)
    p = w.page(f"{SZI}/vakcinacio", "Vakcinációs hajlandóság")
    ident = IdentityMap(tmp_path / "identity_map.jsonl")
    ids, _ = resolve(w.records, w.claims, Overrides(), ident)
    ident.save()
    w2 = World(registry)
    w2.page(f"{SZI}/vakcinacio", "Vakcinációs hajlandóság Magyarországon – 2. hullám")
    ids2, _ = resolve(w2.records, w2.claims, Overrides(), IdentityMap(tmp_path / "identity_map.jsonl"))
    assert ids2[p.source_ref] == ids[p.source_ref]


def test_person_rule_may_use_project_decisions_but_not_the_reverse(tmp_path, registry):
    # Balogh Karolina (common surname) is an unlinked name on the project page; her own
    # profile lists the project under a variant title. The project rule resolves her
    # profile line from the page naming her; the person rule then sees "own profile lists
    # this project" by id. Project rules never read person decisions.
    w = _rich_world(registry)
    ds, ids = w.build(tmp_path)
    pm = pm_on(ds, f"{PTI}/kutato/balogh-karolina")
    assert pm.resolution.method == "title_and_owner" and "PAGE_NAMES_OWNER" in pm.resolution.signals
    (person_m,) = [m for m in ds.mentions.values() if m.stated_name == "Balogh Karolina"]
    assert person_m.resolution.method == "own_profile_project"
    assert person_m.resolution.evidence["project_match"] == "id"
    # the bare Éghajlat title on Kopasz's profile stays ambiguous
    eg = [m for m in ds.project_mentions.values() if m.stated_title == "Éghajlatváltozás és egészség"]
    assert [m.resolution.status for m in eg] == [S.REVIEW_REQUIRED]


def test_qa_rejects_a_title_only_automatic_decision(tmp_path, registry):
    w = _rich_world(registry)
    ds, ids = w.build(tmp_path)
    m = next(m for m in ds.project_mentions.values() if m.resolution.status is S.HIGH_CONFIDENCE_AUTO)
    m.resolution = ProjectMentionResolution(status=S.HIGH_CONFIDENCE_AUTO, project_id=m.resolution.project_id,
                                            method="title_and_owner", signals=["TITLE_EXACT", "SAME_SITE"],
                                            resolver_version="x")
    checks = {f.check: f for f in run_checks(ds, [], None)}
    assert checks["project.title_only_auto"].severity == "error"
    assert m.canonical_id in checks["project.title_only_auto"].subjects
    assert "project.without_evidence" not in checks
    assert all(m.canonical_id == project_mention_id(m.source_ref, m.source_url) for m in ds.project_mentions.values())


# ---------------------------------------------------------------- non-table metadata (moved from #8)
def test_non_table_metadata_is_kept_unattached(tmp_path):
    paths = Paths(tmp_path)
    ingest_fixtures(FIXTURES, paths)
    staged = read_staged(paths, "tk_recens")
    kmetty = "tk_recens|https://recens.tk.elte.hu/kutato/kmetty-zoltan"
    meta = [c for c in staged.claims if c.predicate == "unattached_project_metadata" and c.subject.source_ref == kmetty]
    by_value = {c.value: c.qualifiers for c in meta}
    assert by_value["Kutatásvezető"]["kind"] == "role" and by_value["NKFIH. K147329"]["kind"] == "grant"
    assert all(q["attachment"] == "unresolved" for q in by_value.values())
    # never attached by proximity: no participation claim of Kmetty carries those roles or grants
    roles = {str(c.qualifiers.get("role")) for c in staged.claims
             if c.predicate == "PARTICIPATES_IN" and c.subject.source_ref == kmetty}
    assert "Kutatásvezető" not in roles
    assert not [c for c in staged.claims if c.predicate == "grant_id" and c.evidence.snippet == "NKFIH. K147329"]
