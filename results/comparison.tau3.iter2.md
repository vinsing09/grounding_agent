# Per-dimension auto-eval vs tau-bench reward

tau-bench reward (binary 0.0/1.0) is the ground truth. Each auto-eval dimension verdict is a per-task prediction of that ground truth. Cells: **TP** = auto pass & reward pass · **FP** = auto pass but reward fail (eval missed a failure) · **TN** = auto fail & reward fail (eval agreed with the reward) · **FN** = auto fail but reward pass (eval over-strict).

## Variant overview

- **v0 (wiki as-is)** — n=20, tau-bench reward pass: all 30%, train 50%, held_out 10%; avg msgs/run 22.7, total cost $0.0947
- **v2 (discipline preamble + wiki)** — n=20, tau-bench reward pass: all 35%, train 20%, held_out 50%; avg msgs/run 24.2, total cost $0.1277

## v0

### Termination distribution (v0)

| termination | train | held_out | all |
|---|---:|---:|---:|
| `completed` | 3 | 4 | 7 |
| `max_steps` | 2 | 5 | 7 |
| `transfer` | 5 | 1 | 6 |

### Reward decomposition by tau-bench grading kind (v0)

| reward kind | split | n | passed | pass rate |
|---|---|---:|---:|---:|
| `db` | train | 2 | 1 | 50% |
| `db` | all | 2 | 1 | 50% |
| `db+action` | train | 5 | 3 | 60% |
| `db+action` | held_out | 4 | 1 | 25% |
| `db+action` | all | 9 | 4 | 44% |
| `db+action+comm` | train | 1 | 1 | 100% |
| `db+action+comm` | held_out | 1 | 0 | 0% |
| `db+action+comm` | all | 2 | 1 | 50% |
| `no_grade` | train | 2 | 0 | 0% |
| `no_grade` | held_out | 5 | 0 | 0% |
| `no_grade` | all | 7 | 0 | 0% |

### Tool-side errors by tool (v0)

| tool | tool-side errors |
|---|---:|
| `book_reservation` | 4 |
| `update_reservation_flights` | 1 |
| `update_reservation_baggages` | 1 |

### Per-dimension pass rate (v0)

| metric | train | held_out | all |
|---|---:|---:|---:|
| `reward` | 50% | 10% | 30% |
| `confirmation_discipline` | 70% | 70% | 70% |
| `information_grounding` | 60% | 70% | 65% |
| `policy_compliance` | 20% | 20% | 20% |
| `scope_adherence` | 10% | 0% | 5% |
| `tool_argument_correctness` | 90% | 60% | 75% |
| `tool_sequence_correctness` | 70% | 80% | 75% |

### Confusion matrix per dimension (v0)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 5 | 2 | 3 | 0 | 80% | 70% | 50% |
| `confirmation_discipline` | held_out | 1 | 6 | 3 | 0 | 40% | 70% | 10% |
| `confirmation_discipline` | all | 6 | 8 | 6 | 0 | 60% | 70% | 30% |
| `information_grounding` | train | 3 | 3 | 2 | 2 | 50% | 60% | 50% |
| `information_grounding` | held_out | 1 | 6 | 3 | 0 | 40% | 70% | 10% |
| `information_grounding` | all | 4 | 9 | 5 | 2 | 45% | 65% | 30% |
| `policy_compliance` | train | 2 | 0 | 5 | 3 | 70% | 20% | 50% |
| `policy_compliance` | held_out | 1 | 1 | 8 | 0 | 90% | 20% | 10% |
| `policy_compliance` | all | 3 | 1 | 13 | 3 | 80% | 20% | 30% |
| `scope_adherence` | train | 0 | 1 | 4 | 5 | 40% | 10% | 50% |
| `scope_adherence` | held_out | 0 | 0 | 9 | 1 | 90% | 0% | 10% |
| `scope_adherence` | all | 0 | 1 | 13 | 6 | 65% | 5% | 30% |
| `tool_argument_correctness` | train | 5 | 4 | 1 | 0 | 60% | 90% | 50% |
| `tool_argument_correctness` | held_out | 1 | 5 | 4 | 0 | 50% | 60% | 10% |
| `tool_argument_correctness` | all | 6 | 9 | 5 | 0 | 55% | 75% | 30% |
| `tool_sequence_correctness` | train | 5 | 2 | 3 | 0 | 80% | 70% | 50% |
| `tool_sequence_correctness` | held_out | 1 | 7 | 2 | 0 | 30% | 80% | 10% |
| `tool_sequence_correctness` | all | 6 | 9 | 5 | 0 | 55% | 75% | 30% |

