"""Failure taxonomy for tool-calling LLM agents under evaluation.

Six categories grounded in structural failure modes of tool-using agents
operating against a policy. Each category drives one judge dimension in
the eval pipeline; the contract generator tags every policy clause to
one of these categories so judges can resolve a clause back to a
dimension at scoring time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


JudgeKind = Literal["semantic", "deterministic"]


@dataclass(frozen=True)
class FailureCategory:
    id: str
    name: str
    description: str
    judge_dimension: str
    judge_kind: JudgeKind
    example: str


TAXONOMY: tuple[FailureCategory, ...] = (
    FailureCategory(
        id="policy_compliance",
        name="Policy Compliance",
        description=(
            "Agent enforces business rules of the operating policy: eligibility "
            "constraints, quantity limits, conditional gates. Failure = the "
            "agent permits or recommends an action the policy forbids, or "
            "denies an action the policy allows."
        ),
        judge_dimension="policy_compliance",
        judge_kind="semantic",
        example=(
            "Policy says basic economy cannot be modified. User asks to change "
            "their basic-economy flight. Agent calls update_reservation_flights "
            "anyway — policy_compliance fail."
        ),
    ),
    FailureCategory(
        id="confirmation_discipline",
        name="Confirmation Discipline",
        description=(
            "Before any state-mutating tool call (booking, cancellation, "
            "baggage/flight/passenger edits, certificate sends), the agent "
            "must summarize the action and obtain an explicit affirmative "
            "from the user. Failure = mutation without prior confirmation. "
            "Checked deterministically: for each mutating tool call, the "
            "most recent unused user turn must contain an affirmative "
            "(yes/ok/proceed/...) without a leading negation."
        ),
        judge_dimension="confirmation_discipline",
        judge_kind="deterministic",
        example=(
            "Agent calls book_reservation immediately after gathering flight "
            "details without waiting for the user's 'yes' — "
            "confirmation_discipline fail."
        ),
    ),
    FailureCategory(
        id="information_grounding",
        name="Information Grounding",
        description=(
            "Agent's factual claims must come from the user's messages or "
            "tool outputs. No fabricated prices, dates, eligibility rules, "
            "refund amounts, or procedures; no subjective recommendations. "
            "Failure = an assertion that cannot be traced to a turn upstream."
        ),
        judge_dimension="information_grounding",
        judge_kind="semantic",
        example=(
            "Agent tells the user 'flights between NYC and SEA usually take "
            "six hours' without having called any search tool — "
            "information_grounding fail."
        ),
    ),
    FailureCategory(
        id="scope_adherence",
        name="Scope Adherence",
        description=(
            "Agent transfers to a human only when the request cannot be "
            "handled with the available tools and policy, and never refuses "
            "a request that is in-scope. Failure = transfer-on-in-scope, "
            "transfer-on-policy-denial (should be denied, not escalated), "
            "or attempting to serve a clearly out-of-scope request."
        ),
        judge_dimension="scope_adherence",
        judge_kind="semantic",
        example=(
            "User asks to modify a basic-economy flight. Correct path: "
            "explain policy and offer alternatives (cancel-and-rebook if "
            "eligible). Transferring to a human instead — scope_adherence "
            "fail."
        ),
    ),
    FailureCategory(
        id="tool_sequence_correctness",
        name="Tool Sequence Correctness",
        description=(
            "For each mutating tool call, required prerequisite reads (e.g. "
            "get_user_details before book_reservation; get_reservation_details "
            "before update_reservation_flights) must precede it in the "
            "trajectory. Failure = a mutation without its prerequisite read."
        ),
        judge_dimension="tool_sequence_correctness",
        judge_kind="deterministic",
        example=(
            "Agent calls book_reservation with user_id='mia_li_3668' but "
            "never called get_user_details — tool_sequence_correctness fail."
        ),
    ),
    FailureCategory(
        id="tool_argument_correctness",
        name="Tool Argument Correctness",
        description=(
            "When the agent calls a tool, the arguments must be valid for "
            "the operation: payment splits sum to the total, payment "
            "methods belong to the user, gift-card balances cover the cost, "
            "user/reservation ids exist. The tau-bench tool server is the "
            "deterministic oracle: any tool return starting with 'Error:' "
            "is evidence the agent supplied an argument it should have "
            "validated against prior reads. Added after forensics Finding 3 "
            "showed arithmetic errors dominated the agent's failure mode."
        ),
        judge_dimension="tool_argument_correctness",
        judge_kind="deterministic",
        example=(
            "Agent calls book_reservation with payment_methods summing to "
            "$152 for a $355 flight. Tool returns 'Error: payment amount "
            "does not add up'. The agent should have computed the total — "
            "tool_argument_correctness fail."
        ),
    ),
    FailureCategory(
        id="task_completion",
        name="Task Completion",
        description=(
            "Agent achieves the user's stated goal end-to-end: the requested "
            "booking is made, the cancellation goes through, the question is "
            "answered. Failure = abandonment, clarification loops, stopping "
            "after a partial action when the user's goal required more, or "
            "completing the wrong task."
        ),
        judge_dimension="task_completion",
        judge_kind="semantic",
        example=(
            "User asks to downgrade all three business reservations to "
            "economy; agent downgrades one and ends the conversation — "
            "task_completion fail."
        ),
    ),
)


_BY_ID: dict[str, FailureCategory] = {c.id: c for c in TAXONOMY}

assert len(_BY_ID) == len(TAXONOMY), "duplicate category id in TAXONOMY"
assert len(TAXONOMY) == 7, "taxonomy must have exactly seven categories"


def get_category(category_id: str) -> FailureCategory:
    try:
        return _BY_ID[category_id]
    except KeyError as e:
        raise KeyError(
            f"unknown taxonomy category: {category_id!r}. "
            f"known: {sorted(_BY_ID)}"
        ) from e


def category_ids() -> tuple[str, ...]:
    return tuple(c.id for c in TAXONOMY)
