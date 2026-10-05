from datetime import UTC, datetime

from szocatlas.canonical.build import CanonicalDataset
from szocatlas.models import Institution, Person, Relation
from szocatlas.models.enums import EpistemicStatus, InstitutionType, RelationType
from szocatlas.validation.qa import run_checks

NOW = datetime(2026, 10, 4, tzinfo=UTC)


def rel(rid, t, s, o, **kw):
    return Relation(relation_id=rid, type=t, source_id=s, target_id=o,
                    epistemic_status=kw.pop("status", EpistemicStatus.OBSERVED), confidence=0.9,
                    claim_ids=kw.pop("claim_ids", ["c"]), **kw)


def checks(ds):
    return {f.check: f for f in run_checks(ds, [], None)}


def ins(i):
    return Institution(canonical_id=i, label=i, canonical_name=i, institution_type=InstitutionType.UNIVERSITY)


def test_detects_cycles_intervals_orphans_and_missing_provenance():
    ds = CanonicalDataset()
    ds.entities = {"ins_a": ins("ins_a"), "ins_b": ins("ins_b"),
                   "per_x": Person(canonical_id="per_x", label="X", canonical_name="X",
                                   provenance={"canonical_name": ["missing"]})}
    ds.relations = [
        rel("r1", RelationType.PART_OF, "ins_a", "ins_b"),
        rel("r2", RelationType.PART_OF, "ins_b", "ins_a"),
        rel("r3", RelationType.MEMBER_OF, "per_x", "ins_a", valid_from="2020", valid_until="2010"),
    ]
    found = checks(ds)
    assert found["structure.cyclic_hierarchy"].severity == "error"
    assert found["temporal.impossible_interval"].severity == "error"
    assert found["provenance.field_without_claim"].severity == "error"


def test_orphan_person_and_contradictory_positions():
    ds = CanonicalDataset()
    ds.entities = {"per_y": Person(canonical_id="per_y", label="Y", canonical_name="Y",
                                   position_titles=["Tudományos munkatárs (TK SZI)", "Kutatóprofesszor (TK SZI)"])}
    found = checks(ds)
    assert "structure.orphan_person" in found
    assert "conflict.positions" in found


def test_project_titled_with_metadata_is_flagged():
    from szocatlas.models import Project
    ds = CanonicalDataset()
    ds.entities = {i: Project(canonical_id=i, label=t, title=t) for i, t in
                   [("prj_a", "Korábbi projektek:"), ("prj_b", "NKFIH. K147329"), ("prj_c", "Magyar Ifjúság 2016")]}
    found = checks(ds)["parser.project_title_is_metadata"]
    assert found.subjects == ["prj_a", "prj_b"]
