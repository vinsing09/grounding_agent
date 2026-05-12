"""Tests for judges.py.

Trajectory fixtures use the exact dict shape tau_bench's
ToolCallingAgent.solve emits (verified against tau_bench source):
assistant messages carry tool_calls=[{id, type, function:{name,
arguments(json-string)}}], tool messages carry tool_call_id+name+content.

The semantic judges' LLM-calling paths are covered by smoke test
end-to-end; here we unit-test the vacuous-pass branch (no clauses
tagged to the category) which exercises the same return path without
network.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from grounding_agent.judges import (
    JudgeResult,
    confirmation_discipline_judge,
    extract_tool_calls,
    format_trajectory,
    information_grounding_judge,
    policy_compliance_judge,
    scope_adherence_judge,
    tool_sequence_judge,
)


def _tool_call_msg(call_id: str, name: str, args: dict[str, Any]) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args),
                },
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


def _say_msg(content: str) -> dict:
    return {"role": "assistant", "content": content, "tool_calls": None}


def _trajectory_good() -> list[dict]:
    """get_user_details → book_reservation: prerequisites satisfied."""
    return [
        {"role": "system", "content": "<policy elided>"},
        {"role": "user", "content": "Book me NYC->SEA on May 20."},
        _tool_call_msg("call_1", "get_user_details", {"user_id": "mia_li_3668"}),
        _tool_result_msg("call_1", "get_user_details", '{"user_id":"mia_li_3668","membership":"silver"}'),
        _say_msg("Confirming: book NYC->SEA flight 123 in economy for $250. OK?"),
        {"role": "user", "content": "yes"},
        _tool_call_msg(
            "call_2",
            "book_reservation",
            {"user_id": "mia_li_3668", "flight": "F123"},
        ),
        _tool_result_msg("call_2", "book_reservation", '{"reservation_id":"R001"}'),
        _say_msg("Booked. Reservation R001."),
    ]


def _trajectory_bad_missing_prereq() -> list[dict]:
    """book_reservation called WITHOUT get_user_details. Should fail."""
    return [
        {"role": "user", "content": "Book NYC->SEA."},
        _tool_call_msg("c1", "book_reservation", {"user_id": "x", "flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", '{"reservation_id":"R002"}'),
    ]


def _trajectory_prereq_after_target() -> list[dict]:
    """prerequisite tool called AFTER target. Order matters."""
    return [
        {"role": "user", "content": "Book it."},
        _tool_call_msg("c1", "book_reservation", {"user_id": "x", "flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", '{"reservation_id":"R003"}'),
        _tool_call_msg("c2", "get_user_details", {"user_id": "x"}),
        _tool_result_msg("c2", "get_user_details", "{}"),
    ]


def _contract() -> dict:
    return {
        "agent": "tau_bench_airline",
        "obligations": [
            {
                "id": "obl-confirm",
                "text": "Obtain explicit user confirmation before any state-mutating tool call.",
                "category": "confirmation_discipline",
            },
            {
                "id": "obl-deny-out-of-policy",
                "text": "Deny requests violating policy (e.g. modifying basic economy).",
                "category": "policy_compliance",
            },
        ],
        "forbidden_behaviors": [
            {
                "id": "fb-no-subjective",
                "text": "Do not give subjective recommendations.",
                "category": "information_grounding",
            },
        ],
        "tool_sequences": [
            {
                "id": "ts-book-needs-user",
                "target_tool": "book_reservation",
                "prerequisite_tools": ["get_user_details"],
                "category": "tool_sequence_correctness",
            },
        ],
    }


# ---- extract_tool_calls ---------------------------------------------------


def test_extract_tool_calls_basic():
    calls = extract_tool_calls(_trajectory_good())
    names = [c["name"] for c in calls]
    assert names == ["get_user_details", "book_reservation"]


def test_extract_tool_calls_parses_json_arguments():
    calls = extract_tool_calls(_trajectory_good())
    book = next(c for c in calls if c["name"] == "book_reservation")
    assert book["arguments"] == {"user_id": "mia_li_3668", "flight": "F123"}


def test_extract_tool_calls_position_is_message_index():
    msgs = _trajectory_good()
    calls = extract_tool_calls(msgs)
    for c in calls:
        i = c["position"]
        emitted = msgs[i]["tool_calls"][0]["function"]["name"]
        assert emitted == c["name"]


def test_extract_tool_calls_handles_malformed_args_string():
    msgs = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "x",
                    "type": "function",
                    "function": {"name": "calculate", "arguments": "not-json"},
                }
            ],
        }
    ]
    calls = extract_tool_calls(msgs)
    assert calls[0]["arguments"] == {"_raw_arguments": "not-json"}


def test_extract_tool_calls_ignores_non_assistant_roles():
    msgs = [
        _tool_result_msg("x", "fake", "irrelevant"),
        {"role": "user", "content": "hi"},
    ]
    assert extract_tool_calls(msgs) == []


def test_extract_tool_calls_handles_empty_or_none_tool_calls():
    msgs = [_say_msg("just talking")]
    assert extract_tool_calls(msgs) == []


# ---- tool_sequence_judge --------------------------------------------------


def test_tool_sequence_passes_when_prereq_precedes_target():
    r = tool_sequence_judge(_trajectory_good(), _contract())
    assert isinstance(r, JudgeResult)
    assert r.passed is True
    assert r.category == "tool_sequence_correctness"
    assert "ts-book-needs-user" in r.clause_refs


def test_tool_sequence_fails_when_prereq_missing():
    r = tool_sequence_judge(_trajectory_bad_missing_prereq(), _contract())
    assert r.passed is False
    assert "get_user_details" in r.reason
    assert "ts-book-needs-user" in r.clause_refs


def test_tool_sequence_fails_when_prereq_called_after_target():
    r = tool_sequence_judge(_trajectory_prereq_after_target(), _contract())
    assert r.passed is False


def test_tool_sequence_passes_vacuously_when_target_not_in_trajectory():
    msgs = [
        {"role": "user", "content": "list airports"},
        _tool_call_msg("c1", "list_all_airports", {}),
        _tool_result_msg("c1", "list_all_airports", "[]"),
    ]
    r = tool_sequence_judge(msgs, _contract())
    assert r.passed is True
    assert r.clause_refs == ()


def test_tool_sequence_passes_when_no_tool_sequence_clauses():
    contract = _contract()
    contract["tool_sequences"] = []
    r = tool_sequence_judge(_trajectory_bad_missing_prereq(), contract)
    assert r.passed is True


def test_tool_sequence_handles_multiple_prerequisites():
    contract = _contract()
    contract["tool_sequences"] = [
        {
            "id": "ts-multi",
            "target_tool": "update_reservation_flights",
            "prerequisite_tools": ["get_user_details", "get_reservation_details"],
            "category": "tool_sequence_correctness",
        }
    ]
    msgs = [
        _tool_call_msg("c1", "get_user_details", {"user_id": "x"}),
        _tool_result_msg("c1", "get_user_details", "{}"),
        _tool_call_msg("c2", "update_reservation_flights", {"reservation_id": "R1"}),
        _tool_result_msg("c2", "update_reservation_flights", "{}"),
    ]
    r = tool_sequence_judge(msgs, contract)
    assert r.passed is False
    assert "get_reservation_details" in r.reason


# ---- format_trajectory ----------------------------------------------------


def test_format_trajectory_omits_system_messages():
    out = format_trajectory(_trajectory_good())
    assert "elided" not in out
    assert "policy" not in out.lower() or "Confirming" in out


def test_format_trajectory_includes_tool_calls_and_results():
    out = format_trajectory(_trajectory_good())
    assert "tool_call get_user_details" in out
    assert "tool_call book_reservation" in out
    assert "tool[get_user_details]:" in out
    assert "tool[book_reservation]:" in out


def test_format_trajectory_renders_assistant_and_user_lines():
    out = format_trajectory(_trajectory_good())
    assert "user: Book me NYC->SEA on May 20." in out
    assert "assistant: Confirming" in out


# ---- semantic judges (vacuous-pass path; no network) ---------------------


def test_semantic_judge_vacuous_pass_when_no_clauses_in_category():
    empty_contract = {
        "agent": "x",
        "obligations": [],
        "forbidden_behaviors": [],
        "tool_sequences": [],
    }
    for judge in (
        policy_compliance_judge,
        confirmation_discipline_judge,
        information_grounding_judge,
        scope_adherence_judge,
    ):
        r = judge(_trajectory_good(), empty_contract)
        assert r.passed is True
        assert r.clause_refs == ()
        assert "vacuously" in r.reason
        assert r.category == judge.__name__.replace("_judge", "")


def test_semantic_judges_filter_by_category():
    """Each semantic judge should only see clauses tagged to its own
    category; if a contract has clauses only for other categories, the
    judge takes the vacuous-pass branch and does not call the LLM.
    """
    contract_only_grounding = {
        "agent": "x",
        "obligations": [],
        "forbidden_behaviors": [
            {
                "id": "fb-1",
                "text": "no subjective recs",
                "category": "information_grounding",
            }
        ],
        "tool_sequences": [],
    }
    # policy_compliance has no clauses → vacuous pass, no LLM call
    r = policy_compliance_judge(_trajectory_good(), contract_only_grounding)
    assert r.passed is True
    assert "vacuously" in r.reason