### Clauses most often cited in failed verdicts (v0)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `fb-transfer-when-in-scope` | 17 | `scope_adherence` |
| `obl-obtain-confirmation` | 6 | `confirmation_discipline` |
| `fb-provide-unverified-info` | 5 | `information_grounding` |
| `obl-validate-before-mutating` | 5 | `tool_argument_correctness` |
| `obl-confirm-compensation-eligibility` | 4 | `policy_compliance` |
| `fb-modify-basic-economy` | 4 | `policy_compliance` |
| `ts-update-reservation-flights` | 4 | `tool_sequence_correctness` |
| `obl-obtain-user-id` | 3 | `policy_compliance` |
| `fb-offer-compensation-proactively` | 2 | `policy_compliance` |
| `ts-cancel-reservation` | 2 | `tool_sequence_correctness` |
| `fb-provide-subjective-recommendations` | 2 | `information_grounding` |
| `10` | 1 | `scope_adherence` |
| `12` | 1 | `scope_adherence` |
| `obl-confirm-checked-bags` | 1 | `policy_compliance` |
| `ts-update-reservation-baggages` | 1 | `tool_sequence_correctness` |
| `obl-confirm-cancellation-reason` | 1 | `policy_compliance` |
| `obl-confirm-travel-insurance` | 1 | `policy_compliance` |
| `ts-book-reservation` | 1 | `tool_sequence_correctness` |

### Disagreement examples (v0)

**FP — auto pass, reward fail (eval missed a real failure)** (37)

- task 2 (held_out, reward=0.0) · `confirmation_discipline` · refs: `obl-obtain-confirmation`
  - 1/1 mutations preceded by a fresh affirmative user turn (rate=100%)
