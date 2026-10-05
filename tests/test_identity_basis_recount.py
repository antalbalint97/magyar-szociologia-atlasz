"""research/analysis/identity_basis_recount.py is a second implementation of the identity-basis figures of
validation/readiness.py (#17, #37). On the hand-made release of test_readiness, with and without the cases a
source reference cannot tell apart, the two must give the same counts."""

import ast
import importlib.util
from pathlib import Path

import pytest

from szocatlas.validation import readiness as R

from test_readiness import add_cases_a_source_ref_cannot_tell_apart, make_release

SCRIPT = Path(__file__).resolve().parents[1] / "research" / "analysis" / "identity_basis_recount.py"
spec = importlib.util.spec_from_file_location("identity_basis_recount", SCRIPT)
RC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RC)


@pytest.fixture(params=[False, True], ids=["hand-made", "with the cases a source reference cannot tell apart"])
def release(request, tmp_path) -> Path:
    root = make_release(tmp_path)
    if request.param:
        add_cases_a_source_ref_cannot_tell_apart(root)
    return root


def test_the_recount_agrees_with_the_readiness_indicators(release):
    report = R.readiness_report(release)
    ind, variants = report["indicators"], report["sensitivity"]["variants"]
    recount = RC.recount(release)

    b4 = ind["B4"]["values"]
    assert recount["edges"] == b4["edges"]
    assert recount["edges_by_basis"] == b4["by_basis"]

    b3 = ind["B3"]["values"]["all"]
    st = recount["statements"]
    assert (st["total"], st["in_graph"], st["outside_graph"]) == (
        b3["subjects"], b3["in_graph"]["n"], b3["outside_graph"]["n"])
    assert st["by_status"] == b3["by_status"]

    for name, figures in recount["versions"].items():
        for key in ("projects_with_two_or_more", "persons_with_edge", "ties"):
            assert figures[key] == variants[name][key], (name, key)
    assert recount["versions"]["default"]["persons_in_ties"] == ind["C1"]["values"]["persons_in_ties"]


def test_the_recount_is_independent_code():
    imported = set()
    for node in ast.walk(ast.parse(SCRIPT.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert "szocatlas" not in imported


def test_the_recount_prints_the_same_figures_as_json_and_as_text(release, capsys):
    assert RC.main([str(release), "--json"]) == 0
    printed = capsys.readouterr().out
    assert '"edges_by_basis"' in printed and printed.endswith("\n")
    assert RC.main([str(release)]) == 0
    assert "strict_certain_edges_only:" in capsys.readouterr().out
