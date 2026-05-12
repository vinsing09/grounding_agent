# Per-dimension auto-eval vs tau-bench reward

tau-bench reward (binary 0.0/1.0) is the ground truth. Each auto-eval dimension verdict is a per-task prediction of that ground truth. Cells: **TP** = auto pass & reward pass · **FP** = auto pass but reward fail (eval missed a failure) · **TN** = auto fail & reward fail (eval agreed with the reward) · **FN** = auto fail but reward pass (eval over-strict).

## Variant overview

- **v0 (wiki as-is)** — n=20, tau-bench reward pass: all 10%, train 0%, held_out 20%; avg msgs/run 33.9, total cost $0.1417
- **v2 (discipline preamble + wiki)** — n=20, tau-bench reward pass: all 10%, train 10%, held_out 10%; avg msgs/run 33.1, total cost $0.1475

## v0

### Termination distribution (v0)

| termination | train | held_out | all |
|---|---:|---:|---:|
| `completed` | 7 | 7 | 14 |
| `max_steps` | 1 | 2 | 3 |
| `transfer` | 2 | 1 | 3 |

### Reward decomposition by tau-bench grading kind (v0)

| reward kind | split | n | passed | pass rate |
|---|---|---:|---:|---:|
| `no_grade` | train | 1 | 0 | 0% |
| `no_grade` | held_out | 2 | 0 | 0% |
| `no_grade` | all | 3 | 0 | 0% |
| `r_actions` | train | 7 | 0 | 0% |
| `r_actions` | held_out | 8 | 2 | 25% |
| `r_actions` | all | 15 | 2 | 13% |
| `r_outputs` | train | 2 | 0 | 0% |
| `r_outputs` | all | 2 | 0 | 0% |

### Tool-side errors by tool (v0)

| tool | tool-side errors |
|---|---:|
| `book_reservation` | 16 |
| `update_reservation_flights` | 2 |

### Per-dimension pass rate (v0)

| metric | train | held_out | all |
|---|---:|---:|---:|
| `reward` | 0% | 20% | 10% |
| `confirmation_discipline` | 50% | 80% | 65% |
| `information_grounding` | 70% | 70% | 70% |
| `policy_compliance` | 20% | 10% | 15% |
| `scope_adherence` | 30% | 30% | 30% |
| `tool_argument_correctness` | 60% | 70% | 65% |
| `tool_sequence_correctness` | 100% | 50% | 75% |

### Confusion matrix per dimension (v0)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 0 | 5 | 5 | 0 | 50% | 50% | 0% |
| `confirmation_discipline` | held_out | 2 | 6 | 2 | 0 | 40% | 80% | 20% |
| `confirmation_discipline` | all | 2 | 11 | 7 | 0 | 45% | 65% | 10% |
| `information_grounding` | train | 0 | 7 | 3 | 0 | 30% | 70% | 0% |
| `information_grounding` | held_out | 2 | 5 | 3 | 0 | 50% | 70% | 20% |
| `information_grounding` | all | 2 | 12 | 6 | 0 | 40% | 70% | 10% |
| `policy_compliance` | train | 0 | 2 | 8 | 0 | 80% | 20% | 0% |
| `policy_compliance` | held_out | 1 | 0 | 8 | 1 | 90% | 10% | 20% |
| `policy_compliance` | all | 1 | 2 | 16 | 1 | 85% | 15% | 10% |
| `scope_adherence` | train | 0 | 3 | 7 | 0 | 70% | 30% | 0% |
| `scope_adherence` | held_out | 2 | 1 | 7 | 0 | 90% | 30% | 20% |
| `scope_adherence` | all | 2 | 4 | 14 | 0 | 80% | 30% | 10% |
| `tool_argument_correctness` | train | 0 | 6 | 4 | 0 | 40% | 60% | 0% |
| `tool_argument_correctness` | held_out | 1 | 6 | 2 | 1 | 30% | 70% | 20% |
| `tool_argument_correctness` | all | 1 | 12 | 6 | 1 | 35% | 65% | 10% |
| `tool_sequence_correctness` | train | 0 | 10 | 0 | 0 | 0% | 100% | 0% |
| `tool_sequence_correctness` | held_out | 2 | 3 | 5 | 0 | 70% | 50% | 20% |
| `tool_sequence_correctness` | all | 2 | 13 | 5 | 0 | 35% | 75% | 10% |

### Clauses most often cited in failed verdicts (v0)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `fb-modify-basic-economy` | 9 | `scope_adherence` |
| `obl-ask-travel-insurance` | 8 | `policy_compliance` |
| `obl-confirm-action` | 7 | `confirmation_discipline` |
| `fb-provide-unverified-info` | 6 | `information_grounding` |
| `obl-obtain-user-id` | 5 | `policy_compliance` |
| `fb-cancel-flights-after-use` | 4 | `scope_adherence` |
| `ts-book-reservation` | 2 | `tool_sequence_correctness` |
| `ts-cancel-reservation` | 2 | `tool_sequence_correctness` |
| `ts-update-reservation-flights` | 2 | `tool_sequence_correctness` |
| `obl-obtain-cancellation-details` | 1 | `policy_compliance` |
| `obl-ensure-cancellation-conditions` | 1 | `policy_compliance` |
| `fb-proactive-compensation` | 1 | `policy_compliance` |
| `fb-modify-passenger-count` | 1 | `scope_adherence` |
| `obl-ask-payment-method` | 1 | `policy_compliance` |

