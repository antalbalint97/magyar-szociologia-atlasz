"""Canonical choice between dates of different precision (#16, ADR-0009).

Month-name periods are read at month precision ("2021-06"); the same project's listing may state the day
("2021-06-25"). That is one date at two precisions, not a conflict.
"""

from datetime import UTC, datetime

from szocatlas.canonical.build import PARTIAL_DATE_FIELDS, _choose
from szocatlas.models import Claim, EntityRef, Evidence
from szocatlas.models.enums import EntityType, EpistemicStatus, ExtractionMethod

NOW = datetime(2026, 10, 5, tzinfo=UTC)
PROJECT = EntityRef(entity_type=EntityType.PROJECT, source_ref="tk_kisebbsegkutato|https://kisebbsegkutato.tk.elte.hu/x")


def claim(value, doc="doc_1", locator="project.period"):
    return Claim(subject=PROJECT, predicate="start", value=value, observed_at=NOW,
                 evidence=Evidence(document_id=doc, locator=locator, snippet=str(value)),
                 extraction_method=ExtractionMethod.HTML_PARSER, parser="t", parser_version="0",
                 epistemic_status=EpistemicStatus.OBSERVED, confidence=0.9)


def values(conflicts):
    return sorted(c.value for c in conflicts)


def test_only_start_and_end_are_compared_by_precision():
    assert PARTIAL_DATE_FIELDS == {"start", "end"}


def test_a_coarser_date_agrees_with_the_finer_date_it_prefixes():
    chosen, conflicts = _choose([claim("2021-06", "doc_1"), claim("2021-06-25", "doc_2")], partial_dates=True)
    assert chosen == "2021-06-25" and conflicts == []  # the more precise statement is kept
    chosen, conflicts = _choose([claim("2021", "doc_1"), claim("2021-06", "doc_2")], partial_dates=True)
    assert chosen == "2021-06" and conflicts == []


def test_without_the_flag_precision_still_counts_as_a_difference():
    chosen, conflicts = _choose([claim("2021-06", "doc_1"), claim("2021-06-25", "doc_2")])
    assert len(conflicts) == 2  # other fields are compared as before


def test_different_dates_still_conflict():
    chosen, conflicts = _choose([claim("2021-06-25", "doc_1"), claim("2021-07-01", "doc_2")], partial_dates=True)
    assert values(conflicts) == ["2021-06-25", "2021-07-01"]
    # a month that is not a prefix of the other date is a disagreement, not a precision difference
    chosen, conflicts = _choose([claim("2021-06", "doc_1"), claim("2021-07-01", "doc_2")], partial_dates=True)
    assert values(conflicts) == ["2021-06", "2021-07-01"]


def test_a_coarse_date_that_two_finer_dates_extend_agrees_with_neither():
    chosen, conflicts = _choose([claim("2021", "doc_1"), claim("2021-06", "doc_2"), claim("2021-12", "doc_3")],
                                partial_dates=True)
    assert values(conflicts) == ["2021", "2021-06", "2021-12"]


def test_a_prefix_must_end_at_a_date_part():
    # a longer string that merely begins with the shorter one is not a finer date of it; only "2021-06-" is
    chosen, conflicts = _choose([claim("2021-06"), claim("2021-0615")], partial_dates=True)
    assert len(conflicts) == 2
