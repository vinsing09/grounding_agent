# grounding_agent

An evaluation framework for tool-calling LLM agents. Submission for the Meraki Labs Founding AI Engineer Work Trial (Problem Statement 4: Evaluation Framework from Scratch).

## What this evaluates

The τ-bench customer-support agent (airline domain). A handcrafted failure taxonomy defines six behavioral dimensions on which agent trajectories are scored. Semantic LLM judges plus a deterministic tool-sequence check produce per-dimension verdicts. τ-bench's programmatic reward serves as ground truth.

The framework runs the agent on 20 tasks (10 from the training distribution, 10 held out), compares the automated multi-dimensional score against τ-bench's reward, and surfaces the disagreements as failure analysis.

## Run

> This section is fleshed out as code lands. Clone-and-run will be verified end of Day 2.

```bash
cp .env.example .env                # add ANTHROPIC_API_KEY and OPENAI_API_KEY
pip install -e .
pytest                              # smoke
python scripts/run_eval.py          # full 20-task evaluation
python scripts/compare_to_reward.py # produce results/comparison.md
```

## Documents

- `WRITEUP.md` — methodology, results, failure analysis, production-at-100k. The PS4 thinking artifact.
- `BRIEF.md` — internal project brief and plan.
- `knowledge.md`, `errors.md` — chronological session and error logs.
- `code_review/` — per-implementation reviews.

## Attribution

The τ-bench customer-support agent (policy, tools, tasks, reward) under `vendor/tau_bench/` is from the τ-bench benchmark suite by Sierra Research. Vendored with attribution; this project does not claim authorship of that material.

## License

MIT — see `LICENSE`.
