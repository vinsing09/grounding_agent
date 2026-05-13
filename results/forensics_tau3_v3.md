# Forensics — τ³-bench, pass 3 (after iter-2 and iter-3 contract patches)

> Three iterations on the τ³-bench framework after the migration.
> Final state. Diminishing returns visible; stopping here.

## Headline: τ³-bench reward (stable across all 3 iterations since
trajectories are cached)

| | v0 | v2 | delta |
|---|---:|---:|---|
| τ³-bench reward (all) | 30% | **35%** | v2 +5pp |
| reward (train) | 50% | 20% | v0 +30pp |
| reward (held-out) | 10% | **50%** | **v2 +40pp** |

**v2 beats v0 by 40pp on held-out.** Under the broken τ-bench airline
tasks (iter-3 forensics_v3.md), v2 was 5pp WORSE than v0 overall.
Once the broken ground truth was removed (the τ³-bench migration),
the discipline preamble's effect inverted sign. The framework's
held-out generalization claim now lands with data, not just
prose.

## Per-dimension pass rate (iter-1 → iter-2 → iter-3 on τ³-bench)

| dimension | v0 i1→i2→i3 | v2 i1→i2→i3 | net direction |
|---|---|---|---|
| `confirmation_discipline` | 70 → 70 → 70 | 70 → 70 → 70 | stable |
| `information_grounding` | 65 → 65 → **80** | 65 → 70 → 70 | iter-3 unstuck v0 |
| `policy_compliance` | 25 → 20 → 25 | 15 → 15 → 15 | flat |
| `scope_adherence` | **0** → 5 → **0** | **0** → 10 → **0** | persistently broken |
| `tool_sequence_correctness` | 65 → 75 → 75 | 85 → 85 → 85 | iter-2 fix landed |
| `tool_argument_correctness` | 75 → 75 → 75 | 80 → 80 → 80 | stable |

## What each iter-2/iter-3 fix did

### Iter-2: re-tag the multi-tool-call clause + add missing clauses + fix reward_kind

**Patches to `data/contract.json`:**

1. Moved `fb-make-multiple-tool-calls` from `scope_adherence` →
   `tool_sequence_correctness`. The rule "do not respond to the user
   while making a tool call" is an interaction-discipline rule, not a
   transfer decision. **Result**: 20 stale scope-adherence citations
   eliminated; tool_sequence_correctness moved 65% → 75% on v0.

2. Added `obl-obtain-confirmation` (`confirmation_discipline`) and
   `fb-transfer-when-in-scope` (`scope_adherence`). The τ³-bench
   generator missed these on its own; the policy clearly mandates
   them. **Result**: `confirmation_discipline` now cites the right
   clause when it fails; `scope_adherence` finally has a clause but
   it over-fires (iter-3 problem below).

3. Removed `ts-transfer-to-human` (over-specified: routine refusals
   correctly transfer without `get_user_details` first). **Result**:
   2 stale tool_sequence_correctness citations eliminated.

**Patch to `compare.py`:**

`reward_kind()` rewritten to detect τ³-bench's first-class
`RewardInfo` fields (`db_check`, `env_assertions`, `action_checks`,
`nl_assertions`, `communicate_checks`). Old shape (`r_actions` xor
`r_outputs`) still supported. **Result**: `no_grade` rows replaced
with actual decomposition (e.g. `db+action` for multi-check tasks)
in the comparison report.

### Iter-3: refine the over-firing scope clause

Replaced `fb-transfer-when-in-scope` (generic) with
`fb-transfer-on-handleable-request` (enumerates routine cases the
agent CAN handle, and the cases that warrant transfer). **Intent**:
reduce false-firing on legitimate transfers.

**Result**: information_grounding went 65% → 80% on v0 (side benefit
of removing `obl-validate-before-mutating`, which redundantly fired
in tool_argument_correctness territory). **But scope_adherence went
back to 0%.** The LLM judge still treats every transfer as a
violation, regardless of how the clause is worded.

## Known-stuck dimension: `scope_adherence`

| | scope_adherence confusion (TP/FP/TN/FN) |
|---|---|
| iter-1 v0 | 0 / 0 / 14 / 6 |
| iter-2 v0 | 0 / 1 / 13 / 6 |
| iter-3 v0 | 0 / 0 / 14 / 6 |

The judge's pattern: **any transfer fires the clause as a
violation**, regardless of whether the request was actually
out-of-scope. The dimension's signal lives entirely in the FN tail
(6 tasks where reward=1.0 = correct transfer = framework says
"wrong"). No TPs.

**Why this is structurally hard**: deciding "is the user's request
in-scope?" requires holding the entire policy + the entire tool
catalog in working memory and comparing the user's request against
both. gpt-4o-mini does this poorly with a single clause to cite.

