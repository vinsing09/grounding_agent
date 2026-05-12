"""Tests for compare.py.

Fixture mirrors the shape scripts/run_eval.py writes to
results/{variant}_results.json: variant-level metadata plus a tasks
dict keyed by stringified task index, each carrying reward + a
per-dimension evaluation block.
"""

from __future__ import annotations

import pytest

from grounding_agent.compare import (
    ConfusionCell,
    Disagreement,
    clause_citation_counts,
    confusion_matrix,
    disagreements,
    pass_rate_by_split,
    split_of,
    variant_overview,
)


SPLITS = {"train": [0, 1, 2, 3, 4], "held_out": [10, 11, 12, 13, 14]}


def _ev(passed: bool, clause_refs: list[str] | None = None, reason: str = "") -> dict:
    return {
        "category": "x",
        "passed": passed,
        "reason": reason,
        "clause_refs": list(clause_refs or []),
    }


def _variant_fixture() -> dict:
    return {
        "variant": "v0",
        "label": "v0",
        "tasks": {
            # train: task 0 — agent FAILED, both dims caught it (TN, TN)
            "0": {
                "task_index": 0,
                "reward": 0.0,
                "messages": [{"role": "user"}],
                "total_cost": 0.001,
                "evaluation": {
                    "policy_compliance": _ev(False, ["obl-a"], "missed step"),
                    "tool_sequence_correctness": _ev(False, ["ts-1"], "no prereq"),
                },
            },
            # train: task 1 — agent PASSED, both dims agree (TP, TP)
            "1": {
                "task_index": 1,
                "reward": 1.0,
                "messages": [{"role": "user"}, {"role": "assistant"}],
                "total_cost": 0.002,
                "evaluation": {
                    "policy_compliance": _ev(True),
                    "tool_sequence_correctness": _ev(True),
                },
            },
            # train: task 2 — agent PASSED, eval over-strict on policy (FN), ok on tool seq (TP)
            "2": {
                "task_index": 2,
                "reward": 1.0,
                "messages": [],
                "total_cost": 0.003,
                "evaluation": {
                    "policy_compliance": _ev(False, ["obl-a", "fb-x"], "over-strict"),
                    "tool_sequence_correctness": _ev(True),
                },
            },
            # held_out: task 10 — agent FAILED, eval missed it on policy (FP), caught on tool seq (TN)
            "10": {
                "task_index": 10,
                "reward": 0.0,
                "messages": [],
                "total_cost": 0.004,
                "evaluation": {
                    "policy_compliance": _ev(True),
                    "tool_sequence_correctness": _ev(False, ["ts-1"], "no prereq"),
                },
            },
            # held_out: task 11 — agent PASSED, both dims agree (TP, TP)
            "11": {
                "task_index": 11,
                "reward": 1.0,
                "messages": [],
                "total_cost": 0.005,
                "evaluation": {
                    "policy_compliance": _ev(True),
                    "tool_sequence_correctness": _ev(True),
                },
            },
            # an errored task — should be excluded from all aggregates
            "99": {"task_index": 99, "error": "Boom"},
        },
    }


def test_split_of_returns_correct_split():
    assert split_of(0, SPLITS) == "train"
    assert split_of(11, SPLITS) == "held_out"
    assert split_of(999, SPLITS) is None


def test_confusion_matrix_aggregates_correctly():
    cm = confusion_matrix(_variant_fixture(), SPLITS)
    # policy_compliance: task0(TN), task1(TP), task2(FN), task10(FP), task11(TP)
    pol_all = cm["policy_compliance"]["all"]
    assert pol_all == ConfusionCell(tp=2, fp=1, tn=1, fn=1)
    # train slice: tasks 0,1,2 → TN, TP, FN
    pol_train = cm["policy_compliance"]["train"]
    assert pol_train == ConfusionCell(tp=1, fp=0, tn=1, fn=1)
    # held_out: 10, 11 → FP, TP
    pol_held = cm["policy_compliance"]["held_out"]
    assert pol_held == ConfusionCell(tp=1, fp=1, tn=0, fn=0)


def test_confusion_cell_derived_metrics():
    c = ConfusionCell(tp=2, fp=1, tn=1, fn=1)
    assert c.total == 5
    assert c.agreement == pytest.approx(3 / 5)
    assert c.auto_pass_rate == pytest.approx(3 / 5)
    assert c.reward_pass_rate == pytest.approx(3 / 5)


