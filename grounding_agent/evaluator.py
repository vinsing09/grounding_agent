"""Apply judges to a trajectory.

Single entry point: evaluate_trajectory(messages, contract, model) ->
{<category>: JudgeResult, ...}. Runs every judge in judges.ALL_JUDGES
and indexes the results by category. Returns one entry per applicable
taxonomy category (three semantic + three deterministic = six entries
after Bucket A/C).

If an eventlog is supplied, a judge_invocation event is emitted per
judge with duration, verdict, and clause-ref count.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

from grounding_agent.eventlog import EventLog
from grounding_agent.judges import ALL_JUDGES, JudgeResult


def evaluate_trajectory(
    messages: Sequence[dict[str, Any]],
    contract: dict[str, Any],
    model: str = "gpt-4o-mini",
    *,
    eventlog: EventLog | None = None,
    task_index: int | None = None,
) -> dict[str, JudgeResult]:
    results: dict[str, JudgeResult] = {}
    for judge in ALL_JUDGES:
        t0 = time.time()
        r = judge(messages, contract, model=model)
        elapsed = time.time() - t0
        if r.category in results:
            raise RuntimeError(
                f"duplicate judge category in ALL_JUDGES: {r.category!r}"
            )
        results[r.category] = r
        if eventlog is not None:
            eventlog.emit(
                "judge_invocation",
                task_index=task_index,
                category=r.category,
                passed=r.passed,
                score=r.score,
                n_clause_refs=len(r.clause_refs),
                duration_ms=int(elapsed * 1000),
            )
    return results


def summarize(results: dict[str, JudgeResult]) -> dict[str, Any]:
    """One-line-per-category condensed view, suitable for JSON dump."""
    n_pass = sum(1 for r in results.values() if r.passed)
    return {
        "n_dimensions": len(results),
        "n_passed": n_pass,
        "n_failed": len(results) - n_pass,
        "by_dimension": {
            cat: {
                "passed": r.passed,
                "reason": r.reason,
                "clause_refs": list(r.clause_refs),
                "score": r.score,
            }
            for cat, r in results.items()
        },
    }
