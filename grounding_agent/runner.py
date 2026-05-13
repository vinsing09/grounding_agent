"""Driver: run the τ³-bench airline agent on a single task.

Thin wrapper around tau2 (sierra-research/tau2-bench, which hosts
τ³-bench). Builds a text orchestrator, runs it, and adapts the
result into the same dict shape the framework's judges + evaluator
+ compare have always consumed (OpenAI chat-completion message
dicts). The other modules (taxonomy, contract, judges, evaluator,
compare, eventlog) do not need any τ³-bench-specific knowledge.

Migration history: we originally targeted the old sierra-research/
tau-bench package. After three forensic iterations on that
benchmark we discovered (via web verification) that the original
τ-bench airline tasks contained annotation bugs which τ³-bench
fixed — Sierra's blog post claims +14 to +20 point improvements in
airline pass^1 scores after the fixes. This module is the τ³-bench
port. See `results/tau1_vs_tau3.md` for the meta-finding.
"""

from __future__ import annotations

import json
import time
from typing import Any, Sequence

from grounding_agent.eventlog import EventLog


# Tau2 termination_reason → our termination kind.
# Bucket-D semantics: completed = env-graded; transfer overrides if the
# agent called transfer_to_human_agents; max_steps and the timeout-style
# failures cluster together; everything else is an error.
_TERMINATION_KIND_MAP: dict[str, str] = {
    "user_stop": "completed",
    "agent_stop": "completed",
    "max_steps": "max_steps",
    "timeout": "max_steps",
    "context_window_exceeded": "max_steps",
    "too_many_errors": "error",
    "agent_error": "error",
    "user_error": "error",
    "infrastructure_error": "error",
    "unexpected_error": "error",
}


def _serialize_tool_call(tc: Any) -> dict[str, Any]:
    """tau2.ToolCall → OpenAI tool_call shape.

    tau2: {id, name, arguments(dict), requestor}
    OpenAI: {id, type, function: {name, arguments(str)}}
    """
    args = getattr(tc, "arguments", {}) or {}
    return {
        "id": getattr(tc, "id", "") or "",
        "type": "function",
        "function": {
            "name": getattr(tc, "name", ""),
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def _flatten_messages(messages: Sequence[Any]) -> list[dict[str, Any]]:
    """Convert tau2's pydantic Message list to OpenAI-style dicts.

    Side effects:
    - MultiToolMessage wrappers are flattened into their child tool
      messages, preserving order.
    - Tool messages get the `name` field re-attached from the
      preceding assistant tool_call with the matching id (our judges
      and our extract_tool_errors expect tool messages to carry the
      tool name).
    """
    out: list[dict[str, Any]] = []
    id_to_tool_name: dict[str, str] = {}

    for m in messages:
        role = getattr(m, "role", None)

        # Check MultiToolMessage FIRST (it also has role="tool" but
        # carries multiple wrapped tool messages instead of one).
        sub = getattr(m, "tool_messages", None)
        if sub is not None:
            for tm in sub:
                tool_id = getattr(tm, "id", "") or ""
                out.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": id_to_tool_name.get(tool_id, ""),
                    "content": getattr(tm, "content", "") or "",
                    "error": bool(getattr(tm, "error", False)),
                })
            continue

        if role == "assistant":
            tcs_raw = getattr(m, "tool_calls", None) or []
            tcs: list[dict[str, Any]] = []
            for tc in tcs_raw:
                d = _serialize_tool_call(tc)
                id_to_tool_name[d["id"]] = d["function"]["name"]
                tcs.append(d)
            out.append({
                "role": "assistant",
                "content": getattr(m, "content", None),
                "tool_calls": tcs or None,
            })

        elif role == "user":
            out.append({
                "role": "user",
                "content": getattr(m, "content", "") or "",
            })

        elif role == "tool":
            tool_id = getattr(m, "id", "") or ""
            out.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "name": id_to_tool_name.get(tool_id, ""),
                "content": getattr(m, "content", "") or "",
                "error": bool(getattr(m, "error", False)),
            })

        elif role == "system":
            out.append({"role": "system", "content": getattr(m, "content", "") or ""})

    return out


def classify_termination(
    messages: Sequence[dict[str, Any]],
    info: dict[str, Any],
    max_steps: int,
) -> dict[str, Any]:
    """Map tau2's termination_reason (now first-class) to our kind.

    Transfer-to-human is detected from the trajectory (independent
    signal) and takes precedence when present alongside a graded
    completion.
    """
    raw = (info or {}).get("termination_reason")
    kind = _TERMINATION_KIND_MAP.get(str(raw), "unknown")
    transferred = any(
        ((tc or {}).get("function") or {}).get("name") == "transfer_to_human_agents"
        for m in messages
        if m.get("role") == "assistant"
        for tc in (m.get("tool_calls") or [])
    )
    if transferred and kind == "completed":
        kind = "transfer"
    return {
        "kind": kind,
        "raw_termination_reason": str(raw) if raw is not None else None,
        "transferred": transferred,
        "n_messages": len(messages),
    }