def test_pass_rate_by_split_includes_reward():
    rates = pass_rate_by_split(_variant_fixture(), SPLITS)
    assert "reward" in rates
    # reward in train: tasks 0,1,2 → 0,1,1 = 2/3
    assert rates["reward"]["train"] == pytest.approx(2 / 3)
    # reward in held_out: 10,11 → 0,1 = 1/2
    assert rates["reward"]["held_out"] == pytest.approx(1 / 2)
    # reward overall: 3/5
    assert rates["reward"]["all"] == pytest.approx(3 / 5)


def test_clause_citation_counts_orders_by_frequency():
    counts = clause_citation_counts(_variant_fixture())
    assert counts["ts-1"]["failed_count"] == 2  # cited on tasks 0 and 10
    assert counts["obl-a"]["failed_count"] == 2  # cited on tasks 0 and 2
    assert counts["fb-x"]["failed_count"] == 1
    # ordering: most-frequent first
    keys = list(counts.keys())
    assert counts[keys[0]]["failed_count"] >= counts[keys[-1]]["failed_count"]


def test_clause_citation_tracks_citing_dimensions():
    counts = clause_citation_counts(_variant_fixture())
    assert counts["ts-1"]["citing_dimensions"] == ["tool_sequence_correctness"]
    assert counts["obl-a"]["citing_dimensions"] == ["policy_compliance"]


def test_disagreements_all_returns_both_directions():
    ds = disagreements(_variant_fixture(), SPLITS, kind="all")
    cases = {(d.task_index, d.dimension, d.auto_passed) for d in ds}
    # task 2 / policy_compliance: auto fail, reward pass → FN
    assert (2, "policy_compliance", False) in cases
    # task 10 / policy_compliance: auto pass, reward fail → FP
    assert (10, "policy_compliance", True) in cases


def test_disagreements_filters_fp_only():
    ds = disagreements(_variant_fixture(), SPLITS, kind="fp")
    assert all(d.auto_passed and d.reward < 1.0 for d in ds)
    assert {d.task_index for d in ds} == {10}


def test_disagreements_filters_fn_only():
    ds = disagreements(_variant_fixture(), SPLITS, kind="fn")
    assert all((not d.auto_passed) and d.reward >= 1.0 for d in ds)
    assert {d.task_index for d in ds} == {2}


def test_disagreement_dataclass_is_frozen():
    d = Disagreement(
        task_index=1,
        split="train",
        reward=1.0,
        dimension="policy_compliance",
        auto_passed=False,
        reason="x",
    )
    with pytest.raises(Exception):
        d.task_index = 2  # type: ignore[misc]


def test_variant_overview_excludes_errored_tasks():
    ov = variant_overview(_variant_fixture(), SPLITS)
    assert ov["n_tasks"] == 5  # task 99 errored, excluded
    assert ov["reward_pass_overall"] == pytest.approx(3 / 5)
    assert ov["reward_pass_by_split"]["train"] == pytest.approx(2 / 3)
    assert ov["reward_pass_by_split"]["held_out"] == pytest.approx(1 / 2)
    assert ov["total_cost"] == pytest.approx(0.015)


def test_errored_tasks_excluded_from_confusion_matrix():
    cm = confusion_matrix(_variant_fixture(), SPLITS)
    # task 99 has no evaluation block; should not have produced any cells
    for cat, by_split in cm.items():
        for bk, cell in by_split.items():
            assert cell.total <= 5


# ---- Bucket D: reward_kind / termination_kind / breakdowns ----------------


