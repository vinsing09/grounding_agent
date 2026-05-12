"""Evaluator tests.

Use a contract with NO obligations/forbidden_behaviors so the four
semantic judges all take the vacuous-pass branch (no LLM call). The
deterministic tool_sequence judge runs for real against the supplied
trajectory.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from grounding_agent.evaluator import evaluate_trajectory, summarize
from grounding_agent.judges import JudgeResult


def _tool_call_msg(call_id: str, name: str, args: dict[str, Any]) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


def _tool_result_msg(call_id: str, name: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": content,
    }


def _empty_semantic_contract() -> dict:
    return {
        "agent": "tau_bench_airline",
        "obligations": [],
        "forbidden_behaviors": [],
        "tool_sequences": [
            {
                "id": "ts-book-needs-user",
                "target_tool": "book_reservation",
                "prerequisite_tools": ["get_user_details"],
                "category": "tool_sequence_correctness",
            }
        ],
    }


def _good_trajectory() -> list[dict]:
    return [
        {"role": "system", "content": "<wiki>"},
        {"role": "user", "content": "Book me NYC->SEA."},
        _tool_call_msg("c1", "get_user_details", {"user_id": "u1"}),
        _tool_result_msg("c1", "get_user_details", "{}"),
        _tool_call_msg("c2", "book_reservation", {"user_id": "u1", "flight": "F1"}),
        _tool_result_msg("c2", "book_reservation", '{"reservation_id":"R1"}'),
    ]


def _bad_trajectory() -> list[dict]:
    return [
        {"role": "user", "content": "Book."},
        _tool_call_msg("c1", "book_reservation", {"user_id": "u1", "flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", "{}"),
    ]


def test_evaluate_returns_one_result_per_category():
    results = evaluate_trajectory(_good_trajectory(), _empty_semantic_contract())
    assert set(results.keys()) == {
        "policy_compliance",
        "confirmation_discipline",
        "information_grounding",
        "scope_adherence",
        "tool_sequence_correctness",
    }
    for r in results.values():
        assert isinstance(r, JudgeResult)


def test_evaluate_all_pass_on_well_formed_trajectory():
    results = evaluate_trajectory(_good_trajectory(), _empty_semantic_contract())
    assert all(r.passed for r in results.values())


def test_evaluate_flags_tool_sequence_violation():
    results = evaluate_trajectory(_bad_trajectory(), _empty_semantic_contract())
    assert results["tool_sequence_correctness"].passed is False
    # semantic judges still vacuous-pass since the contract has no
    # obligations/forbidden_behaviors for them
    for cat in (
        "policy_compliance",
        "confirmation_discipline",
        "information_grounding",
        "scope_adherence",
    ):
        assert results[cat].passed is True


def test_summarize_shape():
    results = evaluate_trajectory(_bad_trajectory(), _empty_semantic_contract())
    s = summarize(results)
    assert s["n_dimensions"] == 5
    assert s["n_failed"] == 1
    assert s["n_passed"] == 4
    assert set(s["by_dimension"].keys()) == set(results.keys())
    failing = s["by_dimension"]["tool_sequence_correctness"]
    assert failing["passed"] is False
    assert isinstance(failing["clause_refs"], list)


def test_evaluate_results_indexed_by_judge_category():
    results = evaluate_trajectory(_good_trajectory(), _empty_semantic_contract())
    for cat, r in results.items():
        assert r.category == cat
