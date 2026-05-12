# grounding_agent

> Submission for Meraki Labs Founding AI Engineer Work Trial, Problem
> Statement 4 — *Evaluation Framework from Scratch*. Two-day work
> trial, scope ruthless.

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

## How it works (one diagram, two paragraphs)

```
                                   policy.md + tools
                                          │
                       one LLM call ──────┼────►  data/contract.json
                                          │      (obligations / forbidden / tool_sequences,
                                          │       each tagged to one taxonomy category)
                                          ▼
                  ┌─────────────────  taxonomy ──────────────────┐
                  │   policy_compliance / confirmation_discipline │
                  │   information_grounding / scope_adherence     │
                  │   tool_sequence_correctness / task_completion │
                  └────────────────┬───────────────────┬──────────┘
                                   │                   │
                                   ▼                   ▼
        4 semantic LLM judges               1 deterministic tool-sequence checker
              ▲                                       ▲
              │     per-dimension verdicts            │
              │   {passed, reason, clause_refs}       │
              │                                       │
              ▼                                       ▼
        runner.py drives tau-bench agent;  evaluator.py aggregates;
        compare.py contrasts verdicts vs tau-bench's binary reward.
```

A six-category **failure taxonomy** is the load-bearing decision:
those six dimensions constrain the contract structure and the judge
prompts. The taxonomy is policy-agnostic — it captures structural
failure modes of *tool-using agents* (not "airline support agents").

The **contract** is generated from the policy in one LLM call rather
than hand-authored, so it cannot be tuned in our favour. Every clause
is tagged with a taxonomy category at generation time. Semantic
judges filter the contract by category and ask an LLM for a JSON
verdict; the deterministic judge walks the trajectory to check
prerequisite ordering.

The sixth category (`task_completion`) is intentionally **not** a
semantic judge: τ-bench's programmatic reward already measures end-to-
end completion, and running a separate LLM judge on the same
dimension would conflate evaluator noise with ground truth. That
category is observed via the comparison step in `compare.py`.

## What's deliberately not built

- Auto-generated test cases. τ-bench provides 20; we use them.
- Hand-labeling rubric. τ-bench's reward is reproducible programmatic ground truth.
- Optimization (audit / refine / synth). PS4 is eval, not improvement.
- A generic eval framework. Scoped to tool-calling agents with explicit goals.
- More than six taxonomy categories. Six well-justified beats eleven shallow.

See `WRITEUP.md` for the full set of trade-offs.

## Clone-and-run

```bash
git clone https://github.com/vinsing09/grounding_agent.git
cd grounding_agent

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# add OPENAI_API_KEY=... (ANTHROPIC_API_KEY optional)

# (1) sanity: tests pass on a clean checkout
pytest

# (2) generate the contract (one LLM call against vendored policy.md)
python scripts/generate_contract.py        # writes data/contract.json

# (3) end-to-end smoke on tasks 0 + 1
python scripts/smoke_test.py

# (4) full eval (20 tasks × 2 variants ≈ 80 min, ~$0.40 in tokens)
python scripts/run_eval.py                  # writes results/{v0,v2}_results.json

# (5) auto-eval vs τ-bench reward, with disagreement examples
python scripts/compare_to_reward.py         # writes results/comparison.md
```

The eval is **idempotent per task** — each completed task is cached
in the variant's results JSON, so re-runs only re-execute missing or
`--force`'d tasks.

## Repo layout

```
grounding_agent/
├── BRIEF.md                          # cold-start project context
├── WRITEUP.md                        # methodology, results, failure analysis (PS4 thinking artifact)
├── knowledge.md                      # chronological session log
├── errors.md                         # chronological error log
├── code_review/                      # per-implementation review docs
├── pyproject.toml
├── grounding_agent/
│   ├── taxonomy.py                   # six FailureCategory dataclasses
│   ├── contract.py                   # validator + generator + io
│   ├── judges.py                     # 4 semantic + 1 deterministic
│   ├── runner.py                     # drives tau-bench agent
│   ├── evaluator.py                  # applies judges to trajectory
│   └── compare.py                    # confusion / clause-citation / disagreements
├── vendor/tau_bench_airline/         # policy.md, license, tool catalog
├── data/
│   ├── contract.json                 # generated, committed
│   ├── tasks.json                    # train (0–9) + held_out (10–19) indices
│   └── variants/v2_preamble.md       # prompt-discipline preamble for v2
├── scripts/
│   ├── generate_contract.py
│   ├── smoke_test.py
│   ├── run_eval.py
│   └── compare_to_reward.py
├── results/
│   ├── v0_results.json               # produced by run_eval.py
│   ├── v2_results.json
│   └── comparison.md                 # produced by compare_to_reward.py
└── tests/                            # 66 tests
    ├── test_taxonomy.py
    ├── test_contract.py
    ├── test_judges.py
    ├── test_evaluator.py
    ├── test_runner.py
    └── test_compare.py
```

## Attribution

τ-bench (`tau_bench` on PyPI / [GitHub](https://github.com/sierra-research/tau-bench))
is the work of Sierra Research, released under the MIT License. The
policy text in `vendor/tau_bench_airline/policy.md` and the test tasks
loaded via the pip dependency are unmodified excerpts of that
project.

Citation: Yao et al., 2024. *τ-bench: A Benchmark for Tool-Agent-User
Interaction in Real-World Domains.*

`grounding_agent` is independent work that uses τ-bench as the
system-under-test and ground-truth source.

## License

MIT. See `LICENSE`.
