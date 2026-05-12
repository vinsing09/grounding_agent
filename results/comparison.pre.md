# Per-dimension auto-eval vs tau-bench reward

tau-bench reward (binary 0.0/1.0) is the ground truth. Each auto-eval dimension verdict is a per-task prediction of that ground truth. Cells: **TP** = auto pass & reward pass · **FP** = auto pass but reward fail (eval missed a failure) · **TN** = auto fail & reward fail (eval agreed with the reward) · **FN** = auto fail but reward pass (eval over-strict).

## Variant overview

- **v0 (wiki as-is)** — n=19, tau-bench reward pass: all 16%, train 11%, held_out 20%; avg msgs/run 30.6, total cost $0.1180
- **v2 (discipline preamble + wiki)** — n=20, tau-bench reward pass: all 5%, train 0%, held_out 10%; avg msgs/run 40.2, total cost $0.2054

## v0

### Per-dimension pass rate (v0)

| metric | train | held_out | all |
|---|---:|---:|---:|
| `reward` | 11% | 20% | 16% |
| `confirmation_discipline` | 0% | 0% | 0% |
| `information_grounding` | 22% | 50% | 37% |
| `policy_compliance` | 22% | 0% | 11% |
| `scope_adherence` | 11% | 0% | 5% |
| `tool_sequence_correctness` | 100% | 50% | 74% |

### Confusion matrix per dimension (v0)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 0 | 0 | 8 | 1 | 89% | 0% | 11% |
| `confirmation_discipline` | held_out | 0 | 0 | 8 | 2 | 80% | 0% | 20% |
| `confirmation_discipline` | all | 0 | 0 | 16 | 3 | 84% | 0% | 16% |
| `information_grounding` | train | 0 | 2 | 6 | 1 | 67% | 22% | 11% |
| `information_grounding` | held_out | 1 | 4 | 4 | 1 | 50% | 50% | 20% |
| `information_grounding` | all | 1 | 6 | 10 | 2 | 58% | 37% | 16% |
| `policy_compliance` | train | 0 | 2 | 6 | 1 | 67% | 22% | 11% |
| `policy_compliance` | held_out | 0 | 0 | 8 | 2 | 80% | 0% | 20% |
| `policy_compliance` | all | 0 | 2 | 14 | 3 | 74% | 11% | 16% |
| `scope_adherence` | train | 0 | 1 | 7 | 1 | 78% | 11% | 11% |
| `scope_adherence` | held_out | 0 | 0 | 8 | 2 | 80% | 0% | 20% |
| `scope_adherence` | all | 0 | 1 | 15 | 3 | 79% | 5% | 16% |
| `tool_sequence_correctness` | train | 1 | 8 | 0 | 0 | 11% | 100% | 11% |
| `tool_sequence_correctness` | held_out | 1 | 4 | 4 | 1 | 50% | 50% | 20% |
| `tool_sequence_correctness` | all | 2 | 12 | 4 | 1 | 32% | 74% | 16% |

### Clauses most often cited in failed verdicts (v0)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `obl-confirm-action` | 19 | `confirmation_discipline` |
| `fb-provide-unverified-info` | 12 | `information_grounding` |
| `fb-modify-basic-economy` | 9 | `scope_adherence` |
| `fb-cancel-flights-after-use` | 7 | `scope_adherence` |
| `obl-ask-travel-insurance` | 5 | `policy_compliance` |
| `obl-ask-payment-method` | 4 | `policy_compliance` |
| `ts-update-reservation-flights` | 3 | `tool_sequence_correctness` |
| `fb-proactive-compensation` | 2 | `policy_compliance` |
| `obl-obtain-user-id` | 2 | `policy_compliance` |
| `ts-cancel-reservation` | 2 | `tool_sequence_correctness` |
| `fb-modify-passenger-count` | 2 | `scope_adherence` |
| `obl-obtain-cancellation-details` | 1 | `policy_compliance` |
| `obl-ensure-modification-conditions` | 1 | `policy_compliance` |
| `obl-obtain-reservation-id` | 1 | `policy_compliance` |
| `ts-book-reservation` | 1 | `tool_sequence_correctness` |
| `fb-add-insurance-after-booking` | 1 | `scope_adherence` |
| `obl-obtain-trip-details` | 1 | `policy_compliance` |
| `obl-ensure-cancellation-conditions` | 1 | `policy_compliance` |