**Fix options** (NOT taken in iter-3):
- A deterministic `scope_adherence` check (impossible: policy nuance
  isn't mechanically encodable).
- A multi-shot judge (3-of-3 panel; expensive).
- A higher-capability judge model (gpt-4o or claude-opus); cost ↑↑.
- Drop the dimension entirely; accept 6 of 7 categories.

The HONEST documentation: `scope_adherence` is the dimension where
**the LLM-judge approach hits its limit**. This is a real finding
about what semantic LLM judges can and cannot do, and it is the
right kind of result for the framework to surface.

## What worked everywhere

- **τ³-bench reward jump** (10% → 30/35%): not a framework
  improvement, a benchmark-fix windfall. Documented in `tau1_vs_tau3.md`.
- **v2 held-out generalization** (50% vs v0's 10%): the framework
  finally had clean ground truth and detected the variant's strength.
- **Confirmation_discipline** at 70% on both variants: deterministic
  check is solid and consistent across iterations.
- **Tool_argument_correctness** at 75-80%: tau³-bench's
  `ToolMessage.error: bool` field is a deterministic signal cleaner
  than our prior grep-for-`Error:` heuristic.

## Post-iter-3 audit: dimensions vs reward at task level

After the three-iteration cycle, a task-level audit was run to
sanity-check the per-dimension story against the reward story
(prompted by the question "the per-dim deltas are 10–20pp but the
held-out reward delta is 40pp — what's driving the gap?").

**Reward shift on held-out (v0 → v2):** 1/10 → 5/10 = +40pp.

**Per-dimension shift on held-out (v0 → v2), averaged across the
six dimensions:** roughly +5pp.

**The discrepancy decomposes as follows:**

| v2 win | split | v0 termination | v2 termination | dims where v0 F → v2 P |
|---|---|---|---|---|
| task 6 | held | max_steps | transfer | confirmation, info, tool_arg |
| task 16 | held | completed | completed | **none** (all 6 dims identical) |
| task 18 | held | completed | completed | info, tool_seq |
| task 19 | held | max_steps | completed | **none** (all 6 dims identical) |

2 of 4 held-out wins (tasks 16 and 19) have **identical per-dim
verdicts in v0 and v2** but different reward. The other 2 are
partially explained by dimensional movement plus a termination-kind
flip (`max_steps` → graded completion).

**Conclusion: the 6 dimensions don't fully cover what τ³-bench's
reward scores.** That's a coverage gap, not a calibration error.
The framework correctly produces honest per-dim verdicts; the
mismatch with reward at the task level tells the operator their
taxonomy is incomplete relative to the benchmark's grading.

**Implications for the framework's headline framing:**

- The honest claim is **"v2 trades dev wins for held-out wins"**
  (a distribution shift), not **"v2 generalises +40pp better"**
  (which conflates a per-dimension claim with a reward claim).
- Two next-step dimensions would close most of this gap:
  - a `termination_kind` dimension (scored, not just tracked).
  - per-sub-check decomposition of τ³-bench's `RewardInfo`
    (db_check / action_checks / nl_assertions / communicate_checks).

The presentation and WRITEUP §3.4 + §4.3 have been updated to
reflect this honestly.

## Decision: stop at iter-3

Three iterations were performed. Iter-1 → iter-2 produced clear
movement; iter-2 → iter-3 moved one dimension up (info_grounding +
15pp) and one back down (scope_adherence -5pp). Net: small
improvements with one persistently-broken dimension.

The same pattern emerged in the τ-bench iter-3 forensics: the
framework converges fast (1–2 iterations), then plateaus on
LLM-judge-noise-dominated dimensions. Continuing past iter-3 would
move 1–2 cells per attempt without improving the dominant signal
(the v2 held-out generalization story).

## State files

| iter | v0 file | v2 file | comparison | contract |
|---|---|---|---|---|
| 1 | `v0_results.tau3.iter1.json` | `v2_results.tau3.iter1.json` | `comparison.tau3.iter1.md` | `contract.tau3.iter1.json` |
| 2 | `v0_results.tau3.iter2.json` | `v2_results.tau3.iter2.json` | `comparison.tau3.iter2.md` | (in-place; restored to iter1 in `.tau3.iter1.json` for diff) |
| 3 (final) | `v0_results.json` | `v2_results.json` | `comparison.md` | `data/contract.json` |
| (pre-migration) | `v0_results.tau1.iter3.json` | `v2_results.tau1.iter3.json` | `comparison.tau1.iter3.md` | `data/contract.tau1.json` |

Each iteration's event log lives at
`results/logs/<run_id>/<variant>.jsonl`. iter-1 used run_id
`tau3-iter1-20260513-070516`; rejudges used `tau3-iter2-rejudge` and
`tau3-iter3-rejudge`.
