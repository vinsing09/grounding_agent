"""Compare per-dimension auto-eval verdicts against tau-bench reward.

Pure-computation module. Loads no files; the CLI wrapper
`scripts/compare_to_reward.py` reads results/{v0,v2}_results.json,
feeds the dicts in here, and renders the output to markdown.

Vocabulary:
  - reward (tau-bench's binary 0.0/1.0) is the GROUND TRUTH.
  - each auto-eval dimension verdict (passed=true/false) is a PREDICTION
    of the ground-truth pass/fail for that task.
  - we score predictions per dimension and per split (train / held_out).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class ConfusionCell:
    tp: int = 0  # auto pass and reward pass
    fp: int = 0  # auto pass but reward fail
    tn: int = 0  # auto fail and reward fail
    fn: int = 0  # auto fail but reward pass

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def agreement(self) -> float:
        if self.total == 0:
            return float("nan")
        return (self.tp + self.tn) / self.total

    @property
    def auto_pass_rate(self) -> float:
        if self.total == 0:
            return float("nan")
        return (self.tp + self.fp) / self.total

    @property
    def reward_pass_rate(self) -> float:
        if self.total == 0:
            return float("nan")
        return (self.tp + self.fn) / self.total


def _iter_task_records(
    variant_data: dict[str, Any]
) -> list[tuple[int, dict[str, Any]]]:
    out: list[tuple[int, dict[str, Any]]] = []
    for key, rec in (variant_data.get("tasks") or {}).items():
        if "error" in rec:
            continue
        out.append((int(key), rec))
    out.sort(key=lambda kv: kv[0])
    return out


def split_of(
    task_index: int, splits: dict[str, list[int]]
) -> str | None:
    for name, ids in splits.items():
        if task_index in ids:
            return name
    return None


def confusion_matrix(
    variant_data: dict[str, Any],
    splits: dict[str, list[int]],
) -> dict[str, dict[str, ConfusionCell]]:
    """{category: {split: ConfusionCell, 'all': ConfusionCell}}."""
    out: dict[str, dict[str, dict[str, int]]] = {}
    for ti, rec in _iter_task_records(variant_data):
        sp = split_of(ti, splits) or "unknown"
        reward_pass = float(rec.get("reward", 0.0)) >= 1.0
        ev = rec.get("evaluation") or {}
        for cat, verdict in ev.items():
            auto_pass = bool(verdict.get("passed"))
            for bucket in (sp, "all"):
                cell = out.setdefault(cat, {}).setdefault(
                    bucket, {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
                )
                if auto_pass and reward_pass:
                    cell["tp"] += 1
                elif auto_pass and not reward_pass:
                    cell["fp"] += 1
                elif not auto_pass and not reward_pass:
                    cell["tn"] += 1
                else:
                    cell["fn"] += 1
    return {
        cat: {bk: ConfusionCell(**cells) for bk, cells in by_bk.items()}
        for cat, by_bk in out.items()
    }


def pass_rate_by_split(
    variant_data: dict[str, Any],
    splits: dict[str, list[int]],
) -> dict[str, dict[str, float]]:
    """{category|reward: {split: pass_rate}}. 'reward' tracks tau-bench."""
    by_cat: dict[str, dict[str, list[int]]] = {}
    reward: dict[str, list[int]] = {}
    for ti, rec in _iter_task_records(variant_data):
        sp = split_of(ti, splits) or "unknown"
        reward.setdefault(sp, []).append(
            1 if float(rec.get("reward", 0.0)) >= 1.0 else 0
        )
        reward.setdefault("all", []).append(
            1 if float(rec.get("reward", 0.0)) >= 1.0 else 0
        )
        ev = rec.get("evaluation") or {}
        for cat, verdict in ev.items():
            by_cat.setdefault(cat, {}).setdefault(sp, []).append(
                1 if verdict.get("passed") else 0
            )
            by_cat.setdefault(cat, {}).setdefault("all", []).append(
                1 if verdict.get("passed") else 0
            )

    def _rates(by_split: dict[str, list[int]]) -> dict[str, float]:
        return {
            sp: (sum(xs) / len(xs) if xs else float("nan"))
            for sp, xs in by_split.items()
        }

    out: dict[str, dict[str, float]] = {
        cat: _rates(by_split) for cat, by_split in by_cat.items()
    }
    out["reward"] = _rates(reward)
    return out


def clause_citation_counts(
    variant_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """For each clause id mentioned in a FAILED verdict, count how often
    it was cited and which dimension cited it. Surfaces 'always-fires'
    clauses (likely judge over-strictness or a real systemic gap) and
    'never-fires' clauses (likely dead weight in the contract).
    """
    fail_counts: Counter[str] = Counter()
    citing_dims: dict[str, set[str]] = {}
    for _, rec in _iter_task_records(variant_data):
        ev = rec.get("evaluation") or {}
        for cat, verdict in ev.items():
            if verdict.get("passed"):
                continue
            for cid in verdict.get("clause_refs") or []:
                fail_counts[cid] += 1
                citing_dims.setdefault(cid, set()).add(cat)
    return {
        cid: {"failed_count": ct, "citing_dimensions": sorted(citing_dims[cid])}
        for cid, ct in fail_counts.most_common()
    }


@dataclass(frozen=True)
class Disagreement:
    task_index: int
    split: str
    reward: float
    dimension: str
    auto_passed: bool
    reason: str
    clause_refs: tuple[str, ...] = field(default_factory=tuple)


def disagreements(
    variant_data: dict[str, Any],
    splits: dict[str, list[int]],
    kind: str = "all",
) -> list[Disagreement]:
    """Return per-dimension auto-vs-reward disagreements.

    kind:
      'all' — every disagreement
      'fp'  — auto pass when reward fail (FALSE PASS — eval missed a real failure)
      'fn'  — auto fail when reward pass (FALSE FAIL — eval over-strict)
    """
    out: list[Disagreement] = []
    for ti, rec in _iter_task_records(variant_data):
        sp = split_of(ti, splits) or "unknown"
        reward_pass = float(rec.get("reward", 0.0)) >= 1.0
        ev = rec.get("evaluation") or {}
        for cat, verdict in ev.items():
            auto_pass = bool(verdict.get("passed"))
            if auto_pass == reward_pass:
                continue
            if kind == "fp" and not (auto_pass and not reward_pass):
                continue
            if kind == "fn" and not (not auto_pass and reward_pass):
                continue
            out.append(
                Disagreement(
                    task_index=ti,
                    split=sp,
                    reward=float(rec.get("reward", 0.0)),
                    dimension=cat,
                    auto_passed=auto_pass,
                    reason=str(verdict.get("reason") or ""),
                    clause_refs=tuple(verdict.get("clause_refs") or ()),
                )
            )
    return out


def variant_overview(
    variant_data: dict[str, Any],
    splits: dict[str, list[int]],
) -> dict[str, Any]:
    """One-row summary of a variant: reward pass rate, per-dim pass rate,
    total cost, message counts. Used by the CLI to print a comparison
    table side-by-side.
    """
    n_tasks = 0
    n_reward_pass = 0
    n_cost = 0.0
    n_msgs: list[int] = []
    per_split_reward: dict[str, list[int]] = {}
    n_errors = 0
    for ti_rec in (variant_data.get("tasks") or {}).items():
        tk, rec = ti_rec
        if "error" in rec:
            n_errors += 1
            continue
    for ti, rec in _iter_task_records(variant_data):
        n_tasks += 1
        rp = 1 if float(rec.get("reward", 0.0)) >= 1.0 else 0
        n_reward_pass += rp
        per_split_reward.setdefault(
            split_of(ti, splits) or "unknown", []
        ).append(rp)
        n_cost += float(rec.get("total_cost") or 0.0)
        n_msgs.append(len(rec.get("messages") or []))

    return {
        "variant": variant_data.get("variant"),
        "label": variant_data.get("label"),
        "n_tasks": n_tasks,
        "n_errors": n_errors,
        "reward_pass_overall": (
            n_reward_pass / n_tasks if n_tasks else float("nan")
        ),
        "reward_pass_by_split": {
            sp: (sum(xs) / len(xs) if xs else float("nan"))
            for sp, xs in per_split_reward.items()
        },
        "avg_messages": (sum(n_msgs) / len(n_msgs)) if n_msgs else 0.0,
        "total_cost": n_cost,
    }


# ---- Bucket D: termination + reward-kind breakdowns -----------------------


def reward_kind(record: dict[str, Any]) -> str:
    """Categorise a graded task record by tau-bench reward kind.

    Returns one of:
      - 'r_actions'  — DB-state match against gold action list
      - 'r_outputs'  — final-text-match against expected outputs
      - 'no_grade'   — env did not compute reward_info (max_steps,
                       crash, etc.)
    """
    info = record.get("info") or {}
    ri = info.get("reward_info")
    if ri is None:
        return "no_grade"
    inner = (ri.get("info") or {}) if isinstance(ri, dict) else {}
    if "r_actions" in inner:
        return "r_actions"
    if "r_outputs" in inner:
        return "r_outputs"
    return "no_grade"


def termination_kind(record: dict[str, Any]) -> str:
    """Termination kind from the runner's classification.

    Returns 'max_steps' / 'transfer' / 'completed' for graded records;
    'error' for errored records (those carry no 'termination' field);
    'unknown' for older records that pre-date Bucket D.
    """
    if "error" in record:
        return "error"
    t = record.get("termination") or {}
    return t.get("kind", "unknown")


def reward_kind_breakdown(
    variant_data: dict[str, Any],
    splits: dict[str, list[int]],
) -> dict[str, dict[str, dict[str, int]]]:
    """{kind: {split: {n, n_passed}}} for each reward_kind seen,
    with an 'all' bucket per kind."""
    out: dict[str, dict[str, dict[str, int]]] = {}
    for ti, rec in _iter_task_records(variant_data):
        kind = reward_kind(rec)
        sp = split_of(ti, splits) or "unknown"
        passed = float(rec.get("reward", 0.0)) >= 1.0
        for bucket in (sp, "all"):
            d = out.setdefault(kind, {}).setdefault(
                bucket, {"n": 0, "n_passed": 0}
            )
            d["n"] += 1
            if passed:
                d["n_passed"] += 1
    return out


def termination_breakdown(
    variant_data: dict[str, Any],
    splits: dict[str, list[int]],
) -> dict[str, dict[str, int]]:
    """{kind: {split: count}} for each termination_kind. Includes
    errored tasks under the 'error' bucket."""
    out: dict[str, dict[str, int]] = {}
    for tk_str, rec in (variant_data.get("tasks") or {}).items():
        try:
            tk = int(tk_str)
        except ValueError:
            continue
        kind = termination_kind(rec)
        sp = split_of(tk, splits) or "unknown"
        for bucket in (sp, "all"):
            out.setdefault(kind, {})[bucket] = (
                out.setdefault(kind, {}).get(bucket, 0) + 1
            )
    return out


def tool_error_counts(
    variant_data: dict[str, Any],
) -> dict[str, int]:
    """Count how often each tool's call resulted in a tool-side error
    across the variant. Reads `record['tool_errors']` (populated by
    runner.run_task after Bucket D). Returns {} for older records
    that lack the field."""
    out: dict[str, int] = {}
    for _, rec in _iter_task_records(variant_data):
        for err in (rec.get("tool_errors") or []):
            tool = err.get("tool") or "?"
            out[tool] = out.get(tool, 0) + 1
    return out
