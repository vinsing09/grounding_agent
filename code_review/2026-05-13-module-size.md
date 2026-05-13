# Code review — module size discipline

**Date:** 2026-05-13
**Trigger:** pre-ship audit found three modules over the BRIEF's
300-line target.

## Rule (from BRIEF.md)

> Each Python module ≤ 300 lines; up to 500 only with explicit
> justification recorded in `code_review/`.

## What was found

| module | lines | status before | status after |
|---|---|---|---|
| `judges.py` | 598 | **over 500 cap** | split into a package (see below) |
| `compare.py` | 398 | over 300, under 500 | justification, kept as-is |
| `runner.py` | 338 | over 300, under 500 | justification, kept as-is |

## Action taken on `judges.py` — split into a package

`grounding_agent/judges.py` (598 lines) replaced with the
`grounding_agent/judges/` package:

```
grounding_agent/judges/
├── __init__.py          (78 lines) — re-exports + ALL_JUDGES tuple
├── _common.py          (205 lines) — JudgeResult, MUTATING_TOOLS,
│                                     affirmative detection,
│                                     trajectory rendering helpers
├── _deterministic.py   (233 lines) — 3 deterministic judges
└── _semantic.py        (156 lines) — semantic judge plumbing
                                      + 3 wrappers
```

The public surface is unchanged. Every previous import path still
resolves through `__init__.py`'s re-exports — including the private
`_build_semantic_judge_prompt` that tests rely on. 126/126 tests pass
after the split with zero test changes.

The split is along the natural seam — deterministic checks have
nothing in common with the semantic-LLM call path except the
shared `JudgeResult` dataclass and trajectory rendering helpers,
which live in `_common.py`.

## Action taken on `compare.py` (398) and `runner.py` (338) — kept

Both fall within the BRIEF's 300-500 "with justification" range.
The justification:

### `compare.py` (398 lines)
Single coherent responsibility: turn `results/{v0,v2}_results.json`
into compared metrics. Cleanly factored into:
- `ConfusionCell` + derived metrics (33 lines)
- helpers (`split_of`, `_iter_task_records`) (35 lines)
- `confusion_matrix` (30 lines)
- `pass_rate_by_split` (40 lines)
- `clause_citation_counts` (20 lines)
- `Disagreement` + `disagreements` (50 lines)
- `variant_overview` (30 lines)
- Bucket D additions: `reward_kind`, `termination_kind`,
  `reward_kind_breakdown`, `termination_breakdown`,
  `tool_error_counts` (~100 lines)
- module docstring + imports (~30 lines)
- blank/spacing lines (~30 lines)

Splitting would put each function in its own file or partition by
"old vs new (Bucket D) helpers" — neither is a natural seam. The
module is already factored into independent functions; adding
package boundaries would add ceremony without aiding navigation.

### `runner.py` (338 lines)
Single coherent responsibility: drive the τ³-bench agent on one
task and adapt its output into our framework's shape. Cleanly
factored into:
- module docstring + imports (~25 lines)
- `_TERMINATION_KIND_MAP` constant (~15 lines)
- `_serialize_tool_call` (15 lines)
- `_flatten_messages` (50 lines) — message-shape adapter
- `classify_termination` (35 lines)
- `extract_tool_errors` (30 lines)
- `_reward_info_to_dict` (10 lines)
- `run_task` (~120 lines) — public API; includes the
  TextRunConfig wiring + the wiki_override branch
- `airline_tool_catalog` (20 lines)

The adapter functions are tightly coupled with `run_task`. Splitting
them into a separate `_adapters.py` would force every caller to
either import from two paths or thread a re-export, with no
readability win. The module reads top-to-bottom as one workflow.

## Why not push compare/runner under 300

Three approaches considered and rejected:

1. **Move `compare.py`'s Bucket D helpers into a separate file** —
   they share data structures and call sites with the older helpers.
   The split would either duplicate the `_iter_task_records` helper
   or create a circular-ish dependency.
2. **Move `runner.py`'s adapter functions into `_adapters.py`** —
   they are used nowhere else and don't form a stable public
   surface. Hidden coupling with `run_task` would make the split
   purely visual.
3. **Inline-trim docstrings and blanks** — each module's docstring
   carries non-obvious why-context (forensics findings, design
   decisions). Removing this content to hit a line count is
   exactly the kind of "make the number look right" move the
   BRIEF's lean-code rule was written to prevent.

Each module remains coherent and tested. Both are under the 500-line
cap. The deviations are documented here per the rule.

## Tests after the change

126 of 126 pass on a clean checkout. The split was purely
mechanical — no function bodies changed, no signatures changed,
no public names dropped. Existing tests continue to verify the
behaviour through the package's `__init__.py` re-exports.
