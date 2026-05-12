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
        '    {"id": "obl-<slug>", "text": "<imperative>", "category": "<one of: '
        + ", ".join(known)
        + '>"}\n'
        '  ],\n'
        '  "forbidden_behaviors": [\n'
        '    {"id": "fb-<slug>", "text": "<prohibition>", "category": "<one of the categories above>"}\n'
        '  ],\n'
        '  "tool_sequences": [\n'
        '    {"id": "ts-<slug>", "target_tool": "<one of the tool names listed below>", '
        '"prerequisite_tools": ["<tool name>", ...], "category": "tool_sequence_correctness"}\n'
        '  ]\n'
        '}'
    )
    system = (
        "You extract a structured contract from an agent's operating "
        "policy. Return ONLY a JSON object (no prose, no markdown fences) "
        "in EXACTLY this schema:\n\n"
        + schema_example
        + "\n\nRULES:\n"
        "- EVERY clause in EVERY section (obligations, forbidden_behaviors, "
        "tool_sequences) MUST include all fields shown above. The 'id' "
        "field is mandatory on every clause; ids must be unique across "
        "the whole document (lowercase-kebab, prefixed obl- / fb- / ts-).\n"
        "- 'category' must be one of EXACTLY these strings: "
        + ", ".join(known)
        + ". No other category values are allowed.\n"
        "- Emit a tool_sequences entry only for mutating tools where the "
        "policy implies a prerequisite read (e.g. get_user_details before "
        "book_reservation). Each prerequisite must be a tool name from "
        "the catalog below.\n"
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
