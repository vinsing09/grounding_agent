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
