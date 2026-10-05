from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from szocatlas.models import Claim, EntityRef, Evidence, Person, Topic
from szocatlas.models.enums import EntityType, EpistemicStatus, ExtractionMethod

NOW = datetime(2026, 10, 4, tzinfo=UTC)
P = EntityRef(entity_type=EntityType.PERSON, source_ref="tk_recens|https://recens.tk.elte.hu/kutato/x")
EV = Evidence(document_id="doc_1", locator="profile.h1", snippet="X Y")


def claim(**kw):
    base = dict(subject=P, predicate="name", value="X Y", observed_at=NOW, evidence=EV,
                extraction_method=ExtractionMethod.HTML_PARSER, parser="t", parser_version="0",
                epistemic_status=EpistemicStatus.OBSERVED, confidence=0.9)
    return Claim(**(base | kw))


def test_claim_id_is_deterministic():
    assert claim().claim_id == claim().claim_id
    assert claim().claim_id != claim(value="Z").claim_id


def test_claim_needs_exactly_one_of_value_or_object():
    with pytest.raises(ValidationError):
        claim(value=None)
    with pytest.raises(ValidationError):
        claim(object=P)


def test_non_observed_claims_need_derivation_method():
    with pytest.raises(ValidationError):
        claim(epistemic_status=EpistemicStatus.INFERRED)
    assert claim(epistemic_status=EpistemicStatus.INFERRED, derivation_method="x").derivation_method


def test_llm_output_is_never_observed_fact():
    with pytest.raises(ValidationError, match="LLM"):
        claim(extraction_method=ExtractionMethod.LLM_ASSISTED)
    ok = claim(extraction_method=ExtractionMethod.LLM_ASSISTED,
               epistemic_status=EpistemicStatus.INFERRED, derivation_method="llm-classifier v0")
    assert ok.epistemic_status is EpistemicStatus.INFERRED


@pytest.mark.parametrize("bad", ["2024-1", "24", "2024/01/01", "c. 1980"])
def test_dates_are_partial_iso_only(bad):
    with pytest.raises(ValidationError):
        claim(valid_from=bad)


def test_interval_order():
    with pytest.raises(ValidationError):
        claim(valid_from="2020", valid_until="2019")
    assert claim(valid_from="2019", valid_until="2019-06").valid_until == "2019-06"


def test_snippets_are_bounded():
    long = Evidence(document_id="d", locator="l", snippet="a " * 1000)
    assert len(long.snippet) <= 600


def test_canonical_id_prefix_enforced():
    Person(canonical_id="per_0123456789", label="X", canonical_name="X")
    with pytest.raises(ValidationError):
        Person(canonical_id="ins_0123456789", label="X", canonical_name="X")


def test_topic_and_method_are_distinct_types():
    from szocatlas.models import Method
    assert Topic.entity_type is EntityType.TOPIC
    assert Method.entity_type is EntityType.METHOD
    Method(canonical_id="met_1", label="Network analysis", key="network_analysis",
           name_en="Network analysis", name_hu="Hálózatelemzés")
    with pytest.raises(ValidationError):
        Method(canonical_id="top_1", label="x", key="x", name_en="x", name_hu="x")


def test_data_dictionary_is_current():
    from szocatlas.datadict import TARGET, render
    assert TARGET.read_text(encoding="utf-8") == render(), "run: python -m szocatlas.datadict"
