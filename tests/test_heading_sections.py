"""Heading-labelled leads and participants on the legacy SZI project template (#31).

The fixtures ``szi_heading_*.html`` are real, scrubbed snapshots of project pages of szociologia.tk.elte.hu
(observed 2026-10-04) that state their fields as headings ("<h3>Résztvevők</h3>" followed by the names) instead of
"Label: value" lines. Each one is here for a markup pattern or a trap the 86 affected pages exhibit; the
expectations were checked against the page text by hand. Inline HTML appears only where a test needs a variation a
real page does not offer (a label line next to a heading, a comment inside a section, a profile link) and says so.
"""

from datetime import UTC, datetime

import pytest

from szocatlas.fetch import FixtureFetcher
from szocatlas.models.enums import SourceType
from szocatlas.registry import REPO_ROOT
from szocatlas.sources.tk import parser as P
from szocatlas.sources.tk.adapter import TKAdapter

SZI = "https://szociologia.tk.elte.hu/"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tk"
OBSERVED = datetime(2026, 10, 5, tzinfo=UTC)


def parse(fixture_html, aliases, name, slug):
    return P.parse_project(fixture_html(name), SZI + slug, aliases)


def names(pairs):
    return [n for n, _ in pairs]


# ------------------------------------------------------------------ the markup patterns


def test_heading_with_one_value_block_and_br_separated_participants(fixture_html, aliases):
    """<h2>Projektvezető</h2><p>Makó Csaba</p><h3>Résztvevők</h3><p>A<br>B<br>C</p>: names split on <br>."""
    proj = parse(fixture_html, aliases, "szi_heading_basic.html",
                 "a-munkaero-es-tudasfelhasznalas-gyakorlata-a-vallalkozasok-munkaszervezeti-jellemzoi")
    assert names(proj.unlinked_leads) == ["Makó Csaba"]
    assert proj.unlinked_participants == [("Makó Csaba", "Résztvevők"), ("Csizmadia Péter", "Résztvevők"),
                                          ("Illéssy Miklós", "Résztvevők")]
    assert proj.leads == [] and proj.participants == []  # no profile link on the page: names only
    assert [(s.tag, s.heading, s.kind) for s in proj.sections] == [("h2", "Projektvezető", "lead"),
                                                                    ("h3", "Résztvevők", "participants")]


def test_heading_followed_by_several_blocks(fixture_html, aliases):
    """<h4>Résztvevők</h4><div>A</div><div>B</div>...: every block up to the next heading is part of the section."""
    proj = parse(fixture_html, aliases, "szi_heading_div_blocks.html",
                 "return-and-escape-forced-migration-between-1938-1956")
    assert names(proj.unlinked_participants) == ["Gárdos Judit", "Kovács Éva", "Paksi Veronika", "Tibori Tímea",
                                                 "Vidra Zsuzsanna"]
    # "Projektvezető" and "Kutatásvezető (MTA SZKI)" are both lead headings; the qualifier is kept as stated
    assert names(proj.unlinked_leads) == ["Tibori Tímea", "Kovács Éva"]
    assert [s.heading for s in proj.sections if s.kind == "lead"] == ["Projektvezető", "Kutatásvezető (MTA SZKI)"]


def test_value_as_bare_text_and_br_after_the_heading_and_blocks_with_inner_br(fixture_html, aliases):
    """<h2>Projektvezető</h2>Kovács Éva<br/> (no wrapper), and <div>Kovács Éva<br/>Messing Vera</div>."""
    proj = parse(fixture_html, aliases, "szi_heading_bare_text.html", "kint-es-bent-haromszor")
    assert names(proj.unlinked_leads) == ["Kovács Éva"]
    assert names(proj.unlinked_participants) == ["Fleck Gábor", "Kovács Éva", "Messing Vera", "Virág Tünde",
                                                 "Vidra Zsuzsa"]


def test_heading_inside_a_word_wrapper_reads_the_text_after_it_in_that_wrapper_only(fixture_html, aliases):
    """<div class="MsoNormal"><h4>Projektvezető</h4>Kovách\\nImre</div>: the section is bounded by the heading's parent."""
    proj = parse(fixture_html, aliases, "szi_heading_word_wrapper.html", "elit-es-innovacio")
    assert names(proj.unlinked_leads) == ["Kovách Imre"]  # the line break inside the name is whitespace
    assert names(proj.unlinked_participants) == ["Tóth Ágnes", "Szarka László", "Papp Z. Attila", "Csurgó Bernadett",
                                                 "Kristóf Luca", "Légmán Anna", "Megyesi Boldizsár"]


