# grounding_agent — writeup

> Submission for Meraki Labs Founding AI Engineer Work Trial, Problem
> Statement 4 — *Evaluation Framework from Scratch*.
> Author: vineet@digitalgreen.org. Two-day work-trial.

## TL;DR

`grounding_agent` is an evaluation framework for tool-calling LLM
agents that produces per-dimension, structurally-grounded verdicts on
every trajectory. It is evaluated against the τ-bench airline customer-
support agent on 20 tasks (10 in the training distribution, 10 held
out) under two prompt variants. τ-bench's programmatic reward is the
ground truth; the framework's multi-dimensional auto-eval is
compared against it. **The disagreements are the result.**

Headline numbers are in §3 and `results/comparison.md`.

---

## 1. The dimensions

A six-category failure taxonomy is the load-bearing design decision.
It constrains what the contract structure looks like and what each
judge prompt asks. **Each category is grounded in a structural failure
mode of tool-using agents** — not in a vibe-list. See
`grounding_agent/taxonomy.py` (one frozen dataclass per category, with
an `id`, `description`, `judge_dimension`, `judge_kind` ∈ `{semantic,
deterministic}`, and an `example`).

| Category | Failure mode | Judge kind | Maps to which policy clauses |
|---|---|---|---|
| `policy_compliance` | Agent permits or recommends an action the policy forbids, or denies an in-scope action. | semantic | Business rules: basic-economy mod ban, refund eligibility, payment-method limits, "deny user requests against policy". |
| `confirmation_discipline` | Mutation without explicit user "yes" beforehand. | semantic | "Before any actions that update the booking database… obtain explicit user confirmation (yes) to proceed." |
| `information_grounding` | Factual claims that don't trace to a user turn or tool output. | semantic | "Should not provide any information, knowledge, or procedures not provided by the user or available tools." |
| `scope_adherence` | Transfer-on-in-scope, or attempting an out-of-scope task. | semantic | "Transfer to a human agent if and only if the request cannot be handled within the scope of your actions." |
| `tool_sequence_correctness` | A mutation called without its prerequisite read (e.g., `get_user_details` before `book_reservation`). | **deterministic** | "Only one tool call at a time" + all prerequisite-read patterns. |
| `task_completion` | Agent abandons, loops, or finishes the wrong task. | **observed via τ-bench reward** | (Implicit; ground truth) |

### Why these six (and not eleven)

`knowledge.md` records the trim from a longer first-draft taxonomy.
Categories cut included `hallucination`, `refusal_quality`, and
`instruction_adherence` — each collapses cleanly into one of the six
above (`information_grounding`, `scope_adherence`,
`policy_compliance`). Six well-justified dimensions beat eleven
shallow ones in a 20-minute review.

### Why 4 semantic + 1 deterministic + 1 reward-tracked

- Tool-sequence prerequisites are a **mechanical** check (`<` over
  positions of named tool calls in a trajectory). A semantic judge
  here would burn tokens to do something a loop does for free.
- `task_completion` is *defined* by τ-bench's binary reward in this
  setup. Running a separate semantic judge over the same dimension
  would conflate evaluator noise with the very signal we're treating
  as ground truth. Tracked, but not judged.

---

## 2. Methodology

```
policy.md + tools ──[one LLM call]── data/contract.json ──[5 judges]── per-dim verdicts
                                                                              │
                                  τ-bench reward (ground truth) ──[compare]───┘
```

### 2.1 Agent under test
τ-bench airline customer-support (Sierra Research, MIT-licensed). 14
tools, 50 test tasks. Reward = binary 1.0/0.0 on (final DB state +
executed actions) match. We use tasks 0–9 (train) and 10–19 (held
out).

### 2.2 Contract generation, not curation
`scripts/generate_contract.py` makes one LLM call (`gpt-4o-mini`,
`response_format=json_object`) against `vendor/tau_bench_airline/policy.md`
+ the 14-tool catalog. Output: 11 obligations + 7 forbidden behaviors
+ 3 tool_sequences, each tagged to one taxonomy category, committed
as `data/contract.json`. The validator rejects unknown categories,
duplicate clause ids, missing fields, and malformed prerequisites at
save and load time.

**Why generated, not hand-curated**: removes the
"candidate-curated-favourable-clauses" critique; gains reproducibility;
introduces tagging noise that becomes a data point of its own (§4.2).

### 2.3 Judges
Four semantic judges, one per applicable category. Each:
1. Filters the contract for clauses tagged to its category;
2. Renders the trajectory (role-tagged, system-message stripped);
3. Calls litellm with `response_format=json_object`, asking for
   `{passed, reason, violated_clause_ids}`;
4. Returns a `JudgeResult(category, passed, reason, clause_refs)`.

