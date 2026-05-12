# Error log

Chronological. Each entry: date, what broke, root cause, fix or workaround, what to watch out for next.

## 2026-05-12 — contract generator: missing 'id' on tool_sequences

**Symptom:** `python scripts/generate_contract.py` → `ContractError: tool_sequences[0] missing key: 'id'`.

**Root cause:** The system prompt in `contract.generate_contract`
said "every clause must include an 'id' … and a 'category'" but only
gave a 'text' example for obligations/forbidden_behaviors. gpt-4o-mini
inferred from the asymmetry that tool_sequences clauses needed only
target_tool + prerequisite_tools + category, dropping `id` (and we
have no fallback id assigner — the validator rejects, by design).

**Fix:** tighten the prompt with an explicit one-line example per
section showing every required field. Keep `validate_contract` strict
— silently auto-filling ids would let a degraded generator produce
contracts whose clauses can't be referenced.

**Watch out for:** Same class of issue may surface as missing
'text', empty 'prerequisite_tools', etc. across providers. The
schema-by-example pattern in the prompt should cover all of them.

## 2026-05-12 — v0 task 9: tau-bench JSON decode error in message_to_action

**Symptom:** `[v0] task 9: ERROR (280.6s)` — `json.decoder.JSONDecodeError:
Unterminated string starting at: line 1 column 15 (char 14)`. Raised
inside `tau_bench/agents/tool_calling_agent.py:90`:
`kwargs=json.loads(tool_call["function"]["arguments"])`.

**Root cause:** gpt-4o-mini emitted a truncated/malformed JSON string
in a function-call `arguments` field. tau-bench's agent unconditionally
calls `json.loads` on whatever arguments string the model produces,
without catching the JSONDecodeError. v2 on the same task ran cleanly
— transient model output, not a deterministic bug for that task index.

**Fix:** none needed in our code. `run_eval.py`'s per-task `try/except`
caught it, wrote `{error: "..."}` to v0_results.json["tasks"]["9"],
moved on. `compare.py.confusion_matrix` excludes records that have
an 'error' key, so the metric is reported over n=19 not n=20 for v0
(this is surfaced in `variant_overview` via `n_tasks` and in the
writeup).

**Watch out for:** at scale, expect this class of LLM-output-malformed
errors at the 0.5–2% level. The error-record-and-continue pattern is
the right operational stance; alternatives (retry-with-temperature-0,
patch tau-bench's `message_to_action` to be tolerant) are out of scope
for a 2-day work trial. WRITEUP §5.3 mentions this explicitly.