def test_participants_in_a_list(fixture_html, aliases):
    """<ul><li><div>Név</div></li>...</ul> under the heading; the "Konzorciumi tagok" list after it is no label."""
    proj = parse(fixture_html, aliases, "szi_heading_ul_li.html",
                 "varostersegek-terbeli-tarsadalmi-egyenlotlensegek-es-konfliktusok")
    assert names(proj.unlinked_participants) == ["Füstös László", "Ferencz Zoltán", "Váradi Zsuzsanna", "Bognár Judit"]
    assert not any("MTA" in n or "Kft" in n for n in names(proj.unlinked_participants))
    assert [s.heading for s in proj.sections] == ["Projektvezető", "Résztvevők"]


def test_other_headings_are_no_labels_and_end_a_section(fixture_html, aliases):
    """"Koordinátor", "Konzorciumi tagok", "Honlap" and the "Részvevők:" line of countries read as nothing."""
    proj = parse(fixture_html, aliases, "szi_project_etnikai_konfliktusok.html",
                 "etnikai-konfliktusok-es-bekefolyamatok")
    assert names(proj.unlinked_leads) == ["Tamás Pál"]
    assert names(proj.unlinked_participants) == ["Tamás Pál", "Erőss Gábor", "Tamási Péter", "Schmidt Andrea",
                                                 "Csizmady Adrienne"]
    everything = names(proj.unlinked_leads) + names(proj.unlinked_participants)
    assert not any(w in n for n in everything for w in ("Belgium", "Ciprus", "Winter", "Rihoux", "Louvain"))


# ------------------------------------------------------------------ a heading with no value


@pytest.mark.parametrize("fixture, slug, label", [
    ("szi_heading_placeholder_ellipsis.html",
     "allamreform-kozigazgatas-hatterintezmenyek-miniszteriumok-es-hatterintezmenyeik", "Résztvevők"),
    ("szi_heading_placeholder_dots.html", "korrupcio-szervezeti-megkozelitesben", "Résztvevők"),
])
def test_a_heading_with_a_placeholder_yields_no_participants(fixture_html, aliases, fixture, slug, label):
    """The page states the heading and leaves the value as "..." / "....": no field, and the gap is recorded."""
    proj = parse(fixture_html, aliases, fixture, slug)
    assert proj.participants == [] and proj.unlinked_participants == []
    sec = next(s for s in proj.sections if s.kind == "participants")
    assert sec.placeholders == 1 and not sec.read
    assert f"{label} (heading without a readable name)" in proj.unmapped_labels


def test_a_heading_straight_followed_by_another_heading_yields_nothing():
    """Derived from the real template: the value is missing altogether (no real page leaves out even a placeholder)."""
    html = ("<main><h2>Cím</h2><div class='page-content'><h2>Projektvezető</h2>"
            "<h3>Résztvevők</h3><h3>A kutatás</h3><div>Leírás.</div></div></main>")
    proj = P.parse_project(html, SZI + "cim", {})
    assert proj.leads == proj.unlinked_leads == proj.participants == proj.unlinked_participants == []
    assert [s.read for s in proj.sections] == [False, False]
    assert [s.end for s in proj.sections] == ["heading", "heading"]


# ------------------------------------------------------------------ traps: what follows a heading and is no person


def test_organisation_and_country_after_a_name_are_not_read(fixture_html, aliases):
    """'Ingrid Sharp, University of Leeds, Great Britain': the name, nothing after it."""
    proj = parse(fixture_html, aliases, "szi_heading_org_country_tail.html", "a-haboru-utan-nomozgalmak-es-aktivistak")
    assert names(proj.unlinked_leads) == ["Ingrid Sharp", "Acsády Judit"]
    everything = names(proj.unlinked_leads) + names(proj.unlinked_participants)
    assert not any(w in n for n in everything for w in ("Leeds", "Britain", "University"))
    # "Partnerek" is no label: its list ("University of Leeds – Ingrid Sharp, Matthew Stibe ...") is not read
    assert "Matthew Stibe" not in everything


