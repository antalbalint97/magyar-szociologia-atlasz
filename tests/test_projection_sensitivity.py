"""research/analysis/projection_sensitivity.py (#17): the projection weights, the agreement measures and the
determinism of the report, on the hand-made release of test_readiness (counts there are done by hand)."""

import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("networkx")

from test_readiness import A_HOST, dump, make_release, person  # noqa: E402  (the hand-made release, counted by hand there)

SCRIPT = Path(__file__).resolve().parents[1] / "research" / "analysis" / "projection_sensitivity.py"
spec = importlib.util.spec_from_file_location("projection_sensitivity", SCRIPT)
PS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PS)



@pytest.fixture
def release(tmp_path) -> Path:
    return make_release(tmp_path)


# project -> Persons of the hand-made release: A {1,2,3}, B {1,4}, C {1..8}, D {11}, E {9,10}
MEM = {"A": {"p1", "p2", "p3"}, "B": {"p1", "p4"}, "C": {f"p{n}" for n in range(1, 9)}, "D": {"p11"}, "E": {"p9", "p10"}}


def test_the_three_weightings_of_one_projection():
    unweighted, count, discounted = (PS.projection(MEM, w) for w in PS.WEIGHTINGS)
    # 28 pairs of C, A and B repeat pairs of C except (1,4)... which C also has: 29 ties in all with E's (9,10)
    assert unweighted.number_of_edges() == count.number_of_edges() == discounted.number_of_edges() == 29
    assert sum(d["weight"] for *_, d in unweighted.edges(data=True)) == 29
    assert sum(d["weight"] for *_, d in count.edges(data=True)) == 33  # 28 + 3 + 1 + 1 shared projects over pairs
    assert round(sum(d["weight"] for *_, d in discounted.edges(data=True)), 6) == 7.5  # 28/7 + 3/2 + 1 + 1
    assert count["p1"]["p2"]["weight"] == 2  # A and C
    assert round(discounted["p1"]["p2"]["weight"], 6) == round(1 / 2 + 1 / 7, 6)
    assert set(unweighted) == {f"p{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)}  # p11 stays, as an isolate


def test_size_discounted_strength_is_the_number_of_projects_with_two_or_more_persons():
    g = PS.projection(MEM, "size_discounted")
    strength = dict(g.degree(weight="weight"))
    assert round(strength["p1"], 9) == 3  # A, B, C
    assert round(strength["p11"], 9) == 0  # alone on D
    assert round(strength["p9"], 9) == round(strength["p10"], 9) == 1  # E only
    assert round(strength["p8"], 9) == 1  # C only


def test_removing_large_projects_keeps_the_persons_and_drops_their_ties():
    g = PS.projection(MEM, "unweighted", drop_from=8)  # C goes
    assert g.number_of_edges() == 5  # (1,2) (1,3) (2,3) from A, (1,4) from B, (9,10) from E
    assert g.number_of_nodes() == 11  # nobody leaves the person universe: p5-p8 become isolates


def test_spearman_nmi_and_the_top_set_do_what_they_say():
    a = {"x": 1.0, "y": 2.0, "z": 3.0, "w": 4.0}
    assert PS.spearman(a, a) == 1.0
    assert PS.spearman(a, {k: -v for k, v in a.items()}) == -1.0
    assert PS.spearman(a, {k: 5.0 for k in a}) is None  # no spread, no correlation
    assert PS.nmi({"x": 0, "y": 0, "z": 1, "w": 1}, {"x": "u", "y": "u", "z": "v", "w": "v"}) == 1.0  # relabelled
    assert PS.nmi({"x": 0, "y": 0, "z": 1, "w": 1}, {"x": 0, "y": 1, "z": 0, "w": 1}) == 0.0  # independent
    scores = {f"s{i}": v for i, v in enumerate([3, 2, 2, 1, 0, 0, 0, 0, 0, 0])}
    assert len(PS.top_set(scores, set(scores), 0.2)) == 3  # the tie at the cut-off keeps both tied persons
    assert PS.top_set({"a": 0.0, "b": 0.0}, {"a", "b"}) == set()  # a zero score is never in the top


def test_ranks_share_the_mean_rank_of_a_tie():
    assert PS._ranks([5, 1, 1, 9]) == [3.0, 1.5, 1.5, 4.0]


def test_report_agrees_with_the_readiness_indicators_and_is_deterministic(release):
    from szocatlas.validation.readiness import readiness_report

    first = PS.sensitivity(release, seeds=3)
    again = PS.sensitivity(release, seeds=3)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    ind = readiness_report(release)["indicators"]
    w = first["weightings"]["unweighted"]
    assert w["ties"] == ind["C1"]["values"]["ties"] == 29
    assert w["ties_across_institutes"] == ind["C4"]["values"]["ties"]["n"] == 15  # the same definition as C4
    assert (w["components"], w["largest_component"]) == (ind["C5"]["values"]["count"], ind["C5"]["values"]["largest"])
    assert first["weightings"]["size_discounted"]["total_weight"] == ind["C3"]["values"]["total_size_discounted_weight"]
    assert first["size_discounted_strength_equals_projects_with_two_or_more_persons"] is True
    for name, variant in readiness_report(release)["sensitivity"]["variants"].items():
        if name != "default":
            assert first["identity_policy"][name]["ties"] == variant["ties"]


def add_review_mentions(root: Path) -> None:
    """Review mentions on project A of the hand-made release (p22 is already there, with no candidate).
    p22: one candidate on another institute, per_9 (on E only); the same name is also seen in a second document (one
    statement, two records). p23: two candidates. p24: its one candidate is rejected. p25: one candidate of the same
    institute with a common surname, already on A. p26: one candidate of the same institute, per_12, who has no project
    edge. p27: one candidate, but it carries no project claim at all."""
    page_a = f"src_a|https://{A_HOST}/A"
    ref = lambda n: f"src_a|name-mention:p{n}@{page_a}"  # noqa: E731
    cand = lambda pid, rejected=False, signals=("NAME_EXACT",), negative=(): {  # noqa: E731
        "person_id": pid, "name_match": "NAME_EXACT", "rejected": rejected, "signals": list(signals),
        "negative_signals": list(negative)}
    other, same = ("NAME_EXACT", "UNIQUE_NAME_IN_FAMILY"), ("NAME_EXACT", "SAME_INSTITUTE", "UNIQUE_NAME_IN_FAMILY")
    record = lambda n, cands, cid: {  # noqa: E731
        "source_ref": ref(n), "normalized_name": f"person {n}", "source_id": "src_a",
        "resolution": {"status": "REVIEW_REQUIRED"}, "candidates": cands,
        "context": [{"relation": "PARTICIPATES_IN", "target_id": "prj_A", "claim_ids": [cid]}] if cid else []}
    path = root / "entities" / "PersonMention.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for r in rows:
        if r["normalized_name"] == "person 22":
            r["candidates"] = [cand("per_9", signals=other, negative=("DIFFERENT_INSTITUTE",))]
    extra = [record(22, [cand("per_9", signals=other, negative=("DIFFERENT_INSTITUTE",))], "clm_review_22_listing"),
             record(23, [cand("per_10"), cand("per_11")], "clm_review_23"),
             record(24, [cand("per_5", rejected=True)], "clm_review_24"),
             record(25, [cand("per_1", signals=same, negative=("COMMON_SURNAME",))], "clm_review_25"),
             record(26, [cand("per_12", signals=same)], "clm_review_26"), record(27, [cand("per_8")], None)]
    dump(path, rows + extra)
    claims = [json.loads(line) for line in (root / "claims.jsonl").read_text(encoding="utf-8").splitlines()]
    claims += [{"claim_id": r["context"][0]["claim_ids"][0], "predicate": "PARTICIPATES_IN", "subject": {"source_ref": r["source_ref"]},
                "object": {"source_ref": page_a}} for r in extra if r["context"]]
    dump(root / "claims.jsonl", claims)
    dump(root / "entities" / "Person.jsonl", [json.loads(line) for line in
                                              (root / "entities" / "Person.jsonl").read_text(encoding="utf-8").splitlines()]
         + [person(12, A_HOST)])


def test_the_review_upper_bound_accepts_only_mentions_with_exactly_one_candidate(release):
    from szocatlas.validation.readiness import ReleaseData, review_candidates_accepted

    add_review_mentions(release)
    mem, info = review_candidates_accepted(ReleaseData(release))
    assert info == {"review_mention_records": 7, "review_statements": 5, "with_one_candidate": 3,
                    "with_several_candidates": 1, "with_no_viable_candidate": 1, "pairs": 3, "new_edges": 2,
                    "persons_gaining_a_first_edge": 1, "projects_gaining_a_person": 1}
    ids = lambda ms: {f"per_{p[1:]}" for p in ms}  # noqa: E731  (the MEM names p1 for per_1)
    assert mem["prj_A"] == {"per_1", "per_2", "per_3", "per_9", "per_12"}
    assert {k: v for k, v in mem.items() if k != "prj_A"} == {f"prj_{k}": ids(v) for k, v in MEM.items() if k != "A"}

    rep = PS.sensitivity(release, seeds=2)
    bound = rep["identity_upper_bound"]["all single-candidate statements accepted"]
    # A gains p9 (site b) and p12: 7 new ties (9-1, 9-2, 9-3, 12-1, 12-2, 12-3, 9-12), 4 of them across the two sites
    assert (bound["persons_with_edge"], bound["ties"], bound["ties_across_institutes"]) == (12, 36, 19)
    assert (bound["components"], bound["largest_component"]) == (1, 11)  # {1..8} and {9, 10} are joined
    assert bound["new_edges"] == 2
    default = rep["weightings"]["unweighted"]
    assert (default["ties"], default["ties_across_institutes"], default["components"]) == (29, 15, 2)  # the baseline is untouched
    assert "all single-candidate statements accepted" not in rep["identity_policy"]  # a bound, not a version
    # where the bound comes from: one kind of review statement at a time (kinds are read from the recorded signals)
    kinds = rep["identity_upper_bound"]
    assert PS.review_kind({"signals": ["NAME_EXACT"], "negative_signals": ["LINK_NAME_MISMATCH"]}) == "a link or name conflict"
    assert (kinds["only: another institute"]["ties"], kinds["only: another institute"]["ties_across_institutes"]) == (32, 18)
    assert kinds["only: same institute"]["ties"] == 32 and kinds["only: same institute"]["ties_across_institutes"] == 15
    assert kinds["only: same institute, common surname"]["ties"] == 29  # its Person is already on the project: nothing new
    assert "only: a link or name conflict" not in kinds  # no such statement in this release


def test_the_upper_bound_is_labelled_and_never_part_of_a_release(release):
    from szocatlas.validation.readiness import readiness_report

    add_review_mentions(release)
    text = PS.render(PS.sensitivity(release, seeds=2))
    assert "Review queue accepted (an upper bound, not a version of the data)" in text
    assert "7 review mention records are 5 distinct (Project, stated name) statements still in review" in text
    assert "By viable candidates: one Person 3 (accepted), several 1 (left out), none 1." in text
    assert "review_mentions_on_a_project" not in json.dumps(readiness_report(release))  # the release says nothing of it


def test_report_names_no_person(release):
    text = json.dumps(PS.sensitivity(release, seeds=2)) + PS.render(PS.sensitivity(release, seeds=2))
    assert "Person 1" not in text and "per_1" not in text
    assert "Do the communities restate the institutes?" in text


def test_a_release_without_project_edges_gets_a_note_not_a_crash(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"release_id": "none"}))
    rep = PS.sensitivity(root)
    assert rep["release_id"] == "none" and "no Person has a project edge" in rep["note"]
    assert "no Person has a project edge" in PS.render(rep)
