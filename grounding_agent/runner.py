"""Driver: run the tau-bench airline agent on a single task.

Thin wrapper around tau_bench. Constructs the airline env, the
tool-calling agent, runs solve(), and returns a structured dict with
the trajectory + the tau-bench ground-truth reward.

Importing this module does not import tau_bench at module load — the
imports happen inside run_task so the rest of the framework (taxonomy,
contract, judges) stays cheap to import in unit tests.
"""

from __future__ import annotations

from typing import Any


def run_task(
    task_index: int,
    *,
    agent_model: str = "gpt-4o-mini",
    agent_provider: str = "openai",
    user_model: str = "gpt-4o-mini",
    user_provider: str = "openai",
    max_steps: int = 30,
    wiki_override: str | None = None,
) -> dict[str, Any]:
    """Run the tau-bench tool-calling agent on one airline task.

    `wiki_override` replaces the system prompt the agent sees without
    touching the env (so the user-sim, reward function, and ground-truth
    actions stay exactly as tau-bench defines them). Used by run_eval
    to swap in the v2 prompt variant.

    Returns:
        {
          "task_index": int,
          "reward": float,            # tau-bench ground truth (0.0 or 1.0)
          "messages": list[dict],     # OpenAI chat-completion shape
          "info": dict,               # tau-bench env info (incl. reward_info)
          "total_cost": float | None,
          "agent_model": str,
          "user_model": str,
        }
    """
    from tau_bench.agents.tool_calling_agent import ToolCallingAgent
    from tau_bench.envs.airline.env import MockAirlineDomainEnv

    env = MockAirlineDomainEnv(
        user_model=user_model,
        user_provider=user_provider,
        task_index=task_index,
    )
    agent_wiki = wiki_override if wiki_override is not None else env.wiki
    agent = ToolCallingAgent(
        tools_info=env.tools_info,
        wiki=agent_wiki,
        model=agent_model,
        provider=agent_provider,
    )
    result = agent.solve(env, task_index=task_index, max_num_steps=max_steps)

    return {
        "task_index": task_index,
        "reward": float(result.reward),
        "messages": list(result.messages),
        "info": dict(result.info or {}),
        "total_cost": result.total_cost,
        "agent_model": agent_model,
        "user_model": user_model,
    }


def airline_tool_catalog() -> list[dict[str, str]]:
    """Return the 14 airline tools as [{name, description}] entries.

    Used by scripts/generate_contract.py to feed contract.generate_contract.
    Constructed without an LLM env so it does not require API keys.
    """
    from tau_bench.envs.airline.tools import ALL_TOOLS

    out: list[dict[str, str]] = []
    for tool in ALL_TOOLS:
        info = tool.get_info()
        fn = info.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        out.append({"name": name, "description": desc})
    return out