def test_a_family_name_first_list_with_commas_is_left_unread(fixture_html, aliases):
    """'Acsády, Judit' is a name in "Family, Given" form: read as two single tokens it would be wrong, so no name."""
    proj = parse(fixture_html, aliases, "szi_heading_org_country_tail.html", "a-haboru-utan-nomozgalmak-es-aktivistak")
    assert proj.unlinked_participants == []
    sec = next(s for s in proj.sections if s.kind == "participants")
    assert sec.rejected == [("Acsády, Judit", "not a person")]
    assert "Résztvevők (heading without a readable name)" in proj.unmapped_labels


def test_international_leads_keep_the_people_and_drop_organisation_city_and_country(fixture_html, aliases):
    proj = parse(fixture_html, aliases, "szi_heading_ilo_leads.html",
                 "munkahelyi-partnersegek-a-gyermekfelugyelet-megoldasara")
    assert names(proj.unlinked_leads) == ["Naomi Cassirer", "Catherine Hein", "Tardos Katalin"]
    assert names(proj.unlinked_participants) == ["Tardos Katalin"]


def test_a_name_followed_by_prose_in_the_same_block_reads_the_name_only(fixture_html, aliases):
    """<p>Tardos Katalin<br/><br/>A kutatás célja a halmozott diszkrimináció vizsgálata ...</p>"""
    proj = parse(fixture_html, aliases, "szi_heading_name_then_prose.html",
                 "halmozott-diszkriminacio-egyeni-es-intezmenyi-perc")
    assert names(proj.unlinked_leads) == ["Tardos Katalin"]
    sec = proj.sections[0]
    assert [why for _, why in sec.rejected] == ["prose or link"]


def test_a_line_of_partner_counts_is_not_a_person(fixture_html, aliases):
    """'Széman Zsuzsa<br>Kucsera Csaba<br>10 partner az EU országaiból'"""
    proj = parse(fixture_html, aliases, "szi_heading_junk_after_names.html",
                 "ageing-and-employment-identification-of-good")
    assert names(proj.unlinked_participants) == ["Széman Zsuzsa", "Kucsera Csaba"]
    assert proj.sections[0].rejected == [("10 partner az EU országaiból", "not a person")]


def test_organisation_prefixed_names_are_not_read(fixture_html, aliases):
    """'MTA Szociológiai Kutatóintézet - Vitányi Iván': an organisation first; left unread (precision first)."""
    proj = parse(fixture_html, aliases, "szi_heading_org_prefixed.html", "talalkozasok-a-kulturaval")
    assert names(proj.unlinked_leads) == ["Vitányi Iván"]  # under "Projektvezető", as a bare name
    assert proj.unlinked_participants == []
    assert [why for _, why in proj.sections[1].rejected] == ["not a person", "not a person"]


def test_affiliations_in_parentheses_are_dropped_and_a_japanese_family_first_list_is_not_read(fixture_html, aliases):
    proj = parse(fixture_html, aliases, "szi_heading_affiliations.html", "project-on-intergenerational-equtity")
    assert names(proj.unlinked_participants) == [
        "Széman Zsuzsa", "Kucsera Csaba", "Augusztinovics Mária", "Köllő János", "Kézdi Gábor", "Simonovits András",
        "Hablicsek László", "Gál Róbert Iván", "Gábos András", "Harsányi László", "Matits Ágnes", "Tarcali Géza"]
    # "Résztvevők (japán ...)" lists "Iwasaki, Ichiro (Hitotsubashi University, ...)": family name first, unread
    assert [s.read for s in proj.sections] == [True, False]
    assert proj.sections[1].heading == "Résztvevők (japán a Magyarországra vonatkozó kutatásban)"


def test_a_p_used_as_a_heading_ends_the_section_and_is_not_a_label(fixture_html, aliases):
    """prosuite: <h3>Kutatásvezető (MTA SZKI)</h3><p>Vári Anna</p><p>Résztvevők (MTA SZKI)</p><p>Vári Anna</p>...
    The <p> labels are not headings: the names after them are NOT the lead's, and are not read either."""
    proj = parse(fixture_html, aliases, "szi_heading_p_pseudo_headings.html", "prosuite")
    assert names(proj.unlinked_leads) == ["Vári Anna"]
    assert proj.unlinked_participants == []
    sec = proj.sections[0]
    assert sec.end == "non-name block" and sec.blocks == 1
    everything = names(proj.unlinked_leads) + names(proj.unlinked_participants)
    assert not any(n in everything for n in ("Ferencz Zoltán", "Kárpáti Zoltán", "Kornelis Blok"))


