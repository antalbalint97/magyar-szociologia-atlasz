"""Parser tests against real TK page snapshots (contact details scrubbed; see tests/fixtures/tk/README.md)."""

from szocatlas.normalize.urls import canonical_url, mtmt_id
from szocatlas.scrub import scrub_html
from szocatlas.sources.tk import parser as P

RECENS = "TK Számítógépes Társadalomtudomány - CSS-RECENS"
SZI = "TK Szociológiai Intézet"


def test_host_aliases_collapse_historical_hosts(aliases):
    a = canonical_url("http://szociologia.tk.mta.hu/kutato/acsady-judit/", aliases=aliases)
    b = canonical_url("https://szociologia.tk.hu/kutato/acsady-judit", aliases=aliases)
    c = canonical_url("https://szociologia.tk.elte.hu/kutato/acsady-judit", aliases=aliases)
    assert a == b == c == "https://szociologia.tk.elte.hu/kutato/acsady-judit"


def test_mtmt_id_formats():
    assert mtmt_id("https://m2.mtmt.hu/gui2/?type=authors&mode=browse&sel=10031086") == "10031086"
    assert mtmt_id("https://m2.mtmt.hu/gui2/?type=authors&mode=browse&sel=authors10014830") == "10014830"
    assert mtmt_id("https://m2.mtmt.hu/api/author/10049910") == "10049910"
    assert mtmt_id("https://example.org/?sel=10031086") is None


def test_listing_finds_profiles_positions_and_pagination(fixture_html, aliases):
    page = P.parse_listing(fixture_html("recens_kutatok.html"), "https://recens.tk.elte.hu/kutatok", aliases)
    names = {link.text: pos for link, pos in page.people}
    assert len(names) == 10
    assert "" not in names  # photo links carry no name and are skipped
    assert names["Bocskor Ákos"] == "Kutató, Tudományos munkatárs (TK Recens)"
    assert names["Freigang István"] == "Kutatási asszisztens (TK Recens)"
    assert "https://recens.tk.elte.hu/kutatok?page=2" in page.next_pages
    assert "https://recens.tk.elte.hu/kutatok/k" in page.next_pages


def test_letter_listing_has_koltai(fixture_html, aliases):
    page = P.parse_listing(fixture_html("recens_kutatok_k.html"), "https://recens.tk.elte.hu/kutatok/k", aliases)
    names = {link.text: pos for link, pos in page.people}
    assert names["Koltai Júlia"] == "Kutató, Kutatóprofesszor (TK Recens)"
    assert names["Kmetty Zoltán"] == "Kutató, Kutatóprofesszor (TK Recens)"


def test_koltai_profile_outside_sociology_institute(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("recens_koltai_julia.html"),
                           "https://recens.tk.elte.hu/kutato/koltai-julia", aliases, RECENS)
    assert prof.name == "Koltai Júlia"
    assert prof.staff_category == "Kutató"
    assert prof.positions == ["Kutatóprofesszor (TK Recens)"]
    assert prof.institute_codes == ["TK Recens"]
    assert prof.unit_lines == []
    assert prof.mtmt_id == "10031086"
    assert prof.cv_url == "https://recens.tk.elte.hu/kutato/pdf/285"
    assert prof.titles == ["PhD"]
    # "<b>2022-2027 vezető kutató</b>" + description paragraph -> one dated mention
    lendulet = prof.projects[0]
    assert lendulet.title == "Társadalmi struktúra és egyenlőtlenség a digitális adatok tükrében"
    assert (lendulet.period_from, lendulet.period_until, lendulet.role) == ("2022", "2027", "vezető kutató")
    assert len(prof.projects) == 5


def test_category_only_position(fixture_html, aliases):
    """'<h4>Kutatási asszisztens</h4> (TK Recens)': the category is the stated position."""
    prof = P.parse_profile(fixture_html("recens_freigang_istvan.html"),
                           "https://recens.tk.elte.hu/kutato/freigang-istvan", aliases, RECENS)
    assert prof.positions == ["Kutatási asszisztens (TK Recens)"]
    assert prof.unit_lines == []  # "(TK Recens)" is an institute code, not a unit


