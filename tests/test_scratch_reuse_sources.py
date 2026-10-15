"""Synthetic source linkage; real public static regions/oracles, no private CI data.

Original parent HCI replay is explicitly stubbed in metadata tests. Separate
private replay is an operator preflight, never a CI fixture or live-device test.
"""

import copy
import json
from unittest.mock import patch

import pytest
from test_dual_probe import info

from rcominote.experiments import scratch_reuse_sources as S


def save(path, value):
    path.write_text(json.dumps(value))
    return S.sha(path.read_bytes())


@pytest.fixture
def static_fixture(tmp_path, monkeypatch):
    proof = json.loads(S.STATIC_RECEIPT.read_bytes())
    data = bytearray(927632)
    for region in proof["regions"]:
        start, end = [int(region[key], 16) - 0x10000000 for key in ("start", "end_exclusive")]
        data[start:end] = bytes.fromhex(region["hex"])
    image = tmp_path / "synthetic-image.bin"
    image.write_bytes(data)
    proof["image"]["sha256"] = S.sha(data)
    receipt = tmp_path / "synthetic-static.json"
    monkeypatch.setattr(S, "STATIC_RECEIPT", receipt)
    monkeypatch.setattr(S, "STATIC_SHA", save(receipt, proof))
    monkeypatch.setattr(S, "IMAGE_SHA", S.sha(data))
    return image, receipt, proof


def test_complete_static_chain_matches_actual_supplied_image_regions_without_live_claim(static_fixture):
    image, _, proof = static_fixture
    result = S.static_gate(image)
    assert result["verified_regions"] == 36
    assert result["regions"] == proof["regions"]
    assert result["current_live_code_verified"] is False


@pytest.mark.parametrize(
    "fault", ["receipt-pin", "image-pin", "missing", "duplicate", "id", "range", "size", "hex", "sha"]
)
def test_static_identity_requires_all_original_regions_and_exact_bytes(static_fixture, monkeypatch, fault):
    image, receipt, proof = static_fixture
    if fault == "receipt-pin":
        receipt.write_text("{}")
    elif fault == "image-pin":
        image.write_bytes(image.read_bytes()[:-1])
    else:
        region = proof["regions"][0]
        if fault == "missing":
            proof["regions"].pop()
        elif fault == "duplicate":
            proof["regions"][-1] = copy.deepcopy(region)
        elif fault == "id":
            region["id"] = "unreviewed_region"
        elif fault == "range":
            region["start"] = "0x0"
        elif fault == "size":
            region["bytes"] = True
        elif fault == "hex":
            region["hex"] = "00" * region["bytes"]
        else:
            region["sha256"] = "0" * 64
        monkeypatch.setattr(S, "STATIC_SHA", save(receipt, proof))
    with pytest.raises(ValueError):
        S.static_gate(image)


@pytest.fixture
def sources(tmp_path, monkeypatch):
    known, state = tmp_path / "known", tmp_path / "final"
    (known / "boot").mkdir(parents=True)
    (state / "2e00").mkdir(parents=True)
    baseline = b"synthetic original owned download".ljust(4096, b"B")
    (known / "boot/download.bin").write_bytes(baseline)
    monkeypatch.setattr(S, "BASELINE_SHA", S.sha(baseline))
    known_raw, final_raw = b"synthetic known capture", b"synthetic final capture"
    (known / "session.btsnoop").write_bytes(known_raw)
    (state / "2e00/session.btsnoop").write_bytes(final_raw)
    monkeypatch.setattr(S, "KNOWN_HCI_SHA", S.sha(known_raw))
    monkeypatch.setattr(S, "FINAL_HCI_SHA", S.sha(final_raw))
    path = f"/SD:/RECORDER/Call-{S.NAME}.mp3"
    boot = {
        "name": S.NAME,
        "phase": "boot",
        "device_path": path,
        "producer": S.T.PRODUCER,
        "source_address": hex(S.BUFFER),
        "source_bytes": 4096,
        "dump_command": f"dbg dumpbuf {S.BUFFER} 4096 {path}",
        "transport_profile": "interval6-ce1",
        "download_bytes": 4096,
        "received_bytes": 4096,
        "download_sha256": S.BASELINE_SHA,
        "ok": True,
        "live_complete": True,
        "sd_write_attempted": True,
    }
    original = {
        "profile": "dual-known-boot0-recovery4200",
        "serial": S.OWNED_SERIAL,
        "source_image_sha256": S.IMAGE_SHA,
        "ok": True,
        "operations": [boot, {"phase": "recovery-block1"}],
        "after": info(6),
        "started_at": "2026-10-13T23:57:06+00:00",
        "ended_at": "2026-10-13T23:57:19+00:00",
    }
    result = {
        "partition_range": [0x2000, 0x3000],
        "partition_bytes": 4096,
        "partition_sha256": S.FULL_BOOT_SHA,
    }
    final = {
        "ok": True,
        "verification": result,
        "started_at": "2026-10-14T05:08:19+00:00",
        "ended_at": "2026-10-14T05:08:41.755729+00:00",
    }
    pair = {
        "ok": True,
        "pair_verified": True,
        "final_audit_complete": True,
        "source_image_sha256": S.IMAGE_SHA,
        "after": info(9),
        "started_at": "2026-10-14T05:08:24+00:00",
        "ended_at": "2026-10-14T05:08:41+00:00",
    }
    monkeypatch.setattr(S, "KNOWN_REPORT_SHA", save(known / "report.json", original))
    monkeypatch.setattr(S, "FINAL_REPORT_SHA", save(state / "report.json", final))
    monkeypatch.setattr(S, "FINAL_PAIR_SHA", save(state / "2e00/report.json", pair))
    return {
        "known": known,
        "state": state,
        "baseline": baseline,
        "original": original,
        "final": final,
        "pair": pair,
        "result": result,
        "image": tmp_path / "unused-image",
    }


