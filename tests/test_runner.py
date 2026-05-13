"""Tests for grounding_agent.runner (τ³-bench port).

The old test_runner monkey-patched MockAirlineDomainEnv + ToolCallingAgent
from the original τ-bench. After the τ³-bench migration, run_task uses
tau2.run.run_simulation; the easiest things to test in isolation are
the pure adapter functions (_serialize_tool_call, _flatten_messages,
classify_termination, extract_tool_errors).

The live end-to-end behaviour is exercised by scripts/smoke_test.py and
scripts/run_eval.py against the actual tau2-bench installation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from grounding_agent.runner import (
    _flatten_messages,
    _serialize_tool_call,
    airline_tool_catalog,
    classify_termination,
    extract_tool_errors,
)


# ----- _serialize_tool_call -------------------------------------------------


def test_serialize_tool_call_converts_to_openai_shape():
    tc = SimpleNamespace(id="call_1", name="book_reservation", arguments={"flight": "F1"})
    out = _serialize_tool_call(tc)
    assert out["id"] == "call_1"
    assert out["type"] == "function"
    assert out["function"]["name"] == "book_reservation"
    # arguments is JSON-serialized to a string in OpenAI shape
    assert isinstance(out["function"]["arguments"], str)
    assert '"flight"' in out["function"]["arguments"]
    assert '"F1"' in out["function"]["arguments"]


def test_serialize_tool_call_handles_empty_args():
    tc = SimpleNamespace(id="x", name="ping", arguments={})
    out = _serialize_tool_call(tc)
    assert out["function"]["arguments"] == "{}"


def test_serialize_tool_call_handles_missing_id():
    tc = SimpleNamespace(id="", name="ping", arguments={})
    out = _serialize_tool_call(tc)
    assert out["id"] == ""


# ----- _flatten_messages ----------------------------------------------------


def _fake_assistant_msg(content, tool_calls=None):
    """Imitates a tau2 AssistantMessage (pydantic) using SimpleNamespace.
    The adapter only reads .role / .content / .tool_calls."""
    return SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls or [])


def _fake_user_msg(content):
    return SimpleNamespace(role="user", content=content)


def _fake_tool_msg(call_id, content, error=False):
    return SimpleNamespace(role="tool", id=call_id, content=content, error=error)


def _fake_tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, name=name, arguments=arguments)


def test_flatten_messages_basic_round_trip():
    msgs = [
        _fake_user_msg("Book me NYC->SEA."),
        _fake_assistant_msg(
            None,
            tool_calls=[_fake_tool_call("c1", "get_user_details", {"user_id": "u"})],
        ),
        _fake_tool_msg("c1", '{"ok": true}'),
        _fake_assistant_msg("got it"),
    ]
    out = _flatten_messages(msgs)
    assert [m["role"] for m in out] == ["user", "assistant", "tool", "assistant"]
    assert out[0]["content"] == "Book me NYC->SEA."
    assert out[1]["tool_calls"][0]["function"]["name"] == "get_user_details"
    # tool message gets `name` re-attached from the preceding tool_call by id
    assert out[2]["name"] == "get_user_details"
    assert out[2]["tool_call_id"] == "c1"
    assert out[2]["error"] is False
    assert out[3]["content"] == "got it"


def test_flatten_messages_propagates_tool_error_flag():
    msgs = [
        _fake_assistant_msg(
            None,
            tool_calls=[_fake_tool_call("c1", "book_reservation", {})],
        ),
        _fake_tool_msg("c1", "Error: payment amount does not add up", error=True),
    ]
    out = _flatten_messages(msgs)
    assert out[1]["error"] is True
    assert out[1]["name"] == "book_reservation"


def test_flatten_messages_handles_multi_tool_message():
    """tau2.MultiToolMessage wraps multiple ToolMessages; we flatten
    them in order so judges see one tool entry per call."""
    multi = SimpleNamespace(
        role="tool",
        tool_messages=[
            _fake_tool_msg("c1", "{}"),
            _fake_tool_msg("c2", "Error: nope", error=True),
        ],
    )
    msgs = [
        _fake_assistant_msg(
            None,
            tool_calls=[
                _fake_tool_call("c1", "get_user_details", {}),
                _fake_tool_call("c2", "book_reservation", {}),
            ],
        ),
        multi,
    ]
    out = _flatten_messages(msgs)
    # 1 assistant + 2 flattened tool entries
    assert len(out) == 3
    assert out[1]["name"] == "get_user_details"
    assert out[2]["name"] == "book_reservation"
    assert out[2]["error"] is True


def test_flatten_messages_assistant_without_tool_calls_uses_none():
    """A talk-only assistant message gets tool_calls=None (OpenAI
    convention) so our judges' `or []` defaulting works correctly."""
    msgs = [_fake_assistant_msg("hello", tool_calls=[])]
    out = _flatten_messages(msgs)
    assert out[0]["tool_calls"] is None


# ----- classify_termination --------------------------------------------------


def _msgs_with_transfer():
    return [{
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "x", "type": "function",
            "function": {"name": "transfer_to_human_agents", "arguments": "{}"},
        }],
    }]


def test_classify_termination_user_stop_is_completed():
    t = classify_termination([], {"termination_reason": "user_stop"}, max_steps=25)
    assert t["kind"] == "completed"
    assert t["transferred"] is False