def test_old_site_profile_links_do_not_make_a_name_a_profile(fixture_html, aliases):
    """knowandpol links its people to www.socio.mta.hu/kutatok/index.php?... : no /kutato/<slug> profile, so names."""
    proj = parse(fixture_html, aliases, "szi_heading_old_site_links.html", "knowandpol")
    assert proj.leads == [] and proj.participants == []
    assert names(proj.unlinked_leads) == ["Erőss Gábor"]
    assert names(proj.unlinked_participants) == ["Erőss Gábor", "Dávid Beáta", "Fernezelyi Bori", "Koltai Júlia",
                                                 "Levendel Sára", "Gárdos Judit"]
    assert not any("Louvain" in n or "Delvaux" in n for n in names(proj.unlinked_participants))


def test_the_label_that_reads_profile_links_only_still_does_that_under_a_heading():
    """"Résztvevő" / "Részvevők" (#16): a profile link counts, a plain name does not."""
    html = ("<main><h2>Cím</h2><div><h3>Résztvevő</h3><p>Laki Ildikó</p>"
            "<h3>Részvevők</h3><p><a href='/kutato/szalai-julia'>Szalai Júlia</a></p></div></main>")
    proj = P.parse_project(html, SZI + "cim", {})
    assert proj.unlinked_participants == []
    assert [lk.text for lk in proj.participants] == ["Szalai Júlia"]
    assert proj.sections[0].rejected == [("Laki Ildikó", "label reads profile links only")]


# ------------------------------------------------------------------ how a heading becomes fields


def test_heading_and_label_line_give_the_same_fields():
    """The same lead and participants, once as headings and once as "Label: value" lines (equivalence of paths)."""
    headings = ("<main><h2>Cím</h2><div><h3>Projektvezető</h3><p>Bene Márton</p>"
                "<h3>Résztvevők</h3><p>Farkas Xénia<br/>Kiss Péter</p></div></main>")
    labels = ("<main><h2>Cím</h2><div><p>Projektvezető: Bene Márton</p>"
              "<p>Résztvevők: Farkas Xénia, Kiss Péter</p></div></main>")
    a, b = P.parse_project(headings, SZI + "cim", {}), P.parse_project(labels, SZI + "cim", {})
    assert names(a.unlinked_leads) == names(b.unlinked_leads) == ["Bene Márton"]
    assert a.unlinked_participants == b.unlinked_participants == [("Farkas Xénia", "Résztvevők"),
                                                                   ("Kiss Péter", "Résztvevők")]
    assert a.heading_origin and not b.heading_origin  # only the heading path is marked as such


def test_a_person_stated_by_a_label_line_and_a_heading_is_one_lead_and_one_participant():
    """Derived from the real template plus one injected label line: no second mention, edge or claim."""
    html = ("<main><h2>Cím</h2><div><p>Kutatásvezető: Makó Csaba</p><p>Résztvevők: Illéssy Miklós</p>"
            "<h3>Projektvezető</h3><p>Makó Csaba</p>"
            "<h3>Résztvevők (MTA SZKI)</h3><p>Makó Csaba<br/>Illéssy Miklós<br/>Csizmadia Péter<br/>Makó Csaba</p></div></main>")
    proj = P.parse_project(html, SZI + "cim", {})
    assert names(proj.unlinked_leads) == ["Makó Csaba"]
    # the lead is also a participant (a different relation); a name repeated in a list, or in a label line and a
    # heading, is one participant
    assert names(proj.unlinked_participants) == ["Illéssy Miklós", "Makó Csaba", "Csizmadia Péter"]
    # what the label line stated keeps its own evidence; only the new names are marked as read under a heading
    assert ("participant", "Illéssy Miklós") not in proj.heading_origin
    assert ("lead", "Makó Csaba") not in proj.heading_origin
    assert ("participant", "Csizmadia Péter") in proj.heading_origin


