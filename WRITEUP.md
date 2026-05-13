# grounding_agent — writeup

> Personal project. Submission for Meraki Labs Founding AI Engineer
> Work Trial, Problem Statement 4 — *Evaluation Framework from Scratch*.
> Read time ≈ 15 minutes. Reference companion to `PRESENTATION.md`
> (the 5-minute deck) and the `forensics_*.md` series (the
> iteration-by-iteration analysis).

## TL;DR

`grounding_agent` is an evaluation framework for **tool-calling LLM
agents**. It produces a **seven-dimension verdict on every
trajectory** (policy compliance, confirmation discipline, information
grounding, scope adherence, tool sequence correctness, tool argument
correctness, task completion) and compares those verdicts against an
external ground-truth reward.

It is applied to the airline customer-support agent from
[τ³-bench](https://github.com/sierra-research/tau2-bench) (the
March 2026 release from Sierra Research; their repo name retains
"tau2" while shipping the τ³-bench fixes), on 20 tasks (10
development + 10 held-out), under two prompt variants.

### Headline numbers (final iteration, τ³-bench, gpt-4o-mini end-to-end)

- **v0 (baseline prompt) reward 30%** (6/20).
- **v2 (with discipline preamble) reward 35%** (7/20).
- **v2 held-out: 50%** vs v0's 10%. The 40-percentage-point gap on
  tasks the framework didn't see during development is the clearest
  generalization signal.
- **`confirmation_discipline`** went from 0% pass-rate (under an LLM
  judge) to 70% (under a deterministic Python check) — and the
  reclassification holds across benchmarks.
- **`tool_argument_correctness`** is a deterministic check on τ³-bench's
  `ToolMessage.error: bool` flag — 75% pass-rate, catches every
  payment-arithmetic failure.
- **`scope_adherence` is structurally stuck at 0%** — the LLM judge
  cannot reliably decide whether a transfer-to-human was scope-
  appropriate, regardless of clause wording. Documented as a known
  LLM-judge limit.

Full per-dimension tables in `results/comparison.md`.

---

## 1. The dimensions

A seven-category failure taxonomy is the load-bearing design
decision. It constrains the contract structure and the judge prompts.
The categories are policy-agnostic: they capture structural failure
modes of *tool-using agents*, not "airline support agents." See
`grounding_agent/taxonomy.py`.

| Category | Failure mode | Judge kind | Maps to policy clauses about |
|---|---|---|---|
| `policy_compliance` | Agent permits or recommends an action the policy forbids, or denies an in-scope action. | semantic | Business rules: cabin-class limits, refund eligibility, payment-method limits, "deny user requests against policy." |
| `confirmation_discipline` | Mutation without an explicit user "yes" beforehand. | **deterministic** | "Before any actions that update the booking database… obtain explicit user confirmation (yes) to proceed." |
| `information_grounding` | Factual claims that don't trace to a user turn or tool output. | semantic | "Should not provide any information, knowledge, or procedures not provided by the user or available tools." |
| `scope_adherence` | Transfer-on-in-scope, or attempting an out-of-scope task. | semantic | "Transfer to a human agent if and only if the request cannot be handled within scope." |
| `tool_sequence_correctness` | A mutation called without its prerequisite read (e.g., `get_user_details` before `book_reservation`). | **deterministic** | "Only one tool call at a time" + all prerequisite-read patterns. |
| `tool_argument_correctness` | Agent calls a tool with arguments the tool rejects (bad payment math, nonexistent ID, insufficient balance). | **deterministic** | Validate before mutating: "the agent must make sure rules apply before calling the API." |
| `task_completion` | Agent abandons, loops, or finishes the wrong task. | observed via τ³-bench reward | (Implicit; ground truth.) |

Three semantic + three deterministic + one reward-observed = **seven
dimensions, six judges.**

### Why these seven

Each category is anchored in a load-bearing clause of the airline
policy. Earlier drafts had eleven categories; categories like
"hallucination," "refusal quality," and "instruction adherence"
collapsed cleanly into `information_grounding`, `scope_adherence`,
and `policy_compliance` respectively. **Seven well-justified
dimensions beat eleven shallow ones.**

