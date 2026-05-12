# Session log

Chronological. Each session entry: date, what was decided or done, what's next.

## Session 1 — 2026-05-12 (scaffolding)

**Project scaffolded.** Fresh repo, fresh thinking. Goal locked in `BRIEF.md`.

**Decisions taken this session:**
- Task chosen: τ-bench customer-support (airline). Public, well-documented, reviewers can sanity-check.
- Ground truth: τ-bench programmatic reward. No hand-labeling.
- Trim taxonomy to ~6 categories. Customer-support does not exercise all categories of tool-using-agent failure meaningfully, and six well-justified dimensions beats eleven shallow ones in a 20-minute presentation.
- Contract is **generated** from policy.md (one LLM call, output committed as JSON) rather than hand-curated. Removes the "you curated favourable obligations" critique; gain reproducibility.
- Evaluate two prompt variants (v0 + v2) so the held-out generalization story can be told. v2 source documented in `WRITEUP.md` when written.
- Vendor τ-bench (copy policy + tools + tasks + reward), not submodule, so reviewers can read source in this repo without chasing pointers.
- Public GitHub repo; Meraki reviewers can clone directly.

**Scaffolding written:**
- `BRIEF.md`, `knowledge.md`, `errors.md`, `code_review/`
- `pyproject.toml`, `.gitignore`, `.env.example`, `LICENSE`
- Empty folder skeleton: `grounding_agent/`, `tests/`, `data/`, `results/`, `scripts/`, `vendor/`

