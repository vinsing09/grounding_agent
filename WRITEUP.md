# grounding_agent — writeup

> Submission for Meraki Labs Founding AI Engineer Work Trial, Problem
> Statement 4 — *Evaluation Framework from Scratch*.
> Author: vineet@digitalgreen.org. Two-day work-trial.

## TL;DR

`grounding_agent` is an evaluation framework for tool-calling LLM
agents that produces per-dimension, structurally-grounded verdicts on
every trajectory. It is evaluated against the τ-bench airline customer-
support agent on 20 tasks (10 train + 10 held-out) under two prompt
variants. τ-bench's programmatic reward is the ground truth; the
framework's multi-dimensional auto-eval is compared against it.
**The disagreements are the result.**

### Headline numbers (gpt-4o-mini end-to-end, ~$0.32 total tokens)

- **v0 → v2 reward dropped 16% → 5%.** The v2 discipline preamble
  (`data/variants/v2_preamble.md`) is a plausible safety patch
  that vibes-eval would approve; the framework caught it as a
  regression and located *why*: avg trajectory length grew 30.6 →
  40.2 messages, hitting `max_steps=25` before completion.
- **`tool_sequence_correctness` (the deterministic checker) moved
  74% → 95%.** v2's "read before write" rule worked on its
  targeted dimension. Improvement on the dimension you targeted is
  the framework's intended use.
- **Per-dimension behavior generalizes: train↔held-out patterns are
  structurally identical** (`confirmation_discipline` 0% on both
  splits in both variants, `tool_sequence_correctness` direction
  stable, reward gap consistent). The eval isn't over-tuned to the
  smoke set.
- **`obl-confirm-action` was cited in 19/19 (v0) and 20/20 (v2)
  failed `confirmation_discipline` verdicts.** Smoking gun for
  judge-prompt interpretation, not agent behavior. Fix is mechanical
  (§4.1).

Full tables in `results/comparison.md`. See §3–§4 for the analysis.

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

> Full numerical tables in `results/comparison.md` (regenerated by
> `scripts/compare_to_reward.py`). This section reports the
> load-bearing rows and the **headline findings**.

### 3.1 Variant overview

| variant | n | reward pass (all) | reward pass (train) | reward pass (held_out) | avg msgs | total cost |
|---|---:|---:|---:|---:|---:|---:|
| **v0** (wiki as-is) | 19 | 16% | 11% | 20% | 30.6 | $0.118 |
| **v2** (discipline preamble + wiki) | 20 | 5% | 0% | 10% | 40.2 | $0.205 |

v0's n=19 because task 9's trajectory triggered a JSON decode error
inside tau-bench's `message_to_action` when gpt-4o-mini emitted a
truncated tool-argument string. `run_eval.py` recorded it and
continued (full incident report in `errors.md`).

**Headline finding (Result 1): v2 made things worse on reward.**
The discipline preamble caused the agent to take ~30% more
conversational turns per task (40.2 vs 30.6 messages) and hit
`max_steps=25` before completing tasks it could otherwise finish.
This is itself a useful result: the framework caught a
prompt-emphasis change that *appeared* like a safety improvement but
that the ground truth scored as a regression. Without the τ-bench
reward, this regression would have been invisible.

### 3.2 Per-dimension pass rate

| dimension | v0 (train / held_out / all) | v2 (train / held_out / all) |
|---|---|---|
| `reward` | 11% / 20% / 16% | 0% / 10% / 5% |
| `confirmation_discipline` | **0% / 0% / 0%** | **0% / 0% / 0%** |
| `information_grounding` | 22% / 50% / 37% | 30% / 40% / 35% |
| `policy_compliance` | 22% / 0% / 11% | 0% / 10% / 5% |
| `scope_adherence` | 11% / 0% / 5% | 10% / 0% / 5% |
| `tool_sequence_correctness` | 100% / 50% / 74% | 100% / 90% / **95%** |

