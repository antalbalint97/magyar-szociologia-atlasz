"""Source discovery from profile project links (#16, ADR-0009).

The scenario is a real KI profile (Eiler Ferenc, observed 2026-10-04) whose "Projektek" section links four KI
project pages, one of them through the historical host ``kisebbsegkutato.tk.hu``, plus the project page of one of
them (observed 2026-10-05). Pages without a fixture behave like pages that cannot be fetched.
"""

import json
from datetime import UTC, datetime

import pytest

from szocatlas import discovery as D
from szocatlas.fetch import FixtureFetcher
from szocatlas.models.enums import SourceType
from szocatlas.pipeline import build, write_staged
from szocatlas.registry import REPO_ROOT, load_registry
from szocatlas.sources.base import LinkedProject, ParseResult
from szocatlas.sources.tk.adapter import TKAdapter

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tk"
OBSERVED = datetime(2026, 10, 5, tzinfo=UTC)
KI_ID = "tk_kisebbsegkutato"
KI = "https://kisebbsegkutato.tk.elte.hu/"
EILER = KI + "kutato/eiler-ferenc"
PARLAMENTI = KI + "a-kisebbsegek-parlamenti-kepviselete-osszehasonlitasban"
# the other project links of the same profile section
OTHER_LINKS = [KI + "a-magyarorszagi-nemet-szervezetek", KI + "a-bevandorlas-kerdesenek-helye",
               KI + "etnicitas-helyi-tarsadalom-es-hatalom-egy-magyarorszagi"]