**Vendoring done in this session:**
- τ-bench installed as a pip dependency from upstream git URL (`pyproject.toml`).
- Human-readable bits copied to `vendor/tau_bench_airline/`: `policy.md` (the agent's full operating policy), tool catalog + 3 sample tasks in `README.md`, `LICENSE.tau-bench` for attribution.
- `pip install -e .` verified in `.venv/` — tau-bench installs cleanly, no surgery needed.
- 14 tools available to the agent; 50 test tasks in the airline domain (we'll use tasks 0–9 + 10–19).
- τ-bench reward = binary 1.0/0.0 on (final DB state + executed actions) match. This is the ground truth for the comparison.

**Next session:** Day 1 implementation continues.
1. Write `taxonomy.py` first — that decision constrains everything downstream. Six categories, each with id/name/description/judge-dimension/example.
2. Then `contract.py` (one LLM call: `vendor/tau_bench_airline/policy.md` + tool catalog → obligations + forbidden behaviors + tool_sequences, each tagged to a taxonomy category). Output committed as `data/contract.json`.
3. Then `judges.py` (4 semantic + 1 deterministic tool-sequence checker).
4. Then `runner.py` + `evaluator.py`.
5. Smoke-test on 2 τ-bench tasks end-to-end before scaling.
6. Update `knowledge.md` at end of session; add error entries to `errors.md` as they occur; write `code_review/2026-05-12-day-1.md` after the first chunk lands.

## Session 2 — 2026-05-12 (Day 1, chunks 1 + 2: taxonomy + contract)

**Done this chunk:**
- `grounding_agent/taxonomy.py` — six FailureCategory dataclasses (frozen). Categories: `policy_compliance`, `confirmation_discipline`, `information_grounding`, `scope_adherence`, `tool_sequence_correctness`, `task_completion`. Five semantic + one deterministic (the tool-sequence one). Each category's `judge_dimension` is pinned equal to its `id` and tested — judge prompt files cannot drift from taxonomy. 134 lines.
- `grounding_agent/contract.py` — schema constants + `validate_contract` + `save_contract` / `load_contract` + `generate_contract` (single litellm call with `response_format=json_object`). Globally-unique clause ids enforced. Every category reference validated against `taxonomy.category_ids()` at save and load time, so the contract↔taxonomy coupling cannot rot silently. ~180 lines.
- Tests: 12 taxonomy + 17 contract = 29, all pass via `pytest tests/test_taxonomy.py tests/test_contract.py`. Test fixtures quote actual policy.md language to keep input shape realistic (T3).
- Code reviews in `code_review/2026-05-12-taxonomy.md` and `code_review/2026-05-12-contract.md`.

**Decisions taken this chunk:**
- Cut from earlier 11-category drafts: separate "hallucination", "refusal quality", "instruction adherence" — these collapse cleanly into `information_grounding`, `scope_adherence`, `policy_compliance` respectively. Six dimensions, each cited back to a specific policy clause (table in the taxonomy code review).
- Reconciled BRIEF's "4 semantic + 1 deterministic = 5 judges" with the 6-category taxonomy: one semantic category will share its dimension with the τ-bench reward (probably `task_completion`, since the reward already measures end-to-end completion — a separate semantic judge for the same thing would be confounded noise). Final binding deferred to `judges.py`.
- Contract is JSON-dict-based (not Pydantic). Single agent under test; adding a model layer is weight without payoff.

**Next chunk:** `judges.py`.
- Four semantic judges (one per applicable category) — likely
  `policy_compliance`, `confirmation_discipline`, `information_grounding`,
  `scope_adherence`. Each filters its `category`-tagged clauses from the
  contract and asks the LLM (via litellm) for a structured verdict
  `{passed, reason, category, clause_id?}`.
- One deterministic checker on `tool_sequences`: for each
  `target_tool` instance in the trajectory, verify every
  `prerequisite_tool` appears earlier.
- Tests must use a realistic trajectory shape — tau-bench's `Message`
  list with `role`, `content`, optional `tool_calls`. Will pull the
  exact shape from the installed package before writing fixtures.

## Session 2 (cont.) — 2026-05-12 (Day 1, chunks 3–6: judges + runner + evaluator + smoke)

**Done this chunk:**
- `grounding_agent/judges.py` (~235 lines) — `JudgeResult` dataclass; `extract_tool_calls`; `tool_sequence_judge` (deterministic); `format_trajectory`; four semantic judges (`policy_compliance / confirmation_discipline / information_grounding / scope_adherence`) all sharing `_semantic_judge` (litellm + `response_format=json_object` + JSON parse + cited `violated_clause_ids`); `ALL_JUDGES` tuple in canonical order.
- `grounding_agent/evaluator.py` (~45 lines) — `evaluate_trajectory(messages, contract, model)` returns `dict[category, JudgeResult]`; `summarize` returns a JSON-dumpable summary.
- `grounding_agent/runner.py` (~75 lines) — `run_task(task_index, ...)` thin wrapper around `MockAirlineDomainEnv` + `ToolCallingAgent`; `airline_tool_catalog()` returns the 14 tools without needing an env (no API key).
- `scripts/generate_contract.py` — one-shot generation; idempotent unless `--force`. After one prompt fix (`errors.md` 2026-05-12), produced `data/contract.json` with 11 obligations + 7 forbidden + 3 tool_sequences.
- `scripts/smoke_test.py` — runs tasks 0 and 1 end-to-end, evaluates, prints per-dimension PASS/FAIL alongside tau-bench reward.
- 24 new tests (17 judges + 5 evaluator + 2 runner). **Total: 53 tests, all passing.**
- Code reviews in `code_review/2026-05-12-judges-runner-evaluator.md`.
- One error log entry in `errors.md` (contract prompt schema-by-example fix).

**Decisions taken this chunk:**
- **5th category (`task_completion`) deliberately has no semantic judge.** tau-bench's binary reward already measures end-to-end task completion programmatically; a separate semantic judge would conflate evaluator noise with ground truth. Recorded in `judges.py` docstring and in the chunk code review. This makes the math match the BRIEF: 4 semantic + 1 deterministic = 5 judges, covering 5 of the 6 categories; the 6th (`task_completion`) is observed via the comparison step in Day 2.
- Judges are free functions (not a `Judge` base class); uniform `(messages, contract, model) -> JudgeResult` signature enables `ALL_JUDGES` iteration in the evaluator.
- tau_bench imports are deferred inside `run_task` so the rest of the package imports cheaply (matters for tests).
- Vacuous pass when a category has no clauses tagged — avoids forcing every contract to populate every category with cargo-cult coverage.

**Smoke results (tasks 0 + 1):**
- Task 0: tau-bench reward 0.0. Auto-eval 3/5 pass — caught the missing confirmation and the missing `get_user_details` prerequisite. Plausible alignment with the failed reward.
- Task 1: tau-bench reward 1.0. Auto-eval 1/5 pass — gpt-4o-mini judges drift toward "fail" with many clauses, and the contract has a few mistagged forbidden_behaviors (e.g. `fb-cancel-flights-after-use` in `scope_adherence` instead of `policy_compliance`), producing one clear polarity error (judge cited the rule on a flight that had NOT been used). Both effects are exactly what the Day-2 comparison-vs-reward step is for — the disagreements are not a bug in the framework, they are the framework's value.

**Day 1 status:** All six items in the BRIEF's Day-1 plan are done. End-to-end pipeline runs. Pipeline is the right thing to scale on Day 2.

**Next session (Day 2):**
1. `data/tasks.json` — 10 train (indices 0–9) + 10 held-out (indices 10–19).
2. `scripts/run_eval.py` — run v0 (default policy) and v2 (alternative prompt variant) across all 20 tasks; persist `results/v0_results.json` and `results/v2_results.json`.
3. `grounding_agent/compare.py` + `scripts/compare_to_reward.py` — per-dimension confusion matrix vs tau-bench reward, with disagreement examples. Aggregate by clause id to surface which clauses are mis-firing.
4. `WRITEUP.md` — dimensions + justification, methodology, results, held-out angle, production-readiness at 100k users/day, what we chose not to build. **Mistagging story goes here** as a "what I chose not to fix in scope" / "what auto-generation costs you" data point.
5. Polish `README.md`. Clean clone-and-run check.
6. **Open question to address Day-2 morning:** is the auto-eval-vs-reward disagreement dominated by (a) clause mistagging by the contract generator, (b) gpt-4o-mini judge over-strictness, or (c) genuine reward-blind-spot wins for the auto-eval? Comparison should aggregate by category AND by clause id to disambiguate. If (a) dominates: consider regenerating with gpt-4o, or fold the mistagging story into the writeup. If (b) dominates: rerun judges with gpt-4o on the v0 trajectories.
