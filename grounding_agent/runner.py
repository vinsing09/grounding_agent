"""Driver: run the tau-bench airline agent on a single task.

Thin wrapper around tau_bench. Constructs the airline env, the
tool-calling agent, runs solve(), and returns a structured dict with
the trajectory + the tau-bench ground-truth reward + termination
classification + tool-side error list.

Importing this module does not import tau_bench at module load — the
imports happen inside run_task so the rest of the framework (taxonomy,
contract, judges) stays cheap to import in unit tests.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

from grounding_agent.eventlog import EventLog


def classify_termination(
    messages: Sequence[dict[str, Any]],
    info: dict[str, Any],
    max_steps: int,
) -> dict[str, Any]:
    """Categorise how a trajectory ended.

    Kinds:
      - 'max_steps'  — env did not grade (info.reward_info is None);
                       happens when the step budget runs out before
                       the user-sim emits ###STOP### or a terminate
                       tool fires. Surfaced after forensics Finding 2.
      - 'transfer'   — agent called transfer_to_human_agents AND env
                       graded the trajectory.
      - 'completed'  — env reached a graded terminal state without
                       transfer.
    """
    transferred = False
    for m in messages:
        if m.get("role") != "assistant":
            continue
        for tc in (m.get("tool_calls") or []):
            fn = (tc or {}).get("function") or {}
            if fn.get("name") == "transfer_to_human_agents":
                transferred = True
                break
        if transferred:
            break

    reward_info_present = (info or {}).get("reward_info") is not None
    if not reward_info_present:
        return {
            "kind": "max_steps",
            "reason": (
                f"env did not compute reward_info; {len(messages)} messages, "
                f"max_steps={max_steps}, transferred={transferred}"
            ),
            "transferred": transferred,
            "n_messages": len(messages),
        }
    if transferred:
        return {
            "kind": "transfer",
            "reason": "transfer_to_human_agents called; env graded",
            "transferred": True,
            "n_messages": len(messages),
        }
    return {
        "kind": "completed",
        "reason": "env reached terminal state without transfer",
        "transferred": False,
        "n_messages": len(messages),
    }


def extract_tool_errors(
    messages: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Walk the trajectory; for each tool-return that starts with
    'Error:', attribute it to the triggering assistant tool_call by
    FIFO pairing (tau-bench's tool_calling_agent emits one tool_call
    per assistant message and one tool return immediately after).

    Returns: [{position: int, tool: str, message: str}].
    """
    pending: list[tuple[int, str]] = []
    out: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        role = m.get("role")
        if role == "assistant":
            for tc in (m.get("tool_calls") or []):
                fn = (tc or {}).get("function") or {}
                name = fn.get("name")
                if name:
                    pending.append((i, name))
        elif role == "tool":
            content = (m.get("content") or "").strip()
            if pending:
                pos, name = pending.pop(0)
            else:
                pos, name = i, m.get("name") or "?"
            if content.startswith("Error:") or content.startswith("Error "):
                out.append({
                    "position": pos,
                    "tool": name,
                    "message": content[:200],
                })
    return out


def run_task(
    task_index: int,
    *,
    agent_model: str = "gpt-4o-mini",
    agent_provider: str = "openai",
    user_model: str = "gpt-4o-mini",
    user_provider: str = "openai",
    max_steps: int = 30,
    wiki_override: str | None = None,
    eventlog: EventLog | None = None,
) -> dict[str, Any]:
    """Run the tau-bench tool-calling agent on one airline task.

    `wiki_override` replaces the system prompt the agent sees without
    touching the env (so the user-sim, reward function, and ground-truth
    actions stay exactly as tau-bench defines them). Used by run_eval
    to swap in the v2 prompt variant.

    `eventlog`, if provided, receives task_start / task_end events
    with timing and termination classification.

    Returns:
        {
          "task_index": int,
          "reward": float,            # tau-bench ground truth (0.0 or 1.0)
          "messages": list[dict],     # OpenAI chat-completion shape
          "info": dict,               # tau-bench env info (incl. reward_info)
          "total_cost": float | None,
          "agent_model": str,
          "user_model": str,
          "max_steps": int,
          "termination": dict,        # see classify_termination()
          "tool_errors": list[dict],  # see extract_tool_errors()
          "duration_s": float,
        }
    """
    from tau_bench.agents.tool_calling_agent import ToolCallingAgent
    from tau_bench.envs.airline.env import MockAirlineDomainEnv

    if eventlog is not None:
        eventlog.emit(
            "task_start",
            task_index=task_index,
            agent_model=agent_model,
            user_model=user_model,
            max_steps=max_steps,
            wiki_override=(wiki_override is not None),
        )

    t0 = time.time()
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
    duration_s = time.time() - t0

    messages = list(result.messages)
    info = dict(result.info or {})
    termination = classify_termination(messages, info, max_steps)
    tool_errors = extract_tool_errors(messages)

    if eventlog is not None:
        eventlog.emit(
            "task_end",
            task_index=task_index,
            reward=float(result.reward),
            termination_kind=termination["kind"],
            n_messages=len(messages),
            n_tool_errors=len(tool_errors),
            total_cost=result.total_cost,
            duration_s=duration_s,
        )

    return {
        "task_index": task_index,
        "reward": float(result.reward),
        "messages": messages,
        "info": info,
        "total_cost": result.total_cost,
        "agent_model": agent_model,
        "user_model": user_model,
        "max_steps": max_steps,
        "termination": termination,
        "tool_errors": tool_errors,
        "duration_s": duration_s,
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