def _variant_with_termination_and_kinds() -> dict:
    """Mirrors the record shape after Bucket D: each non-errored
    record has `termination` and `info.reward_info.info` with either
    r_actions or r_outputs."""
    return {
        "variant": "v0",
        "label": "v0",
        "tasks": {
            "0": {
                "task_index": 0,
                "reward": 1.0,
                "messages": [],
                "total_cost": 0.01,
                "info": {"reward_info": {"info": {"r_actions": 1.0}, "reward": 1.0}},
                "termination": {"kind": "completed", "transferred": False},
                "tool_errors": [],
                "evaluation": {
                    "policy_compliance": {
                        "category": "policy_compliance",
                        "passed": True, "reason": "", "clause_refs": [],
                    }
                },
            },
            "1": {
                "task_index": 1,
                "reward": 0.0,
                "messages": [],
                "total_cost": 0.01,
                "info": {"reward_info": {"info": {"r_outputs": 0.0, "outputs": {}}, "reward": 0.0}},
                "termination": {"kind": "completed", "transferred": False},
                "tool_errors": [{"position": 4, "tool": "book_reservation",
                                 "message": "Error: payment amount does not add up"}],
                "evaluation": {
                    "policy_compliance": {
                        "category": "policy_compliance",
                        "passed": False, "reason": "", "clause_refs": ["obl-x"],
                    }
                },
            },
            "2": {
                "task_index": 2,
                "reward": 1.0,
                "messages": [],
                "total_cost": 0.01,
                "info": {"reward_info": {"info": {"r_actions": 1.0}, "reward": 1.0}},
                "termination": {"kind": "transfer", "transferred": True},
                "tool_errors": [],
                "evaluation": {"policy_compliance": {
                    "category": "policy_compliance",
                    "passed": True, "reason": "", "clause_refs": [],
                }},
            },
            "10": {
                "task_index": 10,
                "reward": 0.0,
                "messages": [],
                "total_cost": 0.01,
                "info": {"reward_info": None},
                "termination": {"kind": "max_steps", "transferred": False},
                "tool_errors": [
                    {"position": 8, "tool": "book_reservation", "message": "Error: gift card"},
                    {"position": 12, "tool": "book_reservation", "message": "Error: gift card"},
                ],
                "evaluation": {"policy_compliance": {
                    "category": "policy_compliance",
                    "passed": False, "reason": "", "clause_refs": [],
                }},
            },
            "99": {"task_index": 99, "error": "Boom"},
        },
    }


def test_reward_kind_returns_r_actions():
    from grounding_agent.compare import reward_kind
    rec = _variant_with_termination_and_kinds()["tasks"]["0"]
    assert reward_kind(rec) == "r_actions"


def test_reward_kind_returns_r_outputs():
    from grounding_agent.compare import reward_kind
    rec = _variant_with_termination_and_kinds()["tasks"]["1"]
    assert reward_kind(rec) == "r_outputs"


def test_reward_kind_returns_no_grade_when_reward_info_none():
    from grounding_agent.compare import reward_kind
    rec = _variant_with_termination_and_kinds()["tasks"]["10"]
    assert reward_kind(rec) == "no_grade"


def test_termination_kind_uses_recorded_classification():
    from grounding_agent.compare import termination_kind
    fx = _variant_with_termination_and_kinds()
    assert termination_kind(fx["tasks"]["0"]) == "completed"
    assert termination_kind(fx["tasks"]["2"]) == "transfer"
    assert termination_kind(fx["tasks"]["10"]) == "max_steps"


def test_termination_kind_handles_errored_record():
    from grounding_agent.compare import termination_kind
    fx = _variant_with_termination_and_kinds()
    assert termination_kind(fx["tasks"]["99"]) == "error"


def test_termination_kind_legacy_record_returns_unknown():
    """Records produced before Bucket D have no `termination` key."""
    from grounding_agent.compare import termination_kind
    assert termination_kind({"task_index": 0, "reward": 0.0}) == "unknown"


def test_reward_kind_breakdown():
    from grounding_agent.compare import reward_kind_breakdown
    bk = reward_kind_breakdown(_variant_with_termination_and_kinds(), SPLITS)
    # tasks 0,2 are r_actions in train, all passed
    # task 1 is r_outputs in train, failed
    # task 10 is no_grade in held_out, failed
    assert bk["r_actions"]["train"] == {"n": 2, "n_passed": 2}
    assert bk["r_actions"]["all"]["n_passed"] == 2
    assert bk["r_outputs"]["train"] == {"n": 1, "n_passed": 0}
    assert bk["no_grade"]["held_out"] == {"n": 1, "n_passed": 0}


def test_termination_breakdown_includes_error():
    from grounding_agent.compare import termination_breakdown
    bk = termination_breakdown(_variant_with_termination_and_kinds(), SPLITS)
    # 0+1=completed (train), 2=transfer (train), 10=max_steps (held_out), 99=error (held_out? no — unknown)
    assert bk["completed"]["train"] == 2
    assert bk["transfer"]["train"] == 1
    assert bk["max_steps"]["held_out"] == 1
    # task 99 has no split (not in train/held_out lists) → "unknown"
    assert bk["error"]["unknown"] == 1


def test_tool_error_counts():
    from grounding_agent.compare import tool_error_counts
    counts = tool_error_counts(_variant_with_termination_and_kinds())
    assert counts["book_reservation"] == 3  # task 1: 1, task 10: 2


def test_variant_overview_includes_n_errors():
    from grounding_agent.compare import variant_overview
    ov = variant_overview(_variant_with_termination_and_kinds(), SPLITS)
    assert ov["n_tasks"] == 4   # 0,1,2,10
    assert ov["n_errors"] == 1  # task 99
