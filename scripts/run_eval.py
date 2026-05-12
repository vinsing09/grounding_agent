"""Run the agent on all 20 tau-bench airline tasks under two prompt
variants and evaluate every trajectory with the six judges.

Outputs:
    results/v0_results.json  — agent with tau-bench's wiki as-is
    results/v2_results.json  — agent with the discipline preamble + wiki
    results/logs/<run_id>/<variant>.jsonl  — structured event log

Per-task records are cached by task_index inside each variant's results
file, so re-running picks up where it left off. Pass --force to redo.

The event log captures run_start, task_start, judge_invocation,
task_end, run_end events with timing and verdicts, in JSON-Lines for
forensic mining.
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from grounding_agent.contract import load_contract
from grounding_agent.evaluator import evaluate_trajectory, summarize
from grounding_agent.eventlog import EventLog, new_run_id
from grounding_agent.runner import run_task


REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_PATH = REPO_ROOT / "data" / "tasks.json"
CONTRACT_PATH = REPO_ROOT / "data" / "contract.json"
V2_PREAMBLE_PATH = REPO_ROOT / "data" / "variants" / "v2_preamble.md"
RESULTS_DIR = REPO_ROOT / "results"


def _serialize_result(r: Any) -> dict[str, Any]:
    d = asdict(r)
    d["clause_refs"] = list(r.clause_refs)
    return d


def _v0_wiki() -> str | None:
    return None  # use env.wiki as-is


def _v2_wiki() -> str:
    from tau_bench.envs.airline.wiki import WIKI

    preamble = V2_PREAMBLE_PATH.read_text(encoding="utf-8")
    return preamble + "\n" + WIKI


VARIANTS: dict[str, dict[str, Any]] = {
    "v0": {"label": "v0 (wiki as-is)", "wiki_fn": _v0_wiki},
    "v2": {"label": "v2 (discipline preamble + wiki)", "wiki_fn": _v2_wiki},
}


def _load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"variant": None, "tasks": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _run_one(
    task_index: int,
    *,
    wiki: str | None,
    agent_model: str,
    user_model: str,
    max_steps: int,
    contract: dict[str, Any],
    judge_model: str,
    eventlog: EventLog | None = None,
) -> dict[str, Any]:
    run = run_task(
        task_index=task_index,
        agent_model=agent_model,
        agent_provider="openai",
        user_model=user_model,
        user_provider="openai",
        max_steps=max_steps,
        wiki_override=wiki,
        eventlog=eventlog,
    )
    results = evaluate_trajectory(
        run["messages"], contract, model=judge_model,
        eventlog=eventlog, task_index=task_index,
    )
    eval_serial = {cat: _serialize_result(r) for cat, r in results.items()}
    return {
        "task_index": task_index,
        "reward": run["reward"],
        "messages": run["messages"],
        "info": run["info"],
        "total_cost": run["total_cost"],
        "agent_model": run["agent_model"],
        "user_model": run["user_model"],
        "max_steps": run["max_steps"],
        "termination": run["termination"],
        "tool_errors": run["tool_errors"],
        "duration_s": run["duration_s"],
        "evaluation": eval_serial,
        "summary": summarize(results),
    }


def run_variant(
    variant: str,
    task_indices: list[int],
    *,
    agent_model: str,
    user_model: str,
    judge_model: str,
    max_steps: int,
    force: bool,
    contract: dict[str, Any],
    eventlog: EventLog | None = None,
) -> dict[str, Any]:
    spec = VARIANTS[variant]
    path = RESULTS_DIR / f"{variant}_results.json"
    data = _load_existing(path)
    data["variant"] = variant
    data["label"] = spec["label"]
    data["agent_model"] = agent_model
    data["user_model"] = user_model
    data["judge_model"] = judge_model
    data["tasks"] = data.get("tasks") or {}
    if eventlog is not None:
        data["run_id"] = eventlog.run_id

    wiki = spec["wiki_fn"]()

    if eventlog is not None:
        # `variant` is auto-injected as a framing field; don't pass it
        # in the payload (the EventLog validator would reject the clobber).
        eventlog.emit(
            "variant_start",
            label=spec["label"],
            agent_model=agent_model,
            user_model=user_model,
            judge_model=judge_model,
            max_steps=max_steps,
            task_indices=list(task_indices),
        )

    n_done = 0
    n_err = 0
    for ti in task_indices:
        key = str(ti)
        if key in data["tasks"] and not force:
            print(f"  [{variant}] task {ti}: cached, skipping")
            continue
        t0 = time.time()
        try:
            record = _run_one(
                ti,
                wiki=wiki,
                agent_model=agent_model,
                user_model=user_model,
                max_steps=max_steps,
                contract=contract,
                judge_model=judge_model,
                eventlog=eventlog,
            )
        except Exception as e:  # surface error, keep moving
            traceback.print_exc()
            record = {"task_index": ti, "error": f"{type(e).__name__}: {e}"}
            if eventlog is not None:
                eventlog.emit(
                    "task_error", task_index=ti,
                    error=f"{type(e).__name__}: {e}",
                )
        elapsed = time.time() - t0
        data["tasks"][key] = record
        _save(path, data)
        if "error" in record:
            n_err += 1
            print(f"  [{variant}] task {ti}: ERROR ({elapsed:.1f}s)")
        else:
            n_done += 1
            s = record["summary"]
            print(
                f"  [{variant}] task {ti}: reward={record['reward']}  "
                f"auto={s['n_passed']}/{s['n_dimensions']}  "
                f"term={record['termination']['kind']}  "
                f"cost=${record.get('total_cost') or 0:.4f}  "
                f"({elapsed:.1f}s, {len(record['messages'])} msgs)"
            )
    if eventlog is not None:
        eventlog.emit(
            "variant_end",
            n_completed=n_done, n_errors=n_err,
        )
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="+", default=["v0", "v2"])
    parser.add_argument(
        "--splits", nargs="+", default=["train", "held_out"]
    )
    parser.add_argument("--agent-model", default="gpt-4o-mini")
    parser.add_argument("--user-model", default="gpt-4o-mini")
    parser.add_argument("--judge-model", default="gpt-4o-mini")
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--run-id", default=None,
        help="event-log subdirectory under results/logs/. Default: auto.",
    )
    args = parser.parse_args()

    load_dotenv()

    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    indices: list[int] = []
    for split in args.splits:
        indices.extend(tasks[split])

    contract = load_contract(CONTRACT_PATH)
    print(
        f"Loaded contract: {len(contract['obligations'])} obl, "
        f"{len(contract['forbidden_behaviors'])} fb, "
        f"{len(contract['tool_sequences'])} ts"
    )
    print(f"Tasks to run: {indices}")

    run_id = args.run_id or new_run_id()
    log_dir = REPO_ROOT / "results" / "logs" / run_id
    print(f"Run id: {run_id}")
    print(f"Event log: {log_dir.relative_to(REPO_ROOT)}/<variant>.jsonl")

    for variant in args.variants:
        if variant not in VARIANTS:
            raise SystemExit(f"unknown variant: {variant!r}")
        print(f"\n=== {VARIANTS[variant]['label']} ===")
        with EventLog(run_id, variant, log_dir=log_dir) as elog:
            elog.emit(
                "run_start",
                agent_model=args.agent_model,
                user_model=args.user_model,
                judge_model=args.judge_model,
                max_steps=args.max_steps,
                indices=list(indices),
                force=args.force,
            )
            run_variant(
                variant,
                indices,
                agent_model=args.agent_model,
                user_model=args.user_model,
                judge_model=args.judge_model,
                max_steps=args.max_steps,
                force=args.force,
                contract=contract,
                eventlog=elog,
            )
            elog.emit("run_end")


if __name__ == "__main__":
    main()
