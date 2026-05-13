# Migration: τ-bench → τ³-bench

> Meta-finding from the fourth iteration of this project: the
> *benchmark* used in iterations 1–3 was itself the wrong artifact.

## What happened

Iterations 1–3 of `grounding_agent` evaluated against
`sierra-research/tau-bench` (the 2024 release).

Web verification (May 2026) confirmed that Sierra Research has since
released τ²-bench (2025) and τ³-bench (March 2026). The τ³-bench
release shipped **27 airline-task fixes** addressing five classes of
defect:

1. Tasks rewarding policy violations (incorrect expected actions)
2. Ambiguous user instructions (underspecified scenarios)
3. Impossible constraints (e.g. payment methods absent from profiles)
4. Missing fallback behaviors (no guidance on tool failure)
5. Policy loophole prevention (e.g. cabin-class upgrade workarounds)

Per Sierra's own taubench.com/blog/tau3-task-fixes.html, airline
scores improved **+14 to +20 points on pass^1** after the fixes,
meaning prior evaluations *systematically penalised correct
behaviour*.

## Implication for iterations 1–3 of this project

Some of what `results/forensics.md` attributed to **agent failure**
was actually **broken ground truth**. The framework's per-dimension
verdicts were still meaningful (judges read the policy + trajectory),
but the τ-bench reward against which we compared was unreliable. In
particular:

- The 16% / 10% / 10% reward pass rates across the three iterations
  were partly artifacts of broken tasks.
- Some "disagreement examples" in `forensics.md` and `forensics_v2.md`
  cited cases where the agent correctly refused but the gold-action
  list expected a refusal that was structurally impossible to
  perform — these may have been τ-bench bugs, not framework bugs.

## Migration done in iteration 4

1. Installed `sierra-research/tau2-bench` (March-2026 release; the
   repo name retains "tau2" but the released version contains τ³-bench
   features including the airline fixes).
2. Replaced `vendor/tau_bench_airline/policy.md` with τ³-bench's
   updated policy. Old policy preserved at
   `vendor/tau_bench_airline/policy.tau1.md`. The new policy is **166
   lines** vs 70 — significantly clarified, with explicit
   sub-sections for payment methods, membership levels, and flight
   attributes, plus a fully-stated transfer-to-human protocol.
3. Rewrote `grounding_agent/runner.py` for tau2-bench's new Python
   API (`tau2.run.run_simulation` + `tau2.runner.build_text_orchestrator`).
   Adapter functions (`_flatten_messages`, `classify_termination`,
   `extract_tool_errors`) convert tau2's pydantic Message types and
   first-class `TerminationReason` enum into our judges' expected
   shapes — **the rest of the framework (taxonomy, contract, judges,
   evaluator, compare, eventlog) was unchanged**. That's the
   framework's portability paying off.
4. Regenerated `data/contract.json` against τ³-bench's policy.
   Old contract preserved at `data/contract.tau1.json`.
5. Updated `data/tasks.json` to use τ³-bench's canonical train/test
   split (10 of 30 train, 10 of 20 test). Task ids are now strings
   ("0", "1", "3", ...) — `compare.split_of` updated to accept
   either int or string ids.

## What's different operationally

| | original τ-bench (iter 1–3) | τ³-bench (iter 4+) |
|---|---|---|
| Install | `pip install git+...` | `uv pip install -e ../tau2-bench-src` |
| Domain count | 2 (airline, retail) | 6 (+telecom, banking_knowledge, mock, voice) |
| Airline policy size | 70 lines | 166 lines |
| Tool count (airline) | 14 | 15 (added `get_flight_status`) |
| Task id type | int | string |
| Reward shape | `r_actions` xor `r_outputs` | `RewardInfo` with db_check + env_assertions + action_checks + nl_assertions + communicate_checks |
| Termination shape | `reward_info=None` implied max_steps | first-class `TerminationReason` enum (10 values) |
| Tool error signal | grep `Error:` from content | explicit `ToolMessage.error: bool` |

τ³-bench's structured RewardInfo replaces our Bucket-D termination-
classification and reward-kind-decomposition work — but we kept those
adapter layers since they normalise across the two backends.

## What stayed identical

- The seven-category failure taxonomy.
- The contract-generator architecture (one LLM call, validator-gated
  save/load).
- All six judges (three semantic, three deterministic).
- The evaluator, comparator, and event log.
- 125 of 125 tests still pass (one new test added for the τ³-bench
  adapter; the prior 124 untouched).

## What this implies for forensics

Forensics passes 1–3 (under τ-bench) found four real bucket-class
fixes:
- Bucket A: confirmation_discipline → deterministic. Still applies.
- Bucket B: agent-actions emphasis in semantic prompts. Still applies.
- Bucket C: tool_argument_correctness dimension. Still applies; even
  more useful under τ³-bench's explicit `ToolMessage.error` flag.
- Bucket D: termination + reward_kind surfaced. Now partly handled by
  τ³-bench natively; our adapters bridge the rest.

A **new forensics pass on τ³-bench** (the iter-4 forensic dig
described in `forensics_tau3.md`) is the only way to know whether
the framework's per-dimension calibration holds under the cleaner
ground truth.

## State files

- `data/contract.tau1.json` — pre-migration contract (under old policy)
- `data/contract.json` — current (under τ³-bench policy)
- `vendor/tau_bench_airline/policy.tau1.md` — old policy
- `vendor/tau_bench_airline/policy.md` — current
- `results/v0_results.tau1.iter3.json` / `v2_results.tau1.iter3.json` —
  final iter-3 results under old τ-bench
- `results/comparison.tau1.iter3.md` — old comparison
- `results/v0_results.json` / `v2_results.json` (after iter-4
  completes) — τ³-bench results
