"""Shared types, constants, and trajectory helpers for the judges.

Kept in one place so deterministic and semantic judges import the
same primitives.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class JudgeResult:
    category: str
    passed: bool
    reason: str
    clause_refs: tuple[str, ...] = field(default_factory=tuple)
    score: float | None = None


SEMANTIC_CATEGORIES: tuple[str, ...] = (
    "policy_compliance",
    "information_grounding",
    "scope_adherence",
)


MUTATING_TOOLS: frozenset[str] = frozenset({
    "book_reservation",
    "cancel_reservation",
    "update_reservation_baggages",
    "update_reservation_flights",
    "update_reservation_passengers",
    "send_certificate",
})


# Affirmative detection — used by confirmation_discipline_judge.
_AFFIRMATIVE_WORDS: tuple[str, ...] = (
    "yes", "yeah", "yep", "yup",
    "ok", "okay",
    "proceed", "confirm", "confirmed",
)

_AFFIRMATIVE_PHRASES: tuple[str, ...] = (
    "go ahead", "go for it",
    "do it", "do that", "please do",
    "sounds good", "looks good", "that works",
    "let's do it", "let us do it",
    "all good",
)

# Negation-leading patterns. Checked at the START of the (stripped,
# lowercased) message. If any matches, the message is NOT treated as
# an affirmative even if an affirmative word appears later in the text.
_NEGATIVE_LEADERS: tuple[str, ...] = (
    "no", "not", "nope",
    "wait", "hold on", "hold up",
    "stop", "cancel",
    "don't", "do not", "dont",
    "actually no", "never mind", "nevermind",
)

_AFFIRMATIVE_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _AFFIRMATIVE_WORDS) + r")\b",
    re.IGNORECASE,
)


def _starts_with_negation(text: str) -> bool:
    lower = (text or "").lower().strip()
    if not lower:
        return False
    for n in _NEGATIVE_LEADERS:
        if lower == n:
            return True
        if (
            lower.startswith(n + " ")
            or lower.startswith(n + ",")
            or lower.startswith(n + ".")
            or lower.startswith(n + "!")
            or lower.startswith(n + "?")
        ):
            return True
    return False


def is_affirmative(text: str) -> bool:
    """True if `text` reads as an explicit user yes.

    - Empty/blank text → not affirmative.
    - Starts with a negation pattern → not affirmative (regardless of
      other words later in the message).
    - Otherwise, contains an affirmative word at a word boundary, OR
      contains an affirmative phrase as a substring.
    """
    if not text or not text.strip():
        return False
    if _starts_with_negation(text):
        return False
    if _AFFIRMATIVE_WORD_RE.search(text):
        return True
    lower = text.lower()
    for phrase in _AFFIRMATIVE_PHRASES:
        if phrase in lower:
            return True
    return False


def extract_tool_calls(
    messages: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flatten an assistant trajectory into one entry per executed tool call.

    Each entry: {"position": int, "name": str, "arguments": dict}.
    `position` is the index in `messages` of the emitting assistant
    message, so prerequisite-ordering checks are unambiguous.
    """
    out: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        tcs = m.get("tool_calls") or []
        for tc in tcs:
            fn = (tc or {}).get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            raw = fn.get("arguments")
            if isinstance(raw, str):
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = {"_raw_arguments": raw}
            elif isinstance(raw, dict):
                args = raw
            else:
                args = {}
            out.append({"position": i, "name": name, "arguments": args})
    return out


def format_trajectory(messages: Sequence[dict[str, Any]]) -> str:
    """Compact, role-tagged rendering for inclusion in judge prompts.

    System messages are omitted — the judge gets the relevant
    obligations/forbidden behaviors via the prompt, not the agent's full
    system prompt (which would dilute attention).
    """
    lines: list[str] = []
    for i, m in enumerate(messages):
        role = m.get("role", "?")
        if role == "system":
            continue
        if role == "assistant":
            tcs = m.get("tool_calls") or []
            for tc in tcs:
                fn = (tc or {}).get("function") or {}
                lines.append(
                    f"[{i}] assistant -> tool_call "
                    f"{fn.get('name')}({fn.get('arguments')})"
                )
            content = m.get("content")
            if content:
                lines.append(f"[{i}] assistant: {content}")
        elif role == "tool":
            lines.append(
                f"[{i}] tool[{m.get('name') or '?'}]: {m.get('content') or ''}"
            )
        elif role == "user":
            lines.append(f"[{i}] user: {m.get('content') or ''}")
        else:
            lines.append(f"[{i}] {role}: {m.get('content') or ''}")
    return "\n".join(lines)


def format_agent_actions(messages: Sequence[dict[str, Any]]) -> str:
    """Render ONLY what the agent did: tool calls (with args), tool
    returns (since they reveal whether the action took effect), and
    the agent's verbal responses. User turns are deliberately excluded
    so judges focus on agent behavior, not on user requests
    (forensics Finding 5).
    """
    lines: list[str] = []
    for i, m in enumerate(messages):
        role = m.get("role")
        if role == "assistant":
            tcs = m.get("tool_calls") or []
            for tc in tcs:
                fn = (tc or {}).get("function") or {}
                lines.append(
                    f"[{i}] AGENT CALL {fn.get('name')}({fn.get('arguments')})"
                )
            content = m.get("content")
            if content:
                lines.append(f"[{i}] AGENT SAYS: {content}")
        elif role == "tool":
            lines.append(
                f"[{i}] TOOL RETURN [{m.get('name') or '?'}]: "
                f"{m.get('content') or ''}"
            )
    return "\n".join(lines) or "(agent did not act)"