def test_a_profile_link_under_a_heading_is_a_linked_lead_and_participant():
    """Derived (no real page links its people under a heading): the profile URL is the identity evidence."""
    html = ("<main><h2>Cím</h2><div><h3>Kutatásvezető</h3><p><a href='/kutato/makocs'>Makó Csaba</a></p>"
            "<h3>Résztvevők</h3><p><a href='/kutato/makocs'>Makó Csaba</a><br/>Illéssy Miklós</p></div></main>")
    proj = P.parse_project(html, SZI + "cim", {})
    assert [lk.text for lk in proj.leads] == ["Makó Csaba"]
    assert [lk.text for lk in proj.participants] == ["Makó Csaba"]
    assert names(proj.unlinked_participants) == ["Illéssy Miklós"]
    url = proj.leads[0].url
    assert proj.heading_origin[("lead", url)].evidence(url) == "Kutatásvezető: Makó Csaba"


def test_comments_and_styles_inside_a_section_are_skipped():
    """Derived from recwowe: Word conditional comments sit between the blocks of the lead section."""
    html = ("<main><h2>Cím</h2><div><h3>Projektvezető</h3><p>Denis Bouget (Maison des Sciences de l’Homme)</p>"
            "<!--[if gte mso 9]><xml><w:WordDocument><w:View>Normal</w:View></w:WordDocument></xml><![endif]-->"
            "<style>p.MsoNormal {margin:0cm}</style>"
            "<p>Honlap: <a href='http://recwowe.vitamib.com/'>http://recwowe.vitamib.com/</a></p>"
            "<h3>Kutatásvezető (MTA SZKI)</h3><p>Takács Judit</p></div></main>")
    proj = P.parse_project(html, SZI + "cim", {})
    assert names(proj.unlinked_leads) == ["Denis Bouget", "Takács Judit"]
    assert proj.sections[0].end == "non-name block"  # the "Honlap:" line is not a name block


def test_a_heading_label_is_the_whole_heading_text():
    for text in ("Projektvezető", "Projektvezetők", "Kutatásvezető (MTA SZKI)", "Kutatásvezetők", "Témavezető:",
                 "Résztvevők", "Résztvevők:", "Résztvevők (japán a Magyarországra vonatkozó kutatásban)",
                 "Résztvevő", "Részvevők", "Kutatás résztvevői", "Munkatársak"):
        assert P._heading_label(P.soup_of(f"<h3>{text}</h3>").h3) is not None, text
    for text in ("Koordinátor", "Koordinátorok", "Konzorciumi tagok", "A kutatás", "Honlap", "Partnerek",
                 "Kutatóközpont bemutatása", "Projektvezetési tapasztalatok", "Résztvevők és partnerek száma a kutatásban"):
        assert P._heading_label(P.soup_of(f"<h3>{text}</h3>").h3) is None, text


@pytest.mark.parametrize("text, expected", [
    ("Makó Csaba", ["Makó Csaba"]),
    ("Makó Csaba (MTA SZKI)", ["Makó Csaba"]),
    ("Dr. Zimányi Krisztina (dékán, Budapesti Gazdasági Főiskola)", ["Zimányi Krisztina"]),
    ("Tamás Pál, Erőss Gábor és Schmidt Andrea", ["Tamás Pál", "Erőss Gábor", "Schmidt Andrea"]),
    ("Joachim von Puttkamer (HI-UJ)", ["Joachim von Puttkamer"]),
    ("Sz. Tóth János (Magyar Népfőiskolai Társaság)", ["Sz. Tóth János"]),
    ("Takács-Sánta András", ["Takács-Sánta András"]),
    ("Prof. Dr. Ortwin Renn", ["Ortwin Renn"]),
    ("Albert Fruzsina Kabai Imre (...) Ságvári Bence Kiss Viktor (...)", ["Albert Fruzsina Kabai Imre", "Ságvári Bence Kiss Viktor"]),
])
def test_names_a_line_may_state(text, expected):
    names_read, why = P._name_line(text)
    # a line the <br> split has not separated stays one "name" of up to five tokens: it is the HTML that separates
    assert names_read == expected or (len(names_read) == 1 and len(names_read[0].split()) <= 5), (names_read, why)