The deterministic checker walks the trajectory once, building
`name → [positions]`, and for each `tool_sequence` clause confirms
every prerequisite appears before the target. Vacuously passes if no
target is observed.

### 2.4 Prompt variants
- **v0** — `tau_bench.envs.airline.wiki.WIKI` as-is (the policy.md
  the upstream benchmark ships).
- **v2** — `data/variants/v2_preamble.md` + v0. The preamble adds
  three explicit rules (mutation confirmation, read-before-write,
  ground-from-tool-output). Same policy, more emphasis on the
  dimensions gpt-4o-mini under-applied in the smoke run.

The hypothesis tested: does emphasizing the dimensions move the
per-dimension scores in the expected direction *on held-out*? If
yes, the dimensions are diagnostic. If only on train, the eval is
over-tuned to the smoke set.

### 2.5 Reproducibility
- Tasks: explicit indices in `data/tasks.json`.
- Contract: regenerated by `scripts/generate_contract.py` and
  committed.
- Models: defaults are gpt-4o-mini for agent / user-sim / judges —
  overridable on the CLI.
- Per-task results cached in JSON. `--force` forces re-runs.
- 66 tests pass on a clean checkout (`pytest`).

---

## 3. Results

> Final tables produced from `results/comparison.md`. Re-running
> `scripts/compare_to_reward.py` after any rerun of `run_eval.py`
> regenerates this section.

### 3.1 Variant overview

<!-- AUTO: overview table -->
_See `results/comparison.md` § Variant overview._

### 3.2 Per-dimension pass rate (train / held-out / all)

<!-- AUTO: pass-rate-by-split tables for v0 and v2 -->
_See `results/comparison.md` § Per-dimension pass rate._

### 3.3 Per-dimension confusion matrix (vs τ-bench reward)

Cells per dimension: **TP** (auto pass & reward pass) · **FP** (auto
pass, reward fail — the eval missed a real failure) · **TN** (auto
fail, reward fail — eval agreed with reward) · **FN** (auto fail,
reward pass — eval over-strict).

<!-- AUTO: confusion matrix tables for v0 and v2 -->
_See `results/comparison.md` § Confusion matrix per dimension._

### 3.4 Held-out angle

The single most informative comparison: does the framework score the
held-out slice the same way it scores the train slice?

Two questions:
1. Does the **deterministic** checker behave consistently on held
   out? It should — it's not learned, so any drift would point at a
   distribution shift in *what tools the agent calls*, not eval
   quality.
2. Do the **semantic** judges' over-strictness patterns persist on
   held-out? If yes, the disagreements are about judge calibration,
   not about over-fitting to the train tasks.

<!-- AUTO: held-out commentary, populated from comparison numbers -->
_See `results/comparison.md`._

### 3.5 Disagreement examples

The disagreements are the result. Selected FP (eval missed a failure)
and FN (eval over-strict) cases in `results/comparison.md` §
Disagreement examples.

---

## 4. Failure analysis

The framework's failures decompose into three classes. Each is
diagnostic of a different thing.

### 4.1 Judge over-strictness (FN: auto fail, reward pass)

When the semantic judge is asked to list violated clauses against a
long obligation list, gpt-4o-mini tends to find one. This produces
FN dimension verdicts on tasks the agent completed correctly. The
WRITEUP's `4.1` row in the disagreement table flags every such case;
their concentration in `policy_compliance` (the category with the
most clauses) is itself the signal.

**Implication**: the judge-model choice is a knob. The framework's
correctness does not depend on gpt-4o-mini being a great judge — it
depends on the framework producing structured, debuggable output. The
fix is mechanical (switch to gpt-4o; or score with a "majority of
three judges"; or restrict each judge's clause set to the top-N most
load-bearing).

### 4.2 Contract mistagging (manifests as cross-dimension FP/FN)

The generator placed several business-rule prohibitions
(`fb-modify-basic-economy`, `fb-cancel-flights-after-use`, etc.) into
`scope_adherence` rather than `policy_compliance`. Effect: those
clauses' violations show up as scope-adherence failures, and a
correct cancellation can produce a polarity error (judge reads the
clause without state-context and says "yes, this was violated"
because the cancellation happened, ignoring whether the segment had
been used).

**Implication**: this is the **honest cost of generated contracts**.
It is exactly the trade-off we accepted to avoid "candidate-curated
favourable clauses." For production, the fix is to regenerate with
a stricter category-definition prompt or to add a one-pass
human-in-the-loop tagging review before committing the contract.

### 4.3 Reward blind spots (FP: auto pass, reward fail)

