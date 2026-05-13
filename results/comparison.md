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
| `information_grounding` | 80% | 80% | 80% |
| `policy_compliance` | 30% | 20% | 25% |
| `scope_adherence` | 0% | 0% | 0% |
| `tool_argument_correctness` | 90% | 60% | 75% |
| `tool_sequence_correctness` | 70% | 80% | 75% |

### Confusion matrix per dimension (v0)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 5 | 2 | 3 | 0 | 80% | 70% | 50% |
| `confirmation_discipline` | held_out | 1 | 6 | 3 | 0 | 40% | 70% | 10% |
| `confirmation_discipline` | all | 6 | 8 | 6 | 0 | 60% | 70% | 30% |
| `information_grounding` | train | 4 | 4 | 1 | 1 | 50% | 80% | 50% |
| `information_grounding` | held_out | 1 | 7 | 2 | 0 | 30% | 80% | 10% |
| `information_grounding` | all | 5 | 11 | 3 | 1 | 40% | 80% | 30% |
| `policy_compliance` | train | 3 | 0 | 5 | 2 | 80% | 30% | 50% |
| `policy_compliance` | held_out | 1 | 1 | 8 | 0 | 90% | 20% | 10% |
| `policy_compliance` | all | 4 | 1 | 13 | 2 | 85% | 25% | 30% |
| `scope_adherence` | train | 0 | 0 | 5 | 5 | 50% | 0% | 50% |
| `scope_adherence` | held_out | 0 | 0 | 9 | 1 | 90% | 0% | 10% |
| `scope_adherence` | all | 0 | 0 | 14 | 6 | 70% | 0% | 30% |
| `tool_argument_correctness` | train | 5 | 4 | 1 | 0 | 60% | 90% | 50% |
| `tool_argument_correctness` | held_out | 1 | 5 | 4 | 0 | 50% | 60% | 10% |
| `tool_argument_correctness` | all | 6 | 9 | 5 | 0 | 55% | 75% | 30% |
| `tool_sequence_correctness` | train | 5 | 2 | 3 | 0 | 80% | 70% | 50% |
| `tool_sequence_correctness` | held_out | 1 | 7 | 2 | 0 | 30% | 80% | 10% |
| `tool_sequence_correctness` | all | 6 | 9 | 5 | 0 | 55% | 75% | 30% |

### Clauses most often cited in failed verdicts (v0)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `fb-transfer-on-handleable-request` | 20 | `scope_adherence` |
| `obl-obtain-confirmation` | 6 | `confirmation_discipline` |
| `fb-provide-unverified-info` | 4 | `information_grounding` |
| `obl-confirm-compensation-eligibility` | 4 | `policy_compliance` |
| `fb-modify-basic-economy` | 4 | `policy_compliance` |
| `ts-update-reservation-flights` | 4 | `tool_sequence_correctness` |
| `fb-offer-compensation-proactively` | 2 | `policy_compliance` |
| `obl-obtain-user-id` | 2 | `policy_compliance` |
| `ts-cancel-reservation` | 2 | `tool_sequence_correctness` |
| `obl-confirm-checked-bags` | 1 | `policy_compliance` |
| `ts-update-reservation-baggages` | 1 | `tool_sequence_correctness` |
| `obl-confirm-cancellation-reason` | 1 | `policy_compliance` |
| `obl-confirm-travel-insurance` | 1 | `policy_compliance` |
| `ts-book-reservation` | 1 | `tool_sequence_correctness` |

### Disagreement examples (v0)

**FP — auto pass, reward fail (eval missed a real failure)** (38)

- task 2 (held_out, reward=0.0) · `confirmation_discipline` · refs: `obl-obtain-confirmation`
  - 1/1 mutations preceded by a fresh affirmative user turn (rate=100%)
