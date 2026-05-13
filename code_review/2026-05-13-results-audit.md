# Code audit — results / judges / wiki_override path

**Date:** 2026-05-13
**Trigger:** feedback noted per-dimension deltas (10-20pp range) didn't
match the headline reward delta (+40pp on held-out). Question: is
this a real coverage gap, or a bug in the code that's producing
misleading numbers?

**Verdict:** real coverage gap, not a bug. Five separate checks
performed; all confirm the code is doing what the documentation
claims. One regression test added to keep it that way.

## Check 1 — `wiki_override` actually mutates the agent's system prompt

**Concern:** if v2's `wiki_override` silently no-ops, v2 would be
identical to v0 and any "v2 vs v0" finding would be spurious.

**Live verification** (separate Python session, no LLM calls):
```
v0 domain_policy length: 7676
v2 domain_policy length: 9747
preamble length:         2071
delta:                   2071  ← matches exactly

v0 system_prompt contains "Execution discipline": False
v2 system_prompt contains "Execution discipline": True
```

The mutation reaches the agent. The system_prompt is a Pydantic
property that reads `self.domain_policy` fresh on each access, so
post-construction mutation takes effect on the agent's first turn.

**Regression test added:** `tests/test_runner.py
::test_wiki_override_mutates_agent_domain_policy` — guards against
a future refactor that breaks this line.

## Check 2 — all 6 judges fire on every trajectory

**Concern:** if `evaluator.evaluate_trajectory` silently dropped a
judge, the missing dimension would always report `null` and never
flag failures.

`grounding_agent/evaluator.py` iterates `ALL_JUDGES`:
```python
for judge in ALL_JUDGES:
    r = judge(messages, contract, model=model)
    if r.category in results:
        raise RuntimeError(...)
    results[r.category] = r
```

`ALL_JUDGES` is a 6-tuple defined in `judges.py:494`. Every cached
task record under `results/{v0,v2}_results.json` has exactly 6
keys under `evaluation`. **Verified by inspection.**

## Check 3 — deterministic judges are reproducible

**Concern:** if a deterministic judge has hidden randomness (it
shouldn't), cached verdicts could differ from live.

Re-ran `confirmation_discipline_judge`, `tool_sequence_judge`,
`tool_argument_correctness_judge` live against the cached
trajectories for tasks 16 and 19 (both variants). **Every verdict
matched cached.** Specifically:

```
task 16, v0: cd=PASS  ts=PASS  ta=PASS  (matches cache)
task 16, v2: cd=PASS  ts=PASS  ta=PASS  (matches cache)
task 19, v0: cd=PASS  ts=PASS  ta=PASS  (matches cache)
task 19, v2: cd=PASS  ts=PASS  ta=PASS  (matches cache)
```

No drift between cached and live deterministic verdicts.

## Check 4 — v0 and v2 trajectories are genuinely different

**Concern:** if some upstream caching layer was reusing the v0
trajectory for v2 too, we'd see "different rewards" with identical
inner content.

**Task 16** — same tool sequence, different *arguments*:

```
v0:  update_reservation_flights(reservation_id="M05KNL", cabin="economy",
       flights=[HAT110, HAT206], ...)
v2:  update_reservation_flights(reservation_id="M05KNL", cabin="economy",
       flights=[HAT110, HAT172], ...)
```

Both succeeded as tool calls. The benchmark's gold-action list
expected one of these two flight numbers (probably HAT172, since
v2 won). **Different agent choice, both syntactically valid.**

**Task 19** — different number of tool calls:

```
v0:  7 tool calls including 2 redundant search_direct_flight calls.
     Hit max_steps before completing.
v2:  5 tool calls. Reached cancel_reservation cleanly. Completed.
```

Trajectories are real, distinct, and the difference matches what
the v2 preamble was designed to encourage (less unnecessary work).

## Check 5 — does τ³-bench's `RewardInfo` carry the info we'd need
to close the gap?

**Yes.** Inspecting one task's cached reward_info:

```python
"action_checks": [{
    "action": {
      "name": "cancel_reservation",
      "arguments": {"reservation_id": "Z7GOZK"},
      ...
    },
    "action_match": True,
    "action_reward": 1.0,
    "tool_type": "write"
}]
```

The gold action's name + arguments + match boolean are sitting in
every record we already persist. A `tool_argument_choice_correctness`
dimension would be ~20 lines of code:
1. Read `info.reward_info.action_checks`.
2. For each gold action, find the matching agent tool call by name.
3. Compare argument dicts (after light normalization for ordering).
4. PASS iff every gold action found a matching call.

Same shape as the existing deterministic judges. This is the most
concrete way to close the dimensions-vs-reward gap.

## Conclusion

**The +40pp held-out reward gap is real and is not explained by any
single dimension because the dimensions don't measure the things
that drove the gap.** Specifically:

1. *Argument-choice correctness* (task 16) — agent picked a
   different valid argument; no dimension scores choice quality.
2. *Termination efficiency* (task 19) — agent did unnecessary work
   and hit max_steps; no dimension penalizes redundancy.

Both gaps are closable with one or two additional deterministic
dimensions. The framework's architecture is ready for them —
`ALL_JUDGES` is a tuple; appending one function is the change.

The "honest reframe" in PRESENTATION.md / WRITEUP.md §3.4 and
`results/forensics_tau3_v3.md` ("Post-iter-3 audit" section) is
correct: the headline is a *distribution shift*, not a uniform
improvement, and the dimension-vs-reward mismatch is itself the
diagnostic finding.

## Tests after this audit

- 126 of 126 passing (added one regression test for `wiki_override`).
- No code changes to runner/judges/evaluator/compare. The earlier
  reframe was at the documentation level only — the code's behavior
  is what was already reported.
