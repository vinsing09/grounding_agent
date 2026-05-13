# Forensics — τ³-bench, pass 1 (post-migration)

> First forensic dig after porting from τ-bench → τ³-bench (see
> `tau1_vs_tau3.md`). 40 trajectories (v0 + v2) at gpt-4o-mini.

## Headline numbers

| metric | iter-3 τ-bench | iter-1 τ³-bench |
|---|---:|---:|
| v0 reward (all) | 10% | **30%** |
| v0 reward (train / held-out) | 0% / 10% | 50% / 10% |
| v2 reward (all) | 10% | **35%** |
| v2 reward (train / held-out) | 10% / 10% | 20% / **50%** |
| v2 messages/run | 33.1 | 24.2 |
| v0 tool errors | 16 | **6** |
| v2 tool errors | 34 | **6** |

Three orders of observation:

1. **The agent moved from 10% to 30-35% reward** without any agent
   change. The benchmark fixes (τ³-bench) recovered ~20pp of
   "agent failure" that was previously broken ground truth.
2. **v2 is now better than v0** (35% vs 30%, +5pp). On the old
   benchmark v2 was 5pp WORSE. The discipline preamble's effect
   reverses sign once the broken tasks are removed.
3. **v2 generalises better.** v2 held-out is 50% pass-rate vs v0's
   10%. Five of 10 held-out tasks pass under v2 vs one under v0.
   This is the framework's intended generalization signal landing.

## Per-dimension pass rates (v0, all-split)

| dimension | iter-3 τ-bench | iter-1 τ³-bench |
|---|---:|---:|
| `confirmation_discipline` | 65% | **70%** |
| `information_grounding` | 70% | 65% |
| `policy_compliance` | 15% | **25%** |
| `scope_adherence` | 30% | **0%** ⚠ |
| `tool_sequence_correctness` | 75% | 65% |
| `tool_argument_correctness` | 65% | **75%** |

Most dimensions moved in roughly the right direction. **One regressed
to 0% — `scope_adherence`** — and the cause is the contract.

## Issues surfaced (τ³-bench bucket classes)

### Bucket τ3-A — `fb-make-multiple-tool-calls` is the only `scope_adherence` clause and it's mistagged

The τ³-bench contract regenerated against the new policy has exactly
one clause tagged `scope_adherence`:

```
fb-make-multiple-tool-calls: "do not respond to the user while making
                              a tool call"
```

This is an interaction-discipline / turn-taking rule, not a
transfer-to-human decision. It should be `tool_sequence_correctness`
or its own dimension. With it as the only clause in
`scope_adherence`, the LLM judge cites it on every task that has any
mixed-turn behaviour — **20 of 20 trajectories**. Pass rate = 0%.

This is the same class of mistagging the iter-3 forensics under
τ-bench (`forensics_v3.md`) flagged. The new contract repeated it
because the generator prompt has not been updated.

### Bucket τ3-B — `reward_kind()` doesn't understand τ³-bench's `RewardInfo` shape

τ-bench had `RewardInfo.info = {r_actions: float}` or `{r_outputs:
float, outputs: dict}`. Our `compare.reward_kind()` reads this shape.
τ³-bench changed `RewardInfo` to carry first-class fields (`db_check`,
`env_assertions`, `action_checks`, `nl_assertions`,
`communicate_checks`). `reward_kind()` falls through to `"no_grade"`
for every task — visible in the comparison's reward-kind table where
every row shows `no_grade`.

This is purely a reporting gap — the underlying reward number is
correct. The decomposition by check kind needs an updated extractor.

### Bucket τ3-C — `ts-transfer-to-human` clause fires on legitimate quick-refusal transfers

The τ³-bench contract added a tool_sequence requiring
`get_user_details` before `transfer_to_human_agents`. But for
out-of-scope requests the agent correctly refuses *without* looking
up the user. Tasks 0, 3, etc. (correctly transferred) get cited as
`tool_sequence_correctness` violations.

This is a contract-level over-specification, not a framework bug.
Either the generator should not emit this clause, or it should
include "OR direct refusal" as a conditional.

### Bucket τ3-D — `confirmation_discipline` and `tool_argument_correctness` got 0 contract clauses

The generator placed no clauses under these two categories in the
τ³-bench contract. The deterministic checks still fire (they encode
the rule directly), but `clause_refs` come back empty on failures
— hampering forensics-by-clause-id later.

## What still works (re-confirmation of iter-1→iter-3 bucket fixes)

- **Bucket A (confirmation deterministic):** ✅ Pass-rate 70%
  on v0. Mean per-mutation score 0.93 (event log). The check
  works as designed on τ³-bench too.
- **Bucket B (agent-actions emphasis):** ✅ Task 0 (refuse-and-
  transfer) had `scope_adherence` cited only via the mistagged
  clause; the `policy_compliance` judge correctly passed on the
  refusal. The "anchor on actions, not requests" rule generalises.
- **Bucket C (tool_argument_correctness):** ✅ 75% pass-rate on
  v0. The 6 tool errors all flagged. `ToolMessage.error: bool`
  from τ³-bench is a cleaner signal than grep-for-`Error:` ever
  was.
- **Bucket D (termination):** ✅ Direct map from τ³-bench's
  `TerminationReason` enum. Surfaces max_steps cleanly.

## Decision: iter-2 fixes τ3-A and τ3-B; defer τ3-C and τ3-D

- **τ3-A (mistagged scope clause)**: 100% impact on `scope_adherence`
  pass-rate. Fix the contract — either regenerate with a sharper
  generator prompt or hand-patch the tag (the clause text is fine).
- **τ3-B (broken reward decomposition)**: pure reporting issue but
  trivial to fix. Patch `compare.reward_kind()` to detect
  τ³-bench's RewardInfo fields.
- **τ3-C (ts-transfer-to-human over-spec)**: lower impact (2 FNs).
  Will revisit if iter-2 forensics show it persisting.
- **τ3-D (missing confirmation/argument clauses)**: deterministic
  judges work without clauses. Clause-citation forensics is degraded
  but not blocked. Defer.

Iter-2 expects ~5–10 pp shifts on the affected dimensions. The
framework's core architecture remains correct on τ³-bench — what
moved is which clauses live where.