def extract_tool_errors(
    messages: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Each tool message carries an explicit `error: bool` from tau2
    (rather than us grepping 'Error:' from content). When the flag is
    True, attribute the error to the most recent assistant tool_call
    with matching id."""
    out: list[dict[str, Any]] = []
    id_to_pos: dict[str, int] = {}
    for i, m in enumerate(messages):
        if m.get("role") == "assistant":
            for tc in (m.get("tool_calls") or []):
                tid = (tc or {}).get("id") or ""
                if tid:
                    id_to_pos[tid] = i
        elif m.get("role") == "tool" and m.get("error"):
            tid = m.get("tool_call_id") or ""
            pos = id_to_pos.get(tid, i)
            out.append({
                "position": pos,
                "tool": m.get("name") or "?",
                "message": (m.get("content") or "")[:200],
            })
    return out


def _reward_info_to_dict(ri: Any) -> dict[str, Any] | None:
    """Pydantic RewardInfo → JSON-safe dict. None passes through."""
    if ri is None:
        return None
    try:
        return ri.model_dump(mode="json")
    except AttributeError:
        # Already a dict (e.g. in tests)
        return dict(ri) if isinstance(ri, dict) else None


def run_task(
    task_index: str | int,
    *,
    agent_model: str = "gpt-4o-mini",
    agent_provider: str = "openai",
    user_model: str = "gpt-4o-mini",
    user_provider: str = "openai",
    max_steps: int = 30,
    wiki_override: str | None = None,
    eventlog: EventLog | None = None,
) -> dict[str, Any]:
    """Run τ³-bench's tool-calling agent on one airline task.

    `task_index` is the τ³-bench task id (string). int is accepted
    and stringified for compatibility with prior call sites.

    `wiki_override` (used by the v2 variant): if non-None, prepend
    its content as the new policy after building the env. Tau2's
    LLMAgent reads agent.domain_policy fresh on each system_prompt
    call, so post-construction mutation is honoured.

    Returns the same shape we have always returned:
        {
          task_index, reward, messages, info, total_cost,
          agent_model, user_model, max_steps, termination,
          tool_errors, duration_s,
        }
    """
    # Tau2 imports inside the function so the rest of the package
    # imports cheaply in unit tests (no LiteLLM bootstrap until needed).
    from tau2.data_model.simulation import TextRunConfig
    from tau2.run import get_tasks, run_simulation
    from tau2.runner import build_text_orchestrator

    task_id = str(task_index)

    if eventlog is not None:
        eventlog.emit(
            "task_start",
            task_index=task_id,
            agent_model=agent_model,
            user_model=user_model,
            max_steps=max_steps,
            wiki_override=(wiki_override is not None),
        )

    # tau2/litellm infers provider from the model name (gpt-* → openai,
    # claude-* → anthropic). Do not pass `provider` in llm_args — it
    # would be forwarded to the OpenAI API and rejected as unrecognized.
    del agent_provider, user_provider  # kept on signature for compatibility
    config = TextRunConfig(
        domain="airline",
        agent="llm_agent",
        llm_agent=agent_model,
        llm_args_agent={"temperature": 0.0},
        user="user_simulator",
        llm_user=user_model,
        llm_args_user={"temperature": 0.0},
        num_trials=1,
        max_steps=max_steps,
        task_set_name="airline",
        task_ids=[task_id],
    )

    tasks = get_tasks("airline", task_ids=[task_id])
    if not tasks:
        raise ValueError(f"no τ³-bench airline task with id {task_id!r}")
    task = tasks[0]

    t0 = time.time()
    orch = build_text_orchestrator(config, task, seed=42)
    if wiki_override is not None:
        # Prepend override to the existing policy. LLMAgent.system_prompt
        # is a property that reads self.domain_policy fresh, so this
        # takes effect on the first agent turn.
        orch.agent.domain_policy = wiki_override + orch.agent.domain_policy
    sim = run_simulation(orch)
    duration_s = time.time() - t0

    messages = _flatten_messages(sim.messages or [])
    reward_info_dict = _reward_info_to_dict(sim.reward_info)
    reward = float(reward_info_dict["reward"]) if reward_info_dict else 0.0
    info = {
        "reward_info": reward_info_dict,
        "termination_reason": (
            sim.termination_reason.value
            if hasattr(sim.termination_reason, "value")
            else str(sim.termination_reason)
        ),
        "duration": sim.duration,
        "agent_cost": sim.agent_cost,
        "user_cost": sim.user_cost,
    }
    termination = classify_termination(messages, info, max_steps)
    tool_errors = extract_tool_errors(messages)
    total_cost = (sim.agent_cost or 0.0) + (sim.user_cost or 0.0)

    if eventlog is not None:
        eventlog.emit(
            "task_end",
            task_index=task_id,
            reward=reward,
            termination_kind=termination["kind"],
            n_messages=len(messages),
            n_tool_errors=len(tool_errors),
            total_cost=total_cost,
            duration_s=duration_s,
        )

    return {
        "task_index": task_id,
        "reward": reward,
        "messages": messages,
        "info": info,
        "total_cost": total_cost,
        "agent_model": agent_model,
        "user_model": user_model,
        "max_steps": max_steps,
        "termination": termination,
        "tool_errors": tool_errors,
        "duration_s": duration_s,
    }


def airline_tool_catalog() -> list[dict[str, str]]:
    """Return the airline tools as [{name, description}] entries.

    Used by scripts/generate_contract.py to feed contract.generate_contract.
    Read via tau2 Tool.openai_schema (stable public surface) so we
    pick up the same description text the agent itself sees.
    """
    from tau2.domains.airline.environment import get_environment

    env = get_environment()
    out: list[dict[str, str]] = []
    for tool in env.get_tools():
        schema = tool.openai_schema
        fn = (schema or {}).get("function") or {}
        out.append({
            "name": fn.get("name") or tool.name,
            "description": fn.get("description") or "",
        })
    return out
