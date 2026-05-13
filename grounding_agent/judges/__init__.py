"""Six judges: three deterministic + three semantic.

Each takes (messages, contract, model) -> JudgeResult and is callable
through this package's flat namespace, e.g.:

    from grounding_agent.judges import (
        JudgeResult,
        ALL_JUDGES,
        tool_sequence_judge,
        confirmation_discipline_judge,
        policy_compliance_judge,
        ...
    )

`task_completion` from the taxonomy is intentionally not judged here:
the τ³-bench reward already measures it; a separate LLM judge would
conflate evaluator noise with ground-truth signal. Observed via
`grounding_agent/compare.py`.
"""

from __future__ import annotations

from typing import Callable

from grounding_agent.judges._common import (
    JudgeResult,
    MUTATING_TOOLS,
    SEMANTIC_CATEGORIES,
    extract_tool_calls,
    format_agent_actions,
    format_trajectory,
    is_affirmative,
)
from grounding_agent.judges._deterministic import (
    confirmation_discipline_judge,
    tool_argument_correctness_judge,
    tool_sequence_judge,
)
from grounding_agent.judges._semantic import (
    _build_semantic_judge_prompt,
    _semantic_judge,
    information_grounding_judge,
    policy_compliance_judge,
    scope_adherence_judge,
)


JudgeFn = Callable[..., JudgeResult]

ALL_JUDGES: tuple[JudgeFn, ...] = (
    policy_compliance_judge,
    confirmation_discipline_judge,
    information_grounding_judge,
    scope_adherence_judge,
    tool_sequence_judge,
    tool_argument_correctness_judge,
)


__all__ = [
    "ALL_JUDGES",
    "JudgeFn",
    "JudgeResult",
    "MUTATING_TOOLS",
    "SEMANTIC_CATEGORIES",
    "_build_semantic_judge_prompt",
    "_semantic_judge",
    "confirmation_discipline_judge",
    "extract_tool_calls",
    "format_agent_actions",
    "format_trajectory",
    "information_grounding_judge",
    "is_affirmative",
    "policy_compliance_judge",
    "scope_adherence_judge",
    "tool_argument_correctness_judge",
    "tool_sequence_judge",
]
