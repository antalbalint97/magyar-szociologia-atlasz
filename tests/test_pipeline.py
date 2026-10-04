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


def test_unlinked_names_stay_separate_people(release):
    _, out, _ = release
    ppl = people(out)
    assert "Bajomi Anna Zsófia" in ppl
    assert len(ppl["Bajomi Anna Zsófia"]["source_refs"]) == 1


def test_project_dates_are_explicit_on_participation(release):
    _, out, _ = release
    proj = next(p for p in load(out, "entities/Project.jsonl") if p["title"].startswith("Az energiaátmenet"))
    assert (proj["start"], proj["end"], proj["grant_id"]) == ("2024-01-01", "2027-12-31", "NKFIH 146987")
    pi = [r for r in load(out, "relations.jsonl")
          if r["type"] == "PRINCIPAL_INVESTIGATOR_OF" and r["target_id"] == proj["canonical_id"]]
    assert len(pi) == 1 and pi[0]["temporal_basis"] == "EXPLICIT" and pi[0]["valid_from"] == "2024-01-01"


def test_rebuild_is_deterministic(release):
    workdir, out, _ = release
    out2, _ = build("t2", paths=workdir, registry_path=workdir.config / "sources.yaml")
    for name in ("relations.jsonl", "entities/Person.jsonl", "claims.jsonl"):
        a = (out / name).read_text()
        b = (out2 / name).read_text()
        assert a == b, name


def test_disputed_claim_rejection_removes_it(release):
    workdir, out, _ = release
    k = people(out)["Koltai Júlia"]
    claim_id = k["provenance"]["mtmt_id"][0]
    (workdir.review / "disputed_claims.yaml").write_text(
        f"decisions:\n  - {{claim_id: {claim_id}, status: REJECTED, reviewer: test, date: 2026-10-04}}\n")
    out2, _ = build("t3", paths=workdir, registry_path=workdir.config / "sources.yaml")
    assert people(out2)["Koltai Júlia"].get("mtmt_id") is None