### Disagreement examples (v0)

**FP — auto pass, reward fail (eval missed a real failure)** (54)

- task 0 (train, reward=0.0) · `policy_compliance` · refs: `obl-obtain-user-id`, `obl-obtain-trip-details`, `obl-ask-travel-insurance`, `obl-obtain-reservation-id`, `obl-obtain-cancellation-details`, `obl-ensure-cancellation-conditions`, `obl-ensure-modification-conditions`, `obl-ask-payment-method`, `obl-deny-requests-against-policy`, `obl-transfer-to-human`, `fb-proactive-compensation`
  - 
- task 0 (train, reward=0.0) · `confirmation_discipline` · refs: `obl-confirm-action`
  - no mutating tool calls in this trajectory
- task 0 (train, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - 
- task 0 (train, reward=0.0) · `scope_adherence` · refs: `fb-modify-basic-economy`, `fb-modify-passenger-count`, `fb-add-insurance-after-booking`, `fb-cancel-flights-after-use`
  - 
- task 0 (train, reward=0.0) · `tool_sequence_correctness` · refs: —
  - no tool_sequence clauses matched this trajectory
- task 0 (train, reward=0.0) · `tool_argument_correctness` · refs: —
  - 3/3 tool calls returned no error (rate=100%)
- … and 48 more

**FN — auto fail, reward pass (eval over-strict)** (2)

- task 11 (held_out, reward=1.0) · `policy_compliance` · refs: `obl-ask-travel-insurance`
  - The agent did not ask if the user wanted to buy travel insurance when booking a flight, which is a requirement under the obligation [obl-ask-travel-insurance]. This is evident in the agent's actions where they proceeded to book the flight without confirming the user's preference 
- task 11 (held_out, reward=1.0) · `tool_argument_correctness` · refs: —
  - 5/7 tool calls succeeded (rate=71%); errors: book_reservation@18: Error: payment amount does not add up, total price is 375, but paid 299; book_reservation@26: Error: payment amount does not add up, total price is 375, but paid 329

## v2

### Termination distribution (v2)

| termination | train | held_out | all |
|---|---:|---:|---:|
| `completed` | 6 | 8 | 14 |
| `max_steps` | 3 | 1 | 4 |
| `transfer` | 1 | 1 | 2 |

### Reward decomposition by tau-bench grading kind (v2)

| reward kind | split | n | passed | pass rate |
|---|---|---:|---:|---:|
| `no_grade` | train | 3 | 0 | 0% |
| `no_grade` | held_out | 1 | 0 | 0% |
| `no_grade` | all | 4 | 0 | 0% |
| `r_actions` | train | 6 | 1 | 17% |
| `r_actions` | held_out | 9 | 1 | 11% |
| `r_actions` | all | 15 | 2 | 13% |
| `r_outputs` | train | 1 | 0 | 0% |
| `r_outputs` | all | 1 | 0 | 0% |

### Tool-side errors by tool (v2)

| tool | tool-side errors |
|---|---:|
| `book_reservation` | 34 |
| `update_reservation_flights` | 3 |
| `get_user_details` | 2 |

### Per-dimension pass rate (v2)

| metric | train | held_out | all |
|---|---:|---:|---:|
| `reward` | 10% | 10% | 10% |
| `confirmation_discipline` | 20% | 60% | 40% |
| `information_grounding` | 40% | 100% | 70% |
| `policy_compliance` | 10% | 0% | 5% |
| `scope_adherence` | 20% | 20% | 20% |
| `tool_argument_correctness` | 50% | 40% | 45% |
| `tool_sequence_correctness` | 100% | 80% | 90% |

### Confusion matrix per dimension (v2)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 1 | 1 | 8 | 0 | 90% | 20% | 10% |
| `confirmation_discipline` | held_out | 0 | 6 | 3 | 1 | 30% | 60% | 10% |
| `confirmation_discipline` | all | 1 | 7 | 11 | 1 | 60% | 40% | 10% |
| `information_grounding` | train | 1 | 3 | 6 | 0 | 70% | 40% | 10% |
| `information_grounding` | held_out | 1 | 9 | 0 | 0 | 10% | 100% | 10% |
| `information_grounding` | all | 2 | 12 | 6 | 0 | 40% | 70% | 10% |
| `policy_compliance` | train | 0 | 1 | 8 | 1 | 80% | 10% | 10% |
| `policy_compliance` | held_out | 0 | 0 | 9 | 1 | 90% | 0% | 10% |
| `policy_compliance` | all | 0 | 1 | 17 | 2 | 85% | 5% | 10% |
| `scope_adherence` | train | 0 | 2 | 7 | 1 | 70% | 20% | 10% |
| `scope_adherence` | held_out | 0 | 2 | 7 | 1 | 70% | 20% | 10% |
| `scope_adherence` | all | 0 | 4 | 14 | 2 | 70% | 20% | 10% |
| `tool_argument_correctness` | train | 1 | 4 | 5 | 0 | 60% | 50% | 10% |
| `tool_argument_correctness` | held_out | 0 | 4 | 5 | 1 | 50% | 40% | 10% |
| `tool_argument_correctness` | all | 1 | 8 | 10 | 1 | 55% | 45% | 10% |
| `tool_sequence_correctness` | train | 1 | 9 | 0 | 0 | 10% | 100% | 10% |
| `tool_sequence_correctness` | held_out | 1 | 7 | 2 | 0 | 30% | 80% | 10% |
| `tool_sequence_correctness` | all | 2 | 16 | 2 | 0 | 20% | 90% | 10% |

### Clauses most often cited in failed verdicts (v2)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `obl-confirm-action` | 12 | `confirmation_discipline` |
| `fb-modify-basic-economy` | 8 | `scope_adherence` |
| `obl-ask-travel-insurance` | 7 | `policy_compliance` |
| `fb-cancel-flights-after-use` | 7 | `scope_adherence` |
| `fb-provide-unverified-info` | 6 | `information_grounding` |
| `obl-obtain-user-id` | 6 | `policy_compliance` |
| `obl-obtain-cancellation-details` | 2 | `policy_compliance` |
| `obl-obtain-trip-details` | 2 | `policy_compliance` |
| `ts-cancel-reservation` | 2 | `tool_sequence_correctness` |
| `ts-book-reservation` | 1 | `tool_sequence_correctness` |
| `fb-modify-passenger-count` | 1 | `scope_adherence` |
| `obl-ask-payment-method` | 1 | `policy_compliance` |

### Disagreement examples (v2)

**FP — auto pass, reward fail (eval missed a real failure)** (48)

- task 0 (train, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - 
- task 0 (train, reward=0.0) · `scope_adherence` · refs: `fb-modify-basic-economy`, `fb-modify-passenger-count`, `fb-add-insurance-after-booking`, `fb-cancel-flights-after-use`
  - 
- task 0 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-book-reservation`
  - all 1 matched tool_sequence clause(s) satisfied
- task 2 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-update-reservation-flights`
  - all 1 matched tool_sequence clause(s) satisfied
- task 2 (train, reward=0.0) · `tool_argument_correctness` · refs: —
  - 10/10 tool calls returned no error (rate=100%)
- task 3 (train, reward=0.0) · `policy_compliance` · refs: `obl-obtain-user-id`, `obl-obtain-trip-details`, `obl-ask-travel-insurance`, `obl-obtain-reservation-id`, `obl-obtain-cancellation-details`, `obl-ensure-cancellation-conditions`, `obl-ensure-modification-conditions`, `obl-ask-payment-method`, `obl-deny-requests-against-policy`, `obl-transfer-to-human`, `fb-proactive-compensation`
  - 
- … and 42 more

**FN — auto fail, reward pass (eval over-strict)** (6)

- task 1 (train, reward=1.0) · `policy_compliance` · refs: `obl-obtain-cancellation-details`
  - The agent did not confirm the reason for cancellation before proceeding with the cancellation request, violating the obligation to obtain cancellation details.
- task 1 (train, reward=1.0) · `scope_adherence` · refs: `fb-cancel-flights-after-use`
  - The agent canceled a reservation for a basic economy flight (reservation ID Z7GOZK) after the user indicated they could not modify it, which is a violation of the forbidden behavior regarding canceling flights after use.
- task 19 (held_out, reward=1.0) · `policy_compliance` · refs: `obl-ask-travel-insurance`
  - The agent did not ask if the user wanted to buy travel insurance when booking a flight, which is a requirement under the obligation [obl-ask-travel-insurance]. This is evident as the agent proceeded with the booking without fulfilling this obligation.
- task 19 (held_out, reward=1.0) · `confirmation_discipline` · refs: `obl-confirm-action`
  - 2/3 mutations confirmed (rate=67%); unconfirmed: update_reservation_baggages@22
- task 19 (held_out, reward=1.0) · `scope_adherence` · refs: `fb-modify-basic-economy`
  - The agent modified the reservation by changing the flights from the original itinerary, which included a basic economy flight, to a new itinerary without adhering to the forbidden behavior of modifying basic economy flights.
- task 19 (held_out, reward=1.0) · `tool_argument_correctness` · refs: —
  - 6/7 tool calls succeeded (rate=86%); errors: update_reservation_flights@12: Error: flight HAT999 not found

