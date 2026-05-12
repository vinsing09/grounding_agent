"""Apply judges to a trajectory.

Single entry point: evaluate_trajectory(messages, contract, model) ->
{<category>: JudgeResult, ...}. Runs every judge in judges.ALL_JUDGES
and indexes the results by category. Returns one entry per applicable
taxonomy category (currently four semantic + one deterministic = five
entries).
"""

from __future__ import annotations

from typing import Any, Sequence

from grounding_agent.judges import ALL_JUDGES, JudgeResult


def evaluate_trajectory(
    messages: Sequence[dict[str, Any]],
    contract: dict[str, Any],
    model: str = "gpt-4o-mini",
) -> dict[str, JudgeResult]:
    results: dict[str, JudgeResult] = {}
    for judge in ALL_JUDGES:
        r = judge(messages, contract, model=model)
        if r.category in results:
            raise RuntimeError(
                f"duplicate judge category in ALL_JUDGES: {r.category!r}"
            )
        results[r.category] = r
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
            }
            for cat, r in results.items()
        },
    }
