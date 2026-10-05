# Source inventory

`config/sources.yaml` is the only place source URLs live; this page explains it.
The table at the bottom is rendered from the registry (2026-10-04). Entry points
were checked by reading the live sites; anything marked "unconfirmed" in the
notes has not been seen to resolve. No data from this inventory enters the graph
until an adapter crawls the page and stores a raw snapshot.

## Crawl rules that apply everywhere

- robots.txt is honoured; an unreachable robots.txt means the fetcher refuses the host (`fetch.PoliteFetcher`).
- Default delay 3 s, page budget 400 per run, snapshots younger than 30 days are reused.
- Our user agent identifies the project and links the repo. We never spoof a browser UA to get past a block.
- Only public, professional data: names, positions, units, projects, stated research areas. Phone numbers, rooms and personal email local parts are dropped by the parsers.
- Pages are fetched because a configured listing shows them or because a profile of an enabled source links them from its project section and the link's host belongs to an enabled source (ADR-0009, one hop, one-segment project paths, verified host aliases only). Links to other hosts are never followed; they are recorded in the release's `frontier.jsonl` with the reason.

## Restrictions found during the inventory

| Host | Finding | Consequence |
|---|---|---|
| doktori.hu | robots.txt disallows ClaudeBot, GPTBot, CCBot, Google-Extended | **Do not crawl automatically.** It is the key supervision/genealogy source, so it needs written permission from the operator or a manual, documented export. Tracked in `review/unresolved.yaml` (`doktori_hu_permission`). |
| btk.unideb.hu | robots.txt blocks the Scrapy UA and `/phonebook/department/*` | Use the sociology department site (szociologia.unideb.hu); never crawl the phonebook paths. |
| demografia.hu (KSH NKI) | robots.txt itself answered HTTP 429 after a few requests | `min_delay_seconds: 15` on `ksh_nki_web`; the institute was renamed in 2025 (`nki_rename` in `review/unresolved.yaml`). |
| tatk.elte.hu | robots.txt was unreachable from the reader | The fetcher will refuse until it is reachable; re-check from the crawl environment. |
| kti.krtk.hu, vki.hu | intermittent timeouts | Low priority. |

## Linked pages the crawl does not follow (#16, observed 2026-10-05)

The four enabled TK sites link 123 distinct pages from the project sections of their profiles
(208 mentions). 90 are on enabled sites' hosts and are all fetched. The other 33 are not,
by decision (`frontier.jsonl`: scope, reason). A one-off polite probe (one request per URL,
robots.txt honoured, nothing stored or parsed) recorded what the other units' hosts answer:

| Linked as written | Registry entry | Mentions / researchers | Probe |
|---|---|---|---|
| `jog.tk.hu/a-nemzetiseg-es-etnicitas-jogi-operacionalizalasa` (also `jog.tk.mta.hu`) | `tk_jog` (adapter `tk`, disabled) | 2 / 2 (KI) | HTTP 200 after a redirect to `jog.tk.elte.hu`, same path |
| `klimacentrum.tk.hu/`, `…/en/visual-persuasion-in-a-transforming-europe-polarvis` | `tk_klimacentrum` (no adapter) | 2 / 2 | HTTP 200 after redirects to `klimacentrum.tk.elte.hu`, same paths |
| `csaladtudomany.tk.hu/` | `tk_csaladtudomany` (no adapter) | 1 / 1 | HTTP 200, no redirect |
| `reprosoc.tk.hu/` | `tk_reprosoc` (no adapter) | 2 / 2 | redirects to `reprosoc.tk.elte.hu`; its robots.txt answered HTTP 500, so the fetcher refuses the host |
| `tk.hun-ren.hu/mobilitas` | `tk_mobilitas` (no adapter) | 3 / 3 | not reachable from the crawl environment (egress policy) |
| `cap.tk.mta.hu/` | none | 1 / 1 | HTTP 200 after a redirect to `cap.tk.elte.hu/en` |
| `intersections.tk.mta.hu/index.php/intersections` | none (`journal_intersections` is registered at `intersections.tk.hu`) | 1 / 1 | HTTP 200, no redirect |
| `www.judicon.tk.mta.hu/` | none | 1 / 1 | redirects to `judicon.tk.hun-ren.hu`, which is not reachable from the environment |

