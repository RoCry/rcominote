"""Full synthetic wire audit with asynchronous status in every transaction and gap."""

import copy

import pytest
from test_window_nor_audit import fixture, validate

from rcominote.experiments import status_event as E

PLACES = (
    "setup",
    "setup-gap",
    "before-leading",
    "before",
    "before-trailing",
    "list-leading",
    "list",
    "list-trailing",
    "warm-gap",
    "first-actions-leading",
    "first-actions",
    "first-actions-trailing",
    "first-normalization-gap",
    "first-download-leading",
    "first-download",
    "first-download-trailing",
    "first-slow-gap",
    "first-identity-leading",
    "first-identity",
    "first-identity-trailing",
    "between-operations",
    "second-actions-leading",
    "second-actions",
    "second-actions-trailing",
    "second-normalization-gap",
    "second-download-leading",
    "second-download",
    "second-download-trailing",
    "second-slow-gap",
    "second-identity-leading",
    "second-identity",
    "second-identity-trailing",
    "final-leading",
    "final",
    "final-trailing",
    "final-tail",
)


@pytest.mark.parametrize("place", PLACES)
def test_event_keeps_original_wire_indices_and_never_substitutes_transaction_data(tmp_path, place):
    report = fixture(tmp_path, status_at=place)
    frozen = copy.deepcopy(report)
    result = validate(report, tmp_path)
    indices, proof = E.verify(report)
    assert len(indices) == 1 and result["status_events"] == proof
    assert result["verified"] and result["new_raw_nor_coverage_bytes"] == 0
    assert report == frozen and report["ok"] is False and report["pair_verified"] is False


@pytest.mark.parametrize(
    "fault", ["missing-ledger", "duplicate", "wrong-index", "unsupported-policy", "default"]
)
def test_full_audit_refuses_unattributed_or_implicitly_permitted_event(tmp_path, fault):
    report = fixture(tmp_path, status_at="second-normalization-gap")
    match fault:
        case "missing-ledger":
            report["status_events"] = []
        case "duplicate":
            report["status_events"].append(copy.deepcopy(report["status_events"][0]))
        case "wrong-index":
            report["status_events"][0]["index"] += 1
        case "unsupported-policy":
            report["status_event_policy"] = "any-notification"
        case "default":
            del report["status_event_policy"], report["status_events"]
    with pytest.raises(ValueError):
        validate(report, tmp_path)