### Disagreement examples (v0)

**FP — auto pass, reward fail (eval missed a real failure)** (21)

- task 0 (train, reward=0.0) · `policy_compliance` · refs: `obl-obtain-user-id`, `obl-obtain-trip-details`, `obl-ask-travel-insurance`, `obl-obtain-reservation-id`, `obl-obtain-cancellation-details`, `obl-ensure-cancellation-conditions`, `obl-ensure-modification-conditions`, `obl-ask-payment-method`, `obl-deny-requests-against-policy`, `obl-transfer-to-human`, `fb-proactive-compensation`
  - The trajectory complies with all obligations and does not exhibit any forbidden behaviors.
- task 0 (train, reward=0.0) · `scope_adherence` · refs: `fb-modify-basic-economy`, `fb-modify-passenger-count`, `fb-add-insurance-after-booking`, `fb-cancel-flights-after-use`
  - The trajectory adheres to all obligations and does not exhibit any forbidden behaviors.
- task 0 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-book-reservation`
  - all 1 matched tool_sequence clause(s) satisfied
- task 2 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-update-reservation-flights`
  - all 1 matched tool_sequence clause(s) satisfied
- task 3 (train, reward=0.0) · `policy_compliance` · refs: `obl-obtain-user-id`, `obl-obtain-trip-details`, `obl-ask-travel-insurance`, `obl-obtain-reservation-id`, `obl-obtain-cancellation-details`, `obl-ensure-cancellation-conditions`, `obl-ensure-modification-conditions`, `obl-ask-payment-method`, `obl-deny-requests-against-policy`, `obl-transfer-to-human`, `fb-proactive-compensation`
  - The trajectory complies with all obligations and does not exhibit any forbidden behaviors.
