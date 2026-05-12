"""Generate data/contract.json from vendored policy.md + airline tools.

One LLM call via litellm. Idempotent unless --force is passed. The
generated file is the operational artifact judges consume; commit it
after generation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from grounding_agent.contract import generate_contract, save_contract
from grounding_agent.runner import airline_tool_catalog


REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "vendor" / "tau_bench_airline" / "policy.md"
CONTRACT_PATH = REPO_ROOT / "data" / "contract.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    load_dotenv()

    if CONTRACT_PATH.exists() and not args.force:
        print(
            f"{CONTRACT_PATH.relative_to(REPO_ROOT)} already exists; "
            "pass --force to regenerate."
        )
        return

    policy_text = POLICY_PATH.read_text(encoding="utf-8")
    tool_catalog = airline_tool_catalog()
    print(f"Generating contract via {args.model} ...")
    contract = generate_contract(
        policy_text=policy_text,
        tool_catalog=tool_catalog,
        model=args.model,
        agent_name="tau_bench_airline",
    )
    save_contract(contract, CONTRACT_PATH)
    print(
        f"  obligations: {len(contract['obligations'])} | "
        f"forbidden: {len(contract['forbidden_behaviors'])} | "
        f"tool_sequences: {len(contract['tool_sequences'])}"
    )
    print(f"Wrote {CONTRACT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
