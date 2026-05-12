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
    # confirmation_discipline is no longer semantic (Bucket A);
    # its behavior on an empty contract is exercised separately.
    for judge in (
        policy_compliance_judge,
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


# ---- confirmation_discipline (deterministic, Bucket A) ----------------------


def _confirmation_contract() -> dict:
    return {
        "agent": "x",
        "obligations": [
            {
                "id": "obl-confirm-action",
                "text": "Obtain explicit user confirmation before any DB-mutating tool call.",
                "category": "confirmation_discipline",
            }
        ],
        "forbidden_behaviors": [],
        "tool_sequences": [],
    }


def test_confirmation_passes_when_no_mutations():
    msgs = [
        {"role": "system", "content": "<wiki>"},
        {"role": "user", "content": "what airports do you serve?"},
        _tool_call_msg("c1", "list_all_airports", {}),
        _tool_result_msg("c1", "list_all_airports", "[]"),
        _say_msg("We serve all major US airports."),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is True
    assert r.score is None
    assert "no mutating tool calls" in r.reason
    assert r.clause_refs == ("obl-confirm-action",)


def test_confirmation_passes_when_yes_precedes_single_mutation():
    msgs = [
        {"role": "user", "content": "Book NYC->SEA"},
        _say_msg("Confirming: book flight F1 in economy for $250. OK?"),
        {"role": "user", "content": "yes"},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", '{"reservation_id": "R1"}'),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is True
    assert r.score == 1.0
    assert "1/1 mutations" in r.reason


def test_confirmation_fails_when_no_user_yes_before_mutation():
    msgs = [
        {"role": "user", "content": "Book NYC->SEA"},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", '{"reservation_id": "R1"}'),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is False
    assert r.score == 0.0
    assert "book_reservation@" in r.reason


def test_confirmation_fails_when_user_says_no():
    msgs = [
        _say_msg("Confirming: book F1 for $250. OK?"),
        {"role": "user", "content": "no, cancel"},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", "{}"),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is False
    assert r.score == 0.0


def test_confirmation_negation_leading_is_not_affirmative():
    """Even if a positive word appears later, a negation-leading user
    message is not an affirmative."""
    msgs = [
        _say_msg("Confirm book?"),
        {"role": "user", "content": "Not yet, I have questions."},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", "{}"),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is False
    assert r.score == 0.0


def test_confirmation_back_to_back_mutations_each_need_own_yes():
    """One user 'yes' authorizes ONE mutation. A second mutation
    immediately after requires its own user turn (the policy reads
    per-action, not per-conversation)."""
    msgs = [
        {"role": "user", "content": "yes"},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", "{}"),
        _tool_call_msg("c2", "book_reservation", {"flight": "F2"}),
        _tool_result_msg("c2", "book_reservation", "{}"),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is False
    assert r.score == 0.5  # 1 of 2 confirmed
    assert "1/2" in r.reason
    # second book is the unconfirmed one
    assert "book_reservation@" in r.reason


def test_confirmation_two_mutations_with_two_yeses_passes():
    msgs = [
        {"role": "user", "content": "yes"},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", "{}"),
        _say_msg("OK now book the return?"),
        {"role": "user", "content": "go ahead"},
        _tool_call_msg("c2", "book_reservation", {"flight": "F2"}),
        _tool_result_msg("c2", "book_reservation", "{}"),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is True
    assert r.score == 1.0


def test_confirmation_only_mutating_tools_count():
    """Non-mutating tools (search, get_user_details, calculate, etc.)
    do not require confirmation, even though tau-bench mediates them."""
    msgs = [
        {"role": "user", "content": "find flights from JFK to SEA"},
        _tool_call_msg("c1", "search_direct_flight", {"origin": "JFK"}),
        _tool_result_msg("c1", "search_direct_flight", "[]"),
        _tool_call_msg("c2", "get_user_details", {"user_id": "u"}),
        _tool_result_msg("c2", "get_user_details", "{}"),
        _say_msg("No flights matched."),
    ]
    r = confirmation_discipline_judge(msgs, _confirmation_contract())
    assert r.passed is True
    assert r.score is None  # no mutations seen
    assert "no mutating tool calls" in r.reason


def test_confirmation_all_six_mutating_tools_recognized():
    """If MUTATING_TOOLS drifts (e.g. the policy gains a tool), this
    test catches it. Each mutating tool call without a preceding yes
    should be flagged."""
    from grounding_agent.judges import MUTATING_TOOLS
    expected = {
        "book_reservation",
        "cancel_reservation",
        "update_reservation_baggages",
        "update_reservation_flights",
        "update_reservation_passengers",
        "send_certificate",
    }
    assert set(MUTATING_TOOLS) == expected


def test_confirmation_works_without_clauses_in_contract():
    """Deterministic check encodes the rule itself; the contract's
    clause list is only metadata. With no confirmation_discipline
    clauses, the check still runs (mutation without yes still fails)."""
    msgs = [
        {"role": "user", "content": "book it"},
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", "{}"),
    ]
    empty_contract = {
        "agent": "x", "obligations": [], "forbidden_behaviors": [],
        "tool_sequences": [],
    }
    r = confirmation_discipline_judge(msgs, empty_contract)
    assert r.passed is False  # rule still applies
    assert r.clause_refs == ()  # no clauses to cite


# ---- Bucket B: agent-actions emphasis in semantic judge prompts ------------


def test_format_agent_actions_excludes_user_turns():
    """User turns must be absent from the agent-actions block — that's
    the whole point of separating it (forensics Finding 5)."""
    from grounding_agent.judges import format_agent_actions
    msgs = [
        {"role": "system", "content": "<wiki>"},
        {"role": "user", "content": "PLEASE REMOVE PASSENGER SOPHIA"},
        _tool_call_msg("c1", "get_reservation_details", {"reservation_id": "R1"}),
        _tool_result_msg("c1", "get_reservation_details", '{"passengers":[]}'),
        _say_msg("I cannot remove a passenger; transferring to a human."),
    ]
    out = format_agent_actions(msgs)
    assert "PLEASE REMOVE PASSENGER SOPHIA" not in out
    assert "REMOVE PASSENGER SOPHIA" not in out
    assert "AGENT CALL get_reservation_details" in out
    assert "TOOL RETURN [get_reservation_details]" in out
    assert "AGENT SAYS: I cannot remove" in out


def test_format_agent_actions_empty_when_no_assistant_actions():
    from grounding_agent.judges import format_agent_actions
    msgs = [
        {"role": "system", "content": "x"},
        {"role": "user", "content": "hi"},
    ]
    assert format_agent_actions(msgs) == "(agent did not act)"


def test_build_semantic_judge_prompt_returns_none_on_empty_clauses():
    from grounding_agent.judges import _build_semantic_judge_prompt
    empty = {"agent": "x", "obligations": [], "forbidden_behaviors": [], "tool_sequences": []}
    assert _build_semantic_judge_prompt("scope_adherence", [], empty) is None


def test_build_semantic_judge_prompt_filters_clauses_by_category():
    """The prompt-building helper must include only clauses tagged to
    the target category. Cross-category leakage would re-introduce
    the noise the taxonomy was designed to avoid."""
    from grounding_agent.judges import _build_semantic_judge_prompt
    contract = {
        "agent": "x",
        "obligations": [
            {"id": "obl-pol", "text": "deny out of policy", "category": "policy_compliance"},
            {"id": "obl-scope", "text": "transfer when out of scope", "category": "scope_adherence"},
        ],
        "forbidden_behaviors": [
            {"id": "fb-no-recs", "text": "no subjective recs", "category": "information_grounding"},
        ],
        "tool_sequences": [],
    }
    msgs = [{"role": "user", "content": "hi"}, _say_msg("hi back")]
    out = _build_semantic_judge_prompt("scope_adherence", msgs, contract)
    assert out is not None
    system, user, refs = out
    assert "transfer when out of scope" in user
    assert "deny out of policy" not in user  # other category
    assert "no subjective recs" not in user  # other category
    assert refs == ("obl-scope",)


def test_build_semantic_judge_prompt_contains_agent_actions_first_and_trajectory_after():
    """The user content must put AGENT ACTIONS before FULL TRAJECTORY
    so the judge's attention is anchored on the agent's behavior."""
    from grounding_agent.judges import _build_semantic_judge_prompt
    contract = {
        "agent": "x",
        "obligations": [],
        "forbidden_behaviors": [
            {"id": "fb-x", "text": "don't do X", "category": "scope_adherence"},
        ],
        "tool_sequences": [],
    }
    msgs = _trajectory_good()
    out = _build_semantic_judge_prompt("scope_adherence", msgs, contract)
    assert out is not None
    _, user, _ = out
    pos_actions = user.find("AGENT ACTIONS")
    pos_full = user.find("FULL TRAJECTORY")
    assert 0 <= pos_actions < pos_full


def test_build_semantic_judge_prompt_system_contains_ground_rules():
    """The system prompt must include the 'only the agent can violate'
    rule. If a refactor drops it, this test catches the regression."""
    from grounding_agent.judges import _build_semantic_judge_prompt
    contract = {
        "agent": "x",
        "obligations": [{"id": "o", "text": "t", "category": "scope_adherence"}],
        "forbidden_behaviors": [],
        "tool_sequences": [],
    }
    out = _build_semantic_judge_prompt("scope_adherence", [], contract)
    assert out is not None
    system, _, _ = out
    assert "ONLY THE AGENT CAN VIOLATE" in system
    assert "user" in system.lower() and "request" in system.lower()


def test_is_affirmative_helper():
    from grounding_agent.judges import is_affirmative
    # positives
    for s in ("yes", "Yes please", "yeah", "yep", "OK",
              "go ahead", "do it", "please do", "sounds good",
              "let's do it", "confirm", "Proceed.",
              "yes, but I have a question"):
        assert is_affirmative(s), f"{s!r} should be affirmative"
    # negatives
    for s in ("", "   ", "no", "no thanks", "not yet",
              "wait", "wait a moment", "cancel", "don't",
              "I'm not sure yet", "stop"):
        assert not is_affirmative(s), f"{s!r} should NOT be affirmative"


# ---- Bucket C: tool_argument_correctness (deterministic) ------------


def test_argument_correctness_no_tool_calls_passes():
    from grounding_agent.judges import tool_argument_correctness_judge
    msgs = [
        {"role": "system", "content": "x"},
        {"role": "user", "content": "hi"},
        _say_msg("hi"),
    ]
    r = tool_argument_correctness_judge(msgs, {"obligations": [], "forbidden_behaviors": []})
    assert r.passed is True
    assert r.score is None
    assert "no tool calls" in r.reason


def test_argument_correctness_all_success_passes():
    from grounding_agent.judges import tool_argument_correctness_judge
    msgs = [
        _tool_call_msg("c1", "get_user_details", {"user_id": "u"}),
        _tool_result_msg("c1", "get_user_details", '{"user_id":"u"}'),
        _tool_call_msg("c2", "search_direct_flight", {"origin": "JFK"}),
        _tool_result_msg("c2", "search_direct_flight", "[]"),
    ]
    r = tool_argument_correctness_judge(msgs, {})
    assert r.passed is True
    assert r.score == 1.0
    assert "2/2" in r.reason


def test_argument_correctness_flags_error_response():
    from grounding_agent.judges import tool_argument_correctness_judge
    msgs = [
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg(
            "c1", "book_reservation",
            "Error: payment amount does not add up, total price is 355, but paid 152",
        ),
    ]
    r = tool_argument_correctness_judge(msgs, {})
    assert r.passed is False
    assert r.score == 0.0
    assert "book_reservation@" in r.reason
    assert "payment amount" in r.reason


def test_argument_correctness_mixed_success_and_error():
    from grounding_agent.judges import tool_argument_correctness_judge
    msgs = [
        _tool_call_msg("c1", "get_user_details", {"user_id": "u"}),
        _tool_result_msg("c1", "get_user_details", '{"user_id":"u"}'),
        _tool_call_msg("c2", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c2", "book_reservation", "Error: gift card balance is not enough"),
        _tool_call_msg("c3", "search_direct_flight", {"origin": "JFK"}),
        _tool_result_msg("c3", "search_direct_flight", "[]"),
    ]
    r = tool_argument_correctness_judge(msgs, {})
    assert r.passed is False
    assert r.score == pytest.approx(2 / 3)
    assert "2/3" in r.reason


def test_argument_correctness_picks_up_contract_clause_refs():
    """If the contract has clauses tagged to tool_argument_correctness,
    clause_refs should include them (same convention as other det
    judges)."""
    from grounding_agent.judges import tool_argument_correctness_judge
    contract = {
        "obligations": [
            {"id": "obl-validate-payment", "text": "validate payment math",
             "category": "tool_argument_correctness"},
        ],
        "forbidden_behaviors": [],
        "tool_sequences": [],
    }
    msgs = [
        _tool_call_msg("c1", "book_reservation", {"flight": "F1"}),
        _tool_result_msg("c1", "book_reservation", '{"ok":true}'),
    ]
    r = tool_argument_correctness_judge(msgs, contract)
    assert r.clause_refs == ("obl-validate-payment",)


def test_argument_correctness_truncates_many_errors():
    from grounding_agent.judges import tool_argument_correctness_judge
    msgs: list[dict] = []
    for i in range(8):
        msgs.append(_tool_call_msg(f"c{i}", "book_reservation", {}))
        msgs.append(_tool_result_msg(f"c{i}", "book_reservation", f"Error: case {i}"))
    r = tool_argument_correctness_judge(msgs, {})
    assert r.passed is False
    assert r.score == 0.0
    assert "+3 more" in r.reason  # 8 errors; 5 shown + 3 more
