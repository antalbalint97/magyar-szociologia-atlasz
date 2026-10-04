"""Adapter for the TK institute websites (one CMS, several sites)."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from urllib.parse import urlsplit

from ...fetch import Page
from ...models.enums import AssertionType, EntityType, SourceType, TemporalBasis
from ...models.provenance import EntityRef, SourceRecord
from ...normalize.names import slugify
from ...normalize.urls import canonical_url
from ..base import ClaimFactory, ParseResult, SourceAdapter, local_ref
from . import parser as P


class TKAdapter(SourceAdapter):
    name = "tk"
    parser_version = P.PARSER_VERSION

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.base = self.entry.base_url.rstrip("/")
        self.cfg = self.entry.adapter_config
        self._listing_positions: dict[str, str] = {}
        self._project_status: dict[str, str] = {}

    # ------------------------------------------------------------ refs

    def owner_source(self, url: str) -> str:
        """The registry source that owns a URL's host (so cross-site links resolve)."""
        host = (urlsplit(url).hostname or "").lower()
        for s in self.registry.sources:
            if s.base_url and (urlsplit(s.base_url).hostname or "").lower() == host:
                return s.source_id
        return f"external:{host}"

    def person_ref(self, url: str) -> EntityRef:
        return local_ref(self.owner_source(url), EntityType.PERSON, url)

    def site_unit_ref(self) -> EntityRef:
        return local_ref(self.entry, EntityType.ORG_UNIT, "site")

    def institution_ref(self) -> EntityRef:
        return EntityRef(
            entity_type=EntityType.INSTITUTION,
            source_ref=f"registry|institution:{self.entry.institution}",
        )

    def named_unit_ref(self, name: str) -> EntityRef:
        return local_ref(self.entry, EntityType.ORG_UNIT, f"unit-name:{slugify(name)}")

    def project_ref(self, url: str | None, title: str) -> EntityRef:
        if url:
            return local_ref(self.owner_source(url), EntityType.PROJECT, url)
        return local_ref(self.entry, EntityType.PROJECT, f"project-title:{slugify(title)}")

    def url(self, path: str) -> str:
        return canonical_url(path, base=self.base + "/", aliases=self.aliases)

    # ------------------------------------------------------------ discovery

    def _crawl_listings(self, start: str) -> Iterator[tuple[str, str | None]]:
        """BFS over /kutatok pages (pagination + letter filters) until no new pages."""
        queue, seen_pages, seen_people = deque([self.url(start)]), set(), set()
        while queue:
            url = queue.popleft()
            if url in seen_pages:
                continue
            seen_pages.add(url)
            page = self.fetch(url, SourceType.INSTITUTIONAL_LISTING)
            if page is None or page.document.http_status >= 400:
                continue
            self._listing_docs.append(page)
            listing = P.parse_listing(page.text, page.document.final_url, self.aliases)
            for link, position in listing.people:
                if link.url not in seen_people:
                    seen_people.add(link.url)
                    yield link.url, position
            queue.extend(u for u in listing.next_pages if u not in seen_pages)

    def discover_people(self) -> Iterator[str]:
        self._listing_docs: list[Page] = []
        listing = self.cfg.get("people_listing")
        if not listing:
            return
        for url, position in self._crawl_listings(listing):
            if position:
                self._listing_positions[url] = position
            yield url

    def discover_units(self) -> Iterator[str]:
        for u in self.cfg.get("units") or []:
            yield self.url(u["path"])

    def discover_projects(self) -> Iterator[str]:
        """Project links from category listings (same host, single path segment)."""
        excluded = ("kutato", "kutatok", "kategoria", "hirek", "intezet", "kapcsolat", "en")
        self._project_listing_docs: list[tuple[Page, str | None]] = []
        for spec in self.cfg.get("project_listings") or []:
            queue, seen = deque([self.url(spec["path"])]), set()
            while queue:
                url = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                page = self.fetch(url, SourceType.INSTITUTIONAL_LISTING)
                if page is None or page.document.http_status >= 400:
                    continue
                self._project_listing_docs.append((page, spec.get("status_label")))
                soup = P.soup_of(page.text)
                main = P._main(soup)
                # Article title links are the projects; other single-segment links on the
                # page (menus, staff pages) are only a fallback for listings without articles.
                articles = {pp.url for pp in P.parse_project_listing(page.text, page.document.final_url, self.aliases)}
                for link in P._links(main, page.document.final_url, self.aliases):
                    parts = urlsplit(link.url)
                    segs = [s for s in parts.path.split("/") if s]
                    if parts.hostname != urlsplit(self.base).hostname:
                        continue
                    if parts.path == urlsplit(url).path and "page=" in parts.query:
                        queue.append(link.url)
                    elif articles and link.url not in articles:
                        continue
                    elif len(segs) == 1 and segs[0] not in excluded and not parts.query:
                        if link.url not in self._project_status:
                            self._project_status[link.url] = spec.get("status_label")
                            yield link.url

    # ------------------------------------------------------------ parsers

    def run(self) -> ParseResult:
        out = super().run()
        # listing pages: affiliation evidence even when a profile fetch fails
        for page in getattr(self, "_listing_docs", []):
            out.documents.append(page.document)
            out.extend(self.parse_listing(page))
        for page, status in getattr(self, "_project_listing_docs", []):
            out.documents.append(page.document)
            out.extend(self.parse_project_listing(page, status))
        return out

    def parse_listing(self, page: Page) -> ParseResult:
        doc = page.document
        f = ClaimFactory(doc, "tk.listing", self.parser_version)
        res = ParseResult()
        listing = P.parse_listing(page.text, doc.final_url, self.aliases)
        for link, position in listing.people:
            ref = self.person_ref(link.url)
            res.records.append(
                SourceRecord(ref=ref, label=link.text, document_id=doc.document_id,
                             hints={"profile_url": link.url, "site": self.owner_source(link.url)})
            )
            res.claims.append(f.literal(ref, "name", link.text, locator="listing.link_text", snippet=link.text))
            if self.owner_source(link.url) == self.entry.source_id:
                res.claims.append(
                    f.relation(
                        ref, "AFFILIATED_WITH", self.site_unit_ref(),
                        locator="listing.item", snippet=f"{link.text} {position or ''}".strip(),
                        qualifiers={"position_title": position} if position else {},
                        confidence=0.85,
                    )
                )
        return res

    def parse_person(self, page: Page) -> ParseResult:
        doc = page.document
        f = ClaimFactory(doc, "tk.profile", self.parser_version)
        res = ParseResult()
        prof = P.parse_profile(page.text, doc.final_url, self.aliases, self.entry.unit_name)
        ref = self.person_ref(doc.canonical_url)
        hints = {
            "profile_url": doc.canonical_url,
            "site": self.entry.source_id,
            "mtmt_id": prof.mtmt_id,
            "orcid": prof.orcid,
            "email_domain": prof.email_domain,
        }
        res.records.append(
            SourceRecord(ref=ref, label=prof.name, document_id=doc.document_id,
                         hints={k: v for k, v in hints.items() if v})
        )
        c = res.claims
        c.append(f.literal(ref, "name", prof.name, locator="profile.h1", snippet=prof.name_snippet))
        c.append(f.literal(ref, "profile_url", doc.canonical_url, locator="document.url", snippet=doc.canonical_url))
        for t in dict.fromkeys(prof.titles):
            c.append(f.literal(ref, "title", t, locator="profile.header", snippet=t, confidence=0.9))
        if prof.mtmt_id:
            c.append(f.literal(ref, "mtmt_id", prof.mtmt_id, locator="profile.link.mtmt", snippet=prof.mtmt_url))
        if prof.orcid:
            c.append(f.literal(ref, "orcid", prof.orcid, locator="profile.link.orcid", snippet=prof.orcid))
        if prof.scholar_id:
            c.append(f.literal(ref, "google_scholar_id", prof.scholar_id, locator="profile.link.scholar", snippet=prof.scholar_id))
        if prof.email_domain:
            c.append(f.literal(ref, "email_domain", prof.email_domain, locator="profile.mailto.domain", snippet="@" + prof.email_domain))
        for url in prof.other_profiles:
            c.append(f.literal(ref, "profile_url", url, locator="profile.link.external", snippet=url, confidence=0.8))
        if prof.cv_url:
            c.append(f.literal(ref, "cv_url", prof.cv_url, locator="profile.link.cv", snippet=prof.cv_url))
        if prof.biography:
            c.append(f.literal(ref, "biography_excerpt", prof.biography, locator="profile.bio", snippet=prof.biography))

        positions = prof.positions or ([self._listing_positions[doc.canonical_url]]
                                        if doc.canonical_url in self._listing_positions else [])
        for pos in positions:
            q = {"position_title": pos}
            if prof.staff_category:
                q["staff_category"] = prof.staff_category
            c.append(
                f.relation(
                    ref, "AFFILIATED_WITH", self.site_unit_ref(), locator="profile.position",
                    snippet=pos, qualifiers=q,
                )
            )
        if not positions:
            c.append(f.relation(ref, "AFFILIATED_WITH", self.site_unit_ref(),
                                locator="profile.site", snippet=doc.page_title or doc.canonical_url,
                                confidence=0.7))
        for unit_name in prof.unit_lines:
            uref = self.named_unit_ref(unit_name)
            res.records.append(SourceRecord(ref=uref, label=unit_name, document_id=doc.document_id,
                                            hints={"parent_site": self.entry.source_id}))
            c.append(f.literal(uref, "name", unit_name, locator="profile.unit", snippet=unit_name))
            c.append(f.relation(uref, "PART_OF", self.site_unit_ref(), locator="profile.unit",
                                snippet=unit_name, confidence=0.8))
            c.append(f.relation(ref, "MEMBER_OF", uref, locator="profile.unit", snippet=unit_name))
        for area in prof.research_areas:
            c.append(
                f.literal(ref, "stated_research_area", area, locator="profile.section.kutatasi_teruletek",
                          snippet=area, qualifiers={"authorship": "profile page; author not stated"})
            )
        for pm in prof.projects:
            pref = self.project_ref(pm.url, pm.title)
            res.records.append(SourceRecord(ref=pref, label=pm.title, document_id=doc.document_id,
                                            hints={"url": pm.url} if pm.url else {}))
            c.append(f.literal(pref, "title", pm.title, locator="profile.section.projektek", snippet=pm.snippet))
            kw = {}
            if pm.period_from or pm.period_until:
                kw = dict(valid_from=pm.period_from, valid_until=pm.period_until,
                          temporal_basis=TemporalBasis.EXPLICIT)
            q = {}
            if pm.role:
                q["role"] = pm.role
            if pm.stated_lead:
                q["stated_lead"] = pm.stated_lead  # a name only; never resolved to a person here
            c.append(f.relation(ref, "PARTICIPATES_IN", pref, locator="profile.section.projektek",
                                snippet=pm.snippet, confidence=0.85, qualifiers=q, **kw))
            if pm.role and P.PROJECT_LEAD_LABEL_RE.match(pm.role):
                c.append(f.relation(ref, "PRINCIPAL_INVESTIGATOR_OF", pref, locator="profile.section.projektek",
                                    snippet=pm.snippet, confidence=0.85, **kw))
        return res

    def parse_unit(self, page: Page) -> ParseResult:
        doc = page.document
        f = ClaimFactory(doc, "tk.unit", self.parser_version)
        res = ParseResult()
        unit = P.parse_unit(page.text, doc.final_url, self.aliases)
        uref = local_ref(self.entry, EntityType.ORG_UNIT, doc.canonical_url)
        spec = next((u for u in self.cfg.get("units", []) if self.url(u["path"]) == doc.canonical_url), {})
        res.records.append(SourceRecord(ref=uref, label=unit.name, document_id=doc.document_id,
                                        hints={"parent_site": self.entry.source_id, "url": doc.canonical_url}))
        c = res.claims
        c.append(f.literal(uref, "name", unit.name, locator="unit.h1", snippet=unit.name))
        c.append(f.literal(uref, "website", doc.canonical_url, locator="document.url", snippet=doc.canonical_url))
        if spec.get("unit_type"):
            c.append(f.literal(uref, "unit_type", spec["unit_type"], locator="registry.unit_type",
                               snippet=f"registry: {spec['unit_type']}", confidence=0.8))
        if unit.description:
            c.append(f.literal(uref, "description", unit.description, locator="unit.description", snippet=unit.description))
        c.append(f.relation(uref, "PART_OF", self.site_unit_ref(), locator="unit.site", snippet=doc.page_title or unit.name))
        for link, label in unit.leaders:
            pref = self.person_ref(link.url)
            res.records.append(SourceRecord(ref=pref, label=link.text, document_id=doc.document_id,
                                            hints={"profile_url": link.url, "site": self.owner_source(link.url)}))
            c.append(f.literal(pref, "name", link.text, locator="unit.leader", snippet=link.text))
            c.append(f.relation(pref, "LEADS", uref, locator="unit.leader", snippet=f"{label}: {link.text}",
                                qualifiers={"role": label}))
            c.append(f.relation(pref, "MEMBER_OF", uref, locator="unit.leader", snippet=f"{label}: {link.text}"))
        for link in unit.members:
            pref = self.person_ref(link.url)
            res.records.append(SourceRecord(ref=pref, label=link.text, document_id=doc.document_id,
                                            hints={"profile_url": link.url, "site": self.owner_source(link.url)}))
            c.append(f.literal(pref, "name", link.text, locator="unit.members", snippet=link.text))
            c.append(f.relation(pref, "MEMBER_OF", uref, locator="unit.members", snippet=link.text))
        return res

    def parse_project(self, page: Page) -> ParseResult:
        doc = page.document
        f = ClaimFactory(doc, "tk.project", self.parser_version)
        res = ParseResult()
        proj = P.parse_project(page.text, doc.final_url, self.aliases)
        pref = self.project_ref(doc.canonical_url, proj.title)
        self._emit_project(res, f, doc, pref, proj, "project", title_locator="project.h1")
        c = res.claims
        c.append(f.literal(pref, "website", doc.canonical_url, locator="document.url", snippet=doc.canonical_url))
        if status := self._project_status.get(doc.canonical_url):
            c.append(f.literal(pref, "status_label", status, locator="listing.category", snippet=status))
        if proj.description:
            c.append(f.literal(pref, "abstract", proj.description, locator="project.description", snippet=proj.description))
        c.append(f.relation(pref, "HOSTED_BY", self.site_unit_ref(), locator="project.site",
                            snippet=doc.page_title or proj.title, confidence=0.85))
        return res

    def parse_project_listing(self, page: Page, status: str | None) -> ParseResult:
        """Project lines on a category listing, attributed to the listing page itself."""
        doc = page.document
        f = ClaimFactory(doc, "tk.project_listing", self.parser_version)
        res = ParseResult()
        for proj in P.parse_project_listing(page.text, doc.final_url, self.aliases):
            pref = self.project_ref(proj.url, proj.title)
            self._emit_project(res, f, doc, pref, proj, "listing.article", title_locator="listing.article.title")
            if status:
                res.claims.append(f.literal(pref, "status_label", status, locator="listing.category",
                                            snippet=f"{doc.page_title or ''} {proj.title}".strip()))
        return res

    def _emit_project(self, res: ParseResult, f: ClaimFactory, doc, pref: EntityRef, proj: P.ProjectPage,
                      loc: str, *, title_locator: str) -> None:
        res.records.append(SourceRecord(ref=pref, label=proj.title, document_id=doc.document_id,
                                        hints={k: v for k, v in {"url": proj.url, "grant_id": proj.grant_id}.items() if v}))
        c = res.claims
        c.append(f.literal(pref, "title", proj.title, locator=title_locator, snippet=proj.title))
        if proj.grant_id:
            c.append(f.literal(pref, "grant_id", proj.grant_id, locator=f"{loc}.field.azonosito", snippet=proj.grant_snippet))
        if proj.funder:
            # a bare line above the period ("NKFIH ADVANCED", "Horizon Europe") is the
            # funding scheme as the site labels it; weaker than a labelled field
            c.append(f.literal(pref, "funding_body", proj.funder, locator=f"{loc}.field.funder",
                               snippet=proj.funder_snippet or proj.funder,
                               confidence=0.85 if proj.funder_labelled else 0.7))
        if proj.start:
            c.append(f.literal(pref, "start", proj.start, locator=f"{loc}.field.idotartam",
                               snippet=proj.period_snippet, temporal_basis=TemporalBasis.EXPLICIT))
        if proj.end:
            c.append(f.literal(pref, "end", proj.end, locator=f"{loc}.field.idotartam",
                               snippet=proj.period_snippet, temporal_basis=TemporalBasis.EXPLICIT))
        period = dict(valid_from=proj.start, valid_until=proj.end, temporal_basis=TemporalBasis.EXPLICIT) \
            if proj.start else {}
        for link in proj.leads:
            per = self.person_ref(link.url)
            snip = proj.lead_snippets.get(link.url, f"Kutatásvezető: {link.text}")
            res.records.append(SourceRecord(ref=per, label=link.text, document_id=doc.document_id,
                                            hints={"profile_url": link.url, "site": self.owner_source(link.url)}))
            c.append(f.literal(per, "name", link.text, locator=f"{loc}.field.vezeto", snippet=link.text))
            c.append(f.relation(per, "PRINCIPAL_INVESTIGATOR_OF", pref, locator=f"{loc}.field.vezeto",
                                snippet=snip, **period))
            c.append(f.relation(per, "PARTICIPATES_IN", pref, locator=f"{loc}.field.vezeto",
                                snippet=snip, qualifiers={"role": "kutatásvezető"}, **period))
        for name, line in proj.unlinked_leads:
            # No profile link: a name-only record that resolution will never auto-merge.
            per = self._name_mention(name, pref)
            res.records.append(SourceRecord(ref=per, label=name, document_id=doc.document_id,
                                            hints={"unlinked_mention": True}))
            c.append(f.literal(per, "name", name, locator=f"{loc}.field.vezeto.unlinked", snippet=line, confidence=0.8))
            c.append(f.relation(per, "PRINCIPAL_INVESTIGATOR_OF", pref, locator=f"{loc}.field.vezeto.unlinked",
                                snippet=line, confidence=0.8, assertion_type=AssertionType.INSTITUTIONAL, **period))
        for link in proj.participants:
            per = self.person_ref(link.url)
            res.records.append(SourceRecord(ref=per, label=link.text, document_id=doc.document_id,
                                            hints={"profile_url": link.url, "site": self.owner_source(link.url)}))
            c.append(f.literal(per, "name", link.text, locator=f"{loc}.field.resztvevok", snippet=link.text))
            c.append(f.relation(per, "PARTICIPATES_IN", pref, locator=f"{loc}.field.resztvevok",
                                snippet=link.text, **period))
        for name, role in proj.unlinked_participants:
            per = self._name_mention(name, pref)
            res.records.append(SourceRecord(ref=per, label=name, document_id=doc.document_id,
                                            hints={"unlinked_mention": True}))
            c.append(f.literal(per, "name", name, locator=f"{loc}.field.resztvevok.unlinked",
                               snippet=f"{role}: {name}", confidence=0.8))
            c.append(f.relation(per, "PARTICIPATES_IN", pref, locator=f"{loc}.field.resztvevok.unlinked",
                                snippet=f"{role}: {name}", qualifiers={"role": role}, confidence=0.8,
                                assertion_type=AssertionType.INSTITUTIONAL, **period))

    def _name_mention(self, name: str, project: EntityRef) -> EntityRef:
        # keyed by the project, so the listing and the project page share one mention
        return local_ref(self.entry, EntityType.PERSON, f"name-mention:{slugify(name)}@{project.source_ref}")