def test_classify_termination_max_steps_maps_directly():
    t = classify_termination([], {"termination_reason": "max_steps"}, max_steps=25)
    assert t["kind"] == "max_steps"


def test_classify_termination_timeout_treated_as_max_steps():
    """timeout and context_window_exceeded are semantically the same
    failure mode as max_steps for our taxonomy: the agent ran out of
    budget before finishing."""
    for raw in ("timeout", "context_window_exceeded"):
        t = classify_termination([], {"termination_reason": raw}, max_steps=25)
        assert t["kind"] == "max_steps", f"{raw} should map to max_steps"


def test_classify_termination_errors_map_to_error():
    for raw in (
        "too_many_errors", "agent_error", "user_error",
        "infrastructure_error", "unexpected_error",
    ):
        t = classify_termination([], {"termination_reason": raw}, max_steps=25)
        assert t["kind"] == "error", f"{raw} should map to error"


def test_classify_termination_transfer_overrides_completed():
    """When the agent transferred AND env graded, the bucket is
    'transfer' (it carries more information than 'completed')."""
    t = classify_termination(
        _msgs_with_transfer(),
        {"termination_reason": "user_stop"},
        max_steps=25,
    )
    assert t["kind"] == "transfer"
    assert t["transferred"] is True


def test_classify_termination_transfer_does_not_override_error():
    """If the agent transferred BUT env errored, the error bucket wins."""
    t = classify_termination(
        _msgs_with_transfer(),
        {"termination_reason": "infrastructure_error"},
        max_steps=25,
    )
    assert t["kind"] == "error"
    assert t["transferred"] is True


# ----- extract_tool_errors --------------------------------------------------


def test_extract_tool_errors_uses_explicit_error_flag():
    """τ³-bench's ToolMessage.error is the deterministic oracle —
    no need to grep 'Error:' from content."""
    msgs = [
        {
            "role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "book_reservation", "arguments": "{}"}}
            ],
        },
        {
            "role": "tool", "tool_call_id": "c1", "name": "book_reservation",
            "content": "Error: payment amount does not add up", "error": True,
        },
    ]
    errs = extract_tool_errors(msgs)
    assert len(errs) == 1
    assert errs[0]["tool"] == "book_reservation"
    assert errs[0]["position"] == 0


def test_extract_tool_errors_ignores_successful_calls():
    msgs = [
        {
            "role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "get_user_details", "arguments": "{}"}}
            ],
        },
        {
            "role": "tool", "tool_call_id": "c1", "name": "get_user_details",
            "content": '{"user_id": "u"}', "error": False,
        },
    ]
    assert extract_tool_errors(msgs) == []


# ----- airline_tool_catalog (live tau2 import) -----------------------------


def test_airline_tool_catalog_returns_named_tools():
    """Live call into tau2. τ³-bench's airline domain has 15 tools
    (one more than original τ-bench — get_flight_status was added)."""
    cat = airline_tool_catalog()
    assert isinstance(cat, list)
    assert len(cat) >= 14  # at least the original tau-bench set
    names = {entry["name"] for entry in cat}
    for required in ("book_reservation", "get_user_details",
                     "transfer_to_human_agents", "cancel_reservation"):
        assert required in names
    # All entries have a non-empty description (τ³-bench fixed missing
    # docs in the airline tools)
    for entry in cat:
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["description"], str)


def test_wiki_override_mutates_agent_domain_policy():
    """Regression guard: verifies the v2 mechanism actually reaches the
    agent's system prompt. Bug class to catch: a refactor that breaks
    the `orch.agent.domain_policy = wiki_override + ...` line would
    silently turn v2 into a duplicate v0 run.

    Constructs an orchestrator at the same point runner.run_task does,
    applies the same mutation, verifies system_prompt now contains the
    override marker. Live tau2 call; no API key needed (no LLM call)."""
    from tau2.data_model.simulation import TextRunConfig
    from tau2.run import get_tasks
    from tau2.runner import build_text_orchestrator

    config = TextRunConfig(
        domain="airline", agent="llm_agent", llm_agent="gpt-4o-mini",
        llm_args_agent={"temperature": 0.0},
        user="user_simulator", llm_user="gpt-4o-mini",
        llm_args_user={"temperature": 0.0},
        num_trials=1, max_steps=5,
        task_set_name="airline", task_ids=["0"],
    )
    task = get_tasks("airline", task_ids=["0"])[0]
    override_text = "## TEST_MARKER_PREAMBLE\n\nA distinctive sentinel.\n\n"

    orch = build_text_orchestrator(config, task, seed=42)
    baseline_len = len(orch.agent.domain_policy)
    baseline_sys = orch.agent.system_prompt
    assert "TEST_MARKER_PREAMBLE" not in baseline_sys

    # Apply the same mutation runner.run_task uses.
    orch.agent.domain_policy = override_text + orch.agent.domain_policy

    assert len(orch.agent.domain_policy) == baseline_len + len(override_text)
    # The agent's system_prompt is a property that reads domain_policy
    # fresh on each access — the mutation must show up.
    assert "TEST_MARKER_PREAMBLE" in orch.agent.system_prompt
    assert orch.agent.system_prompt.find("TEST_MARKER_PREAMBLE") < orch.agent.system_prompt.find("Airline Agent Policy"), \
        "preamble should appear BEFORE the policy body in the rendered system prompt"
