"""Three deterministic judges — Python-only, no LLM calls.

- `tool_sequence_judge`: prerequisite-read ordering.
- `confirmation_discipline_judge`: per-mutation user yes.
- `tool_argument_correctness_judge`: tool-server error responses.
"""

from __future__ import annotations

from typing import Any, Sequence

from grounding_agent.judges._common import (
    JudgeResult,
    MUTATING_TOOLS,
    extract_tool_calls,
    is_affirmative,
)


def tool_sequence_judge(
    messages: Sequence[dict[str, Any]],
    contract: dict[str, Any],
    model: str | None = None,
) -> JudgeResult:
    """Deterministic. For each tool_sequence clause, every occurrence of
    `target_tool` must be preceded by at least one call to every
    `prerequisite_tool`. Vacuously passes when the contract has no
    tool_sequences or when no clause's target appears in the trajectory.
    """
    del model
    calls = extract_tool_calls(messages)
    name_to_positions: dict[str, list[int]] = {}
    for c in calls:
        name_to_positions.setdefault(c["name"], []).append(c["position"])

    violations: list[str] = []
    matched_clauses: list[str] = []

    for clause in contract.get("tool_sequences", []):
        target = clause["target_tool"]
        prereqs = clause["prerequisite_tools"]
        target_positions = name_to_positions.get(target, [])
        if not target_positions:
            continue
        matched_clauses.append(clause["id"])
        for tp in target_positions:
            for pre in prereqs:
                pre_positions = name_to_positions.get(pre, [])
                if not any(p < tp for p in pre_positions):
                    violations.append(
                        f"{clause['id']}: {target}@{tp} called without "
                        f"prerequisite {pre!r}"
                    )

    if violations:
        return JudgeResult(
            category="tool_sequence_correctness",
            passed=False,
            reason="; ".join(violations),
            clause_refs=tuple(matched_clauses),
        )
    if matched_clauses:
        reason = f"all {len(matched_clauses)} matched tool_sequence clause(s) satisfied"
    else:
        reason = "no tool_sequence clauses matched this trajectory"
    return JudgeResult(
        category="tool_sequence_correctness",
        passed=True,
        reason=reason,
        clause_refs=tuple(matched_clauses),
    )


def confirmation_discipline_judge(
    messages: Sequence[dict[str, Any]],
    contract: dict[str, Any],
    model: str | None = None,
) -> JudgeResult:
    """Deterministic. For each mutating tool call (one of MUTATING_TOOLS),
    require an affirmative user turn somewhere between the previous
    *consumed* affirmative (or the start of the trajectory) and the
    current mutation's position.

    Strict per-mutation: one user "yes" cannot authorize a back-to-back
    second mutation. That matches the policy text — "before any actions
    that update the booking database… obtain explicit user confirmation
    (yes) to proceed" — interpreted per-action.

    Returns `score` = (mutations_confirmed / total_mutations) when
    there are mutations; None otherwise. `passed` is True iff every
    mutation found a fresh preceding affirmative.

    `clause_refs` mirrors the semantic-judge convention: contract
    clauses tagged to this category.
    """
    del model
    clause_ids = tuple(
        c["id"] for c in (
            (contract.get("obligations") or [])
            + (contract.get("forbidden_behaviors") or [])
        ) if c.get("category") == "confirmation_discipline"
    )

    unconfirmed: list[str] = []
    confirmed: list[str] = []
    n_mut = 0
    last_consumed_yes_position = -1

    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        for tc in m.get("tool_calls") or []:
            fn = (tc or {}).get("function") or {}
            name = fn.get("name")
            if name not in MUTATING_TOOLS:
                continue
            n_mut += 1
            confirmed_at = None
            for j in range(i - 1, last_consumed_yes_position, -1):
                mj = messages[j]
                if mj.get("role") != "user":
                    continue
                if is_affirmative(mj.get("content") or ""):
                    confirmed_at = j
                    break
            tag = f"{name}@{i}"
            if confirmed_at is None:
                unconfirmed.append(tag)
            else:
                confirmed.append(tag)
                last_consumed_yes_position = confirmed_at

    if n_mut == 0:
        return JudgeResult(
            category="confirmation_discipline",
            passed=True,
            reason="no mutating tool calls in this trajectory",
            clause_refs=clause_ids,
            score=None,
        )

    rate = len(confirmed) / n_mut
    passed = len(unconfirmed) == 0
    if passed:
        reason = f"{n_mut}/{n_mut} mutations preceded by a fresh affirmative user turn (rate=100%)"
    else:
        head = ", ".join(unconfirmed[:8])
        more = f" (+{len(unconfirmed) - 8} more)" if len(unconfirmed) > 8 else ""
        reason = (
            f"{len(confirmed)}/{n_mut} mutations confirmed (rate={rate:.0%}); "
            f"unconfirmed: {head}{more}"
        )
    return JudgeResult(
        category="confirmation_discipline",
        passed=passed,
        reason=reason,
        clause_refs=clause_ids,
        score=rate,
    )


def tool_argument_correctness_judge(
    messages: Sequence[dict[str, Any]],
    contract: dict[str, Any],
    model: str | None = None,
) -> JudgeResult:
    """Deterministic. The tool server is the oracle: any tool return
    starting with 'Error:' (or carrying error=True in τ³-bench) indicates
    the agent's call had an invalid argument (bad payment math, missing
    balance, nonexistent ID, etc.).

    Returns `score` = (n_calls - n_errors) / n_calls when there are
    tool calls; None otherwise. `passed` iff zero errors observed.
    """
    del model
    clause_ids = tuple(
        c["id"] for c in (
            (contract.get("obligations") or [])
            + (contract.get("forbidden_behaviors") or [])
        ) if c.get("category") == "tool_argument_correctness"
    )

    # Pair each tool-return with its triggering assistant tool_call so
    # we can cite (tool, position). We use FIFO pairing since tool
    # messages don't always carry tool_call_id reliably.
    pending: list[tuple[int, str]] = []
    n_calls = 0
    errors: list[str] = []
    for i, m in enumerate(messages):
        role = m.get("role")
        if role == "assistant":
            for tc in m.get("tool_calls") or []:
                fn = (tc or {}).get("function") or {}
                name = fn.get("name")
                if not name:
                    continue
                pending.append((i, name))
                n_calls += 1
        elif role == "tool":
            content = (m.get("content") or "").strip()
            if pending:
                call_pos, call_name = pending.pop(0)
            else:
                call_pos, call_name = i, m.get("name") or "?"
            if content.startswith("Error:") or content.startswith("Error "):
                errors.append(f"{call_name}@{call_pos}: {content[:120]}")

    if n_calls == 0:
        return JudgeResult(
            category="tool_argument_correctness",
            passed=True,
            reason="no tool calls in this trajectory",
            clause_refs=clause_ids,
            score=None,
        )
    rate = (n_calls - len(errors)) / n_calls
    passed = len(errors) == 0
    if passed:
        reason = f"{n_calls}/{n_calls} tool calls returned no error (rate=100%)"
    else:
        head = "; ".join(errors[:5])
        more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
        reason = (
            f"{n_calls - len(errors)}/{n_calls} tool calls succeeded "
            f"(rate={rate:.0%}); errors: {head}{more}"
        )
    return JudgeResult(
        category="tool_argument_correctness",
        passed=passed,
        reason=reason,
        clause_refs=clause_ids,
        score=rate,
    )
