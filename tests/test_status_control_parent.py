"""Control wrapper linkage only; complete control replay is explicitly mocked."""

import copy
import json
from unittest.mock import patch

import pytest
from test_sd_nor_probe import info

from rcominote.experiments import status_control_parent as K


def fixture(root, monkeypatch):
    state_parent = {"latest_info": info(), "ended_at": "2026-10-14T10:00:00+00:00", "synthetic_source": True}
    plan = {
        "state_parent": state_parent,
        "expected_before": info(),
        "planned_at": "2026-10-14T10:01:00+00:00",
        "source_image_sha256": K.control.C.RAM.IMAGE_SHA,
    }
    (root / "plan.json").write_text(json.dumps(plan))
    job = {
        "plan": K.J.reference(root, root / "plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": "2026-10-14T10:07:00+00:00",
    }
    (root / "report.json").write_text(json.dumps(job))
    for index, kind in enumerate(("seed", "data")):
        (root / kind).mkdir()
        report = {
            "expected_before": info(),
            "before": info(),
            "after": info(),
            "started_at": f"2026-10-14T10:0{3 + 2 * index}:00+00:00",
            "ended_at": f"2026-10-14T10:0{4 + 2 * index}:00+00:00",
        }
        (root / kind / "report.json").write_text(json.dumps(report))
        (root / kind / "session.btsnoop").write_bytes(b"mocked replay input; no synthetic HCI claim")
    monkeypatch.setattr(K, "PINS", {name: K.control.A.sha((root / name).read_bytes()) for name in K.PINS})
    return state_parent


def test_control_requires_full_replay_and_exact_latest_state_wrapper(tmp_path, monkeypatch):
    parent = fixture(tmp_path, monkeypatch)
    with patch.object(K.control, "replay", return_value=dict(K.EXPECTED)) as replay:
        wrapper = K.verify(tmp_path, tmp_path, parent)
    replay.assert_called_once_with(tmp_path, tmp_path)
    K.validate_wrapper(wrapper, parent, planned_at="2026-10-14T10:08:00+00:00")
    assert wrapper["latest_info"] == parent["latest_info"] and wrapper["pins"] == K.PINS


@pytest.mark.parametrize("fault", ["pin", "state-source", "replay", "time"])
def test_control_mismatch_never_supplies_nor_admission(tmp_path, monkeypatch, fault):
    parent = fixture(tmp_path, monkeypatch)
    if fault == "pin":
        (tmp_path / "data/session.btsnoop").write_bytes(b"changed")
    elif fault == "state-source":
        parent = copy.deepcopy(parent) | {"latest_info": info(1)}
    with patch.object(
        K.control,
        "replay",
        return_value=dict(K.EXPECTED),
        side_effect=ValueError("original control failed") if fault == "replay" else None,
    ) as replay:
        if fault == "time":
            wrapper = K.verify(tmp_path, tmp_path, parent)
            with pytest.raises(ValueError):
                K.validate_wrapper(wrapper, parent, planned_at="2026-10-14T10:05:00+00:00")
        else:
            with pytest.raises(ValueError):
                K.verify(tmp_path, tmp_path, parent)
        if fault == "pin":
            replay.assert_not_called()
