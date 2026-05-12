"""Contract: structured rules extracted from an agent's policy.

A contract is the operational artifact judges consume. It is generated
once per agent-under-evaluation (one LLM call against policy.md + tool
catalog) and committed as data/contract.json.

Schema (canonical):

    {
      "agent": "tau_bench_airline",
      "obligations": [
        {"id": "obl-1", "text": "...", "category": "<taxonomy id>"}
      ],
      "forbidden_behaviors": [
        {"id": "fb-1", "text": "...", "category": "<taxonomy id>"}
      ],
      "tool_sequences": [
        {
          "id": "ts-1",
          "target_tool": "book_reservation",
          "prerequisite_tools": ["get_user_details"],
          "category": "tool_sequence_correctness"
        }
      ]
    }

Every clause's `category` must reference a valid taxonomy id.
validate_contract enforces this at save and load time so judges can
assume the link is sound.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grounding_agent.taxonomy import category_ids


CONTRACT_KEYS: tuple[str, ...] = (
    "agent",
    "obligations",
    "forbidden_behaviors",
    "tool_sequences",
)

CLAUSE_KEYS: dict[str, tuple[str, ...]] = {
    "obligations": ("id", "text", "category"),
    "forbidden_behaviors": ("id", "text", "category"),
    "tool_sequences": ("id", "target_tool", "prerequisite_tools", "category"),
}


class ContractError(ValueError):
    pass


def validate_contract(contract: dict[str, Any]) -> None:
    if not isinstance(contract, dict):
        raise ContractError("contract must be a JSON object")

    for k in CONTRACT_KEYS:
        if k not in contract:
            raise ContractError(f"missing top-level key: {k!r}")

    if not isinstance(contract["agent"], str) or not contract["agent"].strip():
        raise ContractError("'agent' must be a non-empty string")

    known = set(category_ids())
    seen_ids: set[str] = set()

    for section, required_keys in CLAUSE_KEYS.items():
        clauses = contract[section]
        if not isinstance(clauses, list):
            raise ContractError(f"{section!r} must be a list")
        for i, clause in enumerate(clauses):
            if not isinstance(clause, dict):
                raise ContractError(f"{section}[{i}] must be an object")
            for rk in required_keys:
                if rk not in clause:
                    raise ContractError(
                        f"{section}[{i}] missing key: {rk!r}"
                    )

            cid = clause["id"]
            if not isinstance(cid, str) or not cid.strip():
                raise ContractError(
                    f"{section}[{i}].id must be a non-empty string"
                )
            if cid in seen_ids:
                raise ContractError(f"duplicate clause id: {cid!r}")
            seen_ids.add(cid)

            cat = clause["category"]
            if cat not in known:
                raise ContractError(
                    f"{section}[{i}] references unknown category {cat!r}; "
                    f"known: {sorted(known)}"
                )

            if section in ("obligations", "forbidden_behaviors"):
                text = clause["text"]
                if not isinstance(text, str) or not text.strip():
                    raise ContractError(
                        f"{section}[{i}].text must be a non-empty string"
                    )
            else:
                target = clause["target_tool"]
                if not isinstance(target, str) or not target.strip():
                    raise ContractError(
                        f"{section}[{i}].target_tool must be a non-empty string"
                    )
                prereqs = clause["prerequisite_tools"]
                if not isinstance(prereqs, list) or not all(
                    isinstance(t, str) and t.strip() for t in prereqs
                ):
                    raise ContractError(
                        f"{section}[{i}].prerequisite_tools must be a list "
                        "of non-empty strings"
                    )


def load_contract(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        contract = json.load(f)
    validate_contract(contract)
    return contract


def save_contract(contract: dict[str, Any], path: Path) -> None:
    validate_contract(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)
        f.write("\n")


def generate_contract(
    policy_text: str,
    tool_catalog: list[dict[str, str]],
    model: str = "gpt-4o-mini",
    agent_name: str = "tau_bench_airline",
) -> dict[str, Any]:
    """Single LLM call: policy + tools → contract JSON.

    Routed through litellm so the same code works against OpenAI,
    Anthropic, etc. The prompt is constrained: the model must emit JSON
    in the documented schema, and every clause must be tagged with one
    of the taxonomy ids. Output is validated before return; ContractError
    on schema violation.
    """
    import litellm

    known = list(category_ids())
    tool_lines = "\n".join(
        f"- {t['name']}: {t['description']}" for t in tool_catalog
    )
    schema_example = (
        '{\n'
        '  "agent": "<agent_name>",\n'
        '  "obligations": [\n'
        '    {"id": "obl-<slug>", "text": "<imperative>", "category": "<one of the categories below>"}\n'
        '  ],\n'
        '  "forbidden_behaviors": [\n'
        '    {"id": "fb-<slug>", "text": "<prohibition>", "category": "<one of the categories below>"}\n'
        '  ],\n'
        '  "tool_sequences": [\n'
        '    {"id": "ts-<slug>", "target_tool": "<one of the tool names listed below>", '
        '"prerequisite_tools": ["<tool name>", ...], "category": "tool_sequence_correctness"}\n'
        '  ]\n'
        '}'
    )
    # Worked example per category — disambiguates the recurring
    # mistagging where business-rule prohibitions ("can't modify basic
    # economy") were placed in scope_adherence rather than
    # policy_compliance (forensics_v2.md Finding 8).
    category_defs = (
        "CATEGORY DEFINITIONS (apply rigorously):\n\n"
        "1. **policy_compliance** — Business rules the agent must "
        "enforce: eligibility, quantity limits, conditional gates. "
        "Examples: 'basic economy flights cannot be modified', "
        "'cancel within 24h of booking only', 'compensate $100 only "
        "for silver/gold members'. ANY rule whose action is 'apply the "
        "rule when X / refuse when Y' belongs here — even if it sounds "
        "like a prohibition. Most business prohibitions are this.\n\n"
        "2. **confirmation_discipline** — Specifically about getting an "
        "explicit user 'yes' before a state-mutating tool call. "
        "Example: 'list the action and obtain explicit confirmation "
        "before booking'.\n\n"
        "3. **information_grounding** — Don't invent facts not in tool "
        "outputs or user messages. Example: 'no procedures or knowledge "
        "not provided by user or tools', 'no subjective recommendations'.\n\n"
        "4. **scope_adherence** — ONLY about the transfer-to-human "
        "decision: when to transfer, when NOT to transfer. Example: "
        "'transfer iff the request cannot be handled within scope'. "
        "Do NOT tag business rules here just because they describe "
        "what the agent cannot do. A 'can't modify basic economy' rule "
        "is policy_compliance — the agent denies the request per the "
        "rule; it does not (and should not) transfer.\n\n"
        "5. **tool_sequence_correctness** — Tool ORDERING rules (call "
        "prerequisite reads before mutating tools). Tag every "
        "tool_sequences clause here.\n\n"
        "6. **tool_argument_correctness** — Argument VALIDITY rules "
        "(check eligibility/availability/balance before calling). "
        "Examples: 'the API does not check these; the agent must make "
        "sure rules apply before calling'. Use sparingly; most rules "
        "are about WHAT to do (policy_compliance), not VALIDATION of "
        "tool arguments per se.\n\n"
        "7. **task_completion** — End-to-end goal achievement; "
        "typically NOT cited in obligations because completion is "
        "implicit. Skip unless the policy has an explicit 'finish the "
        "task' clause.\n\n"
        "DECISION HEURISTIC:\n"
        "- 'Don't do X' where X is a business action → policy_compliance.\n"
        "- 'Don't do X' where X is to transfer/escalate → scope_adherence.\n"
        "- 'Don't say X' where X is unverified → information_grounding.\n"
        "- 'Don't call tool X without read Y' → tool_sequence_correctness.\n"
        "- 'Must validate args before calling X' → tool_argument_correctness.\n"
        "- 'Must obtain user yes before calling X' → confirmation_discipline.\n"
    )
    system = (
        "You extract a structured contract from an agent's operating "
        "policy. Return ONLY a JSON object (no prose, no markdown fences) "
        "in EXACTLY this schema:\n\n"
        + schema_example
        + "\n\n"
        + category_defs
        + "\nRULES:\n"
        "- EVERY clause in EVERY section MUST include all fields shown "
        "above. Ids must be unique across the document (lowercase-kebab, "
        "prefixed obl- / fb- / ts-).\n"
        "- 'category' must be one of EXACTLY these strings: "
        + ", ".join(known)
        + ". No other category values are allowed.\n"
        "- Tag each clause using the DECISION HEURISTIC above. When in "
        "doubt between policy_compliance and scope_adherence, choose "
        "policy_compliance unless the clause is specifically about "
        "transferring to a human.\n"
        "- Emit a tool_sequences entry only for mutating tools where the "
        "policy implies a prerequisite read.\n"
        "- Cover the major policy clauses — every distinct obligation "
        "and prohibition that an evaluator would need to check."
    )
    user = (
        f"Agent name: {agent_name}\n\n"
        f"Available tools:\n{tool_lines}\n\n"
        f"Policy:\n{policy_text}"
    )

    resp = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = resp["choices"][0]["message"]["content"]
    contract = json.loads(content)
    if "agent" not in contract:
        contract["agent"] = agent_name
    validate_contract(contract)
    return contract
