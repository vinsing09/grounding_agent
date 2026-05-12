"""End-to-end smoke test: run agent on 2 tasks, then evaluate.

Loads data/contract.json (produced by scripts/generate_contract.py),
runs the tau-bench tool-calling agent on tasks 0 and 1, applies the
five judges via the evaluator, and prints per-dimension verdicts
alongside the tau-bench ground-truth reward.

Smoke = does the pipeline run end-to-end? Whether the judges happen
to agree with the reward on these two tasks is informational; the
systematic comparison happens in Day 2's scripts/run_eval.py +
scripts/compare_to_reward.py.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from grounding_agent.contract import load_contract
from grounding_agent.evaluator import evaluate_trajectory, summarize
from grounding_agent.runner import run_task


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "data" / "contract.json"

TASKS = [0, 1]
JUDGE_MODEL = "gpt-4o-mini"
AGENT_MODEL = "gpt-4o-mini"
USER_MODEL = "gpt-4o-mini"


def main() -> None:
    load_dotenv()
    contract = load_contract(CONTRACT_PATH)
    print(
        f"Loaded contract: "
        f"{len(contract['obligations'])} obligations, "
        f"{len(contract['forbidden_behaviors'])} forbidden, "
        f"{len(contract['tool_sequences'])} tool_sequences"
    )

    for task_index in TASKS:
        print(f"\n--- task {task_index} ---")
        run = run_task(
            task_index=task_index,
            agent_model=AGENT_MODEL,
            agent_provider="openai",
            user_model=USER_MODEL,
            user_provider="openai",
            max_steps=30,
        )
        print(f"tau-bench reward: {run['reward']}")
        print(
            f"messages: {len(run['messages'])} | "
            f"total_cost: {run['total_cost']}"
        )

        results = evaluate_trajectory(
            run["messages"], contract, model=JUDGE_MODEL
        )
        s = summarize(results)
        print(
            f"auto-eval: {s['n_passed']}/{s['n_dimensions']} dimensions passed"
        )
        for cat, info in s["by_dimension"].items():
            verdict = "PASS" if info["passed"] else "FAIL"
            print(f"  {verdict}  {cat:32s} {info['reason'][:140]}")


if __name__ == "__main__":
    main()
