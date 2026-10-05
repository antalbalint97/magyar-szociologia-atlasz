"""Analysis-readiness indicators (#17): what the structure of a release can carry.

The arithmetic is tested on a small hand-made release whose ties, weights and components can be counted by
hand; the build integration on a release made from the KI fixtures.
"""

import json
from pathlib import Path

import pytest

from szocatlas.validation import readiness as R

from test_discovery import PARLAMENTI, ingest_and_build

A_HOST, B_HOST = "a.example", "b.example"


def dump(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def person(n: int, host: str) -> dict:
    return {"canonical_id": f"per_{n}", "label": f"Person {n}", "canonical_name": f"Person {n}",
            "identity_evidence": ["institutional_profile"], "position_titles": ["Kutató"],
            "profile_urls": [f"https://{host}/kutato/p{n}"], "source_refs": [f"src_{host[0]}|https://{host}/kutato/p{n}"]}


def project(key: str, host: str = A_HOST) -> dict:
    return {"canonical_id": f"prj_{key}", "label": key, "title": key, "website": f"https://{host}/{key}",
            "source_refs": [f"src_{host[0]}|https://{host}/{key}"], "start": "2020"}


def edge(n: int, key: str, claims: list[str], kind: str = "PARTICIPATES_IN") -> dict:
    return {"relation_id": f"rel_{n}_{key}_{kind}", "type": kind, "source_id": f"per_{n}", "target_id": f"prj_{key}",
            "epistemic_status": "OBSERVED", "claim_ids": claims, "document_ids": ["d1"], "valid_from": None,
            "valid_until": None, "derivation_method": None}


def make_release(tmp_path: Path) -> Path:
    """Persons 1-5 and 11 at site a, 6-10 at site b. Projects: A {1,2,3}, B {1,4}, C {1..8} (large), D {11}, E {9,10}.

    Hand count. Ties: C gives all 28 pairs of 1..8, A and B only repeat pairs of C, E adds (9,10): 29 ties.
    Shared projects: (1,2) (1,3) (2,3) (1,4) share two, the other 24 pairs of C one, (9,10) one.
    Size-discounted weight: C 28/7 = 4, A 3/2 = 1.5, B 1, E 1 = 7.5. Cross-site: 1-5 against 6-8 = 15 pairs.
    Components {1..8} and {9,10}; person 11 has an edge and no tie."""
    root = tmp_path / "rel"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"release_id": "hand", "sources": ["src_a", "src_b"]}))
    dump(root / "documents.jsonl", [{"document_id": "d1", "source_id": "src_a", "url": f"https://{A_HOST}/", "canonical_url": f"https://{A_HOST}/"},
                                    {"document_id": "d2", "source_id": "src_b", "url": f"https://{B_HOST}/", "canonical_url": f"https://{B_HOST}/"}])
    members = {"A": [1, 2, 3], "B": [1, 4], "C": list(range(1, 9)), "D": [11], "E": [9, 10]}
    site = lambda n: B_HOST if 6 <= n <= 10 else A_HOST  # noqa: E731
    dump(root / "entities" / "Person.jsonl", [person(n, site(n)) for n in range(1, 12)])
    dump(root / "entities" / "Project.jsonl", [project(k, B_HOST if k == "E" else A_HOST) for k in members])
    dump(root / "entities" / "Institution.jsonl", [{"canonical_id": "inst_1", "label": "Inst"}])
    dump(root / "entities" / "OrganisationalUnit.jsonl", [{"canonical_id": "unit_1", "label": "Unit"},
                                                          {"canonical_id": "unit_2", "label": "Orphan unit"}])
    rels = [edge(n, k, [f"clm_{n}_{k}"]) for k, ns in members.items() for n in ns]
    rels += [{"relation_id": "rel_aff", "type": "AFFILIATED_WITH", "source_id": "per_1", "target_id": "inst_1",
              "epistemic_status": "OBSERVED", "claim_ids": [], "document_ids": ["d1", "d2"], "valid_from": None, "valid_until": None,
              "derivation_method": None},
             {"relation_id": "rel_part", "type": "PART_OF", "source_id": "unit_1", "target_id": "inst_1",
              "epistemic_status": "OBSERVED", "claim_ids": [], "document_ids": [], "valid_from": None, "valid_until": None,
              "derivation_method": None}]
    dump(root / "relations.jsonl", rels)
    # claims: every edge has an anchored claim (the person's profile) except person 2 on A, who is a name mention
    # resolved by an automatic rule, and person 3 on A, who has both
    page = lambda k: f"src_{'b' if k == 'E' else 'a'}|https://{B_HOST if k == 'E' else A_HOST}/{k}"  # noqa: E731
    claims = []
    for k, ns in members.items():
        for n in ns:
            subject = f"src_{site(n)[0]}|https://{site(n)}/kutato/p{n}"
            claims.append({"claim_id": f"clm_{n}_{k}", "predicate": "PARTICIPATES_IN", "subject": {"source_ref": subject},
                           "object": {"source_ref": page(k)}})
    mention = lambda n, status: {"source_ref": f"src_a|name-mention:p{n}@{page('A')}", "normalized_name": f"person {n}",  # noqa: E731
                                 "source_id": "src_a", "resolution": {"status": status}, "candidates": []}
    # person 2: replace the anchored claim by an auto mention claim; person 3: add one; plus two stated names outside the graph
    claims = [c for c in claims if c["claim_id"] != "clm_2_A"]
    claims.append({"claim_id": "clm_2_A", "predicate": "PARTICIPATES_IN", "subject": {"source_ref": mention(2, "X")["source_ref"]},
                   "object": {"source_ref": page("A")}})
    claims.append({"claim_id": "clm_3_A_auto", "predicate": "PARTICIPATES_IN",
                   "subject": {"source_ref": mention(3, "X")["source_ref"]}, "object": {"source_ref": page("A")}})
    rels = [r | {"claim_ids": r["claim_ids"] + (["clm_3_A_auto"] if r["relation_id"] == "rel_3_A_PARTICIPATES_IN" else [])}
            for r in rels]
    dump(root / "relations.jsonl", rels)
    outside = []
    for n, status in ((21, "UNRESOLVED"), (22, "REVIEW_REQUIRED")):
        outside.append({"claim_id": f"clm_out_{n}", "predicate": "PARTICIPATES_IN",
                        "subject": {"source_ref": mention(n, status)["source_ref"]}, "object": {"source_ref": page("A")}})
    dump(root / "claims.jsonl", claims + outside)
    dump(root / "entities" / "PersonMention.jsonl", [mention(2, "HIGH_CONFIDENCE_AUTO"), mention(3, "HIGH_CONFIDENCE_AUTO"),
                                                     mention(21, "UNRESOLVED"), mention(22, "REVIEW_REQUIRED")])
    dump(root / "matches.jsonl", [])
    return root


