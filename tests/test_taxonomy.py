import pytest

from grounding_agent.taxonomy import (
    TAXONOMY,
    FailureCategory,
    category_ids,
    get_category,
)


def test_taxonomy_has_seven_categories():
    """Bucket C added tool_argument_correctness after forensics
    Finding 3 (arithmetic errors dominate failures)."""
    assert len(TAXONOMY) == 7


def test_category_ids_are_unique():
    ids = [c.id for c in TAXONOMY]
    assert len(ids) == len(set(ids))


def test_category_id_equals_judge_dimension():
    for c in TAXONOMY:
        assert c.id == c.judge_dimension, (
            f"{c.id}: judge_dimension drifted to {c.judge_dimension!r}"
        )


def test_every_category_has_nonempty_string_fields():
    for c in TAXONOMY:
        for field in ("id", "name", "description", "judge_dimension", "example"):
            v = getattr(c, field)
            assert isinstance(v, str) and v.strip(), (
                f"category {c.id}: {field} is empty or non-string"
            )


def test_judge_kind_is_constrained():
    for c in TAXONOMY:
        assert c.judge_kind in ("semantic", "deterministic")


def test_deterministic_categories_are_exactly_expected():
    """Three deterministic categories after the forensics-driven
    refactor: tool_sequence (call ordering), confirmation_discipline
    (per-mutation user-yes), tool_argument_correctness (tool-server
    error responses)."""
    det = sorted(c.id for c in TAXONOMY if c.judge_kind == "deterministic")
    assert det == [
        "confirmation_discipline",
        "tool_argument_correctness",
        "tool_sequence_correctness",
    ]


def test_semantic_categories_are_exactly_expected():
    sem = sorted(c.id for c in TAXONOMY if c.judge_kind == "semantic")
    assert sem == [
        "information_grounding",
        "policy_compliance",
        "scope_adherence",
        "task_completion",
    ]


def test_required_ids_present():
    required = {
        "policy_compliance",
        "confirmation_discipline",
        "information_grounding",
        "scope_adherence",
        "tool_sequence_correctness",
        "tool_argument_correctness",
        "task_completion",
    }
    assert {c.id for c in TAXONOMY} == required


def test_taxonomy_is_immutable_dataclass():
    c = TAXONOMY[0]
    assert isinstance(c, FailureCategory)
    with pytest.raises(Exception):
        c.id = "mutated"


def test_get_category_returns_known_id():
    c = get_category("policy_compliance")
    assert isinstance(c, FailureCategory)
    assert c.id == "policy_compliance"


def test_get_category_raises_on_unknown():
    with pytest.raises(KeyError, match="unknown taxonomy category"):
        get_category("not_a_real_category")


def test_category_ids_helper_matches_taxonomy():
    assert set(category_ids()) == {c.id for c in TAXONOMY}
    assert len(category_ids()) == len(TAXONOMY)
