# Forensics — pass 3 (after iter-3 contract regeneration)

> Methodology: kept the iter-2 trajectories (cached in
> `results/{v0,v2}_results.iter2.json`); regenerated `data/contract.json`
> under an iter-3 prompt that adds worked-example-per-category +
> decision-heuristic guidance; re-judged with `--judge-only` (no
> agent re-runs). Total iter-3 cost: ~$0.07 in judge tokens, ~7 min
> wall time.

## Outcome — iter-2 vs iter-3 delta

### Did the targeted mistag move? Yes.

| clause | iter-2 category | iter-3 category | iter-2 fail-cites | iter-3 fail-cites |
|---|---|---|---|---|
| `fb-modify-basic-economy` | `scope_adherence` ❌ | `policy_compliance` ✅ | 9 | **5** (–44%) |
| `fb-modify-passenger-count` | `scope_adherence` ❌ | `policy_compliance` ✅ | 1 | 1 |
| `fb-add-insurance-after-booking` | `scope_adherence` ❌ | `policy_compliance` ✅ | 0 | 0 |
| `obl-transfer-to-human` | `policy_compliance` ❌ | (removed; correctly omitted) | 0 | n/a |

The three business-rule prohibitions that pass-2 Finding 8
identified are now tagged `policy_compliance` where they belong.
Citations on `fb-modify-basic-economy` dropped 44% — the
remaining 5 are the cases where the agent *did* actually modify
a basic-economy reservation, which is now correctly judged under
policy_compliance.

### Per-dimension confusion deltas

**v0:**

| dimension | iter-2 | iter-3 | net |
|---|---|---|---|
| `policy_compliance` | 1/2/16/1 | **2/2/16/0** | +1 TP, -1 FN |
| `scope_adherence` | 2/4/14/0 | 1/4/14/1 | -1 TP, +1 FN (regression) |
| `information_grounding` | 2/12/6/0 | 2/11/7/0 | -1 FP, +1 TN |
| `confirmation_discipline` | 2/11/7/0 | 2/11/7/0 | unchanged |
| `tool_argument_correctness` | 1/12/6/1 | 1/12/6/1 | unchanged |
| `tool_sequence_correctness` | 2/13/5/0 | 2/13/5/0 | unchanged |

**v2:**

| dimension | iter-2 | iter-3 | net |
|---|---|---|---|
| `policy_compliance` | 0/1/17/2 | 0/0/18/2 | -1 FP |
| `scope_adherence` | 0/4/14/2 | **0/2/16/2** | **-2 FP** |
| `information_grounding` | 2/12/6/0 | 2/13/5/0 | +1 FP (regression) |
| `confirmation_discipline` | 1/7/11/1 | 1/7/11/1 | unchanged |
| `tool_argument_correctness` | 1/8/10/1 | 1/8/10/1 | unchanged |
| `tool_sequence_correctness` | 2/16/2/0 | 2/16/2/0 | unchanged |

**Net direction:** improvements outnumber regressions, but the
moves are small (1–2 cell shifts per dimension). The most
diagnostic single result is v2 `scope_adherence`'s FP count
dropping from 4 to 2 — fewer mis-cited refusals of business-rule
prohibitions.

### New mistag — surfaced by iter-3

The iter-3 generator placed `fb-simultaneous-tool-call` ("do not
respond to the user while making a tool call") in `scope_adherence`.
This clause is logically an **interaction discipline** rule
(turn-taking with tool calls), not a transfer-to-human rule.

| clause | iter-2 cites | iter-3 cites |
|---|---|---|
| `fb-simultaneous-tool-call` | 0 | **14** |

This is a new false-firing source. We swapped a known mistag for a
fresh one. The category definitions in the prompt distinguish
`policy_compliance` vs `scope_adherence` well; they don't
disambiguate "interaction discipline" rules (which arguably belong
under `tool_sequence_correctness`).

### Other moves

- `obl-confirm-action` clause id was renamed to
  `obl-obtain-confirmation` in iter-3. Citation count carried
  over: 7 → 7. Behavior identical; just a different slug.
- Three new `tool_argument_correctness` obligations
  (`obl-validate-flight-modification`,
  `obl-validate-cancellation-conditions`,
  `obl-validate-payment-methods`) emerged in iter-3. Each cited 7
  times. The total tool_argument_correctness failure count
  (verdicts) is unchanged; this is just where the failing
  citations now live.

## Decision: stop at iter-3

Diminishing returns are visible:

- iter-1 → iter-2 (bucket fixes): **major shifts** in pass rates and
  FN counts. Bucket A confirmation_discipline went 0% → 65%. Bucket
  B scope_adherence FN went 3 → 0. Bucket C added a new dimension.
- iter-2 → iter-3 (contract retag): **small shifts** (1–2 cells per
  dimension). One mistag fixed, one new mistag emerged.
- Continuing to iter-4 would target the new mistag
  (`fb-simultaneous-tool-call`). Likely yield: another 1-cell
  shift, possibly another mistag emerges elsewhere.

The framework's correctness is bounded by the LLM-generated
contract's category-tagging precision. Mistagging is **structural
noise in generated contracts**, not a bug in the framework.

**Recommendation in WRITEUP**: document this finding as
"production-deployment hardening: after contract generation, route
the JSON through a human-in-the-loop tag review (one pass,
mechanical — does the clause text match the tagged category's
definition?). The validator infrastructure already exists; the
review is a one-time human pass."

## State at end of iter-3

- `data/contract.json` — iter-3 contract (cleaner core tagging;
  one residual mistag).
- `data/contract.iter2.json` — backup of iter-2 contract.
- `results/v0_results.json` / `results/v2_results.json` — iter-3
  judge verdicts against iter-2 cached trajectories.
- `results/v0_results.iter2.json` / `results/v2_results.iter2.json`
  — backup of iter-2 verdicts (under iter-2 contract).
- `results/v0_results.pre.json` / `results/v2_results.pre.json` —
  pre-bucket-fix (iter-1) artifacts.
- `results/logs/20260512-234616-db4444/` — iter-2 agent-rollout
  event log.
- `results/logs/iter3-rejudge/` — iter-3 rejudge event log.
- `results/forensics.md` — forensics pass 1.
- `results/forensics_v2.md` — forensics pass 2.
- `results/forensics_v3.md` — this file.

The repo retains every iteration's artifacts. Anyone can rerun
`scripts/compare_to_reward.py` against any of the three eval
states to reproduce the corresponding `comparison.md`.