@pytest.fixture
def release(tmp_path) -> Path:
    return make_release(tmp_path)


def test_ties_weights_components_and_large_projects_match_a_hand_count(release):
    ind = R.readiness_report(release)["indicators"]
    c1, c2, c3, c4, c5 = (ind[i]["values"] for i in ("C1", "C2", "C3", "C4", "C5"))
    assert (c1["ties"], c1["persons_with_edge"], c1["persons_in_ties"], c1["projects_with_two_or_more"]) == (29, 11, 10, 4)
    assert c1["size_distribution"] == {"1": 1, "2": 2, "3": 1, "4-5": 0, "6-7": 0, "8-9": 1, "10+": 0}
    assert c3["ties_by_shared_projects"] == {"1": 25, "2": 4, "3+": 0, "max": 2}
    assert c3["total_size_discounted_weight"] == 7.5
    big = c2[">=8"]
    assert big["projects"] == 1
    assert (big["ties_through"]["n"], big["ties_through"]["of"]) == (28, 29)
    assert big["ties_only_through"]["n"] == 24  # the four pairs that A or B repeat are not only through C
    assert (big["size_discounted_weight_through"]["n"], big["size_discounted_weight_through"]["of"]) == (4.0, 7.5)
    # persons 5-8 are on C only; 1-4 also share A or B with someone, 9 and 10 tie through E
    assert big["persons_only_tied_through"] == R.share(4, 10)
    assert c2[">=10"]["projects"] == 0 and c2[">=10"]["ties_through"]["n"] == 0
    assert c2[">=10"]["persons_only_tied_through"] == R.share(0, 10)
    assert (c4["ties"]["n"], c4["ties"]["of"], c4["projects_with_a_cross_institute_tie"]) == (15, 29, 1)
    # all 15 cross-site pairs (1-5 against 6-8) run through the large project C and through nothing else
    assert c4["ties_through_the_single_largest_contributor"] == R.share(15, 15)
    assert (c5["count"], c5["largest"], c5["singletons_among_edge_persons"]) == (2, 8, 1)


def test_edge_identity_basis_separates_certain_from_automatic(release):
    b4 = R.readiness_report(release)["indicators"]["B4"]["values"]
    # person 2 on A rests on an automatic mention only; person 3 on A on both; the other edges are anchored
    assert b4["edges"] == 16 and b4["by_basis"] == {"auto_only": 1, "certain": 14, "certain+auto": 1}
    assert b4["auto_only_share"] == R.share(1, 16)