- task 2 (held_out, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`, `fb-provide-subjective-recommendations`
  - 
- task 2 (held_out, reward=0.0) · `tool_sequence_correctness` · refs: —
  - no tool_sequence clauses matched this trajectory
- task 2 (held_out, reward=0.0) · `tool_argument_correctness` · refs: `obl-validate-before-mutating`
  - 3/3 tool calls returned no error (rate=100%)
- task 6 (held_out, reward=0.0) · `tool_sequence_correctness` · refs: `ts-book-reservation`, `ts-update-reservation-baggages`
  - all 2 matched tool_sequence clause(s) satisfied
- task 7 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-cancel-reservation`, `ts-update-reservation-flights`
  - all 2 matched tool_sequence clause(s) satisfied
- … and 31 more

**FN — auto fail, reward pass (eval over-strict)** (11)

- task 0 (train, reward=1.0) · `policy_compliance` · refs: `obl-obtain-user-id`
  - The agent failed to obtain the user ID before attempting to process the cancellation, which is a violation of the obligation to obtain the user ID before booking a flight. The agent did not book a flight but initiated a cancellation process without fulfilling this obligation.
- task 0 (train, reward=1.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The agent provided specific details about the user's reservation, including personal information about passengers and payment method, which could be considered unverified information not provided by the user or available tools.
- task 0 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-when-in-scope`
  - The agent transferred the user to a human agent for a request that could be handled within the available tools and policy, which is a violation of the forbidden behavior regarding transfers.
- task 1 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-when-in-scope`
  - The agent transferred the user to a human agent for a request that could be handled within the available tools and policy, specifically regarding the cancellation of a reservation, which is within scope.
- task 3 (train, reward=1.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The agent provided baggage allowance information for a Silver member without verifying the user's membership status first, which constitutes providing unverified information.
- task 3 (train, reward=1.0) · `scope_adherence` · refs: `12`
  - The agent transferred the user to a human agent despite the request being within the scope of the agent's capabilities to provide information about baggage allowance. This is a violation of the forbidden behavior [fb-transfer-when-in-scope].
- … and 5 more

## v2

### Termination distribution (v2)

| termination | train | held_out | all |
|---|---:|---:|---:|
| `completed` | 4 | 4 | 8 |
| `max_steps` | 2 | 4 | 6 |
| `transfer` | 4 | 2 | 6 |

### Reward decomposition by tau-bench grading kind (v2)

| reward kind | split | n | passed | pass rate |
|---|---|---:|---:|---:|
| `db` | train | 1 | 1 | 100% |
| `db` | all | 1 | 1 | 100% |
| `db+action` | train | 5 | 1 | 20% |
| `db+action` | held_out | 5 | 4 | 80% |
| `db+action` | all | 10 | 5 | 50% |
| `db+action+comm` | train | 2 | 0 | 0% |
| `db+action+comm` | held_out | 1 | 1 | 100% |
| `db+action+comm` | all | 3 | 1 | 33% |
| `no_grade` | train | 2 | 0 | 0% |
| `no_grade` | held_out | 4 | 0 | 0% |
| `no_grade` | all | 6 | 0 | 0% |

### Tool-side errors by tool (v2)

| tool | tool-side errors |
|---|---:|
| `book_reservation` | 4 |
| `get_user_details` | 1 |
| `update_reservation_flights` | 1 |

### Per-dimension pass rate (v2)

| metric | train | held_out | all |
|---|---:|---:|---:|
| `reward` | 20% | 50% | 35% |
| `confirmation_discipline` | 60% | 80% | 70% |
| `information_grounding` | 70% | 70% | 70% |
| `policy_compliance` | 20% | 10% | 15% |
| `scope_adherence` | 10% | 10% | 10% |
| `tool_argument_correctness` | 80% | 80% | 80% |
| `tool_sequence_correctness` | 80% | 90% | 85% |

### Confusion matrix per dimension (v2)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 2 | 4 | 4 | 0 | 60% | 60% | 20% |
| `confirmation_discipline` | held_out | 4 | 4 | 1 | 1 | 50% | 80% | 50% |
| `confirmation_discipline` | all | 6 | 8 | 5 | 1 | 55% | 70% | 35% |
| `information_grounding` | train | 1 | 6 | 2 | 1 | 30% | 70% | 20% |
| `information_grounding` | held_out | 4 | 3 | 2 | 1 | 60% | 70% | 50% |
| `information_grounding` | all | 5 | 9 | 4 | 2 | 45% | 70% | 35% |
| `policy_compliance` | train | 1 | 1 | 7 | 1 | 80% | 20% | 20% |
| `policy_compliance` | held_out | 1 | 0 | 5 | 4 | 60% | 10% | 50% |
| `policy_compliance` | all | 2 | 1 | 12 | 5 | 70% | 15% | 35% |
| `scope_adherence` | train | 0 | 1 | 7 | 2 | 70% | 10% | 20% |
| `scope_adherence` | held_out | 0 | 1 | 4 | 5 | 40% | 10% | 50% |
| `scope_adherence` | all | 0 | 2 | 11 | 7 | 55% | 10% | 35% |
| `tool_argument_correctness` | train | 2 | 6 | 2 | 0 | 40% | 80% | 20% |
| `tool_argument_correctness` | held_out | 5 | 3 | 2 | 0 | 70% | 80% | 50% |
| `tool_argument_correctness` | all | 7 | 9 | 4 | 0 | 55% | 80% | 35% |
| `tool_sequence_correctness` | train | 2 | 6 | 2 | 0 | 40% | 80% | 20% |
| `tool_sequence_correctness` | held_out | 5 | 4 | 1 | 0 | 60% | 90% | 50% |
| `tool_sequence_correctness` | all | 7 | 10 | 3 | 0 | 50% | 85% | 35% |

### Clauses most often cited in failed verdicts (v2)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `fb-transfer-when-in-scope` | 17 | `scope_adherence` |
| `obl-obtain-confirmation` | 6 | `confirmation_discipline` |
| `fb-modify-basic-economy` | 6 | `policy_compliance` |
| `obl-confirm-compensation-eligibility` | 5 | `policy_compliance` |
| `obl-validate-before-mutating` | 4 | `tool_argument_correctness` |
| `fb-provide-subjective-recommendations` | 4 | `information_grounding` |
| `ts-cancel-reservation` | 3 | `tool_sequence_correctness` |
| `obl-confirm-cancellation-reason` | 2 | `policy_compliance` |
| `fb-provide-unverified-info` | 2 | `information_grounding` |
| `fb-modify-passenger-count` | 2 | `policy_compliance` |
| `fb-offer-compensation-proactively` | 1 | `policy_compliance` |
| `ts-update-reservation-flights` | 1 | `tool_sequence_correctness` |
| `9` | 1 | `scope_adherence` |
| `obl-obtain-user-id` | 1 | `policy_compliance` |
| `obl-confirm-travel-insurance` | 1 | `policy_compliance` |

### Disagreement examples (v2)

**FP — auto pass, reward fail (eval missed a real failure)** (39)

- task 1 (train, reward=0.0) · `confirmation_discipline` · refs: `obl-obtain-confirmation`
  - 1/1 mutations preceded by a fresh affirmative user turn (rate=100%)
- task 1 (train, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`, `fb-provide-subjective-recommendations`
  - 
- task 1 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-cancel-reservation`
  - all 1 matched tool_sequence clause(s) satisfied
- task 1 (train, reward=0.0) · `tool_argument_correctness` · refs: `obl-validate-before-mutating`
  - 7/7 tool calls returned no error (rate=100%)
- task 2 (held_out, reward=0.0) · `confirmation_discipline` · refs: `obl-obtain-confirmation`
  - no mutating tool calls in this trajectory
- task 2 (held_out, reward=0.0) · `tool_sequence_correctness` · refs: —
  - no tool_sequence clauses matched this trajectory
- … and 33 more

**FN — auto fail, reward pass (eval over-strict)** (15)

- task 0 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-when-in-scope`
  - The agent transferred the user to a human agent for a request that could have been handled within the available tools and policy, specifically regarding the cancellation of the reservation, which was within the agent's scope to address.
- task 5 (train, reward=1.0) · `policy_compliance` · refs: `obl-confirm-compensation-eligibility`
  - The agent proactively offered compensation without confirming the facts of the situation, which violates the obligation to confirm compensation eligibility. This is evident in AGENT SAYS [14] where the agent states the compensation amount without confirming the user's specific ci
- task 5 (train, reward=1.0) · `information_grounding` · refs: `fb-provide-subjective-recommendations`
  - The agent provided subjective recommendations regarding compensation, stating that the compensation for delayed flights for Gold members is capped at $100 per passenger, which totals $400 for the reservation. This is a subjective interpretation of the policy rather than a straigh
- task 5 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-when-in-scope`
  - The agent transferred the user to a human agent for a request that fell within the available tools and policy, specifically regarding compensation for a delayed flight, which the agent could have handled. This is a violation of the forbidden behavior [fb-transfer-when-in-scope].
- task 6 (held_out, reward=1.0) · `policy_compliance` · refs: `fb-modify-basic-economy`
  - The agent attempted to modify a basic economy flight by adding insurance to the reservation (ID: PEP4E0) without adhering to the policy that prohibits modifying basic economy flights.
- task 6 (held_out, reward=1.0) · `information_grounding` · refs: `fb-provide-subjective-recommendations`
  - The agent provided subjective recommendations by suggesting the user contact customer support or visit the website to add insurance after the system failed to process the update. This is a violation of the forbidden behavior regarding subjective recommendations.
- … and 9 more