def replay_stubs(source):
    return (
        patch.object(
            S, "static_gate", return_value={"verified_regions": 36, "current_live_code_verified": False}
        ),
        patch.object(
            S.S,
            "replay",
            return_value={
                "verified": True,
                "connections": 1,
                "targets": [0, 0x4200],
                "sector_sha256": [S.T.BOOT_SHA, S.T.RECOVERY_BLOCK_SHA],
            },
        ),
        patch.object(S.J, "replay", return_value=source["result"]),
    )


def test_pinned_sources_keep_owned_baseline_and_latest_actual_final_state_distinct(sources):
    static, known, final = replay_stubs(sources)
    with static, known as known_replay, final as final_replay:
        baseline, state, summary = S.verify(sources["image"], sources["known"], sources["state"])
    assert baseline == sources["baseline"] and state == info(9)
    assert summary["known_parent"]["latest_info"] == info(6)
    assert summary["state_parent"]["latest_info"] == info(9)
    assert summary["state_parent"]["ended_at"] == "2026-10-14T05:08:41.755729+00:00"
    assert summary["current_object_live_download_required_before_overwrite"] is True
    assert summary["same_file_overwrite_live_verified"] is False
    assert summary["new_raw_nor_coverage_bytes"] == 0
    assert {key: value["nor_offset"] for key, value in summary["oracles"].items()} == {
        "boot0": 0,
        "4200": 0x4200,
    }
    known_replay.assert_called_once_with(sources["known"], sources["image"])
    final_replay.assert_called_once_with(sources["state"], sources["image"])


@pytest.mark.parametrize(
    "fault", ["known-report", "known-hci", "baseline", "final-report", "final-pair", "final-hci"]
)
def test_changed_original_pin_prevents_its_full_parent_replay(sources, fault):
    paths = {
        "known-report": sources["known"] / "report.json",
        "known-hci": sources["known"] / "session.btsnoop",
        "baseline": sources["known"] / "boot/download.bin",
        "final-report": sources["state"] / "report.json",
        "final-pair": sources["state"] / "2e00/report.json",
        "final-hci": sources["state"] / "2e00/session.btsnoop",
    }
    paths[fault].write_bytes(b"changed")
    static, known, final = replay_stubs(sources)
    with static, known as known_replay, final as final_replay, pytest.raises(ValueError, match="Pinned"):
        S.verify(sources["image"], sources["known"], sources["state"])
    (known_replay if fault.startswith("known") or fault == "baseline" else final_replay).assert_not_called()


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "device_path",
        "dump_command",
        "source_bytes",
        "producer",
        "sd_write_attempted",
        "live_complete",
        "download_bytes",
        "download_sha256",
    ],
)
def test_only_exact_original_written_and_confirmed_scratch_is_admitted(sources, monkeypatch, field):
    report = sources["original"]
    report["operations"][0][field] = False if field in ("sd_write_attempted", "live_complete") else "changed"
    monkeypatch.setattr(S, "KNOWN_REPORT_SHA", save(sources["known"] / "report.json", report))
    static, known, final = replay_stubs(sources)
    with static, known as known_replay, final, pytest.raises(ValueError, match="download-confirmed"):
        S.verify(sources["image"], sources["known"], sources["state"])
    known_replay.assert_not_called()


@pytest.mark.parametrize(
    "fault", ["original-ok", "pair-ok", "pair-audit", "latest-free", "wrong-owned-identity", "time"]
)
def test_latest_state_requires_original_full_final_success_and_exact_actual_state(
    sources, monkeypatch, fault
):
    final, pair = sources["final"], sources["pair"]
    if fault == "original-ok":
        final["ok"] = False
    elif fault == "pair-ok":
        pair["ok"] = False
    elif fault == "pair-audit":
        pair["final_audit_complete"] = False
    elif fault == "latest-free":
        pair["after"] = info(8)
    elif fault == "wrong-owned-identity":
        pair["after"]["serial"] = "other-owned-claim"
    else:
        pair["ended_at"] = "2026-10-14T05:09:00+00:00"
    monkeypatch.setattr(S, "FINAL_REPORT_SHA", save(sources["state"] / "report.json", final))
    monkeypatch.setattr(S, "FINAL_PAIR_SHA", save(sources["state"] / "2e00/report.json", pair))
    static, known, replay = replay_stubs(sources)
    with static, known, replay, pytest.raises(ValueError):
        S.verify(sources["image"], sources["known"], sources["state"])


@pytest.mark.parametrize("target", ["known", "final"])
def test_failed_complete_known_or_final_replay_cannot_produce_sources(sources, target):
    static, known, final = replay_stubs(sources)
    with (
        static,
        known,
        final,
        patch.object(
            S.S if target == "known" else S.J, "replay", side_effect=ValueError("complete chain rejected")
        ),
        pytest.raises(ValueError, match="complete chain rejected"),
    ):
        S.verify(sources["image"], sources["known"], sources["state"])


@pytest.mark.parametrize("fault", ["short", "target", "hash"])
def test_oracles_remain_independent_fixed_targets_and_reject_changed_data(fault):
    original = S.T.oracle

    def short(phase):
        offset, data, proof = original(phase)
        if fault == "short":
            data = data[:-1]
        elif fault == "target":
            offset += 512
        else:
            proof = proof | {"sector_sha256": "0" * 64}
        return offset, data, proof

    with (
        patch.object(S.T, "oracle", side_effect=short),
        pytest.raises(ValueError, match="oracle source/slice"),
    ):
        S.oracles()