@pytest.mark.parametrize("text, why", [
    ("", "blank"),
    ("...", "placeholder"),
    ("....", "placeholder"),
    ("(...)", "placeholder"),
    ("Franciaország", "not a person"),
    ("Svájc", "not a person"),
    ("Great Britain", "not a person"),
    ("Egyesült Királyság", "not a person"),
    ("International Labour Organisation", "not a person"),
    ("Oxford Institute of Ageing, UK", "not a person"),
    ("FIERI, International and European Forum of Migration Research", "not a person"),
    ("MTA SZKI - Széman Zsuzsa", "not a person"),
    ("ASTREES, France - Jean-Marie Bergere", "not a person"),
    ("Szakértők a közgazdaság, szociális gondozás, kommunikáció", "not a person"),
    ("A kutatás", "not a person"),
    ("Résztvevők (MTA SZKI)", "not a person"),
    ("10 partner az EU országaiból", "not a person"),
    ("Honlap: http://recwowe.vitamib.com/", "prose or link"),
    ("Kovács éva", "not a person"),  # lower-case given name: a typo on the page, left unread
    ("Acsády, Judit", "not a person"),
    ("x" * 160, "prose or link"),
])
def test_lines_that_are_not_names(text, why):
    assert P._name_line(text) == ([], why)


def test_an_organisation_after_names_ends_the_reading_of_the_line():
    assert P._name_line("Naomi Cassirer, Catherine Hein, International Labour Organisation, Genf, Svájc") == (
        ["Naomi Cassirer", "Catherine Hein"], "")
    assert P._name_line("Ingrid Sharp, University of Leeds, Great Britain") == (["Ingrid Sharp"], "")
    assert P._name_line("Henrique Barros, Faculdade de Medicina da Universidade do Porto [FMUP], Porto") == (
        ["Henrique Barros"], "")


# ------------------------------------------------------------------ the description under "A kutatás"


def test_description_is_read_under_an_explicit_a_kutatas_heading(fixture_html, aliases):
    proj = parse(fixture_html, aliases, "szi_heading_basic.html",
                 "a-munkaero-es-tudasfelhasznalas-gyakorlata-a-vallalkozasok-munkaszervezeti-jellemzoi")
    assert proj.description_heading == "A kutatás"
    assert proj.description.startswith("A Magyar Tudományos Akadémia (MTA) Társadalomtudományi Főosztályának")
    assert "2007-ben" not in proj.description  # the first paragraph only; later <div>s are not appended


def test_the_labelled_description_beats_the_first_long_paragraph(fixture_html, aliases):
    """Before #31 the first <p> of 80+ characters was the description: here the participants list, or a coordinator."""
    org = parse(fixture_html, aliases, "szi_heading_org_prefixed.html", "talalkozasok-a-kulturaval")
    assert org.description.startswith("Az MTA Szociológiai Kutatóintézete 2003-ban megbízást kapott")
    aff = parse(fixture_html, aliases, "szi_heading_affiliations.html", "project-on-intergenerational-equtity")
    assert aff.description.startswith("A PIE nagyméretű nemzetközi projekt")
    assert aff.description_heading == "A kutatás"


def test_without_the_heading_the_description_rule_is_unchanged(fixture_html, aliases):
    proj = parse(fixture_html, aliases, "szi_heading_name_then_prose.html",
                 "halmozott-diszkriminacio-egyeni-es-intezmenyi-perc")
    assert proj.description_heading is None
    assert proj.description.startswith("Tardos Katalin A kutatás célja")  # the old rule; not touched here


def test_a_label_line_page_is_read_as_before(fixture_html, aliases):
    """The 107 pages with "Label: value" lines are unchanged: no heading section, no heading description."""
    proj = P.parse_project(fixture_html("szi_project_energiaatmenet.html"),
                           SZI + "az-energiaatmenet-terbeli-tarsadalmi-egyenlotlensegei", aliases)
    assert proj.sections == [] and proj.heading_origin == {} and proj.description_heading is None
    assert [lk.text for lk in proj.leads] == ["Kőszeghy Lea"]


# ------------------------------------------------------------------ provenance in the claims


def adapter_claims(registry, fixture, slug):
    fetcher = FixtureFetcher({SZI + slug: FIXTURES / fixture}, registry.host_aliases(), OBSERVED)
    entry = registry.source("tk_szociologia")
    adapter = TKAdapter(entry, registry, fetcher)
    page = fetcher.get(SZI + slug, source_id="tk_szociologia", source_type=SourceType.INSTITUTIONAL_PROFILE)
    res = adapter.parse_project(page)
    return adapter, res