class Recorder(FixtureFetcher):
    """A fixture fetcher that remembers what was asked for."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.asked: list[str] = []

    def get(self, url, **kw):
        self.asked.append(url)
        return super().get(url, **kw)


def ki_adapter(registry, project_fixtures=None, *, follow=True):
    registry = load_registry() if not follow else registry
    if not follow:
        registry.source(KI_ID).adapter_config["follow_profile_project_links"] = False
    mapping = {EILER: FIXTURES / "ki_eiler_ferenc.html"}
    mapping |= {url: FIXTURES / name for url, name in (project_fixtures or {}).items()}
    fetcher = Recorder(mapping, registry.host_aliases(), OBSERVED)
    adapter = TKAdapter(registry.source(KI_ID), registry, fetcher)
    page = fetcher.get(EILER, source_id=KI_ID, source_type=SourceType.INSTITUTIONAL_PROFILE)
    res = adapter.parse_person(page)
    res.documents.append(page.document)
    fetcher.asked.clear()
    return adapter, res, fetcher


def frontier_row(res, url):
    return next(r for r in res.frontier if r["url"] == url)


def test_project_section_links_are_collected_with_the_link_as_written(registry):
    adapter, _, _ = ki_adapter(registry)
    urls = {lp.url: lp for lp in adapter.linked_projects}
    assert set(urls) == {PARLAMENTI, *OTHER_LINKS}
    # one of them was written with the historical host; the canonical URL is the alias-normalised one
    assert urls[PARLAMENTI].stated_url == "https://kisebbsegkutato.tk.hu/a-kisebbsegek-parlamenti-kepviselete-osszehasonlitasban"
    assert urls[PARLAMENTI].title.startswith("A kisebbségek parlamenti képviselete")
    assert urls[PARLAMENTI].profile_url == EILER


def test_only_links_in_the_project_section_are_candidates(registry):
    """The profile has many other links (navigation, units, people); none of them is a candidate."""
    adapter, res, _ = ki_adapter(registry)
    html = (FIXTURES / "ki_eiler_ferenc.html").read_text(encoding="utf-8")
    assert html.count("<a ") > len(adapter.linked_projects) + 5
    assert all("/kutato/" not in lp.url for lp in adapter.linked_projects)
    assert len(adapter.linked_projects) == len({lp.url for lp in adapter.linked_projects}) == 4


def test_a_linked_same_host_page_is_enqueued_fetched_and_parsed(registry):
    adapter, res, fetcher = ki_adapter(registry, {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    counts = D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    assert counts["enqueued"] == 4  # the three without a fixture are attempted too, and fail
    row = frontier_row(res, PARLAMENTI)
    assert (row["decision"], row["scope"], row["owner_source"], row["reason"]) == ("enqueued", "in_scope", KI_ID, None)
    assert row["fetch"]["attempted"] and row["fetch"]["http_status"] == 200 and row["fetch"]["error"] is None
    assert row["fetch"]["redirected"] is False
    # the page went through the ordinary project-page parser
    doc = next(d for d in res.documents if d.canonical_url == PARLAMENTI)
    assert doc.source_type is SourceType.PROJECT_PAGE and row["fetch"]["document_id"] == doc.document_id
    assert any(c.predicate == "funding_body" and c.value == "NKFIH" for c in res.claims)
    assert any(r.identity_anchor == "project_page" and r.ref.source_ref == f"{KI_ID}|{PARLAMENTI}" for r in res.records)
    assert any(d["page_type"] == "project" and d["document_id"] == doc.document_id for d in res.diagnostics)


def test_frontier_rows_record_why_each_url_entered_the_frontier(registry):
    adapter, res, _ = ki_adapter(registry, {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    row = frontier_row(res, PARLAMENTI)
    via = row["discovered_via"]
    assert len(via) == 1
    profile_doc = next(d for d in res.documents if d.canonical_url == EILER)
    assert via[0]["type"] == "profile_project_link" and row["kind"] == "profile_project_link"
    assert via[0]["source_document"] == profile_doc.document_id and via[0]["source_url"] == EILER
    assert via[0]["project_ref"].startswith(f"{KI_ID}|") and via[0]["title"].startswith("A kisebbségek parlamenti")
    # the host the researcher wrote is on record, with the registry's verdict about it
    assert row["stated_urls"] == ["https://kisebbsegkutato.tk.hu/a-kisebbsegek-parlamenti-kepviselete-osszehasonlitasban"]
    assert row["host_status"] in ("canonical", "verified")


def test_a_page_that_cannot_be_fetched_is_recorded_and_not_invented(registry):
    adapter, res, _ = ki_adapter(registry)
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    row = frontier_row(res, OTHER_LINKS[0])
    assert row["decision"] == "enqueued" and row["fetch"]["attempted"] is True
    assert row["fetch"]["error"] and "document_id" not in row["fetch"]
    assert not any(d.canonical_url == OTHER_LINKS[0] for d in res.documents)
    assert {"url": OTHER_LINKS[0], "error": "not fetched"} in res.errors


def test_discovery_is_one_hop(registry):
    adapter, res, fetcher = ki_adapter(registry, {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    # exactly the four candidates were asked for; the fetched page's own links were not followed
    assert sorted(fetcher.asked) == sorted([PARLAMENTI, *OTHER_LINKS])
    assert len(adapter.linked_projects) == 4


def test_a_page_the_crawl_already_has_is_not_fetched_again(registry):
    adapter, res, fetcher = ki_adapter(registry, {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    page = fetcher.get(PARLAMENTI, source_id=KI_ID, source_type=SourceType.PROJECT_PAGE)
    res.documents.append(page.document)  # e.g. found by a category listing
    fetcher.asked.clear()
    counts = D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    assert counts["already_discovered"] == 1
    row = frontier_row(res, PARLAMENTI)
    assert row["decision"] == "already_discovered" and row["fetch"] == {"attempted": False}
    assert PARLAMENTI not in fetcher.asked  # discovery did not ask for it again


def test_the_same_link_on_two_profiles_is_one_frontier_url(registry):
    adapter, res, fetcher = ki_adapter(registry, {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    second = LinkedProject(url=PARLAMENTI, stated_url=PARLAMENTI, title="A kisebbségek parlamenti képviselete",
                           source_id=KI_ID, profile_url=KI + "kutato/someone-else", document_id="doc_x",
                           project_ref=f"{KI_ID}|{PARLAMENTI}")
    adapter.linked_projects.append(second)
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    assert fetcher.asked.count(PARLAMENTI) == 1
    merged = D.merge_frontier(res.frontier)
    assert len([r for r in merged if r["url"] == PARLAMENTI]) == 1
    row = next(r for r in merged if r["url"] == PARLAMENTI)
    assert [v["source_url"] for v in row["discovered_via"]] == [EILER, KI + "kutato/someone-else"]


@pytest.mark.parametrize("url,scope,reason", [
    # an external site: never fetched, whatever the profile says
    ("https://mores-horizon.eu/", "external", "external_host"),
    ("https://cordis.europa.eu/project/id/101060836", "external", "external_host"),
    # a site of the same institution that is not in the registry
    ("https://cap.tk.mta.hu/", "other_unit_site", "site_not_registered"),
    # a registered source that is switched off
    ("https://reprosoc.tk.hu/", "other_unit_site", "source_not_enabled"),
    ("https://jog.tk.elte.hu/a-nemzetiseg-es-etnicitas-jogi-operacionalizalasa", "other_unit_site", "source_not_enabled"),
    # a public grant record states a grant; it is not a project page
    ("https://nyilvanos.otka-palyazat.hu/index.php?lang=HU&menuid=930&num=142410", "grant_registry",
     "grant_registry_link"),
])
def test_the_registry_decides_which_hosts_may_be_fetched(registry, url, scope, reason):
    adapter, res, fetcher = ki_adapter(registry)
    adapter.linked_projects[:] = [LinkedProject(
        url=url, stated_url=url, title="x", source_id=KI_ID, profile_url=EILER, document_id="doc_x",
        project_ref=f"{KI_ID}|x")]
    counts = D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    row = frontier_row(res, url)
    assert (row["decision"], row["scope"], row["reason"]) == ("skipped", scope, reason)
    assert row["fetch"] == {"attempted": False}
    assert fetcher.asked == []  # no request was made
    assert counts == {f"skipped:{reason}": 1}
    assert not any(d.canonical_url == url for d in res.documents)


@pytest.mark.parametrize("path,reason", [
    ("kutato/someone", "not_project_path"),  # a profile
    ("hirek/2020/04/valami", "not_project_path"),  # a news item
    ("kategoria/futo-kutatasok", "not_project_path"),
    ("kisebbsegszociologiai-es-antropologiai-osztaly", "unit_page"),  # a department, not a project
    ("a-projekt?page=2", "not_project_path"),
])
def test_only_the_path_shape_of_a_project_page_is_followed(registry, path, reason):
    adapter, res, fetcher = ki_adapter(registry)
    adapter.linked_projects[:] = [LinkedProject(
        url=KI + path, stated_url=KI + path, title="x", source_id=KI_ID, profile_url=EILER,
        document_id="doc_x", project_ref=f"{KI_ID}|x")]
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    row = frontier_row(res, KI + path)
    assert (row["decision"], row["reason"], row["scope"]) == ("skipped", reason, "in_scope")
    assert fetcher.asked == []


def test_an_inferred_alias_host_is_not_fetched(registry):
    """A host that is only an inferred alias of the canonical one was never verified to map paths one to one."""
    assert registry.alias_status("kisebbsegkutato.tk.hun-ren.hu") == "inferred"
    url = "https://kisebbsegkutato.tk.hun-ren.hu/a-projekt"
    adapter, res, fetcher = ki_adapter(registry)
    adapter.linked_projects[:] = [LinkedProject(
        url=KI + "a-projekt", stated_url=url, title="x", source_id=KI_ID, profile_url=EILER,
        document_id="doc_x", project_ref=f"{KI_ID}|x")]
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    row = frontier_row(res, KI + "a-projekt")
    assert (row["decision"], row["reason"], row["host_status"]) == ("skipped", "alias_unverified", "inferred")
    assert fetcher.asked == []


def test_sources_opt_in_to_following_profile_links(registry):
    adapter, res, _ = ki_adapter(registry, follow=False)
    assert adapter.linked_projects == []
    assert D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry) == {}
    assert res.frontier == []


# ------------------------------------------------------------------------------- the effect on the release
def ingest_and_build(workdir, registry, release, project_fixtures):
    adapter, res, _ = ki_adapter(registry, project_fixtures)
    if project_fixtures is not None:
        D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    write_staged(workdir, KI_ID, res)
    out, findings = build(release, paths=workdir, registry_path=workdir.config / "sources.yaml")
    return out, findings


def load(out, name):
    return [json.loads(x) for x in (out / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def mention_for(out, url):
    return next(m for m in load(out, "entities/ProjectMention.jsonl") if m["linked_url"] == url)


def test_linked_page_becomes_a_project_and_the_mention_resolves_by_url(workdir, registry):
    before, _ = ingest_and_build(workdir, registry, "before", None)
    after, findings = ingest_and_build(workdir, registry, "after", {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    m0, m1 = mention_for(before, PARLAMENTI), mention_for(after, PARLAMENTI)
    assert m0["resolution"]["status"] == "UNRESOLVED" and m0["resolution"]["project_id"] is None
    assert m1["resolution"]["status"] == "DETERMINISTIC" and m1["resolution"]["method"] == "project_url"
    assert "PROJECT_URL_EXACT" in m1["resolution"]["signals"]
    project = next(p for p in load(after, "entities/Project.jsonl") if p["canonical_id"] == m1["resolution"]["project_id"])
    assert project["website"] == PARLAMENTI and project["identity_evidence"] == ["project_page"]
    # no title matching was used to get there: the other three links stay unresolved
    for url in OTHER_LINKS:
        assert mention_for(after, url)["resolution"]["status"] == "UNRESOLVED"
    assert [f for f in findings if f.severity == "error"] == []


def test_unresolved_link_reasons_come_from_the_frontier_not_from_the_url(workdir, registry):
    before, _ = ingest_and_build(workdir, registry, "before", None)
    after, _ = ingest_and_build(workdir, registry, "after", {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    assert "not on the crawl frontier" in mention_for(before, OTHER_LINKS[0])["resolution"]["reason"]
    reason = mention_for(after, OTHER_LINKS[0])["resolution"]["reason"]
    assert "fetch failed" in reason and "no fixture" in reason  # what the fetch returned


def test_release_carries_the_frontier_with_provenance(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    frontier = load(out, "frontier.jsonl")
    assert len(frontier) == 4
    row = next(r for r in frontier if r["url"] == PARLAMENTI)
    assert row["discovered_via"][0]["type"] == "profile_project_link"
    docs = {d["document_id"] for d in load(out, "documents.jsonl")}
    assert row["discovered_via"][0]["source_document"] in docs and row["fetch"]["document_id"] in docs


def test_release_metadata_makes_the_source_set_difference_visible(workdir, registry):
    before, _ = ingest_and_build(workdir, registry, "before", None)
    after, _ = ingest_and_build(workdir, registry, "after", {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    s0 = json.loads((before / "manifest.json").read_text())["source_set"]
    s1 = json.loads((after / "manifest.json").read_text())["source_set"]
    assert s1["documents"] == s0["documents"] + 1
    assert s0["digest"] != s1["digest"]
    assert s1["by_source"][KI_ID]["by_page_type"]["project"] == s0["by_source"][KI_ID]["by_page_type"].get("project", 0) + 1
    assert s1["by_page_type"]["project"] == 1


def test_rebuild_is_byte_identical(workdir, registry):
    adapter, res, _ = ki_adapter(registry, {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    D.follow_profile_project_links({KI_ID: adapter}, {KI_ID: res}, registry)
    write_staged(workdir, KI_ID, res)
    a, _ = build("a", paths=workdir, registry_path=workdir.config / "sources.yaml")
    b, _ = build("b", paths=workdir, registry_path=workdir.config / "sources.yaml")
    for name in ("frontier.jsonl", "parse_report.jsonl", "coverage.json", "entities/Project.jsonl",
                 "entities/ProjectMention.jsonl", "relations.jsonl"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    # the one place the release id appears
    assert (a / "coverage.md").read_text().replace("report: a", "report: b") == (b / "coverage.md").read_text()


def test_empty_result_helpers():
    res = ParseResult()
    assert D.merge_frontier(res.frontier) == []
