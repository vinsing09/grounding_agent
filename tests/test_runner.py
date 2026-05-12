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