def test_contact_details_never_extracted(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("szi_albert_fruzsina.html"),
                           "https://szociologia.tk.elte.hu/kutato/albert-fruzsina", aliases, SZI)
    blob = repr(prof)
    assert "XXX" not in blob and "Épület" not in blob and "Telefon" not in blob
    assert prof.email_domain == "tk.elte.hu"  # domain only, never the local part
    assert not any("linkedin" in u for u in prof.other_profiles)
    assert prof.other_profiles == ["https://sote.academia.edu/FruzsinaAlbert"]


def test_scrub_removes_contact_details():
    html = ('<ul><li><b>E-mail:</b> <a href="mailto:kiss.anna@tk.elte.hu">kiss.anna@tk.elte.hu</a></li>'
            '<li><b>Telefonszám:</b> +36 1 224 6700 / 5434</li><li><b>Épület:</b> B (szoba 1.30)</li></ul>'
            '<script>gtm()</script>')
    out = scrub_html(html)
    assert "kiss.anna" not in out and "6700" not in out and "1.30" not in out and "gtm" not in out
    assert "xxx@tk.elte.hu" in out


def test_profile_units_bio_and_project_roles(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("szi_albert_fruzsina.html"),
                           "https://szociologia.tk.elte.hu/kutato/albert-fruzsina", aliases, SZI)
    assert prof.unit_lines == ["Család és Társas Kapcsolatok Kutatási Osztály"]
    assert prof.positions == ["Kutatóprofesszor (TK SZI)"]
    # the narrative under "Kutatási területek" is a bio, not a list of areas
    assert prof.biography.startswith("Albert Fruzsina, PhD. habil.")
    assert prof.research_areas == []
    # page footer links are not projects
    assert len(prof.projects) == 3
    own, other, unlinked = prof.projects
    assert own.role == "Kutatásvezető" and own.stated_lead is None
    assert other.role is None and other.stated_lead == "Kovách Imre"
    assert unlinked.url is None and unlinked.title == "Egészségbiztonság Nemzeti labor"
    # historical hosts in project links are canonicalised
    assert all(p.url is None or ".tk.hu/" not in p.url for p in prof.projects)


def test_research_areas_and_explicit_project_periods(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("ki_feischmidt_margit.html"),
                           "https://kisebbsegkutato.tk.elte.hu/kutato/feischmidt-margit", aliases,
                           "TK Kisebbségkutató Intézet")
    assert len(prof.research_areas) == 7
    assert "Etnicitás, interetnikus kapcsolatok" in prof.research_areas  # <li> items are not comma-split
    p = next(p for p in prof.projects if p.title.startswith("Az ukrajnai"))
    assert (p.period_from, p.period_until) == ("2022", None)  # open-ended, not invented
    assert prof.unit_lines == ["Kisebbségszociológiai és Antropológiai Osztály"]


def test_comma_separated_areas_and_leading_periods(fixture_html, aliases):
    prof = P.parse_profile(fixture_html("pti_adam_zoltan.html"),
                           "https://politikatudomany.tk.elte.hu/kutato/adam-zoltan", aliases,
                           "TK Politikatudományi Intézet")
    assert prof.research_areas == ["politikai gazdaságtan", "intézményi gazdaságtan", "közpolitika formálás"]
    assert prof.mtmt_id == "10049910"  # /api/author/<id> form
    assert [(p.period_from, p.period_until) for p in prof.projects] == [("2024", None), ("2023", "2027")]
    assert prof.projects[0].title.startswith("Külföldi és hazai gazdasági szereplők")