Nothing is inferred from these pages: no fetch of their content was made. Enabling any of
these units as a source is a Milestone 3 scope decision; `tk_jog` is the only one with an
adapter, and its own note asks for a scope filter first. The same redirects are evidence for
promoting `jog.tk.hu`, `klimacentrum.tk.hu` and `cap.tk.mta.hu` host aliases from inferred to
verified when those units become sources (#14). The remaining 24 links go to 19 external
project sites (EU consortia, other universities, one academic profile) and five NKFIH grant
records; they are recorded, not fetched, and the grant records still count as grant
statements for project resolution (ADR-0008).

## Structural changes to model as events, not overwrites

- ELTE TK, ELTE KRTK: formerly MTA, then ELKH/HUN-REN research centres; old hosts (`*.tk.mta.hu`, `*.tk.hu`) are registered as host aliases.
- Corvinus: sociology is now the Szociológia Tanszék inside the Társadalom- és Politikatudományi Intézet; there is no separate sociology institute any more.
- KSH NKI: renamed in 2025.
- KRTK RKI keeps a "former staff" category (`korabbi-munkatarsak`): first-class historical evidence for WORKED_AT edges.

## Adapter priorities

1. **TK shared CMS** (`tk` adapter): done for four institute sites; the first live crawl runs in its own thread.
2. **MTMT** public JSON API (`/api/author/<mtid>?format=json`): hard identifiers and dated affiliation history. SZTE, PPKE and Miskolc profiles already link MTMT ids, which gives safe ER anchors.
3. **KRTK RKI**: WordPress sitemaps for researchers, projects and units, plus former staff.
4. **TÁRKI**: staff on `/rolunk`, projects with named "Kutatásvezető" and teams.
5. University departments (ELTE TáTK, Corvinus, PTE, SZTE, Debrecen, Miskolc, PPKE): mostly flat staff lists; one generic list-and-profile adapter with per-site selectors should cover them.
6. Journals (editorial boards → EDITOR_OF) and the MSZT sections and prizes.

## Registry

| source_id | Institution | Type | Adapter | Enabled | Entry point | Notes |
|---|---|---|---|---|---|---|
| `tk_szociologia` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | tk | yes | https://szociologia.tk.elte.hu | Datasets link points to openarchive.tk.mta.hu (division SZI). |
| `tk_recens` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | tk | yes | https://recens.tk.elte.hu | Koltai Júlia, Kmetty Zoltán, Kisfalusi Dorottya, Janky Béla and Keller Tamás are listed here, not under the Sociology Institute (observed 2026-10-04). English pages under /en/ list research groups incl. the MTA–TK Lendület DS4 group; group pages need a dedicated parser (next step). |
| `tk_kisebbsegkutato` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | tk | yes | https://kisebbsegkutato.tk.elte.hu | Two departments observed by name (Kisebbségszociológiai és Antropológiai Osztály; Kisebbségtörténeti és Etnopolitikai Osztály); their URLs are not yet confirmed. |
| `tk_politikatudomany` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | tk | yes | https://politikatudomany.tk.elte.hu |  |
| `tk_jog` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | tk | no | https://jog.tk.elte.hu | Include only researchers with socio-legal overlap. Needs a scope filter (stated research areas) before enabling, so the graph does not absorb the whole law institute. |
| `tk_ess` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://ess.tk.hu/ | ESS Hungary national team. Adapter TBD. |
| `tk_milab` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://milab.tk.hu/hu | MILAB social-science groups. Adapter TBD. |
| `tk_reprosoc` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://reprosoc.tk.hu/ | Lendület group site. Adapter TBD. |
| `tk_hpops` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://hpops.tk.hu/ | Lendület group site. Adapter TBD. |
| `tk_enl` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://enl.tk.hu/ | National Laboratory for Health Security. Adapter TBD. |
| `tk_mobilitas` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://tk.hun-ren.hu/mobilitas | Linked from tk.elte.hu under a tk.hun-ren.hu host. Adapter TBD. |
| `tk_gyerekesely` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | http://gyerekesely.tk.hu/ | Child poverty programme (Ferge tradition candidate; do not assert). Adapter TBD. |
| `tk_kdk` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://kdk.tk.hu/ | Research Documentation Centre: survey data archive, relevant for project/data provenance. |
| `tk_mokk` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://mokk.tk.hu/ |  |
| `tk_csaladtudomany` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://csaladtudomany.tk.hu/ |  |
| `tk_klimacentrum` | ELTE Társadalomtudományi Kutatóközpont | institutional_website | — | no | https://klimacentrum.tk.hu |  |
| `journal_intersections` | ELTE Társadalomtudományi Kutatóközpont | journal | — | no | https://intersections.tk.hu/ | Journal published by TK. Editorial board -> EDITOR_OF edges. |
| `tk_openarchive` | ELTE Társadalomtudományi Kutatóközpont | repository | — | no | https://openarchive.tk.mta.hu | EPrints repository; per-division and per-creator views. Candidate publication source. |
| `elte_tatk_sociology` | ELTE Társadalomtudományi Kar | institutional_website | — | no | https://tatk.elte.hu/en/units/institute-of-sociology | ~25 staff in one list; department page /en/units/department-of-sociology; profiles /en/staff/<slug>. tatk.elte.hu robots.txt was unreachable from the reader: confirm before crawling. |
| `elte_tatk_empirical` | ELTE Társadalomtudományi Kar | institutional_website | — | no | https://tatk.elte.hu/en/units/institute-of-empirical-studies | Departments of Statistics and of Social Research Methodology; 29 people inline. |
| `elte_krtk_rki` | ELTE Közgazdaság- és Regionális Tudományi Kutatóközpont | institutional_website | — | no | https://rki.krtk.hu/ | WordPress; robots open; sitemaps for kutatok (403 profiles), projektek, szervezeti_egysegek. Category korabbi-munkatarsak lists FORMER staff (historical evidence). Regional departments in Pécs, Budapest, Győr, Kecskemét, Békéscsaba. Best-structured candidate for the next adapter. |
| `elte_krtk_kti` | ELTE Közgazdaság- és Regionális Tudományi Kutatóközpont | institutional_website | — | no | https://kti.krtk.hu/ | Staff URLs unconfirmed (intermittent timeouts). Include researchers on inequality, education, Roma, labour, networks. |
| `elte_krtk_vgi` | ELTE Közgazdaság- és Regionális Tudományi Kutatóközpont | institutional_website | — | no | http://www.vki.hu/ | Timed out; low priority. |
| `elte_krtk_adatbank` | ELTE Közgazdaság- és Regionális Tudományi Kutatóközpont | institutional_website | — | no | https://krtk.elte.hu/adatbank/ |  |
| `tarki_web` | TÁRKI Társadalomkutatási Intézet Zrt. | institutional_website | — | no | https://tarki.hu/ | Drupal; staff on /rolunk (3 groups) with flat-slug profiles; projects at /kutatasok (?page=0..6) name 'Kutatásvezető' and team. robots: standard Drupal, no AI blocks. |
| `tarki_adatbank` | TÁRKI Társadalomkutatási Intézet Zrt. | data_archive | — | no | https://adatbank.tarki.hu/en/ | CESSDA member, 800+ datasets; study metadata likely lists PIs (DDI). |
| `corvinus_sociology` | Budapesti Corvinus Egyetem | institutional_website | — | no | https://www.uni-corvinus.hu/fooldal/egyetemunkrol/tanszekek/szociologia-tanszek/ | Inside the Társadalom- és Politikatudományi Intézet (no separate 'Szociológia és Társadalompolitika Intézet' any more). Staff page lists PhD students WITH supervisors (genealogy evidence) and MTMT/Scholar links; profiles /elerhetosegek/<slug>. |
| `corvinus_tpi` | Budapesti Corvinus Egyetem | institutional_website | — | no | https://www.uni-corvinus.hu/fooldal/egyetemunkrol/intezetek/tarsadalom-es-politikatudomanyi-intezet/ |  |
| `corvinus_etk` | Budapesti Corvinus Egyetem | institutional_website | — | no | https://www.uni-corvinus.hu/fooldal/kutatas/kutatokozpontok/empirikus-tarsadalomkutato-kozpont/ |  |
| `pte_sociology` | PTE Bölcsészet- és Társadalomtudományi Kar | institutional_website | — | no | https://btk.pte.hu/hu/szociologia | 15 staff at /hu/szociologia/oktatoink linking to faculty directory profiles /hu/munkatarsak/<slug>; Település és Társadalom research group; Demography and Sociology doctoral school. |
| `pte_romology` | PTE Bölcsészet- és Társadalomtudományi Kar | institutional_website | — | no | https://btk.pte.hu/hu/nevtud/romologia-es-nevelesszociologia-tanszek | In the Neveléstudományi Intézet; staff page /hu/node/15595 (9 people, no profile links). Model as potentially distinct from Budapest Roma-research networks (brief §3). |
| `pte_romology_centre` | PTE Bölcsészet- és Társadalomtudományi Kar | institutional_website | — | no | https://btk.pte.hu/hu/tudomany/kutatokozpontok/romologiai-kutatokozpont |  |
| `unideb_sociology` | Debreceni Egyetem | institutional_website | — | no | https://szociologia.unideb.hu/ | Research workshops (InnoDE, employment policy, youth sociology) with named leaders. btk.unideb.hu robots.txt blocks the Scrapy UA and /phonebook/department/*; phonebook appears JS-rendered. |
| `unideb_cherd` | Debreceni Egyetem | institutional_website | — | no | http://cherd.unideb.hu/ | Sociology of (higher) education. |
| `szte_sociology` | Szegedi Tudományegyetem | institutional_website | — | no | https://arts.u-szeged.hu/szociologia-tanszek | 12 staff with research areas; each links an MTMT record (hard identifier). Szeged Studies long-running project. u-szeged.hu robots: Crawl-delay 1. |
| `miskolc_atti` | Miskolci Egyetem | institutional_website | — | no | https://atti.uni-miskolc.hu/ | Static .htm site; oktatok.htm with MTMT links and CV PDFs; Romakutató Központ described on kutatasok.htm. robots.txt 404. |
| `ppke_sociology` | Pázmány Péter Katolikus Egyetem | institutional_website | — | no | https://btk.ppke.hu/szociologiai-intezet | 16 staff in two departments; flat-slug profiles with MTMT links; research groups incl. Társadalomtörténeti and Kulturális emlékezet. No sociology-of-religion unit found (only psychology of religion). |
| `ksh_nki_web` | KSH Népességtudományi Kutatóintézet | institutional_website | — | no | https://demografia.hu/ | robots.txt returned HTTP 429 after a few requests: use a long delay. Staff page /hu/intezetunk/munkatarsak unconfirmed. |
| `mszt_web` | Magyar Szociológiai Társaság | institutional_website | — | no | https://szociologia.hu/ | 16 sections (szakosztályok) with leaders; award laureate pages (Erdei, Polányi, Némedi, Angelusz, Szalai Júlia prizes). robots open. |
| `journal_szociologiai_szemle` | Magyar Szociológiai Társaság | journal | — | no | https://ojs.mtak.hu/index.php/szocszemle | OJS; editorial team at /about/editorialTeam; OAI endpoint to confirm. |
| `journal_socio_hu` | ELTE Társadalomtudományi Kutatóközpont | journal | — | no | https://socio.hu/ | OJS; editorial board at /index.php/so/editorial-board. |
| `journal_replika` | — | journal | — | no | https://replika.hu/ | Custom site; /szerkesztoseg. |
| `journal_metszetek` | Debreceni Egyetem | journal | — | no | https://ojs.lib.unideb.hu/metszetek |  |
| `journal_esely` | — | journal | — | no | https://www.esely.org/ | Seen in search only; TOCs as PDFs; also on EPA/REAL-J. |
| `mtmt` | — | registry | — | no | https://m2.mtmt.hu/ | Public JSON API /api/author/<mtid>?format=json without login: names, degrees, DATED affiliation history. Primary source for hard identifiers and historical affiliations. robots.txt 404. |
| `doktori_hu` | — | registry | — | no | https://www.doktori.hu/ | Key genealogy source (supervision with dates, dissertations, doctoral schools: ELTE SZDI 53, PTE 197, Corvinus SZKDI 233). robots.txt disallows GPTBot, Google-Extended, CCBot and ClaudeBot entirely. DO NOT crawl automatically: ask the National Doctoral Council for permission or a data agreement first. |
| `mta_ix` | Magyar Tudományos Akadémia | institutional_website | — | no | https://mta.hu/ix-osztaly | Section IX member lists; Sociology Scientific Committee page unconfirmed; Lendület winners mostly in PDFs. |