def test_sensitivity_variants_change_the_structure_the_way_the_policy_says(release):
    v = R.readiness_report(release)["sensitivity"]["variants"]
    # strict drops the one edge that rests on an automatic rule only (person 2 on A): ties (2,x) on A stay through C
    assert v["strict_certain_edges_only"]["persons_with_edge"] == 11 and v["strict_certain_edges_only"]["ties"] == 29
    # complete keeps only projects whose stated participants are all in the graph: A has two names outside it
    assert v["complete_projects_only"]["projects_with_two_or_more"] == 3  # B, C, E
    assert v["complete_projects_only"]["ties"] == 29  # C already contains every pair of A
    assert v["default"]["ties"] == 29


def test_participant_subjects_count_those_outside_the_graph(release):
    b3 = R.readiness_report(release)["indicators"]["B3"]["values"]["all"]
    # 16 edges rest on 17 subjects (person 3 on A has a profile and a mention, person 2 only a mention), plus two stated
    # names outside the graph (one UNRESOLVED, one REVIEW_REQUIRED)
    assert b3["subjects"] == 19 and b3["in_graph"] == R.share(17, 19) and b3["outside_graph"] == R.share(2, 19)
    assert b3["by_status"] == {"HIGH_CONFIDENCE_AUTO": 2, "REVIEW_REQUIRED": 1, "UNRESOLVED": 1, "anchored": 15}


def test_per_source_denominators_follow_the_page_hosts(release):
    ind = R.readiness_report(release)["indicators"]
    b1 = ind["B1"]["values"]
    assert (b1["src_a"]["n"], b1["src_a"]["of"]) == (6, 6) and (b1["src_b"]["n"], b1["src_b"]["of"]) == (5, 5)
    assert ind["A1"]["values"]["all"] == {"n": 1, "of": 11, "rate": 0.091}  # only person 1 has an AFFILIATED_WITH
    assert ind["A4"]["values"] == {"n": 1, "of": 2, "rate": 0.5}  # unit_2 is not part of anything
    assert ind["I4"]["values"]["classified"] == {"n": 0, "of": 5, "rate": 0.0}


def test_a_release_from_before_project_mentions_says_so(release):
    i3 = R.readiness_report(release)["indicators"]["I3"]["values"]  # the hand-made release has no ProjectMention
    assert i3["project_mentions_in_release"] is False and i3["by_source"]["all"]["total"] == 0
    assert i3["mentions_per_project"] is None and i3["canonical_projects"] == 5


def test_every_indicator_has_definition_denominator_and_threat():
    for i, spec in R.INDICATORS.items():
        assert spec["layer"] in "ABCDIT" and spec["name"], i
        assert spec["definition"].strip() and spec["denominator"].strip() and spec["threatens"].strip(), i


def test_an_empty_release_is_reported_not_crashed_on(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"release_id": "none"}))
    report = R.readiness_report(root)
    summary = R.readiness_summary(report)
    assert summary["co_participation_ties"] == 0 and summary["person_mentions_outside_the_graph"]["of"] == 0
    assert "## C. Person - person co-participation" in R.render_readiness_markdown(report)


def test_methodology_documents_every_indicator():
    text = (Path(__file__).resolve().parents[1] / "docs" / "methodology.md").read_text(encoding="utf-8")
    for i, spec in R.INDICATORS.items():
        assert f"**{i} {spec['name']}**" in text, f"{i} {spec['name']} is not in docs/methodology.md section 9"


def test_report_names_no_person_and_no_grade(release):
    text = json.dumps(R.readiness_report(release))
    assert "Person 1" not in text  # no person-level output, so nothing reads as a ranking
    md = R.render_readiness_markdown(R.readiness_report(release))
    assert "This is not a verdict" in md and "READY_WITH_RESTRICTIONS" in md  # named as a judgement made elsewhere


def test_build_writes_the_section_and_a_manifest_summary(workdir, registry):
    out, _ = ingest_and_build(workdir, registry, "r", {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"})
    report = json.loads((out / "analysis_readiness.json").read_text(encoding="utf-8"))
    assert set(report["indicators"]) == set(R.INDICATORS) and (out / "analysis_readiness.md").exists()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["analysis_readiness"]["report"] == "analysis_readiness.md"
    assert manifest["analysis_readiness"]["co_participation_ties"] == report["indicators"]["C1"]["values"]["ties"]
    assert report["release_id"] == "r" and report["basis"]["source_set_digest"] == manifest["source_set"]["digest"]
    qa = (out / "quality_report.md").read_text(encoding="utf-8")
    assert "## Analysis readiness" in qa and "analysis_readiness.md" in qa and "not a verdict" in qa


def test_the_report_of_an_unchanged_release_is_byte_identical(workdir, registry):
    pages = {PARLAMENTI: "ki_project_parlamenti_kepviselet.html"}
    first, _ = ingest_and_build(workdir, registry, "r", pages)
    a = [(first / f).read_bytes() for f in ("analysis_readiness.json", "analysis_readiness.md")]
    second, _ = ingest_and_build(workdir, registry, "r", pages)
    assert [(second / f).read_bytes() for f in ("analysis_readiness.json", "analysis_readiness.md")] == a
