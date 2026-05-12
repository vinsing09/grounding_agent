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
