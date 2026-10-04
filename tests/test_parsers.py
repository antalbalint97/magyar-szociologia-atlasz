"""Parser tests against real TK page snapshots (contact details scrubbed; see tests/fixtures/tk/README.md)."""

from bs4 import BeautifulSoup

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


def test_name_split_across_two_links_is_repaired():
    # observed on the SZI "Társadalom- és Közpolitika" unit page (2026-10-04)
    html = ('<td><a href="https://szociologia.tk.mta.hu/kutato/messing-vera">S</a>\n'
            '<a href="https://szociologia.tk.hu/kutato/szikra-dorottya">zikra Dorottya</a></td>')
    links = P._links(P.soup_of(html), "https://szociologia.tk.elte.hu/", {})
    assert [(lk.url.rsplit("/", 1)[1], lk.text) for lk in links] == [("szikra-dorottya", "Szikra Dorottya")]


# --- #8: metadata lines in a profile's "Projektek" section are never projects ---------

PTI = "TK Politikatudományi Intézet"
KI = "TK Kisebbségkutató Intézet"


def _projects(fixture_html, aliases, name, url, unit):
    prof = P.parse_profile(fixture_html(name), url, aliases, unit)
    return prof, {pm.title: pm for pm in prof.projects}


def test_section_headings_are_not_projects(fixture_html, aliases):
    prof, by_title = _projects(fixture_html, aliases, "ki_eiler_ferenc.html",
                               "https://kisebbsegkutato.tk.elte.hu/kutato/eiler-ferenc", KI)
    assert "Aktuális kutatások:" not in by_title and "Lezárt kutatások:" not in by_title
    assert prof.rejected_project_lines == ["Aktuális kutatások:", "Lezárt kutatások:"]
    assert len(prof.projects) == 5
    assert "Németek, helyi társadalom és hatalom (Harta, 1920–1989)" in by_title  # a year range inside a title stays


def test_role_grant_and_funder_lines_are_not_projects(fixture_html, aliases):
    # "2024-2026 <a>Title</a>" / "NKFIH. K147329" / "Kutatásvezető" per project
    prof, by_title = _projects(fixture_html, aliases, "recens_kmetty_zoltan.html",
                               "https://recens.tk.elte.hu/kutato/kmetty-zoltan", RECENS)
    for junk in ("Kutatásvezető", "Kutató", "Szenior Kutató", "Projekt koordinátor", "Vezető kutató, WP vezető",
                 "NKFIH. K147329", "H2020. G-ID: 785125", "TÁMOP 5.4.1-12", "Magyar Tudományos Akadémia"):
        assert junk not in by_title
        assert junk in prof.rejected_project_lines
    # real projects with periods, acronyms and grant vocabulary are kept
    assert by_title["NATCONSUMERS"].period_from == "2015"
    assert by_title["Digitális politikai lábnyomok"].period_until == "2026"
    assert "ISSP – Hálózatok és erőforrások" in by_title
    # uncertain activities stay for activity classification (#9)
    assert "ELKH Zászlóshajó projekt" in by_title and "MTA Kutatócsoport" in by_title
    assert len(prof.projects) == 16


def test_initial_linked_elsewhere_is_joined_to_the_title(fixture_html, aliases):
    _, by_title = _projects(fixture_html, aliases, "recens_kmetty_zoltan.html",
                            "https://recens.tk.elte.hu/kutato/kmetty-zoltan", RECENS)
    pm = by_title["Donáció alapú digitális adatgyűjtés"]
    assert pm.url == "https://recens.tk.elte.hu/donacio-alapu-digitalis-adatgyujtes"
    assert "D" not in by_title


def test_table_header_row_and_cells_are_not_projects(fixture_html, aliases):
    # columns: Cím / téma | Intézmény | Időtartam
    prof, by_title = _projects(fixture_html, aliases, "pti_hajnal_gyorgy.html",
                               "https://politikatudomany.tk.elte.hu/kutato/hajnal-gyorgy", PTI)
    for junk in ("Cím / téma", "Intézmény", "Időtartam", "2005-2009", "Magyar Közigazgatási Intézet"):
        assert junk not in by_title
    assert len(prof.projects) == 7
    pm = by_title["“Közpolitikai kudarcok Magyarországon” – ROP3.1.1"]
    assert (pm.period_from, pm.period_until, pm.role) == ("2005", "2009", "kutatásvezető")
    assert "Magyar Közigazgatási Intézet (kutatásvezető)" in pm.snippet