### Why deterministic for three of them

- **`confirmation_discipline`**: was originally a semantic LLM judge.
  Forensics showed it returned `passed=false` on every trajectory,
  regardless of agent behaviour — the LLM interpreted "explicit
  confirmation" maximally. A 10-line Python check ("did the user's
  most-recent unconsumed turn contain an affirmative before each
  mutating tool call?") immediately outperformed it. **Reclassified
  to deterministic.**
- **`tool_sequence_correctness`**: prerequisite-read ordering is
  mechanical. A loop is cheaper and more reliable than an LLM.
- **`tool_argument_correctness`**: the tool server itself is the
  oracle — if a call returned `Error:` (or, in τ³-bench, has
  `ToolMessage.error: bool == True`), the agent's arguments were
  invalid. No LLM needed.

### Why not a `task_completion` LLM judge

τ³-bench's reward function is the ground truth for end-to-end
completion. Running a separate LLM judge against the same dimension
would conflate evaluator noise with the very signal we treat as
ground truth. **Tracked but not judged.**

---

## 2. Methodology

```
policy.md + tools → contract.json ──[6 judges]──► per-dimension verdicts
                                                            │
              τ³-bench reward (ground truth) ──[compare]────┘
```

### 2.1 Agent under test

τ³-bench airline customer-support, loaded via the `tau2` Python
package from `github.com/sierra-research/tau2-bench`. 15 tools, 50
test tasks. We use 20 (10 development + 10 held-out) drawn from
τ³-bench's canonical train/test split (`data/tasks.json`).

### 2.2 Contract generation, not curation

`scripts/generate_contract.py` makes one LLM call (`gpt-4o-mini`,
`response_format=json_object`) against `vendor/tau_bench_airline/policy.md`
+ the 15-tool catalog. Output: ~15 clauses across obligations +
forbidden behaviors + tool_sequences, each tagged to a taxonomy
category, committed as `data/contract.json`. The validator rejects
unknown categories, duplicate clause ids, missing fields, and
malformed prerequisites at save and load time.

**Why generated, not hand-curated**: removes the
"candidate-curated-favourable-clauses" critique; gains reproducibility.
The cost is tagging noise — generators occasionally place a clause
in the wrong category. This is a known structural risk, addressed
in iteration 2 of the τ³-bench forensics.

### 2.3 Judges

Three semantic judges share one prompt template:
1. Filter the contract for clauses tagged to the target category.
2. Render the trajectory as an "AGENT ACTIONS" block (extracted
   tool calls + assistant content; user turns deliberately excluded
   so the judge anchors on what the agent did) plus the full
   trajectory for context.
3. Call litellm with `response_format=json_object` and a system
   prompt that emphasises: "ONLY THE AGENT CAN VIOLATE. A user
   request is never itself a violation."
4. Return a `JudgeResult(category, passed, reason, clause_refs,
   score)`.

Three deterministic judges walk the trajectory once and return the
same structure. The `score` field carries a continuous rate (e.g.,
fraction of mutations confirmed) where applicable.

### 2.4 Prompt variants

We compared two prompt configurations of the same agent
(`gpt-4o-mini`):

- **v0** — the τ³-bench airline policy as Sierra ships it.
- **v2** — v0 prepended with a three-rule "execution discipline"
  preamble (file at `data/variants/v2_preamble.md`):
  1. Get an explicit user "yes" before any state-mutating tool call.
  2. Read user details before any booking-related write.
  3. Only answer from tool outputs or the user's own messages.

The hypothesis tested: does explicit emphasis on these three
dimensions improve agent behaviour, and does the improvement
generalize from development tasks to held-out tasks?

### 2.5 Development / held-out split

This is **not** ML training. The agent's weights are frozen
(`gpt-4o-mini`). What we tune is the **prompt**.

