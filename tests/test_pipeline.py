"""End-to-end: fixtures -> staged -> canonical release -> QA (in an isolated workdir)."""

import json

import pytest

from szocatlas.models.enums import EpistemicStatus, RelationType
from szocatlas.pipeline import build, ingest_fixtures

from szocatlas.registry import REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tk"


@pytest.fixture
def release(workdir):
    ingest_fixtures(FIXTURES, paths=workdir)
    out, findings = build("t1", paths=workdir, registry_path=workdir.config / "sources.yaml")
    return workdir, out, findings


def load(out, name):
    return [json.loads(x) for x in (out / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def people(out):
    return {p["label"]: p for p in load(out, "entities/Person.jsonl")}


def test_release_layout_and_manifest(release):
    _, out, _ = release
    m = json.loads((out / "manifest.json").read_text())
    assert m["dataset_kind"] == "fixture"  # reconstructed fixtures can never pose as a snapshot
    for key in ("generated_at", "schema_version", "sources", "parser_versions", "quality"):
        assert key in m
    for f in ("relations.jsonl", "claims.jsonl", "documents.jsonl", "matches.jsonl", "quality_report.md"):
        assert (out / f).exists()


def test_no_qa_errors_on_fixture_build(release):
    _, _, findings = release
    assert [f for f in findings if f.severity == "error"] == []


def test_every_field_and_relation_is_traceable(release):
    _, out, _ = release
    claims = {c["claim_id"]: c for c in load(out, "claims.jsonl")}
    docs = {d["document_id"] for d in load(out, "documents.jsonl")}
    for f in (out / "entities").glob("*.jsonl"):
        for e in load(out, f"entities/{f.name}"):
            for fieldname, ids in e["provenance"].items():
                assert ids and all(i in claims for i in ids), (e["canonical_id"], fieldname)
    for r in load(out, "relations.jsonl"):
        assert r["claim_ids"] and all(i in claims for i in r["claim_ids"])
    assert all(c["evidence"]["document_id"] in docs for c in claims.values())


def test_koltai_is_captured_via_css_recens(release):
    _, out, _ = release
    ppl = people(out)
    k = ppl["Koltai Júlia"]
    assert k["mtmt_id"] == "10031086"
    units = {u["canonical_id"]: u for u in load(out, "entities/OrganisationalUnit.jsonl")}
    insts = {i["canonical_id"]: i for i in load(out, "entities/Institution.jsonl")}
    rels = load(out, "relations.jsonl")
    aff = [r for r in rels if r["source_id"] == k["canonical_id"] and r["type"] == "AFFILIATED_WITH"]
    assert len(aff) == 1
    unit = units[aff[0]["target_id"]]
    assert "CSS-RECENS" in unit["label"]
    # the unit hangs under TK, which hangs under ELTE
    parent = next(r["target_id"] for r in rels if r["source_id"] == unit["canonical_id"] and r["type"] == "PART_OF")
    assert insts[parent]["canonical_name"] == "ELTE Társadalomtudományi Kutatóközpont"
    # current-page affiliation is observed-at, not a timeless fact and not an invented interval
    assert aff[0]["temporal_basis"] == "OBSERVED_AT"
    assert aff[0]["valid_from"] is None and aff[0]["valid_until"] is None
    # listing + profile evidence aggregated on one edge, both position strings kept
    assert len(aff[0]["claim_ids"]) == 2
    assert "Kutatóprofesszor (TK Recens)" in aff[0]["qualifiers"]["position_title"]


def test_derived_topics_are_marked_and_point_to_evidence(release):
    _, out, _ = release
    f = people(out)["Feischmidt Margit"]
    claims = {c["claim_id"]: c for c in load(out, "claims.jsonl")}
    topics = {t["canonical_id"]: t for t in load(out, "entities/ResearchTopic.jsonl")}
    rels = [r for r in load(out, "relations.jsonl")
            if r["source_id"] == f["canonical_id"] and r["type"] == RelationType.WORKS_ON_TOPIC]
    keys = {topics[r["target_id"]]["key"] for r in rels}
    assert {"roma_studies", "ethnicity", "nationalism", "migration"} <= keys
    assert "social_mobility" not in keys  # "transznacionális mobilitás" is migration, not mobility
    for r in rels:
        assert r["epistemic_status"] == EpistemicStatus.DERIVED
        assert r["derivation_method"].startswith("taxonomy_keyword_map/")
        for cid in r["claim_ids"]:
            src = claims[claims[cid]["derived_from"][0]]
            assert src["predicate"] == "stated_research_area" and src["epistemic_status"] == "OBSERVED"


def mentions(out):
    return load(out, "entities/PersonMention.jsonl")


def test_unlinked_names_are_mentions_not_people(release):
    # ADR-0006: a name without identity evidence is a PersonMention, never a Person
    _, out, _ = release
    assert "Bajomi Anna Zsófia" not in people(out)
    bajomi = [m for m in mentions(out) if m["stated_name"] == "Bajomi Anna Zsófia"]
    assert bajomi and all(m["resolution"]["status"] == "UNRESOLVED" for m in bajomi)
    assert all(m["linked_profile_url"] is None and m["context"] for m in bajomi)


def test_every_person_has_identity_evidence(release):
    _, out, _ = release
    assert all(p["identity_evidence"] for p in people(out).values())


def test_linked_mentions_resolve_deterministically_to_the_profile(release):
    _, out, _ = release
    k = people(out)["Koltai Júlia"]
    linked = [m for m in mentions(out) if m["resolution"].get("person_id") == k["canonical_id"]]
    assert linked  # the listing page links her profile
    for m in linked:
        assert m["resolution"]["status"] == "DETERMINISTIC" and m["resolution"]["method"] == "profile_url"
        assert m["linked_profile_url"] in k["profile_urls"]
        assert m["source_url"] not in k["profile_urls"]  # her own page is the identity, not a mention


def test_manifest_reports_raw_and_canonical_person_counts(release):
    _, out, _ = release
    c = json.loads((out / "manifest.json").read_text())["counts"]
    assert c["persons"]["canonical"] == len(people(out))
    assert c["person_mentions"]["total"] == len(mentions(out))
    assert c["person_mentions"]["resolved"] + c["person_mentions"]["unresolved"] == c["person_mentions"]["total"]


def test_project_dates_are_explicit_on_participation(release):
    _, out, _ = release
    proj = next(p for p in load(out, "entities/Project.jsonl") if p["title"].startswith("Az energiaátmenet"))
    assert (proj["start"], proj["end"], proj["grant_id"]) == ("2024-01-01", "2027-12-31", "NKFIH 146987")
    pi = [r for r in load(out, "relations.jsonl")
          if r["type"] == "PRINCIPAL_INVESTIGATOR_OF" and r["target_id"] == proj["canonical_id"]]
    # the lead is named without a profile link: a mention, so no canonical PI edge yet
    assert pi == []
    lead = [(m, cx) for m in mentions(out) for cx in m["context"]
            if cx["relation"] == "PRINCIPAL_INVESTIGATOR_OF" and cx["target_id"] == proj["canonical_id"]]
    assert len(lead) == 1
    m, cx = lead[0]
    assert m["resolution"]["status"] == "UNRESOLVED"
    assert cx["valid_from"] == "2024-01-01"


def test_rebuild_is_deterministic(release):
    workdir, out, _ = release
    out2, _ = build("t2", paths=workdir, registry_path=workdir.config / "sources.yaml")
    for name in ("relations.jsonl", "entities/Person.jsonl", "claims.jsonl"):
        a = (out / name).read_text()
        b = (out2 / name).read_text()
        assert a == b, name
    # mention ids, context and decisions are stable; only the decision timestamp moves
    def strip(rows):
        return [{**r, "resolution": {**r["resolution"], "decided_at": None}} for r in rows]
    assert strip(mentions(out)) == strip(mentions(out2))


def test_rebuilding_a_release_id_keeps_no_entity_file_the_build_did_not_write(release):
    """#41: entities/ is build output, so a type with no rows in this build must not keep the last build's file."""
    workdir, out, _ = release
    files = {f.name for f in (out / "entities").glob("*.jsonl")}
    assert {"Person.jsonl", "Project.jsonl", "PersonMention.jsonl", "ProjectMention.jsonl"} <= files
    persons = (out / "entities" / "Person.jsonl").read_text()
    # the same id from a selection with no staged source: no persons, projects or mentions at all
    again, _ = build("t1", source_ids=["no_such_source"], paths=workdir, registry_path=workdir.config / "sources.yaml")
    assert again == out
    manifest = json.loads((out / "manifest.json").read_text())
    on_disk = {f.stem for f in (out / "entities").glob("*.jsonl")}
    assert on_disk == set(manifest["entities"])
    assert not on_disk & {"Person", "Project", "PersonMention", "ProjectMention"}
    # the full source set again restores the same files, byte for byte
    build("t1", paths=workdir, registry_path=workdir.config / "sources.yaml")
    assert {f.name for f in (out / "entities").glob("*.jsonl")} == files
    assert (out / "entities" / "Person.jsonl").read_text() == persons


def test_disputed_claim_rejection_removes_it(release):
    workdir, out, _ = release
    k = people(out)["Koltai Júlia"]
    claim_id = k["provenance"]["mtmt_id"][0]
    (workdir.review / "disputed_claims.yaml").write_text(
        f"decisions:\n  - {{claim_id: {claim_id}, status: REJECTED, reviewer: test, date: 2026-10-04}}\n")
    out2, _ = build("t3", paths=workdir, registry_path=workdir.config / "sources.yaml")
    assert people(out2)["Koltai Júlia"].get("mtmt_id") is None