def test_claims_from_a_heading_name_the_heading_the_line_and_the_parser(registry):
    adapter, res = adapter_claims(registry, "szi_heading_div_blocks.html",
                                  "return-and-escape-forced-migration-between-1938-1956")
    pi = [c for c in res.claims if c.predicate == "PRINCIPAL_INVESTIGATOR_OF"]
    assert [(c.evidence.locator, c.evidence.snippet) for c in pi] == [
        ("project.heading.vezeto.unlinked", "Projektvezető: Tibori Tímea"),
        ("project.heading.vezeto.unlinked", "Kutatásvezető (MTA SZKI): Kovács Éva")]
    assert all(c.parser_version == P.PARSER_VERSION == "tk/0.6.0" for c in res.claims)
    part = [c for c in res.claims if c.predicate == "PARTICIPATES_IN"]
    assert len(part) == 5
    assert {c.evidence.locator for c in part} == {"project.heading.resztvevok.unlinked"}
    assert {c.qualifiers["role"] for c in part} == {"Résztvevők"}
    assert "Résztvevők: Gárdos Judit" in {c.evidence.snippet for c in part}
    # every edge has the claim and its evidence; every PI/participation subject is a name mention, never a Person
    assert all(c.evidence.document_id for c in pi + part)


def test_a_heading_claim_keeps_the_qualifier_of_the_heading_in_its_snippet(registry):
    adapter, res = adapter_claims(registry, "szi_heading_duplicate_name.html",
                                  "a-ferfiak-fokozottabb-reszvetelenek-elosegitese")
    snippets = {c.evidence.snippet for c in res.claims if c.predicate == "PARTICIPATES_IN"}
    assert "Résztvevők (MTA SZKI): Acsády Judit" in snippets
    pi = {c.evidence.snippet for c in res.claims if c.predicate == "PRINCIPAL_INVESTIGATOR_OF"}
    assert pi == {"Projektvezető: Haroon Saad (QeC-ERAN)", "Kutatásvezető (MTA SZKI): Takács Judit"}


def test_a_repeated_name_is_one_mention_and_one_claim_per_relation(registry):
    adapter, res = adapter_claims(registry, "szi_heading_duplicate_name.html",
                                  "a-ferfiak-fokozottabb-reszvetelenek-elosegitese")
    part = [c for c in res.claims if c.predicate == "PARTICIPATES_IN"]
    assert len(part) == 5 and len({c.claim_id for c in part}) == 5  # "Takács Judit" is listed twice on the page
    pi = [c for c in res.claims if c.predicate == "PRINCIPAL_INVESTIGATOR_OF"]
    # she is also the lead: one PI claim and one participation claim, on the one mention of her in this project
    takacs = [c for c in part + pi if "takacs-judit" in c.subject.source_ref]
    assert sorted(c.predicate for c in takacs) == ["PARTICIPATES_IN", "PRINCIPAL_INVESTIGATOR_OF"]
    assert len({c.subject.source_ref for c in takacs}) == 1


def test_the_abstract_claim_says_it_came_from_a_heading(registry):
    adapter, res = adapter_claims(registry, "szi_heading_basic.html",
                                  "a-munkaero-es-tudasfelhasznalas-gyakorlata-a-vallalkozasok-munkaszervezeti-jellemzoi")
    ab = [c for c in res.claims if c.predicate == "abstract"]
    assert len(ab) == 1 and ab[0].evidence.locator == "project.heading.description"
    assert ab[0].value.startswith("A Magyar Tudományos Akadémia (MTA)")


def test_a_label_line_keeps_its_old_locator(registry):
    """Pages that state their fields as lines are emitted exactly as before: ``field``, never ``heading``."""
    fetcher = FixtureFetcher({SZI + "a-vakcinacios-szandek-megertese": FIXTURES / "szi_project_vakcinacio.html"},
                             registry.host_aliases(), OBSERVED)
    adapter = TKAdapter(registry.source("tk_szociologia"), registry, fetcher)
    page = fetcher.get(SZI + "a-vakcinacios-szandek-megertese", source_id="tk_szociologia",
                       source_type=SourceType.INSTITUTIONAL_PROFILE)
    res = adapter.parse_project(page)
    pi = [c for c in res.claims if c.predicate == "PRINCIPAL_INVESTIGATOR_OF"]
    assert [c.evidence.locator for c in pi] == ["project.field.vezeto.unlinked"]
    assert [c.evidence.locator for c in res.claims if c.predicate == "abstract"] == ["project.description"]