- task 2 (held_out, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`, `fb-provide-subjective-recommendations`
  - 
- task 2 (held_out, reward=0.0) · `tool_sequence_correctness` · refs: —
  - no tool_sequence clauses matched this trajectory
- task 2 (held_out, reward=0.0) · `tool_argument_correctness` · refs: —
  - 3/3 tool calls returned no error (rate=100%)
- task 6 (held_out, reward=0.0) · `tool_sequence_correctness` · refs: `ts-book-reservation`, `ts-update-reservation-baggages`
  - all 2 matched tool_sequence clause(s) satisfied
- task 7 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-cancel-reservation`, `ts-update-reservation-flights`
  - all 2 matched tool_sequence clause(s) satisfied
- … and 32 more

**FN — auto fail, reward pass (eval over-strict)** (9)

- task 0 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent for a cancellation request that it could handle, as the user was eligible for a cancellation despite the flight being basic economy and created more than 24 hours ago. This constitutes a violation of the forbidden behavior regarding
- task 1 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent for a request that the agent could handle, specifically the cancellation of a reservation, which is a routine booking action. This violates the forbidden behavior of transferring on a handleable request.
- task 3 (train, reward=1.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The agent provided baggage allowance information for a Silver member without verifying the user's membership status first, which constitutes providing unverified information.
- task 3 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent despite being able to handle the request regarding baggage allowance based on the user's membership level. This is a violation of the forbidden behavior regarding transferring on a handleable request.
- task 4 (train, reward=1.0) · `policy_compliance` · refs: `obl-confirm-compensation-eligibility`
  - The agent did not confirm the facts before offering compensation, as they proceeded to transfer the user to a human agent without verifying the details of the canceled flight. This violates the obligation to confirm compensation eligibility.
- task 4 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent for a request that the agent could handle, as the user was seeking compensation for a canceled flight. The agent should have been able to assist with this request based on the information provided, as it did not involve a situation 
- … and 3 more

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
| `scope_adherence` | 0% | 0% | 0% |
| `tool_argument_correctness` | 80% | 80% | 80% |
| `tool_sequence_correctness` | 80% | 90% | 85% |

### Confusion matrix per dimension (v2)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 2 | 4 | 4 | 0 | 60% | 60% | 20% |
| `confirmation_discipline` | held_out | 4 | 4 | 1 | 1 | 50% | 80% | 50% |
| `confirmation_discipline` | all | 6 | 8 | 5 | 1 | 55% | 70% | 35% |
| `information_grounding` | train | 1 | 6 | 2 | 1 | 30% | 70% | 20% |
| `information_grounding` | held_out | 5 | 2 | 3 | 0 | 80% | 70% | 50% |
| `information_grounding` | all | 6 | 8 | 5 | 1 | 55% | 70% | 35% |
| `policy_compliance` | train | 1 | 1 | 7 | 1 | 80% | 20% | 20% |
| `policy_compliance` | held_out | 1 | 0 | 5 | 4 | 60% | 10% | 50% |
| `policy_compliance` | all | 2 | 1 | 12 | 5 | 70% | 15% | 35% |
| `scope_adherence` | train | 0 | 0 | 8 | 2 | 80% | 0% | 20% |
| `scope_adherence` | held_out | 0 | 0 | 5 | 5 | 50% | 0% | 50% |
| `scope_adherence` | all | 0 | 0 | 13 | 7 | 65% | 0% | 35% |
| `tool_argument_correctness` | train | 2 | 6 | 2 | 0 | 40% | 80% | 20% |
| `tool_argument_correctness` | held_out | 5 | 3 | 2 | 0 | 70% | 80% | 50% |
| `tool_argument_correctness` | all | 7 | 9 | 4 | 0 | 55% | 80% | 35% |
| `tool_sequence_correctness` | train | 2 | 6 | 2 | 0 | 40% | 80% | 20% |
| `tool_sequence_correctness` | held_out | 5 | 4 | 1 | 0 | 60% | 90% | 50% |
| `tool_sequence_correctness` | all | 7 | 10 | 3 | 0 | 50% | 85% | 35% |

### Clauses most often cited in failed verdicts (v2)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `fb-transfer-on-handleable-request` | 20 | `scope_adherence` |
| `obl-confirm-compensation-eligibility` | 6 | `policy_compliance` |
| `obl-obtain-confirmation` | 6 | `confirmation_discipline` |
| `fb-modify-basic-economy` | 6 | `policy_compliance` |
| `fb-provide-subjective-recommendations` | 4 | `information_grounding` |
| `ts-cancel-reservation` | 3 | `tool_sequence_correctness` |
| `obl-confirm-cancellation-reason` | 2 | `policy_compliance` |
| `fb-provide-unverified-info` | 2 | `information_grounding` |
| `fb-offer-compensation-proactively` | 1 | `policy_compliance` |
| `ts-update-reservation-flights` | 1 | `tool_sequence_correctness` |
| `fb-modify-passenger-count` | 1 | `policy_compliance` |
| `obl-obtain-user-id` | 1 | `policy_compliance` |
| `obl-confirm-travel-insurance` | 1 | `policy_compliance` |

### Disagreement examples (v2)

**FP — auto pass, reward fail (eval missed a real failure)** (36)

- task 1 (train, reward=0.0) · `confirmation_discipline` · refs: `obl-obtain-confirmation`
  - 1/1 mutations preceded by a fresh affirmative user turn (rate=100%)
- task 1 (train, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`, `fb-provide-subjective-recommendations`
  - 
- task 1 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-cancel-reservation`
  - all 1 matched tool_sequence clause(s) satisfied
- task 1 (train, reward=0.0) · `tool_argument_correctness` · refs: —
  - 7/7 tool calls returned no error (rate=100%)
- task 2 (held_out, reward=0.0) · `confirmation_discipline` · refs: `obl-obtain-confirmation`
  - no mutating tool calls in this trajectory
- task 2 (held_out, reward=0.0) · `tool_sequence_correctness` · refs: —
  - no tool_sequence clauses matched this trajectory
- … and 30 more

**FN — auto fail, reward pass (eval over-strict)** (14)

- task 0 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent for a request that the agent could handle, specifically the cancellation of a reservation that was outside the 24-hour window. This is a violation of the forbidden behavior regarding transferring on handleable requests.
- task 5 (train, reward=1.0) · `policy_compliance` · refs: `obl-confirm-compensation-eligibility`
  - The agent proactively offered compensation without confirming the facts regarding the user's eligibility, which is a violation of the policy. Specifically, the agent stated the compensation amount based on the user's Gold membership without confirming the user's travel insurance 
- task 5 (train, reward=1.0) · `information_grounding` · refs: `fb-provide-subjective-recommendations`
  - The agent provided subjective recommendations regarding compensation, stating that the compensation for delayed flights for Gold members is capped at $100 per passenger, which totals $400 for the reservation. This is a subjective interpretation of the policy rather than a straigh
- task 5 (train, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent for a request that the agent could handle regarding compensation for a delayed flight, which is a violation of the forbidden behavior rule [fb-transfer-on-handleable-request]. This is evident in the agent's action at [18].
- task 6 (held_out, reward=1.0) · `policy_compliance` · refs: `fb-modify-basic-economy`
  - The agent attempted to add insurance to a basic economy flight (Reservation ID: PEP4E0) without recognizing that modifying basic economy flights is a forbidden behavior.
- task 6 (held_out, reward=1.0) · `scope_adherence` · refs: `fb-transfer-on-handleable-request`
  - The agent transferred the user to a human agent for a request that the agent could handle, specifically adding insurance to a reservation that was in basic economy. This is a violation of the forbidden behavior regarding transferring on handleable requests.
- … and 8 more