def test_unit_page_leader_and_members(fixture_html, aliases):
    unit = P.parse_unit(fixture_html("szi_unit_csalad.html"),
                        "https://szociologia.tk.elte.hu/csalad-es-tarsas-kapcsolatok", aliases)
    assert unit.name == "Család és Társas Kapcsolatok Kutatási Osztály"
    assert [(lk.text, label) for lk, label in unit.leaders] == [("Szalma Ivett", "Osztályvezető")]
    assert len(unit.members) == 10
    assert all(m.url.startswith("https://szociologia.tk.elte.hu/kutato/") for m in unit.members)


def test_unit_leader_named_on_the_line_after_the_link(fixture_html, aliases):
    unit = P.parse_unit(fixture_html("ki_unit_kisebbsegszociologia.html"),
                        "https://kisebbsegkutato.tk.elte.hu/kisebbsegszociologiai-es-antropologiai-osztaly",
                        aliases)
    assert [(lk.text, label) for lk, label in unit.leaders] == [("Zakariás Ildikó", "Osztályvezető")]
    assert len(unit.members) == 13


def test_project_page_fields(fixture_html, aliases):
    proj = P.parse_project(fixture_html("szi_project_energiaatmenet.html"),
                           "https://szociologia.tk.elte.hu/az-energiaatmenet-terbeli-tarsadalmi-egyenlotlensegei",
                           aliases)
    assert proj.grant_id == "NKFIH 146987" and proj.funder == "NKFIH"
    assert (proj.start, proj.end) == ("2024-01-01", "2027-12-31")
    assert [lk.text for lk in proj.leads] == ["Kőszeghy Lea"]
    assert [lk.text for lk in proj.participants] == ["Csurgó Bernadett", "Horzsa Gergely"]
    assert proj.unlinked_participants == [("Bajomi Anna Zsófia", "külső szakértő")]


def test_project_page_br_separated_header(fixture_html, aliases):
    """'MTA<br>2022 - 2024<br>Kutatásvezető: Albert Fruzsina (TK SZI)' on one <p>."""
    proj = P.parse_project(fixture_html("szi_project_vakcinacio.html"),
                           "https://szociologia.tk.elte.hu/a-vakcinacios-szandek-megertese", aliases)
    assert (proj.funder, proj.funder_labelled) == ("MTA", False)
    assert (proj.start, proj.end) == ("2022", "2024")
    assert proj.leads == []
    assert [n for n, _ in proj.unlinked_leads] == ["Albert Fruzsina"]  # affiliation suffix dropped
    assert proj.description.startswith("A Magyar Tudományos Akadémia Poszt-COVID")


def test_project_listing_articles(fixture_html, aliases):
    projects = P.parse_project_listing(fixture_html("szi_futo_kutatasok.html"),
                                       "https://szociologia.tk.elte.hu/kategoria/futo-kutatasok", aliases)
    assert len(projects) == 10
    by_title = {p.title: p for p in projects}
    zs = by_title["Zsidó diaszpóra háború idején"]
    assert (zs.start, zs.end) == ("2024", "2025")
    assert [lk.text for lk in zs.leads] == ["Gerő Márton"]
    assert zs.unlinked_participants == [("Surányi Ráchel", "Kutatás résztvevői"), ("Félix Anikó", "Kutatás résztvevői")]
    so = next(p for p in projects if p.title.startswith("SoGreen"))
    assert [lk.text for lk in so.leads] == ["Messing Vera"]
    assert [n for n, _ in so.unlinked_leads] == ["Ságvári Bence"]  # second lead has no link
    # a free-text article without labelled lines yields no people
    ensz = by_title["Magyarország és az ENSZ"]
    assert ensz.leads == [] and ensz.unlinked_leads == [] and ensz.unlinked_participants == []


def test_parse_period_variants():
    assert P.parse_period("2024.01.01-2027.12.31") == ("2024-01-01", "2027-12-31")
    assert P.parse_period("2019–2023") == ("2019", "2023")
    assert P.parse_period("2022-") == ("2022", None)
    assert P.parse_period("folyamatban") == (None, None)
