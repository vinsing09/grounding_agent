"""Render the per-dimension auto-eval vs tau-bench reward comparison.

Loads results/{v0,v2}_results.json + data/tasks.json, runs the
computations in grounding_agent.compare, writes results/comparison.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grounding_agent.compare import (
    ConfusionCell,
    Disagreement,
    clause_citation_counts,
    confusion_matrix,
    disagreements,
    pass_rate_by_split,
    variant_overview,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
TASKS_PATH = REPO_ROOT / "data" / "tasks.json"
OUTPUT_PATH = RESULTS_DIR / "comparison.md"


def _pct(x: float) -> str:
    if x != x:  # NaN
        return "—"
    return f"{x * 100:.0f}%"


def _cell_line(cell: ConfusionCell) -> str:
    return (
        f"TP={cell.tp} FP={cell.fp} TN={cell.tn} FN={cell.fn} "
        f"(agreement {_pct(cell.agreement)})"
    )


def _overview_table(ov: dict[str, Any]) -> list[str]:
    rps = ov["reward_pass_by_split"]
    return [
        f"- **{ov['label']}** — n={ov['n_tasks']}, "
        f"tau-bench reward pass: all {_pct(ov['reward_pass_overall'])}, "
        f"train {_pct(rps.get('train', float('nan')))}, "
        f"held_out {_pct(rps.get('held_out', float('nan')))}; "
        f"avg msgs/run {ov['avg_messages']:.1f}, total cost ${ov['total_cost']:.4f}"
    ]


def _confusion_section(
    label: str, cm: dict[str, dict[str, ConfusionCell]]
) -> list[str]:
    lines = [f"### {label}", ""]
    lines.append(
        "| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for cat in sorted(cm.keys()):
        for split in ("train", "held_out", "all"):
            cell = cm[cat].get(split)
            if cell is None:
                continue
            lines.append(
                f"| `{cat}` | {split} | {cell.tp} | {cell.fp} | "
                f"{cell.tn} | {cell.fn} | {_pct(cell.agreement)} | "
                f"{_pct(cell.auto_pass_rate)} | {_pct(cell.reward_pass_rate)} |"
            )
    lines.append("")
    return lines


def _rates_section(
    label: str, rates: dict[str, dict[str, float]]
) -> list[str]:
    lines = [f"### {label}", ""]
    lines.append("| metric | train | held_out | all |")
    lines.append("|---|---:|---:|---:|")
    order = ["reward"] + sorted(k for k in rates if k != "reward")
    for k in order:
        r = rates[k]
        lines.append(
            f"| `{k}` | {_pct(r.get('train', float('nan')))} | "
            f"{_pct(r.get('held_out', float('nan')))} | "
            f"{_pct(r.get('all', float('nan')))} |"
        )
    lines.append("")
    return lines


def _clause_section(
    label: str, counts: dict[str, dict[str, Any]]
) -> list[str]:
    lines = [f"### {label}", ""]
    if not counts:
        lines.append("_no clauses cited in failed verdicts_")
        lines.append("")
        return lines
    lines.append("| clause id | failed count | citing dimensions |")
    lines.append("|---|---:|---|")
    for cid, info in counts.items():
        dims = ", ".join(f"`{d}`" for d in info["citing_dimensions"])
        lines.append(f"| `{cid}` | {info['failed_count']} | {dims} |")
    lines.append("")
    return lines


def _disagreement_section(
    label: str,
    ds_fp: list[Disagreement],
    ds_fn: list[Disagreement],
    cap: int = 6,
) -> list[str]:
    lines = [f"### {label}", ""]
    if not ds_fp and not ds_fn:
        lines.append("_no disagreements_")
        lines.append("")
        return lines

    def render(group: list[Disagreement], heading: str) -> list[str]:
        out = [f"**{heading}** ({len(group)})", ""]
        if not group:
            out.append("_none_")
            out.append("")
            return out
        for d in group[:cap]:
            refs = (
                ", ".join(f"`{r}`" for r in d.clause_refs)
                if d.clause_refs
                else "—"
            )
            out.append(
                f"- task {d.task_index} ({d.split}, reward={d.reward}) · "
                f"`{d.dimension}` · refs: {refs}"
            )
            out.append(f"  - {d.reason.strip()[:280]}")
        if len(group) > cap:
            out.append(f"- … and {len(group) - cap} more")
        out.append("")
        return out

    lines.extend(render(ds_fp, "FP — auto pass, reward fail (eval missed a real failure)"))
    lines.extend(render(ds_fn, "FN — auto fail, reward pass (eval over-strict)"))
    return lines


def render_markdown(
    v0: dict[str, Any] | None,
    v2: dict[str, Any] | None,
    splits: dict[str, list[int]],
) -> str:
    lines: list[str] = [
        "# Per-dimension auto-eval vs tau-bench reward",
        "",
        "tau-bench reward (binary 0.0/1.0) is the ground truth. Each auto-eval "
        "dimension verdict is a per-task prediction of that ground truth. "
        "Cells: **TP** = auto pass & reward pass · **FP** = auto pass but "
        "reward fail (eval missed a failure) · **TN** = auto fail & reward "
        "fail (eval agreed with the reward) · **FN** = auto fail but reward "
        "pass (eval over-strict).",
        "",
        "## Variant overview",
        "",
    ]
    if v0 is not None:
        lines.extend(_overview_table(variant_overview(v0, splits)))
    if v2 is not None:
        lines.extend(_overview_table(variant_overview(v2, splits)))
    lines.append("")

    for variant_data, label in ((v0, "v0"), (v2, "v2")):
        if variant_data is None:
            continue
        lines.append(f"## {label}")
        lines.append("")
        lines.extend(
            _rates_section(
                f"Per-dimension pass rate ({label})",
                pass_rate_by_split(variant_data, splits),
            )
        )
        lines.extend(
            _confusion_section(
                f"Confusion matrix per dimension ({label})",
                confusion_matrix(variant_data, splits),
            )
        )
        lines.extend(
            _clause_section(
                f"Clauses most often cited in failed verdicts ({label})",
                clause_citation_counts(variant_data),
            )
        )
        ds_fp = disagreements(variant_data, splits, kind="fp")
        ds_fn = disagreements(variant_data, splits, kind="fn")
        lines.extend(
            _disagreement_section(
                f"Disagreement examples ({label})", ds_fp, ds_fn
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    splits = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    splits = {k: v for k, v in splits.items() if isinstance(v, list)}

    def _load(name: str) -> dict[str, Any] | None:
        p = RESULTS_DIR / f"{name}_results.json"
        if not p.exists():
            print(f"  (skip) {p.relative_to(REPO_ROOT)} not found")
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    v0 = _load("v0")
    v2 = _load("v2")
    if v0 is None and v2 is None:
        raise SystemExit("no results files to compare; run scripts/run_eval.py first")

    md = render_markdown(v0, v2, splits)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(md, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(md)} bytes)")


if __name__ == "__main__":
    main()