- **Development tasks (10):** the 10 tasks we examined during
  framework iteration (designing dimensions, writing contract
  prompts, tuning v2's preamble).
- **Held-out tasks (10):** never inspected during design. Only
  ran the variants against them at evaluation time.

An improvement on development tasks means the design worked. An
improvement on held-out tasks means the improvement *generalizes*.

### 2.6 Reproducibility

- Tasks: explicit ids in `data/tasks.json`.
- Contract: regenerated by `scripts/generate_contract.py` and
  committed.
- Models: gpt-4o-mini end-to-end by default; overridable via CLI.
- Per-task results cached as JSON. `--force` re-runs. `--judge-only`
  re-judges cached trajectories without re-rolling the agent.
- 125 tests pass on a clean checkout (`pytest`).

---

## 3. Results

### 3.1 Variant overview (τ³-bench, final iteration)

| variant | n | reward (all) | reward (dev) | reward (held-out) | avg msgs | total cost |
|---|---:|---:|---:|---:|---:|---:|
| **v0** (baseline) | 20 | 30% | 50% | **10%** | 22.7 | $0.09 |
| **v2** (preamble) | 20 | 35% | 20% | **50%** | 24.2 | $0.13 |

**Headline:** v2's discipline preamble *trades* development-task
reward for held-out-task reward. v2 generalises +40pp on held-out
where v0 fails outright. Reward overall is roughly tied; the
distribution across splits is the result.

### 3.2 Per-dimension pass rates

| dimension | v0 | v2 |
|---|---:|---:|
| `confirmation_discipline` | 70% | 70% |
| `information_grounding` | 80% | 70% |
| `policy_compliance` | 25% | 15% |
| `scope_adherence` | **0%** | **0%** |
| `tool_sequence_correctness` | 75% | 85% |
| `tool_argument_correctness` | 75% | 80% |

Two dimensions improved under v2 (`tool_sequence_correctness`,
`tool_argument_correctness`) — both directly targeted by the
preamble. Two are roughly tied. Two regressed slightly under v2.
Full confusion matrices in `results/comparison.md`.

### 3.3 Per-dimension confusion matrix (vs τ³-bench reward)

Cells: **TP** (auto pass & reward pass) · **FP** (auto pass, reward
fail — eval missed a real failure) · **TN** (auto fail, reward fail
— eval agreed) · **FN** (auto fail, reward pass — eval over-strict).

The four signature rows (v0, all-split):

| dimension | TP | FP | TN | FN | agreement |
|---|---:|---:|---:|---:|---:|
| `confirmation_discipline` | 6 | 8 | 6 | 0 | 60% |
| `tool_argument_correctness` | 6 | 9 | 5 | 0 | 55% |
| `tool_sequence_correctness` | 4 | 9 | 5 | 2 | 45% |
| `scope_adherence` | 0 | 0 | 14 | 6 | 70% |

Read these as: `confirmation_discipline` and
`tool_argument_correctness` have **zero FNs** (the deterministic
checks never fail a task the reward passed). `scope_adherence` has
**zero TPs** — the LLM judge never passes a transfer-containing
trajectory, even when the reward agrees the transfer was correct.

### 3.4 What the framework caught that vibes-eval would not

**1. v2 generalises.** The +40pp lift on held-out tasks (50% vs
10%) is the clearest signal that the discipline preamble produces
transferable behaviour, not memorisation of specific task patterns.
A single-score eval would have shown "v0 30%, v2 35%" and stopped.

**2. Argument-correctness is the dominant failure mode.** Most
agent failures are arithmetic — wrong payment splits, gift-card
balance shortfalls, invented user_ids. Our deterministic check
flags these directly via τ³-bench's `ToolMessage.error: bool`.
Without this dimension we would have attributed many failures to
"policy compliance" or "information grounding" and looked for the
wrong fixes.

**3. One LLM judge was provably worse than a 10-line Python check.**
For `confirmation_discipline`, an LLM judge gave 0% pass rate (it
always found something to flag). A Python check ("did the user's
most-recent unconsumed turn contain an affirmative before each
mutating tool call?") gave 70%. We replaced the LLM judge with the
Python check. The fix held across both the original τ-bench and
τ³-bench iterations — the LLM judge was structurally wrong, not
just badly tuned.

---

## 4. Failure analysis

The framework's residual failures decompose into three classes.
Each is diagnostic of a different thing and each suggests a
different fix.

### 4.1 LLM-judge structural limits

**Evidence:** `scope_adherence` has zero true positives in the
final iteration. Three different clause wordings tried; all caused
the LLM judge to fire on every transfer regardless of whether the
transfer was scope-appropriate.

The judge needs to hold the entire policy + tool catalog in working
memory and compare them against the user's request — a hard
reasoning task that gpt-4o-mini doesn't do reliably from a single
clause.

**Implication:** the judge-model choice is a knob. The framework's
correctness does not depend on gpt-4o-mini being a great judge — it
depends on the framework producing structured, debuggable output
that makes the limit *visible*. Concrete fix paths, in increasing
order of effort: tighten the clause wording, switch the
`scope_adherence` judge to gpt-4o, use a 2-of-3 panel, or accept the
dimension as inherently noisy.

### 4.2 Contract mistagging

**Evidence:** the contract generator placed
`fb-make-multiple-tool-calls` ("do not respond to the user while
making a tool call") under `scope_adherence` rather than
`tool_sequence_correctness`. With it as the only `scope_adherence`
clause, the dimension always fired in iteration 1. Iteration 2
hand-patched the tag; the iteration-2 contract is what ships.

**Implication:** this is the **honest cost of generated contracts**.
We accepted it to remove the "candidate-curated favourable clauses"
critique. For production, the fix is a one-pass human-in-the-loop
tag review before committing the contract. The validator
infrastructure exists; the review is a single mechanical pass.

### 4.3 Coverage gaps

**Evidence:** `tool_sequence_correctness` has the highest FP rate
of any dimension (9 of 20 disagreements). Looking inside, the
pattern is consistent: the agent's call ordering was correct, but
the task failed for a different reason the dimension does not
score (wrong flight number, wrong cabin, wrong payment split).

**Implication:** this is **coverage**, not a bug. The deterministic
check correctly guarantees what it claims to guarantee and nothing
more. If we want it to catch more, we write more deterministic
checks (e.g., "the `cabin` argument to `book_reservation` matches a
user-stated preference in an earlier turn"). The architecture is
ready for them — each new check is one function appended to
`ALL_JUDGES`.

### 4.4 What the framework caught about benchmarks

A noteworthy meta-finding: the **first three iterations of this
project ran against the original τ-bench (2024)**, where v2
appeared to be *worse* than v0 on reward. Web verification revealed
τ-bench had been superseded by τ³-bench (March 2026), which **fixed
27 airline-task definitions** — incorrect expected actions,
ambiguous user instructions, impossible constraints. After migrating
to the corrected benchmark, the same v2 prompt that looked worse
turned out to be **better and to generalise**.

This is the kind of finding multi-dimensional eval is for. A
framework whose value depends on an external ground truth needs
independent verification of that ground truth — at least once. The
full migration story is in `results/tau1_vs_tau3.md`.

---

## 5. Production at 100k trajectories/day

### 5.1 Cost

Per-trajectory cost today (gpt-4o-mini end-to-end):

| component | cost |
|---|---:|
| Agent + simulated user | ~$0.008 |
| 3 LLM judges | ~$0.004 |
| 3 deterministic checks | ~$0 |
| **Total per trajectory** | **~$0.012** |

At 100k/day fully judged = **~$1.2k/day**. To bring this down
without losing signal:
- Deterministic checks on 100% of traffic (free).
- Sample LLM judges to 1–5% of traffic.
- Reserve gpt-4o for arbitration on flagged cases.

Realistic production budget: **~$50–150/day** for the same signal
quality.

### 5.2 Cloud infrastructure topology

```
   agent service                      eval pipeline
   ─────────────                      ─────────────
   ┌──────────┐   trajectory JSON   ┌──────────────────┐
   │  live    │ ──────────────────► │  queue           │
   │  agent   │                     │  (SQS / Kafka /  │
   │ (any LLM)│                     │   Pub-Sub)       │
   └──────────┘                     └────────┬─────────┘
                                             │ fan-out
                  ┌──────────────────────────┴──────────────┐
                  │                                          │
                  ▼                                          ▼
        ┌──────────────────────┐               ┌───────────────────────┐
        │ deterministic        │               │ semantic-judge        │
        │ workers (CPU)        │               │ workers (LLM I/O)     │
        │ — 100% of traffic    │               │ — sampled %          │
        │ — <1 ms each         │               │ — async, batched     │
        └────────┬─────────────┘               └─────────┬─────────────┘
                 │                                       │
                 └──────────┬────────────────────────────┘
                            ▼
                  ┌──────────────────────┐
                  │  results store       │
                  │  blobs → S3-like     │
                  │  metrics → ClickHouse│
                  │           or BigQuery│
                  └────────┬─────────────┘
                           ▼
                  ┌──────────────────────┐
                  │  dashboard + alerts  │
                  │  (Grafana / similar) │
                  └──────────────────────┘
```

**Sizing knobs:**
- *Deterministic workers* — stateless, horizontally scalable, ~10 ms
  per trajectory. A 10-pod deployment handles 100k/day with ~60×
  headroom.
- *Semantic workers* — bottlenecked on LLM API latency (~2 s/call).
  Run async with a connection pool; ~20–50 concurrent calls suffice
  at 1% sampling.
- *Storage* — ~5 KB metrics row + ~30 KB trajectory blob per task.
  ~500 MB blob/day, ~500 KB metrics/day. Trivial.

**Other infra needs at scale:**
- LLM-provider rate limits are the most likely bottleneck.
- Per-tenant isolation in queue + results store.
- Region routing for trajectory data residency.
- Versioned contracts — store the contract id (or content hash) on
  every result row so historical data stays interpretable after
  policy edits.

### 5.3 Reliability

- **Contract validation** runs on save and on load; an unparseable
  or mistagged contract cannot be silently picked up.
- **Errored tasks are recorded, not crashed.** The runner writes
  `{"error": "..."}` records and continues; aggregations exclude
  them but the count is surfaced.
- **Idempotent per task.** Re-runs from a partial state pick up
  where they left off; no double-charging.
- **Structured event log** (`results/logs/<run_id>/<variant>.jsonl`)
  captures per-task and per-judge events with timing — every run
  is replayable.

### 5.4 What breaks at scale (and what doesn't)

- **Doesn't break:** the taxonomy, the contract schema, the
  deterministic checks, the validator gates, per-task caching, the
  event log.
- **Breaks if trusted as final verdicts:** the LLM-based judges.
  At 100k/day, treat their output as **triage signal**, not
  decisions. Route flagged trajectories to a higher-capability
  judge or a human reviewer.
- **Needs work:** the contract gets stale when the policy changes.
  Regeneration is one LLM call; the harder part is migrating
  historical results indexed by old clause ids.

---

## 6. What's next

Ordered by leverage.

1. **`tool_argument_choice_correctness`** — close the coverage gap
   that produces most remaining FPs. A semantic judge that re-derives
   *correct* arguments from tool returns + user constraints and
   compares against the agent's call. Catches the modal failure mode
   (wrong flight numbers, wrong payment splits) that no current
   dimension covers.
2. **Surface τ³-bench's richer reward signal.** `RewardInfo` carries
   five sub-checks (db_check, env_assertions, action_checks,
   nl_assertions, communicate_checks). The framework currently reads
   only the binary roll-up. Decomposing it would expose which check
   class fails most.
3. **Tag-review step** in `scripts/generate_contract.py`: emit the
   draft contract, render it diff-friendly, accept a tag-only
   overlay file. One-pass human review yields a clean tagged
   contract while keeping clause text generator-authored.
4. **Drop or reframe `scope_adherence`.** Three iterations failed to
   stabilise it; accept the dimension as inherently noisy or remove.
5. **Multi-trial at N ≥ 50** for tighter v0/v2 deltas.
6. **Tier production judges** — deterministic on 100%, gpt-4o-mini
   on a sample, gpt-4o arbitration on flagged.
7. **Multi-agent comparison.** The framework evaluates one agent
   today; the plumbing for "evaluate any tool-calling agent" is
   one indirection.

---

## 7. What we chose not to build

- **An eleventh dimension.** Seven cited to policy clauses beat
  eleven shallow categories.
- **Hand-curated clauses.** The generator-based contract has known
  mistagging cost (§4.2); the trade-off is reproducibility and the
  removal of "candidate curated favourable clauses" critique.
- **A separate `task_completion` LLM judge.** The benchmark's
  reward already measures the same dimension programmatically.
- **An optimization loop.** PS4 is the eval, not the improvement.
- **Multi-trial averaging.** Each task is run once per variant.
  With binary rewards, single-trial agreement is the cleanest
  comparison.
- **Async / parallel judge orchestration.** Single-process
  synchronous was enough at n=40. Parallel orchestration is a
  30-minute change to `evaluator.py`; deliberately deferred.
- **Active prompt-tuning of the judges.** Out of scope.
- **A web UI / dashboard.** Markdown + JSON outputs are sufficient
  for review.

---

## 8. What was learned

Six meta-points across the project.

1. **Multi-dimensional eval's value emerges in the disagreements
   with ground truth.** If our framework matched the reward
   perfectly, it would be redundant; it earns its keep when it
   shows *why* the reward failed (and occasionally when it shows
   the reward itself is wrong).
2. **LLM judges and deterministic judges are not interchangeable.**
   Confirmation, ordering, and tool-error detection are
   mechanically observable; LLMs were strictly worse. Reserve LLM
   judges for genuinely subjective dimensions.
3. **`scope_adherence` is where the LLM-judge approach breaks.**
   Three iterations of clause refinement couldn't get the judge to
   reliably evaluate scope. Honest documented limit.
4. **Forensics-driven iteration converges fast.** 1–2 iterations
   produce major shifts; subsequent iterations are 1-cell shifts.
   This held under both τ-bench AND τ³-bench. Plateau is real.
5. **Benchmarks themselves can be broken.** A framework whose value
   depends on a benchmark's ground truth needs **independent
   verification** of that ground truth — at least once.
6. **Portability earns its keep.** Migrating from τ-bench to
   τ³-bench required rewriting one module (`runner.py`) and
   patching one helper. The taxonomy, judges, evaluator, compare,
   eventlog were untouched. The framework is agnostic to the agent
   under test, by design.

---

## Appendix A — historical iteration trail

The framework went through six forensic iterations: three under
the original τ-bench, then a migration to τ³-bench, then three
under τ³-bench. Each iteration's findings, fixes, and results are
documented in:

- `results/forensics.md` — τ-bench pass 1 (six findings, four buckets).
- `results/forensics_v2.md` — τ-bench pass 2 (four bucket fixes verified).
- `results/forensics_v3.md` — τ-bench pass 3 (contract retag).
- `results/tau1_vs_tau3.md` — migration meta-finding and motivation.
- `results/forensics_tau3.md` — τ³-bench pass 1 (two new issues
  surfaced under the corrected benchmark).
- `results/forensics_tau3_v3.md` — τ³-bench passes 2+3 (contract
  patches, refined clauses, final state).

Every iteration's data is preserved (`results/*.iter1`,
`*.iter2`, `*.pre`, etc.); the trajectory of improvement is
auditable end-to-end.

## Appendix B — repo navigation

See `README.md` for the repo layout. Key entry points:
- `grounding_agent/` — 7 modules, all ≤ 300 lines.
- `tests/` — 125 passing tests.
- `code_review/` — per-implementation review documents (lean-code
  accounting, test rigor, risks flagged).
- `knowledge.md`, `errors.md` — chronological session and error
  logs.
- `PRESENTATION.md` / `PRESENTATION.pdf` — the 5-minute deck.