When the eval marks a task pass on every dimension but tau-bench
gives 0.0, one of two things is true: the agent took an action that
matters to the gold trajectory but to none of our dimensions, or our
contract missed a relevant rule. Both are interesting. The first is
a *coverage* result: our dimensions don't cover everything τ-bench
checks (e.g., exact payment-method ordering inside a successful
booking). The second is a *contract-quality* result.

---

## 5. Production at 100k users/day

(Reasoning here is independent of the airline domain — these are the
operational realities of running this kind of multi-dimensional eval
at scale.)

### 5.1 Cost
Per-trajectory cost at the demo scale: ~$0.005 agent + ~$0.005
user-sim + ~$0.005 across the four semantic judges = **~$0.015 per
trajectory** with gpt-4o-mini. At 100k/day that's ~$1500/day
fully-judged.

Reducing cost without losing signal:
- **Sample**: judge 1–5% of trajectories, not all. The framework
  produces structured per-dimension results; downstream dashboards
  aggregate across samples.
- **Tier the judges**: deterministic tool-sequence check on 100% of
  trajectories (it's free); semantic judges on the sample.
- **Cache**: deduplicate trajectories that lead to identical
  evaluator inputs (rare in practice, but available).
- **Choose the judge model by stakes**: gpt-4o-mini for sampled
  inspection; gpt-4o for arbitration on flagged trajectories.

### 5.2 Latency
The eval is offline-by-design. Production agents don't wait for the
judges. Trajectories are emitted to a queue; the evaluator drains it
asynchronously. The runner here is single-process and sequential;
under load it becomes `asyncio` over litellm calls — the judge
functions are already side-effect-free `(messages, contract, model)
→ JudgeResult`, so concurrency is just spawning a task per dimension
per trajectory.

### 5.3 Reliability
- **Contract is the schema-controlled artifact** the rest of the
  system reads from. Validation is run on save and on load; an
  unparseable / mistagged contract cannot be silently picked up.
- **Errored tasks are recorded, not crashed.** `run_eval.py` writes
  `{error: "..."}` records and continues. Comparison aggregates
  exclude them but the count is surfaced in the writeup.
- **Idempotent per task.** A re-run from a partial state picks up
  where it left off; no double-charging.

### 5.4 What breaks at scale (and what doesn't)
- Doesn't break: the taxonomy, contract schema, deterministic
  checker, validation gates, per-task caching.
- Breaks: gpt-4o-mini judges if you trust them as binary verdicts
  rather than as flags-for-review. At 100k/day you'd see ~thousands
  of FN-by-over-strictness daily. **Treat judge verdicts as triage
  signal, not as final-verdict.**
- Needs work: the contract gets stale when the policy changes.
  Regeneration is one LLM call; the harder part is migrating
  historical results indexed by old clause ids. Recommendation:
  version the contract (`agent: "tau_bench_airline@<sha>"`) and
  store the resolved contract id on every result row.

---

## 6. What I chose not to build

- **An eleventh judge category.** Six dimensions, each cited to a
  policy clause. Eleven shallow categories would have been a
  reviewer-hostile choice.
- **Hand-curated obligations.** The generator-based contract has known
  mistagging cost (§4.2); the trade-off is reproducibility and the
  removal of "candidate curated favourable clauses" critique.
- **A separate `task_completion` semantic judge.** τ-bench's reward
  already measures the same dimension programmatically. A second
  semantic judge over the same signal would conflate noise with
  ground truth.
- **An optimization loop.** PS4 is the eval, not the improvement.
  Optimization is a downstream user of the framework; building both
  in two days would have meant doing both badly.
- **Multi-trial averaging.** Each task is run once per variant. With
  binary rewards, single-trial agreement is the cleanest comparison.
  Adding multi-trial would have multiplied cost without adding
  resolution at this N.
- **Async / parallel judge orchestration.** Single-process synchronous
  was enough at N=40. Parallel orchestration is a 30-minute change to
  `evaluator.py` (the judges are already pure functions); deliberately
  deferred.
- **Active prompt-tuning of the judges.** Out of scope; this is what
  Day 3 would have been.
- **A web UI / dashboard.** Markdown + JSON outputs are sufficient for
  a 20-minute reviewer walkthrough.

---

## Appendix A — what's in the repo

See `README.md` § Repo layout for the file tree. Notably:

- `code_review/2026-05-12-{taxonomy, contract, judges-runner-evaluator,
  compare}.md` — per-implementation reviews. Each module's design,
  reconciliation with the BRIEF, lean-code accounting, test-rigor
  notes, and risks-flagged.
- `knowledge.md`, `errors.md` — chronological logs. The error log
  contains the one issue that actually broke during the build (the
  contract-generator prompt was too loose; fixed by adding an
  explicit schema-by-example).
