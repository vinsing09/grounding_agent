# Code review — `judges.py` + `runner.py` + `evaluator.py` + smoke test

**Date:** 2026-05-12
**Modules:**
- `grounding_agent/judges.py` (~235 lines)
- `grounding_agent/evaluator.py` (~45 lines)
- `grounding_agent/runner.py` (~75 lines)
- `scripts/generate_contract.py`, `scripts/smoke_test.py`

**Tests:** 17 judges + 5 evaluator + 2 runner = **24 new tests** (53 total, all passing).

## What was built

### `judges.py`
- `JudgeResult` frozen dataclass: `category`, `passed`, `reason`, `clause_refs`.
- `extract_tool_calls(messages)` — flatten OpenAI-style trajectory into
  `[{position, name, arguments}]` per executed tool call. Robust to
  null content, malformed JSON in arguments, missing tool_calls.
- `tool_sequence_judge` — deterministic. For each `tool_sequence`
  clause, every occurrence of `target_tool` in the trajectory must be
  preceded by at least one call to every `prerequisite_tool`. Vacuous
  pass when contract has no `tool_sequences` or when no target appears.
- `format_trajectory(messages)` — compact role-tagged renderer for
  inclusion in judge prompts. System messages dropped (they would
  dilute attention; the relevant clauses are already in the judge's
  own system prompt).
- Four semantic judges (`policy_compliance_judge`,
  `confirmation_discipline_judge`, `information_grounding_judge`,
  `scope_adherence_judge`), each calling `_semantic_judge` with its
  category. Each filters obligations + forbidden_behaviors by category,
  builds a strict JSON prompt, calls litellm with
  `response_format=json_object`, returns a structured verdict with
  cited `violated_clause_ids` when failing.
- `ALL_JUDGES` tuple = the five judges in canonical order.

### `evaluator.py`
- `evaluate_trajectory(messages, contract, model)` — runs every judge,
  indexes results by category, raises if two judges claim the same
  category (guards against future copy-paste).
- `summarize(results)` — JSON-dumpable summary: `n_dimensions`,
  `n_passed`, `n_failed`, `by_dimension`.

### `runner.py`
- `run_task(task_index, ...)` — thin wrapper: construct
  `MockAirlineDomainEnv`, construct `ToolCallingAgent` with
  `env.tools_info` + `env.wiki`, call `agent.solve(env,
  task_index=...)`, return a dict with the trajectory + tau-bench's
  ground-truth reward.
- `airline_tool_catalog()` — return the 14 tools as `[{name,
  description}]` without needing an env (no API key required), so
  `scripts/generate_contract.py` can run offline of the user-sim
  model.
- tau_bench imports are deferred inside functions so importing
  `grounding_agent.*` modules stays cheap and offline.

### Scripts
- `scripts/generate_contract.py` — one-shot LLM call → committed
  `data/contract.json`. Idempotent unless `--force`.
- `scripts/smoke_test.py` — runs the agent on tasks 0+1, evaluates,
  prints per-dimension PASS/FAIL alongside the tau-bench reward.

## Reconciliation with plan

BRIEF Day 1 items 3, 4, 5, 6:
- "four semantic judges + one deterministic tool-sequence checker": ✅
  All five wired into `ALL_JUDGES`. The fifth taxonomy category
  (`task_completion`) intentionally has no semantic judge — running a
  separate LLM judge for end-to-end completion when τ-bench's reward
  already programmatically measures that exact thing would conflate
  evaluator noise with ground-truth signal. Decision recorded in the
  judges.py module docstring and in this review.
- "runner drives an agent through a τ-bench task, captures
  trajectory": ✅ `run_task` returns trajectory + reward + info.
