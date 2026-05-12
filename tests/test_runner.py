"""Runner tests.

The runner is a thin wrapper around tau_bench. We unit-test its
result-shaping logic by monkeypatching the tau_bench symbols it imports
inside run_task. Live end-to-end execution is covered by the smoke
test in scripts/smoke_test.py.
"""

from __future__ import annotations

from typing import Any

import pytest

import grounding_agent.runner as runner


class _FakeSolveResult:
    def __init__(
        self,
        reward: float,
        messages: list[dict],
        info: dict | None,
        total_cost: float | None,
    ) -> None:
        self.reward = reward
        self.messages = messages
        self.info = info
        self.total_cost = total_cost


class _FakeEnv:
    def __init__(self, **kwargs: Any) -> None:
        self.tools_info = [{"function": {"name": "search_direct_flight"}}]
        self.wiki = "policy text"
        self.kwargs = kwargs


class _FakeAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def solve(self, env: Any, task_index: int, max_num_steps: int) -> _FakeSolveResult:
        return _FakeSolveResult(
            reward=1.0,
            messages=[
                {"role": "system", "content": env.wiki},
                {"role": "user", "content": "hi"},
            ],
            info={"reward_info": {"r_actions": 1.0}},
            total_cost=0.0042,
        )


def test_run_task_returns_expected_keys_and_types(monkeypatch):
    import tau_bench.agents.tool_calling_agent as tc_mod
    import tau_bench.envs.airline.env as env_mod

    monkeypatch.setattr(env_mod, "MockAirlineDomainEnv", _FakeEnv)
    monkeypatch.setattr(tc_mod, "ToolCallingAgent", _FakeAgent)

    out = runner.run_task(
        task_index=0,
        agent_model="m-a",
        agent_provider="openai",
        user_model="m-u",
        user_provider="openai",
        max_steps=5,
    )
    assert out["task_index"] == 0
    assert out["reward"] == 1.0
    assert out["agent_model"] == "m-a"
    assert out["user_model"] == "m-u"
    assert isinstance(out["messages"], list) and len(out["messages"]) == 2
    assert out["messages"][0]["content"] == "policy text"
    assert out["total_cost"] == pytest.approx(0.0042)
    assert "reward_info" in out["info"]
    # Bucket D fields
    assert out["max_steps"] == 5
    assert "termination" in out and "kind" in out["termination"]
    assert "tool_errors" in out and isinstance(out["tool_errors"], list)
    assert "duration_s" in out and out["duration_s"] >= 0


def test_run_task_emits_events_when_eventlog_supplied(monkeypatch, tmp_path):
    import tau_bench.agents.tool_calling_agent as tc_mod
    import tau_bench.envs.airline.env as env_mod
    from grounding_agent.eventlog import EventLog
    import json

    monkeypatch.setattr(env_mod, "MockAirlineDomainEnv", _FakeEnv)
    monkeypatch.setattr(tc_mod, "ToolCallingAgent", _FakeAgent)

    with EventLog("r-test", "v0", log_dir=tmp_path) as elog:
        runner.run_task(task_index=4, eventlog=elog)

    events = [
        json.loads(l) for l in (tmp_path / "v0.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    kinds = [e["event"] for e in events]
    assert "task_start" in kinds
    assert "task_end" in kinds
    end = next(e for e in events if e["event"] == "task_end")
    assert end["task_index"] == 4
    assert "termination_kind" in end
    assert end["reward"] == 1.0


def test_run_task_wiki_override_replaces_agent_system_prompt(monkeypatch):
    """v2 variant passes wiki_override; runner must hand it to the agent
    constructor and NOT to the env. We capture both to prove it."""
    import tau_bench.agents.tool_calling_agent as tc_mod
    import tau_bench.envs.airline.env as env_mod

    captured: dict[str, Any] = {}

    class _CapturingAgent(_FakeAgent):
        def __init__(self, **kwargs: Any) -> None:
            captured["agent_wiki"] = kwargs.get("wiki")
            super().__init__(**kwargs)

    class _CapturingEnv(_FakeEnv):
        def __init__(self, **kwargs: Any) -> None:
            captured["env_kwargs"] = kwargs
            super().__init__(**kwargs)

    monkeypatch.setattr(env_mod, "MockAirlineDomainEnv", _CapturingEnv)
    monkeypatch.setattr(tc_mod, "ToolCallingAgent", _CapturingAgent)

    override = "OVERRIDDEN PROMPT TEXT"
    runner.run_task(task_index=3, wiki_override=override)
    assert captured["agent_wiki"] == override
    # env was NOT given the override (would distort the user-sim/reward path)
    assert "wiki" not in captured["env_kwargs"]


# ---- Bucket D: termination + tool-error extraction ------------------------


def test_classify_termination_max_steps_when_reward_info_none():
    from grounding_agent.runner import classify_termination
    msgs = [{"role": "user", "content": "hi"}]
    info = {"reward_info": None}
    t = classify_termination(msgs, info, max_steps=25)
    assert t["kind"] == "max_steps"
    assert t["transferred"] is False


def test_classify_termination_transfer_when_transfer_tool_called_and_graded():
    from grounding_agent.runner import classify_termination
    msgs = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "x", "type": "function",
             "function": {"name": "transfer_to_human_agents", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "x", "name": "transfer_to_human_agents",
         "content": "Transfer successful"},
    ]
    info = {"reward_info": {"info": {"r_actions": 1.0}, "reward": 1.0}}
    t = classify_termination(msgs, info, max_steps=25)
    assert t["kind"] == "transfer"
    assert t["transferred"] is True


def test_classify_termination_completed_when_graded_without_transfer():
    from grounding_agent.runner import classify_termination
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok done", "tool_calls": None},
    ]
    info = {"reward_info": {"info": {"r_actions": 0.0}, "reward": 0.0}}
    t = classify_termination(msgs, info, max_steps=25)
    assert t["kind"] == "completed"


