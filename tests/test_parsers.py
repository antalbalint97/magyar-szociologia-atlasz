"""Parser tests against the TK fixtures (reconstructed; see tests/fixtures/tk/README.md)."""

from szocatlas.normalize.urls import canonical_url, mtmt_id
from szocatlas.sources.tk import parser as P

RECENS = "TK Számítógépes Társadalomtudomány - CSS-RECENS"


def test_host_aliases_collapse_historical_hosts(aliases):
    a = canonical_url("http://szociologia.tk.mta.hu/kutato/acsady-judit/", aliases=aliases)
    b = canonical_url("https://szociologia.tk.hu/kutato/acsady-judit", aliases=aliases)
    c = canonical_url("https://szociologia.tk.elte.hu/kutato/acsady-judit", aliases=aliases)
    assert a == b == c == "https://szociologia.tk.elte.hu/kutato/acsady-judit"


def test_mtmt_id_formats():
    assert mtmt_id("https://m2.mtmt.hu/gui2/?type=authors&mode=browse&sel=10031086") == "10031086"
    assert mtmt_id("https://m2.mtmt.hu/gui2/?type=authors&mode=browse&sel=authors10014830") == "10014830"
    assert mtmt_id("https://example.org/?sel=10031086") is None


def test_listing_finds_profiles_positions_and_pagination(fixture_html, aliases):
    page = P.parse_listing(fixture_html("recens_kutatok.html"), "https://recens.tk.elte.hu/kutatok", aliases)
    names = {link.text: pos for link, pos in page.people}
    assert {"Koltai Júlia", "Kmetty Zoltán", "Kisfalusi Dorottya", "Janky Béla"} <= set(names)
    assert names["Kmetty Zoltán"] == "Kutató, Kutatóprofesszor (TK Recens)"
    # relative link resolved against the page
    assert any(link.url == "https://recens.tk.elte.hu/kutato/koltai-julia" for link, _ in page.people)
    assert "https://recens.tk.elte.hu/kutatok?page=2" in page.next_pages
    assert "https://recens.tk.elte.hu/kutatok/k" in page.next_pages


def test_koltai_profile_outside_sociology_institute(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("recens_koltai_julia.html"),
                           "https://recens.tk.elte.hu/kutato/koltai-julia", aliases, RECENS)
    assert prof.name == "Koltai Júlia"
    assert prof.positions == ["Kutatóprofesszor (TK Recens)"]
    assert prof.institute_codes == ["TK Recens"]
    assert prof.unit_lines == []  # the site's own unit is not duplicated as a sub-unit
    assert prof.mtmt_id == "10031086"
    assert prof.cv_url == "https://recens.tk.elte.hu/kutato/pdf/285"
    assert "PhD" in prof.titles
    titles = [p.title for p in prof.projects]
    assert any("Lendület" in t for t in titles)


def test_contact_details_never_extracted(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("szi_albert_fruzsina.html"),
                           "https://szociologia.tk.elte.hu/kutato/albert-fruzsina", aliases,
                           "TK Szociológiai Intézet")
    blob = repr(prof)
    assert "+36" not in blob and "Szoba" not in blob and "Épület" not in blob
    assert prof.email_domain == "tk.elte.hu"  # domain only, never the local part
    assert not any("linkedin" in u for u in prof.other_profiles)


def test_profile_units_bio_and_projects(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("szi_albert_fruzsina.html"),
                           "https://szociologia.tk.elte.hu/kutato/albert-fruzsina", aliases,
                           "TK Szociológiai Intézet")
    assert prof.unit_lines == ["Család és Társas Kapcsolatok Kutatási Osztály"]
    assert prof.biography.startswith("Albert Fruzsina, PhD. habil.")
    # historical hosts in project links are canonicalised
    assert all(p.url is None or ".tk.mta.hu" not in p.url for p in prof.projects)


def test_research_areas_and_explicit_project_periods(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("ki_feischmidt_margit.html"),
                           "https://kisebbsegkutato.tk.elte.hu/kutato/feischmidt-margit", aliases,
                           "TK Kisebbségkutató Intézet")
    assert len(prof.research_areas) == 7
    assert "Romák és magyar kisebbségi közösségek Közép- és Kelet-Európában" in prof.research_areas
    p = next(p for p in prof.projects if p.title.startswith("Az ukrajnai"))
    assert (p.period_from, p.period_until) == ("2022", None)  # open-ended, not invented
    assert prof.unit_lines == ["Kisebbségszociológiai és Antropológiai Osztály"]


def test_unit_page_leader_and_members(fixture_html, aliases):
    unit = P.parse_unit(fixture_html("szi_unit_csalad.html"),
                        "https://szociologia.tk.elte.hu/csalad-es-tarsas-kapcsolatok", aliases)
    assert unit.name == "Család és Társas Kapcsolatok Kutatási Osztály"
    assert [(lk.text, label) for lk, label in unit.leaders] == [("Szalma Ivett", "Osztályvezető")]
    assert len(unit.members) == 10
    assert all(m.url.startswith("https://szociologia.tk.elte.hu/kutato/") for m in unit.members)


def test_project_page_fields(fixture_html, aliases):
    proj = P.parse_project(fixture_html("szi_project_energiaatmenet.html"),
                           "https://szociologia.tk.elte.hu/az-energiaatmenet-terbeli-tarsadalmi-egyenlotlensegei",
                           aliases)
    assert proj.grant_id == "NKFIH 146987" and proj.funder == "NKFIH"
    assert (proj.start, proj.end) == ("2024-01-01", "2027-12-31")
    assert [lk.text for lk in proj.leads] == ["Kőszeghy Lea"]
    assert [lk.text for lk in proj.participants] == ["Csurgó Bernadett", "Horzsa Gergely"]
    assert proj.unlinked_participants == [("Bajomi Anna Zsófia", "Külső szakértő")]


def test_parse_period_variants():
    assert P.parse_period("2024.01.01-2027.12.31") == ("2024-01-01", "2027-12-31")
    assert P.parse_period("2019–2023") == ("2019", "2023")
    assert P.parse_period("2022-") == ("2022", None)
    assert P.parse_period("folyamatban") == (None, None)