- "evaluator applies judges to a trajectory, produces per-dimension
  verdicts": ✅ `evaluate_trajectory` returns `dict[category,
  JudgeResult]`.
- "Smoke-test on 2 tasks end-to-end before scaling": ✅ ran on tasks
  0 and 1. See "Smoke results" below.

## Why these specific design choices

- **Deterministic judge is a function, not an LLM.** Tool-sequence
  prerequisites are mechanical: they're a `<` ordering check over
  positions. A semantic judge here would burn money to do something a
  loop does for free. The signature matches the semantic judges so
  `ALL_JUDGES` is uniform.
- **Each judge filters its own clauses.** The contract is read once,
  but each semantic judge sees only the clauses tagged to its
  category. This bounds prompt size and stops the model from
  cross-bleeding between dimensions (e.g. a confirmation issue
  showing up in the policy_compliance verdict).
- **`clause_refs` on the result.** Lets the comparison step in Day 2
  attribute disagreements to specific clauses (e.g. "tau-bench reward
  = pass, but auto-eval failed citing `fb-cancel-flights-after-use`
  — let's check whether that clause is correctly tagged").
- **Vacuous pass when no clauses tagged.** A category with no
  obligations or forbidden_behaviors in the contract should pass
  rather than fail — failure would force every contract to populate
  every category, which would be cargo-cult coverage.
- **`response_format=json_object` on judge calls.** Same reason as
  the generator: binds the output to JSON, fails fast on schema
  drift. Tested locally with gpt-4o-mini; works.

## Lean-code check

| Module | Lines | Limit |
|---|---|---|
| judges.py | ~235 | ≤300 ✅ |
| evaluator.py | ~45 | ≤300 ✅ |
| runner.py | ~75 | ≤300 ✅ |

No abstractions beyond what's used:
- No "Judge" base class — five free functions sharing a result type
  and a uniform `(messages, contract, model)` signature is simpler.
- No async / batching — Day-1 scope is correctness, not throughput.
  20 tasks × 5 judges = 100 judge calls; sequential is fine. Will
  re-evaluate at Day-2 scale.
- No retry on litellm errors — fail loud; let the run script collect
  what it has and report. Adding silent retry hides systematic prompt
  issues.

## Test rigor

- **Trajectory fixtures use the real shape.** `_tool_call_msg /
  _tool_result_msg / _say_msg` produce exactly the dict shape
  `tau_bench.agents.tool_calling_agent.solve` emits (verified by
  reading its source: assistant.tool_calls = list of `{id, type:
  "function", function: {name, arguments: json-string}}`; tool
  messages with `tool_call_id` + `name` + `content`). T3 compliance.
- **Deterministic judge has 6 distinct tests** including order
  reversal (prereq after target), missing prereq, vacuous pass paths,
  multi-prerequisite, and "no tool_sequence clauses at all".
- **Semantic judges' LLM path is NOT unit-tested.** It is exercised
  by the smoke test on real trajectories; mocking litellm in unit
  tests would test our mock, not the contract.
- **Runner test monkeypatches `MockAirlineDomainEnv` and
  `ToolCallingAgent`** so we verify the result-shaping logic without
  hitting the network or running a 30-step LLM loop. Live
  end-to-end-ness is verified by the smoke test.
- **`airline_tool_catalog` test** uses the real tau_bench package
  (no LLM keys needed), confirming 14 tools and key tool names.

## Smoke results (tasks 0 and 1)

```
--- task 0 ---
tau-bench reward: 0.0           (ground truth = FAIL)
auto-eval: 3/5 passed
  PASS  policy_compliance
  FAIL  confirmation_discipline       (no explicit yes before book_reservation)
  PASS  information_grounding
  PASS  scope_adherence
  FAIL  tool_sequence_correctness     (book_reservation called without get_user_details)

--- task 1 ---
tau-bench reward: 1.0           (ground truth = PASS)
auto-eval: 1/5 passed
  FAIL  policy_compliance             (semantic judge over-applied a booking clause to a cancellation)
  FAIL  confirmation_discipline       (debatable — agent did summarize)
  FAIL  information_grounding         (debatable)
  FAIL  scope_adherence               (clear judge polarity error: cited
                                       fb-cancel-flights-after-use but the flight HAD NOT been used)
  PASS  tool_sequence_correctness
```

The disagreements on task 1 are the exact failure modes Day 2's
comparison step is designed to expose: a couple of judges are
over-strict on gpt-4o-mini, and `scope_adherence` mis-applied a
forbidden_behavior whose own category tag is itself debatable
(`fb-cancel-flights-after-use` is more `policy_compliance` than
`scope_adherence` — see "What worked / what didn't" below). The
deterministic judge agrees with reward on both tasks.

## What worked / what didn't

**Worked:**
- Contract generation succeeded after one prompt-tightening pass
  (logged in `errors.md`). 21 clauses across the three sections.
  Tool-sequence clauses are correctly identified for the three
  mutating tools (`book_reservation`, `update_reservation_flights`,
  `cancel_reservation`).
- Deterministic checker correctly flagged the missing
  `get_user_details` prerequisite on task 0.
- The end-to-end pipeline produces structured, JSON-able verdicts —
  ready for the Day-2 comparison.

**Didn't (and is informative):**
- Some clauses are mistagged: `fb-modify-basic-economy`,
  `fb-add-insurance-after-booking`, `fb-cancel-flights-after-use`,
  `fb-modify-passenger-count` all landed in `scope_adherence` when
  they're business rules (`policy_compliance`). `obl-transfer-to-human`
  landed in `policy_compliance` when it should be `scope_adherence`.
  Action: this is the headline tension between generated and curated
  contracts — covered honestly in `WRITEUP.md`. We can rerun the
  generator with gpt-4o or with a stricter category-definition prompt
  if Day 2 reveals the mistagging is the dominant source of
  disagreement with reward.
- gpt-4o-mini semantic judges drift toward "fail" when the prompt
  lists many clauses (it tries to find something to cite). Day 2:
  consider switching judge model to gpt-4o and re-running.

## Risks / things to watch

- Per-task LLM cost: smoke run was ~$0.013 across two tasks
  (agent+user+judges). Twenty tasks × two variants ≈ $0.30. Cheap.
- Judge prompts will be sensitive to clause text quality. The
  `clause_refs` field on `JudgeResult` is the lever for diagnosing
  which clauses are mis-firing; the Day-2 comparison should aggregate
  by clause id to surface the worst offenders.

## Next chunks (Day 2)

- `data/tasks.json` — 10 train + 10 held-out (tau-bench task indices).
- `scripts/run_eval.py` — drive both v0 and v2 variants across 20
  tasks, persist `results/v0_results.json` and `results/v2_results.json`.
- `grounding_agent/compare.py` + `scripts/compare_to_reward.py` —
  per-dimension confusion matrix and disagreement examples.
- `WRITEUP.md` — dimensions + justification, methodology, results
  (incl. held-out angle), production-readiness at 100k/day, what we
  chose not to build (mistagging story goes here).
- `README.md` — clone-and-run verification from clean checkout.
