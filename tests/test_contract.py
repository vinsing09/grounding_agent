import json
from pathlib import Path

import pytest

from grounding_agent.contract import (
    ContractError,
    load_contract,
    save_contract,
    validate_contract,
)


def _fixture() -> dict:
    """Realistic-shape contract: same structure the generator will emit
    against the tau-bench airline policy. Two clauses per section so
    duplicate-id and id-uniqueness tests have something to bite."""
    return {
        "agent": "tau_bench_airline",
        "obligations": [
            {
                "id": "obl-confirm-mutation",
                "text": (
                    "Before any state-mutating tool call (book_reservation, "
                    "cancel_reservation, update_reservation_baggages, "
                    "update_reservation_flights, update_reservation_passengers, "
                    "send_certificate), summarize the action and obtain an "
                    "explicit 'yes' from the user."
                ),
                "category": "confirmation_discipline",
            },
            {
                "id": "obl-deny-out-of-policy",
                "text": (
                    "Deny user requests that violate policy (e.g. modifying a "
                    "basic-economy flight, cancelling a non-business flight "
                    "outside 24h without travel insurance)."
                ),
                "category": "policy_compliance",
            },
        ],
        "forbidden_behaviors": [
            {
                "id": "fb-no-subjective",
                "text": (
                    "Do not provide information, knowledge, or procedures not "
                    "given by the user or returned by tools; do not give "
                    "subjective recommendations."
                ),
                "category": "information_grounding",
            },
            {
                "id": "fb-no-improper-transfer",
                "text": (
                    "Do not transfer to a human agent for requests that fall "
                    "within the available tools and policy."
                ),
                "category": "scope_adherence",
            },
        ],
        "tool_sequences": [
            {
                "id": "ts-book-needs-user",
                "target_tool": "book_reservation",
                "prerequisite_tools": ["get_user_details"],
                "category": "tool_sequence_correctness",
            },
            {
                "id": "ts-update-flights-needs-both",
                "target_tool": "update_reservation_flights",
                "prerequisite_tools": [
                    "get_user_details",
                    "get_reservation_details",
                ],
                "category": "tool_sequence_correctness",
            },
        ],
    }


def test_validate_accepts_realistic_contract():
    validate_contract(_fixture())


def test_validate_rejects_non_object_root():
    with pytest.raises(ContractError, match="JSON object"):
        validate_contract([])  # type: ignore[arg-type]


def test_validate_rejects_missing_top_level_key():
    c = _fixture()
    del c["obligations"]
    with pytest.raises(ContractError, match="obligations"):
        validate_contract(c)


def test_validate_rejects_empty_agent():
    c = _fixture()
    c["agent"] = "   "
    with pytest.raises(ContractError, match="agent"):
        validate_contract(c)


def test_validate_rejects_non_list_section():
    c = _fixture()
    c["obligations"] = {"not": "a list"}
    with pytest.raises(ContractError, match="obligations.*list"):
        validate_contract(c)


def test_validate_rejects_clause_missing_required_key():
    c = _fixture()
    del c["tool_sequences"][0]["prerequisite_tools"]
    with pytest.raises(ContractError, match="prerequisite_tools"):
        validate_contract(c)


def test_validate_rejects_empty_clause_id():
    c = _fixture()
    c["obligations"][0]["id"] = ""
    with pytest.raises(ContractError, match="non-empty string"):
        validate_contract(c)


def test_validate_rejects_duplicate_clause_id_within_section():
    c = _fixture()
    c["obligations"][1]["id"] = c["obligations"][0]["id"]
    with pytest.raises(ContractError, match="duplicate clause id"):
        validate_contract(c)


def test_validate_rejects_duplicate_clause_id_across_sections():
    c = _fixture()
    c["forbidden_behaviors"][0]["id"] = c["obligations"][0]["id"]
    with pytest.raises(ContractError, match="duplicate clause id"):
        validate_contract(c)


def test_validate_rejects_unknown_category():
    c = _fixture()
    c["obligations"][0]["category"] = "made_up_category"
    with pytest.raises(ContractError, match="unknown category"):
        validate_contract(c)


def test_validate_rejects_empty_obligation_text():
    c = _fixture()
    c["obligations"][0]["text"] = ""
    with pytest.raises(ContractError, match="text.*non-empty"):
        validate_contract(c)


def test_validate_rejects_non_list_prerequisites():
    c = _fixture()
    c["tool_sequences"][0]["prerequisite_tools"] = "get_user_details"
    with pytest.raises(ContractError, match="prerequisite_tools"):
        validate_contract(c)


def test_validate_rejects_empty_prerequisite_entry():
    c = _fixture()
    c["tool_sequences"][0]["prerequisite_tools"] = ["get_user_details", ""]
    with pytest.raises(ContractError, match="prerequisite_tools"):
        validate_contract(c)


def test_validate_rejects_empty_target_tool():
    c = _fixture()
    c["tool_sequences"][0]["target_tool"] = ""
    with pytest.raises(ContractError, match="target_tool"):
        validate_contract(c)


def test_save_and_load_roundtrip(tmp_path: Path):
    c = _fixture()
    out = tmp_path / "sub" / "contract.json"
    save_contract(c, out)
    assert out.exists()
    loaded = load_contract(out)
    assert loaded == c
    assert out.read_text(encoding="utf-8").endswith("\n")


def test_load_validates_on_read(tmp_path: Path):
    c = _fixture()
    c["obligations"][0]["category"] = "definitely_not_a_category"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(ContractError):
        load_contract(p)


def test_save_validates_before_write(tmp_path: Path):
    c = _fixture()
    c["obligations"][0]["category"] = "bogus"
    out = tmp_path / "wont_exist.json"
    with pytest.raises(ContractError):
        save_contract(c, out)
    assert not out.exists()
