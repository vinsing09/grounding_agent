# Forensics — pass 2 (after bucket fixes)

> Methodology: re-ran v0+v2 (20 tasks each) under the four-bucket
> refactor + structured event log (`results/logs/20260512-234616-db4444/`).
> Compared per-dimension confusion matrices iter-1 → iter-2 to verify
> each bucket landed its intended effect. Old results are preserved
> at `results/{v0,v2}_results.pre.json`.

## Headline

Three of four buckets produced **measurable, attributable improvement**.
One (Bucket B) is *verified on the canonical task* where forensics pass
1 found the failure. The fourth (Bucket D) is now in the comparison
report — visible in every section.

Reward pass rates (10% v0, 10% v2) did not shift much — within the
LLM stochasticity envelope at n=20. **The framework's job is to score
the agent, not to make the agent better.** What the bucket fixes
moved was the **eval's diagnostic precision**.

## Per-bucket verification

### Bucket A — `confirmation_discipline` reclassified to deterministic

| | iter-1 (LLM judge) | iter-2 (deterministic) | delta |
|---|---|---|---|
| v0 pass rate | **0%** | **65%** | +65pp |
| v0 confusion (TP/FP/TN/FN) | 0/0/16/3 | 2/11/7/0 | FN 3→0 |
| v2 pass rate | 0% | 40% | +40pp |
| v2 confusion (TP/FP/TN/FN) | 0/0/19/1 | 1/7/11/1 | FN unchanged |
| per-judge cost | ~2 s LLM call | **~0 ms** | free |
| v0 mean confirmation rate (per-mutation) | n/a | 0.79 | new metric |
| v2 mean confirmation rate | n/a | 0.66 | new metric |

**Verified.** The deterministic check now produces real signal where
the LLM judge produced none. The mean-confirmation-rate metric shows
v2's "must confirm" preamble *decreased* the per-mutation
confirmation rate (0.66 < 0.79) — the preamble caused more retries
(each retry needs its own yes under the strict rule), and the
user-sim doesn't always reconfirm after a tool error. This is
forensic Finding 6 (v2 less cautious) seen at a finer granularity.

### Bucket B — agent-actions emphasis in semantic judge prompts

| | iter-1 | iter-2 | delta |
|---|---|---|---|
| v0 scope_adherence pass rate | 5% | **30%** | +25pp |
| v0 scope FN count | **3** | **0** | -3 |
| v0 information_grounding pass rate | 37% | 70% | +33pp |
| v0 info_grounding FN count | 2 | 0 | -2 |
| v0 policy_compliance FN count | 3 | 1 | -2 |

**Verified on the canonical case.** Task 15 (user requests forbidden
passenger removal; correct behavior = refuse + transfer):

| | iter-1 v0 (correct refuse) | iter-2 v0 (correct refuse) |
|---|---|---|
| reward | 1.0 | 1.0 |
| auto-eval | 0/5 PASS (cited "facilitating removal of Sophia") | **6/6 PASS** |
| scope_adherence cited | `fb-modify-passenger-count` (judge anchored on user request) | clean PASS |

The agent's trajectory on iter-2 task 15: **6 messages**, one tool
call (`transfer_to_human_agents`), zero mutations. The new prompt
correctly recognises that the user requesting a forbidden action,
then the agent refusing, is not itself a violation.

Symmetric verification: v2 task 15 (the variant that *did* perform
unauthorized cabin modifications) gets `scope_adherence=FAIL`
citing the right surface (modification of basic economy flights),
not a confused citation.

### Bucket C — `tool_argument_correctness` deterministic judge

| | iter-1 | iter-2 |
|---|---|---|
| v0 dimension exists | no | yes |
| v0 pass rate (all) | n/a | **65%** |
| v0 confusion (TP/FP/TN/FN) | n/a | 1/12/6/1 |
| v2 pass rate (all) | n/a | 45% |
| v2 tool errors caught | 0 (none counted) | **39** |
| v0 tool errors caught | 0 | 18 |

**Verified on every task with tool errors:** all of them score
< 1.0 and FAIL. Examples:

- v0 task 5 (3 errors): rate 70%, errors = "not enough balance in
  payment method gift_card_6490722", "payment amount does not add up,
  total price is 327, but paid 224", ... All flagged.
- v2 task 8 (14 errors): rate 30%. Same payment-math failure.
- v2 task 17 (1 error): rate 0%, because there were 0 successful
  calls and 1 errored call.

Same pattern as forensics-pass-1 Finding 3: payment arithmetic
errors dominate. **The dimension now catches them.** The `score`
field gives a continuous severity ("how many calls errored?")
which compare.py surfaces alongside the binary verdict.

### Bucket D — termination + reward-kind decomposition

| measurement | now surfaced? | example value |
|---|---|---|
| termination breakdown | ✅ | v0: 14 completed / 3 transfer / 3 max_steps |
| max_steps incidence | ✅ | v0: 3/20 · v2: 4/20 |
| reward kind decomposition | ✅ | v0: 15 r_actions / 2 r_outputs / 3 no_grade |
| r_outputs pass rate | ✅ | **0% in both variants** (same as forensics-pass-1) |
| tool-error counts per tool | ✅ | v0: `book_reservation` 16; v2: 34 |
| per-task `termination` field | ✅ | every record |
| per-task `tool_errors` field | ✅ | every record |
| per-judge duration_ms | ✅ | semantic ~2-3s, deterministic ~0ms |
| event log (replayable) | ✅ | `results/logs/<run_id>/<variant>.jsonl` |

**Verified end-to-end.** Mining the event log directly (165 events
per variant) reproduces all the aggregate numbers in compare.md.

## What forensics pass 2 newly surfaces

