# grounding_agent — project brief

Cold-start context. Personal project; submission for Meraki Labs
Founding AI Engineer Work Trial, Problem Statement 4 (Evaluation
Framework from Scratch).

## Goal

Build an evaluation framework for **tool-calling LLM agents** that
goes beyond a single pass/fail score. The framework should explain
*why* an agent failed across a small set of structurally-meaningful
dimensions, and it should surface those reasons in a way a human
reviewer can act on (fix the prompt, fix the policy, fix the agent).

## Approach in one paragraph

A seven-category failure taxonomy defines the dimensions on which
agents are evaluated. For each agent under test, a contract is
generated from its policy and tool catalog (one LLM call → JSON of
obligations + forbidden behaviors + tool sequences, each clause
tagged to a taxonomy category). Six judges — three semantic LLM
judges, three deterministic Python checks — score every trajectory
along the seven dimensions. The framework is evaluated against the
[τ³-bench](https://github.com/sierra-research/tau2-bench) airline
customer-support agent across 20 tasks (10 development + 10
held-out). τ³-bench's programmatic reward is the ground truth; the
framework's per-dimension verdicts are compared against it, and the
disagreements are the failure analysis.

## Why this approach

- **The taxonomy is the load-bearing decision.** It constrains what
  dimensions exist, what the contract structure looks like, and what
  each judge prompt asks. Generic LLM-as-judge picks dimensions
  arbitrarily; ours is grounded in the structural failure modes of
  tool-using agents.
- **Deterministic + semantic, not just semantic.** Tool-call ordering,
  argument validity, and per-mutation confirmation are mechanically
  observable; Python checks are cheaper, faster, and more reliable
  than LLM judges for those. LLM judges are reserved for genuinely
  subjective dimensions (policy spirit, scope decisions, factual
  grounding).
- **External ground truth.** τ³-bench's reward function is
  programmatic and authored by independent researchers — removes the
  candidate-marks-own-homework problem.
- **Held-out is the key signal.** Most eval frameworks measure on
  the distribution the system was tuned on. The held-out slice tests
  whether per-dimension scores reflect generalization or fit-to-the-
  pilot.

## Agent under test

τ³-bench customer-support (airline domain). Loaded via the
`tau2` Python package from
[sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench)
(which hosts the τ³-bench release). Policy text mirrored at
`vendor/tau_bench_airline/policy.md`.

## What's in scope

1. `taxonomy.py` — seven failure categories with descriptions,
   examples, judge-kind metadata.
2. `contract.py` — one-LLM-call generator + validator + io for
   `data/contract.json`.
3. `judges.py` — three semantic judges + three deterministic
   checks; uniform signature; `JudgeResult` with optional continuous
   `score` field.
4. `runner.py` — drives the τ³-bench agent through one task,
   captures trajectory + termination + tool errors.
5. `evaluator.py` — applies all judges, returns per-category
   verdicts.
6. `compare.py` — confusion matrices, per-clause citation counts,
   disagreement examples, reward-kind decomposition.
7. `eventlog.py` — JSON-Lines event log for forensic replay.

## What's out of scope

- Auto-generated test cases. τ³-bench provides 50; we use 20.
- Hand-labeled rubrics. Reward function is the ground truth.
- Optimization loops (audit/refine/synth). PS4 is eval, not
  improvement.
- A generic eval framework that handles any agent. Scoped to
  tool-calling agents with explicit goals and a written policy.
- More than seven taxonomy categories.

## Target layout (final)

```
grounding_agent/
├── README.md
├── WRITEUP.md
├── BRIEF.md                           # this file
├── PRESENTATION.md / PRESENTATION.pdf
├── knowledge.md, errors.md            # chronological logs
├── code_review/                       # per-implementation reviews
├── pyproject.toml
├── grounding_agent/
│   ├── taxonomy.py                    # 179 lines
│   ├── contract.py                    # 265 lines
│   ├── judges/                        # package: 4 files, each ≤ 233 lines
│   │   ├── __init__.py                # public surface + ALL_JUDGES tuple
│   │   ├── _common.py                 # JudgeResult, helpers
│   │   ├── _deterministic.py          # 3 deterministic checks
│   │   └── _semantic.py               # 3 LLM judges + prompt builder
│   ├── runner.py                      # τ³-bench port; 338 lines (see code_review/)
│   ├── evaluator.py                   # 69 lines
│   ├── compare.py                     # 398 lines (see code_review/)
│   └── eventlog.py                    # 103 lines
├── vendor/tau_bench_airline/          # mirrored policy.md, license
├── data/
│   ├── contract.json                  # generated
│   ├── tasks.json                     # τ³-bench's canonical split (10 + 10)
│   └── variants/v2_preamble.md
├── scripts/
│   ├── generate_contract.py
│   ├── smoke_test.py
│   ├── run_eval.py                    # supports --judge-only
│   └── compare_to_reward.py
├── results/                           # comparison.md, forensics_*.md,
│                                      # eventlog under results/logs/<run_id>/
└── tests/                             # 125 passing tests
```

## Strict rules

- Each Python module ≤ 300 lines.
- Tests for every module. Test fixtures use real τ³-bench message
  shapes, not toy data.
- Comments only when a non-obvious WHY needs preserving.
- `knowledge.md` and `errors.md` updated chronologically every
  session.
- After each implementation chunk, write a short review in
  `code_review/`.
- No over-engineering. Cut dimensions or judges that aren't paying
  off.

## What "done" looks like

- `pytest` passes from a clean checkout.
- `scripts/run_eval.py` reproduces v0 and v2 results from cache or
  re-runs them.
- `results/comparison.md` shows per-dimension confusion matrices vs
  τ³-bench reward, with disagreement examples.
- `WRITEUP.md` reads cleanly in 15 minutes and answers the PS4
  deliverables.
- `PRESENTATION.pdf` is the 5-minute walkthrough.
- Repo clones and runs without manual intervention beyond `.env`
  setup.

## Status

All scope items shipped. Three forensic iterations recorded under
the original τ-bench; the framework was then migrated to τ³-bench
and another three forensic iterations performed under the corrected
benchmark. Final results in `results/comparison.md` and
`results/forensics_tau3_v3.md`.
