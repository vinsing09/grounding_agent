# grounding_agent

> Submission for Meraki Labs Founding AI Engineer Work Trial, Problem
> Statement 4 — *Evaluation Framework from Scratch*.

## What this is

An evaluation framework for **tool-calling LLM agents** that produces
per-dimension, structurally-grounded verdicts on every trajectory —
not a single vibe-check score.

The framework is evaluated against the [τ-bench](https://github.com/sierra-research/tau-bench)
customer-support agent in the airline domain. τ-bench's programmatic
reward function is the ground truth; the framework's multi-dimensional
auto-eval is compared against it across 20 tasks (10 training-
distribution + 10 held-out) under two prompt variants. The
disagreements between auto-eval and reward are the failure analysis.

**Three iterations on the framework** were performed forensically:
each iteration's findings were bucketed, fixes implemented, and
the results re-mined. Full history in `results/forensics{,_v2,_v3}.md`.

## How it works (one diagram)

```
                              policy.md + tools
                                      │
                   one LLM call ──────┼────►  data/contract.json
                                      │      (obligations / forbidden /
                                      │       tool_sequences, each
                                      │       tagged to a taxonomy
                                      │       category)
                                      ▼
              ┌────────────────  7-category taxonomy  ─────────────────┐
              │ policy_compliance · confirmation_discipline · scope_… │
              │ information_grounding · tool_sequence_correctness ·   │
              │ tool_argument_correctness · task_completion           │
              └────────────┬───────────────────────┬───────────────────┘
                           │                       │
                           ▼                       ▼
              3 semantic LLM judges       3 deterministic Python checks
                      ▲                                ▲
                      │   per-dim verdicts             │
                      │   {passed, reason, score,      │
                      │    clause_refs}                │
                      ▼                                ▼
       runner.py drives tau-bench agent (captures trajectory +
       termination kind + tool errors) → evaluator.py applies all
       six judges → compare.py contrasts verdicts vs tau-bench's
       binary reward → JSON-Lines event log replayable for forensics.
```

A **7-category failure taxonomy** is the load-bearing decision. The
taxonomy is policy-agnostic — it captures structural failure modes
of *tool-using agents*, not "airline support agents."

The **contract** is generated from the policy in one LLM call rather
than hand-authored — no opportunity to curate favourable obligations.
Every clause is tagged to a taxonomy category at generation time. A
validator gates save and load.

**Six judges, two kinds**:

- **3 semantic LLM judges**: `policy_compliance`,
  `information_grounding`, `scope_adherence`. Each receives an
  "AGENT ACTIONS" block first (excluding user turns) then the full
  trajectory for context, with explicit ground rules ("only the
  agent can violate; a user's request is never itself a violation").
- **3 deterministic Python checks**: `confirmation_discipline`
  (per-mutation user-yes with negation-aware detection),
  `tool_sequence_correctness` (prerequisite-read ordering),
  `tool_argument_correctness` (tool-server `Error: …` responses).

The 7th category, `task_completion`, is intentionally **not** judged
— τ-bench's programmatic reward already measures it; a separate LLM
judge would conflate evaluator noise with ground truth. Observed via
`compare.py`.

## Headline results (final iteration)

- v0 reward 10% (2/20). v2 reward 10% (2/20).
- v2 had **2× the booking attempts** of v0 (39 vs 13 `book_reservation`
  calls) and **34 tool-side errors** vs v0's 16. The "execution
  discipline" preamble in v2 made the agent more action-oriented,
  not more cautious.
- **`confirmation_discipline`** moved from 0% pass-rate under an LLM
  judge to 65% pass-rate as a deterministic check (Bucket A).
- **Task 15** (refuse-and-transfer, the canonical Bucket B test case):
  went from 0/5 PASS in iter-1 to 6/6 PASS in iter-2 because
  semantic judges no longer anchor on user requests.
- Most-cited mistagged clause (`fb-modify-basic-economy`) dropped
  9 → 5 citations after iter-3 contract regeneration. Reaching zero
  needs a human-in-the-loop tag review.

Full numbers in `results/comparison.md` and the per-iteration
forensics docs.

## What's deliberately not built

- Auto-generated test cases. τ-bench provides 20; we use them.
- Hand-labeling rubric. τ-bench's reward is reproducible programmatic ground truth.
- Optimization (audit / refine / synth). PS4 is eval, not improvement.
- A generic eval framework. Scoped to tool-calling agents with explicit goals.
- More than seven taxonomy categories.

See `WRITEUP.md` and `PRESENTATION.md` for the full set of
trade-offs and the "way forward" section.

## Clone-and-run

```bash
git clone https://github.com/vinsing09/grounding_agent.git
cd grounding_agent

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# add OPENAI_API_KEY=...

# (1) sanity: 120 tests pass on a clean checkout
pytest

# (2) generate the contract (one LLM call against vendored policy.md)
python scripts/generate_contract.py        # writes data/contract.json

# (3) end-to-end smoke on tasks 0 + 1
python scripts/smoke_test.py

# (4) full eval (20 tasks × 2 variants ≈ 30 min, ~$0.30 in tokens)
python scripts/run_eval.py                  # writes results/{v0,v2}_results.json
                                            # plus results/logs/<run_id>/<variant>.jsonl

# (4a) optional: re-judge cached trajectories under a fresh contract
python scripts/run_eval.py --judge-only

# (5) auto-eval vs τ-bench reward, with disagreement examples
python scripts/compare_to_reward.py         # writes results/comparison.md
```

The eval is **idempotent per task** — each completed task is cached
in the variant's results JSON, so re-runs only re-execute missing or
`--force`'d tasks. `--judge-only` reuses cached trajectories and runs
only the judges — useful after regenerating the contract.

## Repo layout

```
grounding_agent/
├── BRIEF.md                          # cold-start project context
├── WRITEUP.md                        # methodology, results, failure
│                                     # analysis, production-at-100k
├── PRESENTATION.md                   # 5-minute narrative walkthrough
├── knowledge.md                      # chronological session log
├── errors.md                         # chronological error log
├── code_review/                      # per-implementation reviews
├── pyproject.toml
├── grounding_agent/
│   ├── taxonomy.py                   # 7 FailureCategory dataclasses
│   ├── contract.py                   # validator + LLM generator + io
│   ├── judges.py                     # 3 semantic + 3 deterministic
│   ├── runner.py                     # drives tau-bench; termination
│   │                                 # classification; tool-error extraction
│   ├── evaluator.py                  # applies judges to trajectory
│   ├── compare.py                    # confusion / clause counts /
│   │                                 # disagreements / reward-kind /
│   │                                 # termination-kind breakdowns
│   └── eventlog.py                   # JSON-Lines event log
├── vendor/tau_bench_airline/         # policy.md, license, tool catalog
├── data/
│   ├── contract.json                 # generated, committed (iter-3 prompt)
│   ├── contract.iter2.json           # backup of pre-iter-3 contract
│   ├── tasks.json                    # train (0–9) + held_out (10–19)
│   └── variants/v2_preamble.md       # v2's discipline preamble
├── scripts/
│   ├── generate_contract.py
│   ├── smoke_test.py
│   ├── run_eval.py                   # supports --judge-only
│   └── compare_to_reward.py
├── results/
│   ├── v0_results.json               # iter-3 verdicts on iter-2 trajectories
│   ├── v2_results.json               # iter-3 verdicts on iter-2 trajectories
│   ├── v0_results.iter2.json         # iter-2 verdicts (pre-iter-3 contract)
│   ├── v2_results.iter2.json
│   ├── v0_results.pre.json           # iter-1 (pre-bucket-fix) verdicts
│   ├── v2_results.pre.json
│   ├── comparison.md                 # iter-3 rendered comparison
│   ├── comparison.iter2.md
│   ├── comparison.pre.md
│   ├── forensics.md                  # forensics pass 1 (six findings)
│   ├── forensics_v2.md               # pass 2 (bucket fixes verified)
│   ├── forensics_v3.md               # pass 3 (contract retag)
│   └── logs/                         # results/logs/<run_id>/<variant>.jsonl
└── tests/                            # 120 tests
    ├── test_taxonomy.py
    ├── test_contract.py
    ├── test_judges.py
    ├── test_evaluator.py
    ├── test_runner.py
    ├── test_compare.py
    └── test_eventlog.py
```

## Forensic iteration workflow

The framework was hardened forensically — three rounds of:

1. **Run eval** → trajectories + verdicts persisted.
2. **Mine the data** → findings reported in `forensics{,_v2,_v3}.md`.
3. **Bucketize findings** by issue class (misclassified judge,
   wrong input shape, missing dimension, reporting/visibility).
4. **Implement fixes**, with tests proving each invariant.
5. **Re-run** (or re-judge with `--judge-only`) and repeat.

Each iteration's artifacts are preserved (`.pre.json`, `.iter2.json`,
current), so the trajectory of improvement is auditable end-to-end.
The JSON-Lines event log at `results/logs/<run_id>/<variant>.jsonl`
makes per-event timing and verdicts replayable.

## Attribution

τ-bench (`tau_bench` on PyPI / [GitHub](https://github.com/sierra-research/tau-bench))
is the work of Sierra Research, released under the MIT License. The
policy text in `vendor/tau_bench_airline/policy.md` and the test tasks
loaded via the pip dependency are unmodified excerpts of that project.

Citation: Yao et al., 2024. *τ-bench: A Benchmark for Tool-Agent-User
Interaction in Real-World Domains.*

`grounding_agent` is independent work that uses τ-bench as the
system-under-test and ground-truth source.

## License

MIT. See `LICENSE`.