def test_table_grant_and_role_cells_qualify_the_title(fixture_html, aliases):
    # columns: grant | funder – role | title
    prof, by_title = _projects(fixture_html, aliases, "pti_szabo_andrea.html",
                               "https://politikatudomany.tk.elte.hu/kutato/szabo-andrea", PTI)
    for junk in ("119603 jelű", "kutatásvezető", "vezető kutató", "K–OTKA –résztvevő kutató"):
        assert junk not in by_title
    pm = by_title["Részvétel, képviselet, pártosság. Választáskutatás, 2018."]
    assert (pm.grant_id, pm.role) == ("119603 jelű", "kutatásvezető")
    assert by_title["ESS Magyarország"].role == "résztvevő kutató"
    assert len(prof.projects) == 8


def test_table_period_cell_before_the_title(fixture_html, aliases):
    prof, by_title = _projects(fixture_html, aliases, "szi_szalai_julia.html",
                               "https://szociologia.tk.elte.hu/kutato/szalai-julia", SZI)
    assert not any(P.PERIOD_LINE_RE.match(t) for t in by_title)
    assert len(prof.projects) == 5
    assert {(pm.period_from, pm.period_until) for pm in prof.projects} >= {("2002", "2004"), ("2003", None)}


def test_link_whose_text_is_a_url_is_not_a_title(fixture_html, aliases):
    prof, _ = _projects(fixture_html, aliases, "szi_csizmady_adrienne.html",
                        "https://szociologia.tk.elte.hu/kutato/csizmady-adrienne", SZI)
    titles = [pm.title for pm in prof.projects]
    assert "https://tinlab.hu/" not in titles and "" not in titles
    first = prof.projects[0]
    assert first.title.startswith("Techceptance") and "https://" not in first.title
    assert first.url is None and first.role == "kutatásvezető"


def test_is_project_metadata_is_conservative():
    meta = ["Korábbi projektek:", "Futó projektek:", "Projektek", "Kutatásvezető", "Projektvezető",
            "Kutatás résztvevői", "Résztvevők", "2022-2024", "2022–2024", "2024", "2021-",
            "NKFIH. K147329", "119603 jelű", "OTKA PD kutatás – kutatásvezető",
            # singular and stacked section labels, chapter-author link text (seen in release 2026-10-tk)
            "Futó kutatási projekt:", "Lezárult kutatási projekt:", "Jelenleg futó projektek", "Fejezetszerző"]
    titles = ["NATCONSUMERS", "Magyar Ifjúság 2016", "ESS Magyarország", "ELKH Zászlóshajó projekt",
              "NKFIH K 124384 Rétegződés és mobilitás", "OTKA – „A magyar központi közigazgatás”",
              "Választáskutatás, 2018.", "MTA Kutatócsoport", "Krízis és Innováció", "ISSP 2017",
              "Comparative Agendas Project", "Adaptációs mechanizmusok", "Kutatási projektek értékelése"]
    assert [t for t in meta if not P.is_project_metadata(t)] == []
    assert [t for t in titles if P.is_project_metadata(t)] == []


def test_person_links_keep_the_url_as_written(aliases):
    # #5: identity rules must know whether a link reached the canonical host only through an alias
    html = ('<div><a href="https://politikatudomany.tk.hun-ren.hu/kutato/ujlaki-anna">Ujlaki Anna</a>'
            '<a href="/kutato/gyulai-attila">Gyulai Attila</a></div>')
    links = P._links(BeautifulSoup(html, "html.parser").div, "https://politikatudomany.tk.elte.hu/p", aliases)
    assert [(lk.url, lk.stated_url) for lk in links] == [
        ("https://politikatudomany.tk.elte.hu/kutato/ujlaki-anna",
         "https://politikatudomany.tk.hun-ren.hu/kutato/ujlaki-anna"),
        ("https://politikatudomany.tk.elte.hu/kutato/gyulai-attila",
         "https://politikatudomany.tk.elte.hu/kutato/gyulai-attila"),
    ]


def test_registry_alias_status(registry):
    assert registry.alias_status("szociologia.tk.elte.hu") == "canonical"
    assert registry.alias_status("szociologia.tk.mta.hu") == "verified"
    assert registry.alias_status("szociologia.tk.hun-ren.hu") == "inferred"
    assert registry.alias_status("example.org") == "unknown"
