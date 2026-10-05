from datetime import UTC, datetime

from szocatlas.models import Claim, EntityRef, Evidence, SourceRecord
from szocatlas.models.enums import EntityType, EpistemicStatus, ExtractionMethod, MatchStatus
from szocatlas.resolution.matcher import IdentityMap, Overrides, resolve

NOW = datetime(2026, 10, 4, tzinfo=UTC)


def rec(ref, label, anchor="institutional_profile", **hints):
    """A person record; by default from the person's own profile page (an identity anchor)."""
    return SourceRecord(ref=EntityRef(entity_type=EntityType.PERSON, source_ref=ref), label=label,
                        document_id="doc", hints=hints, identity_anchor=anchor)


def mtmt(ref, value):
    return Claim(subject=EntityRef(entity_type=EntityType.PERSON, source_ref=ref), predicate="mtmt_id",
                 value=value, observed_at=NOW, evidence=Evidence(document_id="doc", locator="l", snippet=value),
                 extraction_method=ExtractionMethod.HTML_PARSER, parser="t", parser_version="0",
                 epistemic_status=EpistemicStatus.OBSERVED, confidence=0.9)


A = "tk_recens|https://recens.tk.elte.hu/kutato/kovacs-anna"
B = "tk_szociologia|https://szociologia.tk.elte.hu/kutato/kovacs-anna"
C = "elte_tatk|https://tatk.elte.hu/staff/anna-kovacs"


def run(records, claims=(), overrides=None, tmp_path=None, map_name="map.jsonl"):
    ident = IdentityMap(tmp_path / map_name)
    ids, decisions = resolve(records, list(claims), overrides or Overrides(), ident)
    ident.save()
    return ids, {(d.left, d.right): d for d in decisions}


def test_same_name_is_never_merged_automatically(tmp_path):
    ids, dec = run([rec(A, "Kovács Anna", email_domain="tk.elte.hu"),
                    rec(B, "Kovács Anna", email_domain="tk.elte.hu")], tmp_path=tmp_path)
    assert ids[A] != ids[B]
    d = dec[tuple(sorted((A, B)))]
    assert d.status is MatchStatus.POSSIBLE
    assert d.signals["same_institution_family"] and d.signals["same_profile_slug"]


def test_inverted_name_order_is_a_candidate_not_a_merge(tmp_path):
    ids, dec = run([rec(A, "Kovács Anna"), rec(C, "Anna Kovács")], tmp_path=tmp_path)
    assert ids[A] != ids[C]
    assert dec[tuple(sorted((A, C)))].status is MatchStatus.POSSIBLE


def test_shared_mtmt_and_name_merges(tmp_path):
    ids, dec = run([rec(A, "Kovács Anna"), rec(B, "Kovács Anna")],
                   [mtmt(A, "100"), mtmt(B, "100")], tmp_path=tmp_path)
    assert ids[A] == ids[B]
    assert dec[tuple(sorted((A, B)))].method == "auto:hard_id+name"


def test_shared_mtmt_with_different_names_needs_review(tmp_path):
    ids, dec = run([rec(A, "Kovács Anna"), rec(B, "Szabó Péter")],
                   [mtmt(A, "100"), mtmt(B, "100")], tmp_path=tmp_path)
    assert ids[A] != ids[B]
    assert dec[tuple(sorted((A, B)))].status is MatchStatus.POSSIBLE


def test_conflicting_mtmt_rejects_same_name(tmp_path):
    ids, dec = run([rec(A, "Kovács Anna"), rec(B, "Kovács Anna")],
                   [mtmt(A, "100"), mtmt(B, "200")], tmp_path=tmp_path)
    assert ids[A] != ids[B]
    assert dec[tuple(sorted((A, B)))].status is MatchStatus.REJECTED


def test_manual_overrides_win(tmp_path):
    ov = Overrides(same_as=[(A, B)])
    ids, _ = run([rec(A, "Kovács Anna"), rec(B, "Kovács Anna")], overrides=ov, tmp_path=tmp_path)
    assert ids[A] == ids[B]
    ov = Overrides(not_same_as=[(A, B)])
    ids, dec = run([rec(A, "Kovács Anna"), rec(B, "Kovács Anna")], [mtmt(A, "1"), mtmt(B, "1")],
                   overrides=ov, tmp_path=tmp_path, map_name="m2.jsonl")
    assert ids[A] != ids[B]
    assert dec[tuple(sorted((A, B)))].method == "manual:not_same_as"


def test_rejection_blocks_transitive_merge(tmp_path):
    # A=B by MTMT, B=C by manual, but A!=C manually: C must not join the A/B cluster
    ov = Overrides(same_as=[(B, C)], not_same_as=[(A, C)])
    ids, _ = run([rec(A, "Kovács Anna"), rec(B, "Kovács Anna"), rec(C, "Kovács Anna")],
                 [mtmt(A, "1"), mtmt(B, "1")], overrides=ov, tmp_path=tmp_path)
    assert ids[A] == ids[B]
    assert ids[C] != ids[A]


def test_canonical_ids_are_stable_across_runs_and_new_sources(tmp_path):
    first, _ = run([rec(A, "Kovács Anna")], tmp_path=tmp_path)
    second, _ = run([rec(C, "Anna Kovács"), rec(A, "Kovács Anna")], tmp_path=tmp_path)
    assert first[A] == second[A]
    # merging a new record into an existing person keeps the existing id
    third, _ = run([rec(A, "Kovács Anna"), rec(B, "Kovács Anna")], [mtmt(A, "1"), mtmt(B, "1")],
                   tmp_path=tmp_path)
    assert third[A] == third[B] == first[A]


def test_records_without_identity_evidence_get_no_person_id(tmp_path):
    # ADR-0006: a name on someone else's page is a mention, not a Person
    M = "tk_szociologia|name-mention:kovacs-anna@tk_szociologia|https://szociologia.tk.elte.hu/p"
    ids, dec = run([rec(A, "Kovács Anna"), rec(M, "Kovács Anna", anchor=None)], tmp_path=tmp_path)
    assert A in ids and M not in ids
    assert dec[tuple(sorted((A, M)))].status is MatchStatus.POSSIBLE  # stays a review candidate


def test_hard_id_alone_anchors_an_identity(tmp_path):
    ids, _ = run([rec(C, "Kovács Anna", anchor=None)], [mtmt(C, "100")], tmp_path=tmp_path)
    assert ids[C].startswith("per_")


def test_retired_mentions_leave_the_identity_map(tmp_path):
    M = "tk_szociologia|name-mention:kovacs-anna@tk_szociologia|https://szociologia.tk.elte.hu/p"
    path = tmp_path / "map.jsonl"
    path.write_text('{"source_ref": "%s", "entity_type": "Person", "canonical_id": "per_0000000000", '
                    '"assigned_at": "2026-10-04T00:00:00+00:00"}\n' % M, encoding="utf-8")
    run([rec(A, "Kovács Anna"), rec(M, "Kovács Anna", anchor=None)], tmp_path=tmp_path)
    assert M not in path.read_text(encoding="utf-8")