def test_classify_termination_max_steps_even_if_transferred_but_not_graded():
    """If the agent transferred but reward_info is still None (rare but
    possible if max_steps and transfer happened the same step), this is
    surfaced as max_steps with transferred=True."""
    from grounding_agent.runner import classify_termination
    msgs = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "x", "type": "function",
             "function": {"name": "transfer_to_human_agents", "arguments": "{}"}}
        ]},
    ]
    info = {"reward_info": None}
    t = classify_termination(msgs, info, max_steps=25)
    assert t["kind"] == "max_steps"
    assert t["transferred"] is True


def test_extract_tool_errors_returns_empty_for_clean_trajectory():
    from grounding_agent.runner import extract_tool_errors
    msgs = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "1", "type": "function",
             "function": {"name": "get_user_details", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "1", "name": "get_user_details",
         "content": '{"ok": true}'},
    ]
    assert extract_tool_errors(msgs) == []


def test_extract_tool_errors_attributes_error_to_calling_tool():
    from grounding_agent.runner import extract_tool_errors
    msgs = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "1", "type": "function",
             "function": {"name": "book_reservation", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "1", "name": "book_reservation",
         "content": "Error: payment amount does not add up"},
    ]
    errs = extract_tool_errors(msgs)
    assert len(errs) == 1
    assert errs[0]["tool"] == "book_reservation"
    assert errs[0]["position"] == 0
    assert "payment amount" in errs[0]["message"]


def test_extract_tool_errors_handles_multiple_calls_in_order():
    from grounding_agent.runner import extract_tool_errors
    msgs = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "1", "type": "function",
             "function": {"name": "get_user_details", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "1", "name": "get_user_details",
         "content": '{"ok": true}'},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "2", "type": "function",
             "function": {"name": "book_reservation", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "2", "name": "book_reservation",
         "content": "Error: gift card balance is not enough"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "3", "type": "function",
             "function": {"name": "book_reservation", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "3", "name": "book_reservation",
         "content": "Error: number of passengers does not match"},
    ]
    errs = extract_tool_errors(msgs)
    assert len(errs) == 2
    assert [e["tool"] for e in errs] == ["book_reservation", "book_reservation"]
    assert all(e["position"] > 0 for e in errs)


def test_airline_tool_catalog_returns_fourteen_named_tools():
    cat = runner.airline_tool_catalog()
    assert isinstance(cat, list)
    assert len(cat) == 14
    names = {entry["name"] for entry in cat}
    # Spot-check three of the tools listed in the policy + vendored README
    assert "book_reservation" in names
    assert "get_user_details" in names
    assert "transfer_to_human_agents" in names
    for entry in cat:
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["description"], str)
