# grounding_agent — session protocol

## At session start
1. Read `BRIEF.md` in full — goal, approach, two-day plan, what's deliberately not being built.
2. Read `knowledge.md` — chronological session log; last entry tells you where to pick up.
3. Read `errors.md` — known issues to avoid repeating.
4. Honor the strict rules in `~/.claude/CLAUDE.md` (project-agnostic global rules): lean code, tests with realistic input shape, no over-engineering, no unnecessary comments, ≤300 lines per Python module.

## During the session
- Update `knowledge.md` as decisions are made.
- Append to `errors.md` whenever something breaks — root cause + fix or workaround.
- After every implementation chunk, write a short review in `code_review/` (file per dated chunk).
- Run the relevant `pytest` files after each chunk; never claim work is done without running them.

## At session end
- Append a session entry to `knowledge.md` summarising what was done and what's next.

## Project-specific routing
- This is a 2-day work-trial submission. Scope ruthlessly.
- The agent under evaluation lives under `vendor/tau_bench/`. Treat it as read-only.
- `data/contract.json` is generated, not hand-written. If editing the policy or the generator, regenerate and commit.
