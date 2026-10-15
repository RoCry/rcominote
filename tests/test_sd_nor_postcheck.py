"""A later identity check can complete only the bounded postinfo-failed context."""

import json
import struct
from unittest.mock import AsyncMock, patch

import pytest
from test_sd_nor_probe import attach_actions, info, receipt, save

from rcominote.experiments import sd_nor_postcheck as post
from rcominote.experiments import sd_nor_probe as probe

pytest_plugins = ("test_sd_nor_probe",)


@pytest.fixture
def original_context(guards, tmp_path):
    image, directories = guards
    verified = probe.validate_guards(directories, image, None)
    data = struct.pack("<5I", 100, 100, 0, 4096, probe.BUFFER) + b"\x01\0" + bytes(6)
    report = attach_actions(receipt("rc0000000100", probe.CONTEXT, 28, phase=probe.Phase.context))
    report.pop("after")
    report.update(
        ok=False,
        guards=verified,
        verification=probe.context_fields(data),
        error=post.POSTINFO_ERROR,
        after_error=post.POSTINFO_ERROR,
        started_at="2026-10-13T15:57:00+00:00",
        ended_at="2026-10-13T15:58:00+00:00",
    )
    directory = save(tmp_path / "original", report, data)
    image_file = tmp_path / "image.bin"
    image_file.write_bytes(image)
    return image_file, directory, verified, data


def test_one_identity_reuses_raw_and_previous_accepts_bound_derived(original_context, tmp_path):
    image, directory, verified, data = original_context
    old_report = (directory / "report.json").read_bytes()
    out = tmp_path / "postcheck"
    with (
        patch.object(
            post.sd_bootstrap, "identity", AsyncMock(return_value=(info(free_decrease=1), []))
        ) as identity,
        patch.object(post.sd_bootstrap, "write_file", AsyncMock()) as write,
        patch.object(post.sd_bootstrap, "download_file", AsyncMock()) as download,
    ):
        post.main(image, directory, out)
        identity.assert_awaited_once()
        write.assert_not_awaited()
        download.assert_not_awaited()
    report = json.loads((out / "report.json").read_text())
    original = json.loads(old_report)
    assert report["ok"] is True and report["download_reused"] is True
    assert report["origin_error"] == post.POSTINFO_ERROR
    assert report["started_at"] == original["started_at"] and report["att_packets"] == original["att_packets"]
    assert report["origin_ended_at"] == original["ended_at"]
    assert report["state_verification"]["free_capacity_decrease"] == 1
    assert (out / "download.bin").read_bytes() == data
    assert (directory / "download.bin").read_bytes() == data
    assert (directory / "report.json").read_bytes() == old_report
    assert probe.previous(out, probe.Phase.context, verified, image.read_bytes(), None)["report_sha256"]
    # The original remains failed and cannot directly satisfy the baseline gate.
    with pytest.raises(ValueError, match="Previous receipt"):
        probe.previous(directory, probe.Phase.context, verified, image.read_bytes(), None)


@pytest.mark.parametrize(
    "change",
    [
        "phase",
        "success",
        "primary-error",
        "post-error",
        "after-present",
        "other-error",
        "source",
        "producer",
        "fake-actions",
        "guard-hash",
        "struct",
        "short-download",
    ],
)
def test_offline_gate_failure_never_calls_identity(original_context, tmp_path, change):
    image, directory, _verified, _data = original_context
    path = directory / "report.json"
    report = json.loads(path.read_text())
    if change == "phase":
        report["phase"] = "baseline"
    elif change == "success":
        report["ok"] = True
    elif change == "primary-error":
        report["error"] = "ValueError: producer failed"
    elif change == "post-error":
        report["after_error"] = "OSError: other failure"
    elif change == "after-present":
        report["after"] = info()
    elif change == "other-error":
        report["cleanup_error"] = "STOP failed"
    elif change == "source":
        report["source_address"] = "0x1800a9b8"
    elif change == "producer":
        report["producer"] = probe.PRODUCER
    elif change == "fake-actions":
        report["att_packets"] = []
    elif change == "guard-hash":
        report["guards"][0]["report_sha256"] = "0" * 64
    elif change == "struct":
        report["verification"]["capacity"] = 8192
    else:
        (directory / "download.bin").write_bytes(b"short")
    path.write_text(json.dumps(report))
    out = tmp_path / "rejected"
    with patch.object(post.sd_bootstrap, "identity", AsyncMock()) as identity:
        with pytest.raises(ValueError):
            post.main(image, directory, out)
        identity.assert_not_awaited()
    assert not out.exists()


def test_later_identity_failure_is_retained_without_retry_or_old_rewrite(original_context, tmp_path):
    image, directory, _verified, data = original_context
    before = (directory / "report.json").read_bytes()
    out = tmp_path / "postcheck-failed"
    with patch.object(
        post.sd_bootstrap, "identity", AsyncMock(side_effect=OSError(38, "LE ATT connect failed"))
    ) as identity:
        with pytest.raises(OSError, match="LE ATT connect failed"):
            post.main(image, directory, out)
        identity.assert_awaited_once()
    report = json.loads((out / "report.json").read_text())
    assert report["ok"] is False and report["origin_error"] == report["error"] == report["after_error"]
    assert (out / "download.bin").read_bytes() == data and (directory / "report.json").read_bytes() == before


def test_later_state_change_is_failure_and_existing_output_refused(original_context, tmp_path):
    image, directory, _verified, _data = original_context
    out = tmp_path / "bad-state"
    with patch.object(
        post.sd_bootstrap, "identity", AsyncMock(return_value=(info(free_decrease=2), []))
    ) as identity:
        with pytest.raises(ValueError, match="Unexpected state change"):
            post.main(image, directory, out)
        identity.assert_awaited_once()
    assert json.loads((out / "report.json").read_text())["ok"] is False
    with patch.object(post.sd_bootstrap, "identity", AsyncMock()) as identity:
        with pytest.raises(FileExistsError):
            post.main(image, directory, out)
        identity.assert_not_awaited()


def test_previous_revalidates_original_parent_bytes(original_context, tmp_path):
    image, directory, verified, _data = original_context
    out = tmp_path / "derived"
    with patch.object(post.sd_bootstrap, "identity", AsyncMock(return_value=(info(), []))):
        post.main(image, directory, out)
    path = directory / "report.json"
    original = json.loads(path.read_text())
    original["note"] = "Modified after the postcheck; identical acquisition payload"
    path.write_text(json.dumps(original))
    with pytest.raises(ValueError, match="parent hash/path changed"):
        probe.previous(out, probe.Phase.context, verified, image.read_bytes(), None)