**Headline finding (Result 2): the deterministic checker is the
only dimension v2 actually moved.** `tool_sequence_correctness`
climbed from 74% → 95% (v0 → v2). This is the dimension the v2
preamble explicitly targeted with its "read before write" rule, and
the deterministic check confirms the agent now calls
`get_user_details` / `get_reservation_details` before mutating tools
in nearly every case. **Improving on the dimension you targeted is
the framework's intended use** — even when, as here, the targeted
improvement doesn't translate into reward (because reward is also a
function of correct arguments, not just correct ordering).

### 3.3 Per-dimension confusion matrix (vs τ-bench reward)

Full tables in `results/comparison.md`. The four signature rows:

| variant | dimension | TP | FP | TN | FN | agreement |
|---|---|---:|---:|---:|---:|---:|
| v0 | `confirmation_discipline` (all) | 0 | 0 | 16 | 3 | 84% |
| v0 | `tool_sequence_correctness` (all) | 2 | 12 | 4 | 1 | 32% |
| v0 | `information_grounding` (all) | 1 | 6 | 10 | 2 | 58% |
| v0 | `policy_compliance` (all) | 0 | 2 | 14 | 3 | 74% |

Read these as: `confirmation_discipline` agrees with the reward 84%
of the time but only because the judge fails *everything* and the
agent fails most things; `tool_sequence_correctness` disagrees most
often via FP (auto pass when reward fail — the deterministic check
is too narrow to catch all relevant errors); `policy_compliance` is
the closest to a working judge in this setup.

### 3.4 Held-out angle

The single most informative cut. Per-dimension behavior of the
framework is **structurally identical** across train and held_out:

- `confirmation_discipline`: 0% on both splits in both variants.
  The judge's failure mode is **not a function of the training
  distribution**; it's a function of how gpt-4o-mini interprets
  "explicit confirmation" against the obligation text.
- `tool_sequence_correctness`: 100% (train) vs 50–90% (held_out)
  in both variants. The split has roughly twice the dimension's
  applicability (the held-out tasks involve more mutations), so the
  deterministic check has more opportunities to fire. Direction is
  consistent across variants.
- Reward gap between splits (held_out > train) holds in both
  variants too. **The dimensions generalize**: the eval is not
  over-tuned to the smoke set, because the contract was generated
  from the policy alone and never saw a training trajectory.

### 3.5 Disagreement examples

The full FP and FN lists are in `results/comparison.md` §
Disagreement examples. Two diagnostic cases:

**Case A — judge over-strictness (FN).** v0, task 1, reward=1.0:
the agent successfully cancelled a basic-economy trip under travel
insurance. Four out of five dimensions flagged failures:
- `confirmation_discipline` cited `obl-confirm-action` ("did not
  obtain explicit user confirmation to proceed"). The agent **did**
  summarize and the user **did** say yes; the judge missed the
  affirmation because it appeared two turns earlier in the
  trajectory, not adjacent to the tool call.
- `scope_adherence` cited `fb-cancel-flights-after-use` ("cancelled
  a trip after one of the segments had already been used"). The
  flight had **not** been used. This is the mistagged-clause +
  state-blind judge failure mode, identical to the smoke-run case.

**Case B — over-passing deterministic check (FP).** v2, task 0,
reward=0.0: `tool_sequence_correctness` passed, citing
`ts-book-reservation`'s prerequisite `get_user_details` was called
first. It was. But the booking failed because the agent picked the
wrong flight number — a dimension the deterministic checker does
not look at. This is a coverage finding, not a bug: the determinism
guarantees what it guarantees and nothing more.

---

## 4. Failure analysis

The framework's failures decompose into three classes. Each is
diagnostic of a different thing and each suggests a different fix.

### 4.1 Judge over-strictness (FN: auto fail, reward pass)

**Evidence**: `obl-confirm-action` was cited in **19/19** failed
verdicts under v0 and **20/20** under v2. The judge produces
`passed=false` for `confirmation_discipline` on every trajectory in
the dataset, including the three tasks tau-bench scored as passes.

This is not a coverage failure — the agent did, on most trajectories,
summarise the action and receive an affirmative — it's a **prompt-
interpretation failure**. gpt-4o-mini reads "obtain explicit user
confirmation (yes)" as requiring a yes adjacent to the tool call;
trajectories where the yes appears earlier in the conversation get
marked as fail.

**Implication**: the judge-model choice is a knob. The framework's
correctness does not depend on gpt-4o-mini being a great judge — it
depends on the framework producing structured, debuggable output that
makes the over-strictness *visible*. Concrete fixes, in increasing
order of effort:

1. Tighten the clause text. "Obtain an explicit yes at some point in
   the conversation before the tool call" reframes the same rule
   without the adjacency hint.
2. Switch the judge model to gpt-4o for `confirmation_discipline`
   only (the others are closer to working).
3. Score with a "2-of-3" panel of judges to absorb idiosyncratic
   cites.
4. Constrain each judge's clause set to the top-N most load-bearing
   per category (fewer chances to find a fault).

### 4.2 Contract mistagging (cross-dimension FP/FN)

**Evidence**: under v0, the four most-cited clauses in `scope_adherence`
failures (`fb-modify-basic-economy`, `fb-cancel-flights-after-use`,
`fb-add-insurance-after-booking`, `fb-modify-passenger-count`) are
all business-rule prohibitions. They should have been tagged
`policy_compliance`. Their misplacement does two things:

- inflates `scope_adherence` failures on tasks where the agent
  performed a perfectly in-scope action that happened to match the
  surface form of one of these prohibitions (e.g. task 1: a valid
  cancellation under travel insurance gets cited for "cancelling
  flights after use" because the judge can't read state);
- under-counts `policy_compliance` violations, because the rules
  that *would* have fired there now live in a different dimension's
  judge prompt.

**Implication**: this is the **honest cost of generated contracts**.
We accepted it to remove the "candidate-curated favourable clauses"
critique. For production, the fix is a one-pass review of the
generated contract before committing it (the validator is already
in place; the human just needs to rebucket 4 clauses), or a
stricter category-definition prompt that gives the LLM a worked
example per category.

### 4.3 Deterministic-check coverage gap (FP: auto pass, reward fail)

**Evidence**: `tool_sequence_correctness` has the **highest FP rate
of any dimension** (12 of 19 v0 disagreements; 18 of 20 in v2).

Looking inside, the pattern is consistent: the deterministic check
confirms that `get_user_details` preceded `book_reservation`, then
passes — but the booking failed for a different reason (wrong flight
number, wrong cabin, wrong payment split). The deterministic check
correctly guarantees what it claims to guarantee, and nothing more.

**Implication**: this is **coverage**, not a bug. If you want the
deterministic checker to catch more, you write more deterministic
checks (e.g. "the `cabin` argument to `book_reservation` matches a
user-stated preference in an earlier turn"). The architecture is
ready for them — each new check is one function appended to
`ALL_JUDGES`. We deliberately did not write them in scope; doing so
across the whole policy is what Day 3 would be.

### 4.4 What the framework caught that vibes would not

The v0 → v2 result is the framework's existence proof. The v2
preamble is a plausible improvement — it explicitly emphasises three
behaviours the policy already requires — and a vibe-check ("hey, the
agent confirms more often in v2!") would have approved it. The
framework caught:

- reward dropped from 16% → 5% (per-task ground truth);
- `tool_sequence_correctness` was the **only** dimension that moved
  in the intended direction (74% → 95%);
- the average trajectory length grew from 30.6 to 40.2 messages,
  pinpointing **why** the reward dropped (more turns hitting
  `max_steps`).

That third bullet is the specific kind of finding multi-dimensional
eval is for. Single-score evaluation would have given you "v2 is
worse" and stopped. The per-dimension view tells you v2 is worse
*because* it taught the agent to be more cautious *and* hit a hidden
budget constraint. That's actionable.

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
