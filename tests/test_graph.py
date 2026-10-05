import os
import re

import pytest

from szocatlas.graph.loader import MENTION_REL_TYPES, edge_rows, load_release, node_rows
from szocatlas.models.enums import RelationType
from szocatlas.pipeline import build, ingest_fixtures
from szocatlas.registry import REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tk"


@pytest.fixture
def release(workdir):
    ingest_fixtures(FIXTURES, paths=workdir)
    out, _ = build("g1", paths=workdir, registry_path=workdir.config / "sources.yaml")
    return out


class RecordingSession:
    def __init__(self):
        self.calls = []

    def run(self, query, **params):
        self.calls.append((query, params))


def test_rows_are_deterministic_and_scalar(release):
    assert node_rows(release) == node_rows(release)
    assert edge_rows(release) == edge_rows(release)
    for rows in node_rows(release).values():
        for r in rows:
            for v in r["props"].values():
                assert v is None or isinstance(v, (str, int, float, bool, list))


def test_only_enum_relation_types_reach_cypher(release):
    valid = {t.value for t in RelationType}
    assert set(edge_rows(release)) <= valid


def test_load_is_merge_only_and_repeatable(release):
    s1, s2 = RecordingSession(), RecordingSession()
    load_release(s1, release)
    load_release(s2, release)
    assert s1.calls == s2.calls  # same input -> same statements and parameters
    writes = [q for q, _ in s1.calls if not q.startswith("CREATE ")]
    assert writes and all(" CREATE " not in q for q in writes)  # upserts only
    for q, _ in s1.calls:
        for t in re.findall(r"\[r:(\w+)", q):
            assert t in {x.value for x in RelationType} | set(MENTION_REL_TYPES)


def test_prune_only_when_asked(release):
    s = RecordingSession()
    load_release(s, release)
    assert not any("DETACH DELETE" in q for q, _ in s.calls)
    s = RecordingSession()
    load_release(s, release, prune=True)
    assert any("DETACH DELETE" in q for q, _ in s.calls)


def test_networkx_export_observed_only(release):
    pytest.importorskip("networkx")
    from szocatlas.graph.export import to_networkx
    g = to_networkx(release)
    assert all(d["epistemic_status"] == "OBSERVED" for _, _, d in g.edges(data=True))
    g_all = to_networkx(release, observed_only=False)
    assert g_all.number_of_edges() > g.number_of_edges()


@pytest.mark.neo4j
@pytest.mark.skipif(not os.environ.get("NEO4J_URI"), reason="needs a running Neo4j (NEO4J_URI)")
def test_neo4j_double_load_is_idempotent(release):
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    with driver.session() as s:
        load_release(s, release, prune=True)
        counts1 = s.run("MATCH (n) WITH count(n) AS n MATCH ()-[r]->() RETURN n, count(r) AS r").single()
        load_release(s, release, prune=True)
        counts2 = s.run("MATCH (n) WITH count(n) AS n MATCH ()-[r]->() RETURN n, count(r) AS r").single()
    driver.close()
    assert tuple(counts1) == tuple(counts2)
