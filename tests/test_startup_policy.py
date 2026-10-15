"""Synthetic original HCI transactions; DEFAULT never implies FAST readiness."""

import asyncio
import copy
from unittest.mock import patch

import pytest
from test_param_window import LINK, capture, remote, update

from rcominote.experiments import startup_policy as K
from rcominote.experiments import window_ram_probe as R


def transaction(*, default=False):
    rows = remote(24, 40) + [update(36)] if default else remote(6, 12) + [update(12)]
    return K.parameters.inspect(capture(rows), link=LINK, final=True)["transactions"][0]


def test_exact_default_requires_explicit_policy_and_separate_fast_settlement():
    value = transaction(default=True)
    original = copy.deepcopy(value)
    with pytest.raises(ValueError, match="explicit FAST/DEFAULT policy"):
        K.classify(value)
    proof = K.classify(value, policy=K.POLICY)
    assert proof["mode"] == "default" and proof["parameters"] == [24, 40, 0, 500]
    assert proof["requires_fast_before_normalization"] is True
    assert value == original
    assert K.classify(transaction())["mode"] == "fast"
    assert K.classify(transaction(), policy=K.POLICY)["requires_fast_before_normalization"] is False


@pytest.mark.parametrize(
    "fault", ["tuple", "origin", "accept", "status", "applied", "handle", "records", "missing"]
)
def test_classifier_rejects_incomplete_or_changed_original_transaction(fault):
    value = transaction(default=True)
    if fault == "tuple":
        value["request"]["max"] = 72
    elif fault == "origin":
        value["origin"] = "host"
    elif fault == "accept":
        value["remote_accept"]["identifier"] += 1
    elif fault == "status":
        value["status"]["status"] = 1
    elif fault == "applied":
        value["update"]["interval"] = 12
    elif fault == "handle":
        value["update"]["handle"] += 1
    elif fault == "records":
        value["status"]["record"] = value["request"]["record"]
    else:
        value["remote_accept"] = None
    with pytest.raises(ValueError):
        K.classify(value, policy=K.POLICY)


def test_wait_preserves_actual_transaction_and_does_not_use_default_without_policy():
    value = transaction(default=True)
    snapshot = {"transactions": [value], "pending": []}
    with patch.object(R, "observe", return_value=snapshot):
        actual, proof = asyncio.run(K.wait_startup(None, None, LINK, policy=K.POLICY))
        assert actual is value and proof["requires_fast_before_normalization"] is True
        with pytest.raises(ValueError):
            asyncio.run(K.wait_startup(None, None, LINK))


@pytest.mark.parametrize("fault", ["extra", "pending", "unknown-policy", "timeout"])
def test_wait_rejects_extra_pending_or_unsupported_stage(fault):
    snapshot = {"transactions": [transaction()], "pending": []}
    if fault == "extra":
        snapshot["transactions"].append(transaction())
    elif fault == "pending":
        snapshot["pending"] = [{"kind": "awaiting-update"}]
    elif fault == "timeout":
        snapshot["transactions"] = []
    with patch.object(R, "observe", return_value=snapshot) as observe:
        with pytest.raises(TimeoutError if fault == "timeout" else ValueError):
            asyncio.run(
                K.wait_startup(
                    None, None, LINK, policy="other" if fault == "unknown-policy" else K.POLICY, seconds=0.01
                )
            )
        if fault == "unknown-policy":
            observe.assert_not_called()
