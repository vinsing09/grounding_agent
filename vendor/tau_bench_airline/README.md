# Vendored: τ-bench airline customer-support

## What this is

`grounding_agent` evaluates the τ-bench airline customer-support agent. τ-bench is installed as a Python package dependency (see top-level `pyproject.toml`). This folder vendors the **human-readable** parts of that agent so reviewers can read them without leaving this repo:

- `policy.md` — the agent's full operating policy (the system prompt context the agent runs with).
- `LICENSE.tau-bench` — τ-bench's upstream MIT license.
- Tool catalog (below) — the 14 tools the agent has access to.
- Task samples (below) — three example tasks from the test set the framework evaluates against.

The executable parts (env, reward function, task structures, tool implementations) come from the pip-installed `tau_bench` package, **not** from this folder. Vendoring those would bloat the repo unnecessarily.

## Attribution

> τ-bench (`tau_bench` package on PyPI / [GitHub: sierra-research/tau-bench](https://github.com/sierra-research/tau-bench)) is the work of Sierra Research, released under the MIT License (see `LICENSE.tau-bench`). The policy text in `policy.md` and the task instructions quoted below are unmodified excerpts from that project.
>
> Citation: Yao et al., 2024. *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.*

`grounding_agent` is independent work that uses τ-bench as the system-under-test and ground-truth source.

## Tool catalog (14 tools)

| Tool | Description |
|---|---|
| `book_reservation` | Book a reservation. |
| `calculate` | Calculate the result of a mathematical expression. |
| `cancel_reservation` | Cancel the whole reservation. |
| `get_reservation_details` | Get the details of a reservation. |
| `get_user_details` | Get the details of an user, including their reservations. |
| `list_all_airports` | List all airports and their cities. |
| `search_direct_flight` | Search direct flights between two cities on a specific date. |
| `search_onestop_flight` | Search one-stop flights between two cities on a specific date. |
| `send_certificate` | Send a certificate to a user. Be careful! |
| `think` | Append a thought to the log. Does not obtain information or change state. Used for explicit reasoning. |
| `transfer_to_human_agents` | Transfer the user to a human agent. Only on explicit user request or when the issue cannot be resolved with the available tools. |
| `update_reservation_baggages` | Update the baggage information of a reservation. |
| `update_reservation_flights` | Update the flight information of a reservation. |
| `update_reservation_passengers` | Update the passenger information of a reservation. |

## Task samples (3 of 50 in the test split)

**Task 0 — book a flight.** User `mia_li_3668`: "*Your user id is mia_li_3668. You want to fly from New York to Seattle on May 20 (one way). You do not want to fly before 11am est. You want to fly in economy. You prefer direct flights but one stopover also fine. … You have 3 baggages. You do not want insurance. You want to use your two certificates to pay…*" Ground truth: a single `book_reservation` call with the correct flight numbers, payment split, and baggage count.

**Task 1 — cancel within policy.** User `olivia_gonzalez_2305`: "*You currently reside in Newark, and you will have a crazy half-day trip to Texas. … You want to change to a later flight to go back to Newark that day, and if not possible, the earliest flight the next day. … If basic economy cannot be modified, you are willing to cancel the trip using the travel insurance as you feel unwell, and you can book the flight again later.*" Ground truth: `cancel_reservation` with the specific reservation_id, only after the agent confirms basic economy cannot be modified.

**Task 2 — multi-step downgrade.** User `omar_davis_3817`: "*You just faced some money issue and want to downgrade all business flights to economy, without changing the flights or passengers. … You want to know how much money you have saved in total. You are emotional and a bit angry, but you are willing to cooperate with the agent.*" Ground truth: 4+ `update_reservation_flights` calls (one per reservation), then a final response with the saved total.

## How the agent is graded by τ-bench

The τ-bench reward function (`Env.calculate_reward`) compares:
1. The final database state (reservations, baggage, payment splits) against the expected state implied by the gold actions.
2. The set of executed tool calls against the gold action list.

If both match, reward = 1.0. Otherwise reward = 0.0. Binary, deterministic, reproducible. This is the **ground truth** that `grounding_agent`'s multi-dimensional automated eval is compared against.