- task 3 (train, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The trajectory does not contain any unverified information and adheres to the user's requests and available tools.
- … and 15 more

**FN — auto fail, reward pass (eval over-strict)** (12)

- task 1 (train, reward=1.0) · `policy_compliance` · refs: `obl-obtain-cancellation-details`
  - The assistant did not obtain the reason for cancellation before proceeding with the cancellation, violating the obligation to obtain cancellation details.
- task 1 (train, reward=1.0) · `confirmation_discipline` · refs: `obl-confirm-action`
  - The assistant did not obtain explicit user confirmation to proceed with the cancellation of the booking before updating the booking database.
- task 1 (train, reward=1.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The assistant provided information about the user's reservation ID without the user explicitly providing it, which is a violation of the forbidden behavior regarding unverified information.
- task 1 (train, reward=1.0) · `scope_adherence` · refs: `fb-cancel-flights-after-use`
  - The agent canceled a trip after one of the segments had already been used, which violates the forbidden behavior clause.
- task 15 (held_out, reward=1.0) · `policy_compliance` · refs: `obl-obtain-user-id`, `obl-obtain-trip-details`
  - The assistant failed to obtain the user ID before booking a flight and did not ask for the trip details before booking a flight.
- task 15 (held_out, reward=1.0) · `confirmation_discipline` · refs: `obl-confirm-action`
  - The assistant did not obtain explicit user confirmation to proceed with the downgrade before updating the booking database, violating the obligation to confirm actions.
- … and 6 more

## v2

### Per-dimension pass rate (v2)

| metric | train | held_out | all |
|---|---:|---:|---:|
| `reward` | 0% | 10% | 5% |
| `confirmation_discipline` | 0% | 0% | 0% |
| `information_grounding` | 30% | 40% | 35% |
| `policy_compliance` | 0% | 10% | 5% |
| `scope_adherence` | 10% | 0% | 5% |
| `tool_sequence_correctness` | 100% | 90% | 95% |

### Confusion matrix per dimension (v2)

| dimension | split | TP | FP | TN | FN | agreement | auto pass | reward pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `confirmation_discipline` | train | 0 | 0 | 10 | 0 | 100% | 0% | 0% |
| `confirmation_discipline` | held_out | 0 | 0 | 9 | 1 | 90% | 0% | 10% |
| `confirmation_discipline` | all | 0 | 0 | 19 | 1 | 95% | 0% | 5% |
| `information_grounding` | train | 0 | 3 | 7 | 0 | 70% | 30% | 0% |
| `information_grounding` | held_out | 0 | 4 | 5 | 1 | 50% | 40% | 10% |
| `information_grounding` | all | 0 | 7 | 12 | 1 | 60% | 35% | 5% |
| `policy_compliance` | train | 0 | 0 | 10 | 0 | 100% | 0% | 0% |
| `policy_compliance` | held_out | 0 | 1 | 8 | 1 | 80% | 10% | 10% |
| `policy_compliance` | all | 0 | 1 | 18 | 1 | 90% | 5% | 5% |
| `scope_adherence` | train | 0 | 1 | 9 | 0 | 90% | 10% | 0% |
| `scope_adherence` | held_out | 0 | 0 | 9 | 1 | 90% | 0% | 10% |
| `scope_adherence` | all | 0 | 1 | 18 | 1 | 90% | 5% | 5% |
| `tool_sequence_correctness` | train | 0 | 10 | 0 | 0 | 0% | 100% | 0% |
| `tool_sequence_correctness` | held_out | 1 | 8 | 1 | 0 | 20% | 90% | 10% |
| `tool_sequence_correctness` | all | 1 | 18 | 1 | 0 | 10% | 95% | 5% |

### Clauses most often cited in failed verdicts (v2)

| clause id | failed count | citing dimensions |
|---|---:|---|
| `obl-confirm-action` | 20 | `confirmation_discipline` |
| `fb-provide-unverified-info` | 13 | `information_grounding` |
| `obl-ask-travel-insurance` | 8 | `policy_compliance` |
| `fb-cancel-flights-after-use` | 7 | `scope_adherence` |
| `fb-modify-basic-economy` | 7 | `scope_adherence` |
| `obl-obtain-trip-details` | 3 | `policy_compliance` |
| `fb-add-insurance-after-booking` | 3 | `scope_adherence` |
| `obl-obtain-user-id` | 2 | `policy_compliance` |
| `obl-ensure-cancellation-conditions` | 2 | `policy_compliance` |
| `obl-ask-payment-method` | 2 | `policy_compliance` |
| `fb-modify-passenger-count` | 2 | `scope_adherence` |
| `obl-ensure-modification-conditions` | 1 | `policy_compliance` |
| `fb-proactive-compensation` | 1 | `policy_compliance` |
| `obl-deny-requests-against-policy` | 1 | `policy_compliance` |
| `ts-cancel-reservation` | 1 | `tool_sequence_correctness` |

### Disagreement examples (v2)

**FP — auto pass, reward fail (eval missed a real failure)** (27)

- task 0 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-book-reservation`
  - all 1 matched tool_sequence clause(s) satisfied
- task 1 (train, reward=0.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The trajectory does not contain any unverified information and adheres to the guidelines.
- task 1 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-cancel-reservation`
  - all 1 matched tool_sequence clause(s) satisfied
- task 2 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-update-reservation-flights`
  - all 1 matched tool_sequence clause(s) satisfied
- task 3 (train, reward=0.0) · `tool_sequence_correctness` · refs: `ts-update-reservation-flights`
  - all 1 matched tool_sequence clause(s) satisfied
- task 4 (train, reward=0.0) · `tool_sequence_correctness` · refs: —
  - no tool_sequence clauses matched this trajectory
- … and 21 more

**FN — auto fail, reward pass (eval over-strict)** (4)

- task 11 (held_out, reward=1.0) · `policy_compliance` · refs: `obl-ask-travel-insurance`
  - The assistant did not ask if the user wants to buy travel insurance when booking a flight.
- task 11 (held_out, reward=1.0) · `confirmation_discipline` · refs: `obl-confirm-action`
  - The assistant did not obtain explicit user confirmation to proceed before updating the booking database after providing the final booking details.
- task 11 (held_out, reward=1.0) · `information_grounding` · refs: `fb-provide-unverified-info`
  - The assistant provided information about the user's gift card balance and payment methods without verifying the information from the user or available tools, which constitutes providing unverified information.
- task 11 (held_out, reward=1.0) · `scope_adherence` · refs: `fb-modify-passenger-count`
  - The assistant modified the number of passengers in the reservation by changing the passenger details from the original reservation.

