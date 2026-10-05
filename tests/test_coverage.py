"""Coverage QA (#12, ADR-0009): how much of the in-scope sources a release covers, apart from whether it is consistent.

Built on the same KI scenario as test_discovery: one real profile that links four project pages, one of which is
fetched in the "after" release.
"""

import json
from types import SimpleNamespace

from szocatlas.validation import coverage as C

from test_discovery import KI_ID, OTHER_LINKS, PARLAMENTI, ingest_and_build, load

PAGE = {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"}


def cov(out):
    return json.loads((out / "coverage.json").read_text(encoding="utf-8"))


def walk_shares(node, path=""):
    """Every {"n", "of", "rate"} dict in the report."""
    if isinstance(node, dict):
        if set(node) == {"n", "of", "rate"}:
            yield path, node
        else:
            for k, v in node.items():
                yield from walk_shares(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_shares(v, f"{path}[{i}]")


def test_share_always_carries_its_denominator():
    assert C.share(1, 4) == {"n": 1, "of": 4, "rate": 0.25}
    assert C.share(0, 0) == {"n": 0, "of": 0, "rate": None}  # no denominator, no rate


def test_every_reported_rate_names_its_denominator(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", PAGE)
    shares = list(walk_shares(cov(out)))
    assert len(shares) > 20
    for path, s in shares:
        assert 0 <= s["n"] <= s["of"] or s["of"] == 0, path
        assert s["rate"] == (round(s["n"] / s["of"], 3) if s["of"] else None), path
    md = (out / "coverage.md").read_text(encoding="utf-8")
    assert "Every figure names its denominator" in md and "1 of 4" in md  # "1 of 4 linked project pages were fetched"


def test_linked_pages_not_fetched_go_down_when_the_page_is_added(workdir, registry):
    before, _ = ingest_and_build(workdir, registry, "before", None)
    after, _ = ingest_and_build(workdir, registry, "after", PAGE)
    b = cov(before)["discovery"]["project_links"]
    a = cov(after)["discovery"]["project_links"]
    assert b["in_scope"]["fetched"] == {"n": 0, "of": 4, "rate": 0.0}
    assert a["in_scope"]["fetched"] == {"n": 1, "of": 4, "rate": 0.25}
    assert b["in_scope"]["by_status"] == {"not_attempted": 4}
    assert a["in_scope"]["by_status"] == {"fetch_failed": 3, "fetched": 1}
    ki = a["in_scope"]["by_source"][KI_ID]
    assert (ki["urls"], ki["fetched"], ki["not_fetched"]) == (4, 1, 3)
    assert ki["fetched_share"] == {"n": 1, "of": 4, "rate": 0.25}
    # the same figure, per URL, with the reason
    detail = {r["url"]: r for r in a["urls_detail"]}
    assert detail[PARLAMENTI]["status"] == "fetched" and detail[PARLAMENTI]["resolved_mentions"] == 1
    assert detail[OTHER_LINKS[0]]["status"] == "fetch_failed" and detail[OTHER_LINKS[0]]["reason"]
    assert detail[PARLAMENTI]["researchers"] == 1 and detail[PARLAMENTI]["owner_source"] == KI_ID


def test_qa_reports_the_gap_as_a_warning_and_never_as_an_error(workdir, registry):
    out, findings = ingest_and_build(workdir, registry, "r", PAGE)
    checks = {f.check: f for f in findings}
    f = checks["coverage.linked_project_pages"]
    assert f.severity == "warning" and "1 of 4" in f.message
    assert sorted(f.subjects) == sorted(OTHER_LINKS)
    assert not [f for f in findings if f.severity == "error"]


def test_project_mentions_have_an_explicit_reason_for_staying_unresolved(workdir, registry):
    before, _ = ingest_and_build(workdir, registry, "before", None)
    after, _ = ingest_and_build(workdir, registry, "after", PAGE)
    b = cov(before)["canonicalization"]["project_mentions"]
    a = cov(after)["canonicalization"]["project_mentions"]
    assert b["unresolved_by_category"]["all"]["linked_page_no_discovery_record"] == 4
    assert a["unresolved_by_category"]["all"]["linked_page_fetch_failed"] == 3
    assert "linked_page_no_discovery_record" not in a["unresolved_by_category"]["all"]
    ki = a["by_source"][KI_ID]
    assert ki["resolved"] == b["by_source"][KI_ID]["resolved"] + 1  # URL-exact, once the page exists
    assert ki["resolved_share"] == {"n": ki["resolved"], "of": ki["total"], "rate": round(ki["resolved"] / ki["total"], 3)}
    assert ki["DETERMINISTIC"] + ki.get("HIGH_CONFIDENCE_AUTO", 0) + ki.get("MANUAL_CONFIRMED", 0) == ki["resolved"]
    # every reason is a category the report defines
    for cats in a["unresolved_by_category"].values():
        assert set(cats) <= set(C.UNRESOLVED_CATEGORIES)


def test_unresolved_category_is_derived_from_the_mention_and_the_frontier():
    def mention(url=None, observation="profile_list", status="UNRESOLVED", method=None):
        return SimpleNamespace(linked_url=url, observation=observation,
                               resolution=SimpleNamespace(status=SimpleNamespace(value=status), method=method))

    frontier = {
        "https://ext.example/p": {"decision": "skipped", "scope": "external", "reason": "external_host", "fetch": {}},
        "https://other.tk.hu/p": {"decision": "skipped", "scope": "other_unit_site", "reason": "source_not_enabled", "fetch": {}},
        "https://ki/p": {"decision": "enqueued", "scope": "in_scope", "reason": None,
                         "fetch": {"attempted": True, "error": "HTTP 404"}},
        "https://ki/q": {"decision": "enqueued", "scope": "in_scope", "reason": None,
                         "fetch": {"attempted": True, "error": None}},
        "https://ki/n": {"decision": "skipped", "scope": "in_scope", "reason": "not_project_path", "fetch": {}},
    }
    cat = C.unresolved_category
    assert cat(mention(status="REVIEW_REQUIRED"), frontier) == "identity_review"
    assert cat(mention(method="manual:project_deferred"), frontier) == "deferred_to_ontology"
    # a deferred mention is also held in the review queue: it is counted as deferred, not as an identity question
    assert cat(mention(status="REVIEW_REQUIRED", method="manual:project_deferred"), frontier) == "deferred_to_ontology"
    assert cat(mention(), frontier) == "title_only_no_page_link"
    assert cat(mention("https://ext.example/p"), frontier) == "linked_page_external_site"
    assert cat(mention("https://other.tk.hu/p"), frontier) == "linked_page_other_unit_site"
    assert cat(mention("https://ki/p"), frontier) == "linked_page_fetch_failed"
    assert cat(mention("https://ki/q"), frontier) == "linked_page_fetched_no_project"
    assert cat(mention("https://ki/n"), frontier) == "linked_page_not_project_path"
    assert cat(mention("https://ki/x"), frontier) == "linked_page_no_discovery_record"
    assert cat(mention("https://ki/x", observation="project_listing"), frontier) == "linked_page_not_project_path"
    assert cat(mention("https://nyilvanos.otka-palyazat.hu/index.php?lang=HU&menuid=930&num=142410"),
               frontier) == "linked_page_grant_registry"


def test_parse_coverage_separates_parsed_empty_and_unmapped(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", PAGE)
    parse = cov(out)["parse"]
    proj = parse["by_source"][KI_ID]["project"]
    assert proj["parsed"] == 1 and proj["ok"] == 1 and proj.get("empty", 0) == 0 and proj.get("error", 0) == 0
    assert proj["with_unmapped_labels"] == 1  # narrative section labels no field takes
    assert parse["retrieved_ok"] == parse["with_parse_record"] == 2 and parse["without_parse_record"] == 0
    assert {"page_type": "project", "label": "A kutatás céljai, kérdései", "pages": 1} in parse["unmapped_labels"]
    # a page the parser read but that offered nothing beyond its title is `empty`, not an error
    row = next(r for r in load(out, "parse_report.jsonl") if r["page_type"] == "project")
    assert row["status"] == "ok" and row["fields"]["funder"] is True and row["parser"].startswith("tk/")


def test_field_coverage_denominators_are_the_canonical_entities(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", PAGE)
    f = cov(out)["fields"]
    projects = load(out, "entities/Project.jsonl")
    assert f["projects"]["by_source"]["all"]["total"] == len(projects) == 1
    p = f["projects"]["by_source"][KI_ID]
    assert p["funding_body"] == {"n": 1, "of": 1, "rate": 1.0} and p["grant_id"]["n"] == 1 and p["period"]["n"] == 1
    # a missing optional field is a rate below 100%, never a finding
    persons = f["persons"]["by_source"][KI_ID]
    assert persons["total"] == 1 and persons["orcid"] == {"n": 0, "of": 1, "rate": 0.0}


def test_network_bias_exposes_researchers_without_project_edges(workdir, registry):
    before, _ = ingest_and_build(workdir, registry, "before", None)
    after, _ = ingest_and_build(workdir, registry, "after", PAGE)
    b = cov(before)["network_bias"]["persons_without_project_edges"][KI_ID]
    a = cov(after)["network_bias"]["persons_without_project_edges"][KI_ID]
    assert b["without_project_edges"] == {"n": 1, "of": 1, "rate": 1.0}
    # the reasons are explicit categories: the links were never put on the frontier; one mention states no page
    why = b["by_unresolved_category (persons; one person can have several)"]
    assert why == {"linked_page_no_discovery_record": 1, "title_only_no_page_link": 1}
    assert set(why) <= set(C.UNRESOLVED_CATEGORIES)
    md = (before / "coverage.md").read_text(encoding="utf-8")
    assert "linked_page_no_discovery_record (the link was never put on the frontier): 1" in md
    # Eiler is a participant of the page that was fetched: the edge exists now
    assert a["without_project_edges"] == {"n": 0, "of": 1, "rate": 0.0}
    assert cov(after)["network_bias"]["realised"]["persons_with_project_edges"] == {"n": 1, "of": 1, "rate": 1.0}


def test_seeds_are_sentinels_and_never_enter_a_denominator(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", PAGE)
    c = cov(out)
    assert "not a coverage estimate" in c["sentinels"]["note"]
    assert c["sentinels"]["missing"], "the one-profile world misses most seeds"
    assert c["fields"]["persons"]["by_source"]["all"]["total"] == 1  # seeds did not add to the denominator
    findings = json.loads((out / "quality_report.json").read_text())
    sentinel = next(f for f in findings if f["check"] == "coverage.sentinels_missing")
    assert sentinel["severity"] == "info" and "sentinel" in sentinel["message"]


def test_document_universe_digest_is_stable_and_follows_the_set(workdir, registry):
    a, _ = ingest_and_build(workdir, registry, "a", PAGE)
    b, _ = ingest_and_build(workdir, registry, "b", PAGE)
    c, _ = ingest_and_build(workdir, registry, "c", None)
    sa, sb, sc = (cov(x)["source_set"] for x in (a, b, c))
    assert sa["digest"] == sb["digest"] != sc["digest"]
    assert sa["documents"] == 2 and sc["documents"] == 1
    assert sa["by_source"][KI_ID]["by_page_type"] == {"profile": 1, "project": 1}
    assert sa["by_page_type"] == {"profile": 1, "project": 1}


def test_markdown_report_has_every_layer(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", PAGE)
    md = (out / "coverage.md").read_text(encoding="utf-8")
    for heading in ("## Document universe", "## Discovery", "## Fetch", "## Parse", "## Canonicalisation",
                    "## Field coverage", "## Structural consequences for network analysis", "## Sentinels",
                    "## Blind spots"):
        assert heading in md, heading
    assert "(exposed, not corrected)" in md
    assert "## Blind spots" in md and "no denominator" in md
    qa = (out / "quality_report.md").read_text(encoding="utf-8")
    assert "not whether it is complete" in qa and "coverage.md" in qa
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["coverage"]["in_scope_project_links_fetched"] == {"n": 1, "of": 4, "rate": 0.25}
    assert manifest["source_set"]["documents"] == 2