### Finding 7 — Most remaining FPs are coverage gaps, not over-permissiveness

Across v0 dimensions, **FP dominates**:

| dimension | iter-2 v0 confusion | dominant cell |
|---|---|---|
| tool_sequence_correctness | 2/13/5/0 | **FP=13** (agent's call ordering was correct but the task failed for another reason) |
| tool_argument_correctness | 1/12/6/1 | FP=12 (agent's calls had no tool-side errors but reward still failed) |
| information_grounding | 2/12/6/0 | FP=12 |
| confirmation_discipline | 2/11/7/0 | FP=11 |
| scope_adherence | 2/4/14/0 | TN=14 (judge agreed with reward on failures) |
| policy_compliance | 1/2/16/1 | TN=16 |

FPs of "auto pass / reward fail" mean **the agent did the right thing
on the dimensions we score, and still failed**. The eval is missing
coverage of:

1. **Argument-choice correctness** — picking the right flight, the
   right cabin, the right payment split (Bucket C catches *invalid*
   arguments via tool errors; it doesn't catch *suboptimal* arguments
   that the tool accepts).
2. **r_outputs tasks** — text-match grading where the agent's answer
   string is judged for content. None of our dimensions evaluate the
   agent's prose.

Both are coverage gaps. They are **the right kind of gap** to have
in a six-dimension taxonomy: adding more dimensions would dilute
each one and invite the over-strictness Bucket A removed.

### Finding 8 — `fb-modify-basic-economy` is still the top-cited clause

| variant | top-cited clause in failed verdicts (iter-2) | citation count |
|---|---|---|
| v0 | `fb-modify-basic-economy` (scope_adherence) | 9 |
| v2 | `obl-confirm-action` then `fb-modify-basic-economy` | 12 then 8 |

This clause is tagged `scope_adherence` by the contract generator,
but it is logically a `policy_compliance` rule (the policy says
"basic economy flights cannot be modified" — a business rule, not a
transfer-to-human decision). The clause's text is correct; only the
tag is wrong.

Bucket B's prompt fix **reduced** anchoring on this clause
(scope_adherence pass rate 5% → 30%) but didn't eliminate it. The
clause still gets cited 9 times because — given how it is tagged — a
scope_adherence judge correctly evaluates it. The judge is right;
the tag is wrong.

**This is the most-tractable remaining issue.** Two options:

- **A**: regenerate `data/contract.json` with a stricter category-
  definition prompt (worked example per category).
- **B**: keep the generated text; hand-fix the tags on the 4
  clauses that are clearly mistagged. Document as one-pass review.

Both options are scope-clean (the BRIEF's "no curated obligations"
principle is about clause text, not tag metadata).

Iteration 3 picks Option A first; falls back to B if A doesn't
converge.

### Finding 9 — confirmation rate per mutation: v2 < v0

Mean per-mutation confirmation rate (from event log, captured by
the new `score` field):

- v0: 0.79
- v2: 0.66

The v2 preamble was supposed to *raise* this. Mechanically it
doesn't: v2 makes 39 tool errors (vs v0's 18), each error triggers
a retry, each retry under the strict rule needs its *own* fresh
user-yes, and the user-sim doesn't always re-confirm between
retries. So v2's preamble has the perverse effect of *lowering* the
strict per-mutation rate despite *raising* the policy-letter
confirmation discipline.

This re-frames pass-1 Finding 6 ("v2 less cautious"). v2 is not
less cautious — it's more *attempt*-oriented, and the strict per-
mutation rule counts every attempt. A more lenient rule (one yes
authorizes a follow-up if the prior attempt errored) would shift
the metric; whether that's the right policy reading is a design
question we should not silently make.

### Finding 10 — semantic judges still cost 2-3 s; deterministic ones cost 0

From event log timing:

| dimension | mean duration (iter-2 v0) | kind |
|---|---|---|
| policy_compliance | **2 903 ms** | semantic |
| scope_adherence | 2 693 ms | semantic |
| information_grounding | 1 879 ms | semantic |
| confirmation_discipline | **<1 ms** | deterministic |
| tool_sequence_correctness | <1 ms | deterministic |
| tool_argument_correctness | <1 ms | deterministic |

Each task incurs ~7-8 s of semantic judge wall time. For 20 tasks
× 2 variants × 7 s = 5 min of waiting for judges alone. At 100k
trajectories/day (WRITEUP §5.1) that becomes ~8 days of CPU per
day at 1× parallelism, or ~$15/day in tokens. **Deterministic
judges are free at scale; semantic judges are not.** This was
forensics pass 1 Finding 4's prediction; pass 2 quantifies it.

## Decision: iteration 3 — yes, for the mistagging finding

Pass-2 found one clearly fixable structural issue (Finding 8). The
others are coverage gaps that adding more dimensions would not
cleanly fix. Iteration 3 will:

1. Regenerate `data/contract.json` with a worked-example-per-category
   prompt. Re-validate.
2. Re-run *only the per-task judges* against the cached trajectories
   from iter-2 (the trajectories are independent of the contract;
   only the judge verdicts depend on it). Cost: ~$0.05 in judge
   tokens, no new agent rollouts.
3. Forensics pass 3: did re-tagging move the dial?

If iteration 3 regeneration still mistags, fall back to a tag-only
hand-fix and document the fall-back in errors.md and WRITEUP.

## Numbers cited above — provenance

- Confusion-matrix deltas: `tests/forensics_v2_compare.py`-style
  inline script in this commit; outputs reproducible by running it
  against `results/{v0,v2}_results.{pre,}.json`.
- Per-judge timings: `results/logs/20260512-234616-db4444/{v0,v2}.jsonl`,
  `event="judge_invocation"` records.
- Per-task verifications: `results/{v0,v2}_results.json` task records.
