"""CLI validation against the pinned app layout; no device connection."""

import json

import pytest
from typer.testing import CliRunner

from rcominote.cli import app
from rcominote.device_commands import parse_record_reply
from rcominote.settings import encode_setting


@pytest.mark.parametrize(
    ("setting", "value", "payload", "readback"),
    [
        ("usb", "on", b"\x01", True),
        ("indicator", "off", b"\x00", False),
        ("noise", "16", b"\x10", 16),
        ("segment", "2h", b"\x02", 2),
    ],
)
def test_app_setting_payload_spec(setting, value, payload, readback):
    assert encode_setting(setting, value) == (payload, readback)


@pytest.mark.parametrize(
    ("setting", "value"), [("usb", "1"), ("noise", "17"), ("noise", "-1"), ("segment", "4h")]
)
def test_invalid_setting_fails_before_connection(setting, value):
    result = CliRunner().invoke(app, ["settings", "set", "--", setting, value])
    assert isinstance(result.exception, ValueError)
    assert "expects" in str(result.exception)


def test_record_reply_layout_requires_mode_byte():
    # App success layout: status0, 14-byte name, mode. Truncation was accepted
    # by its original >=15 check; strict parser requires the missing mode too.
    with pytest.raises(ValueError, match="malformed"):
        parse_record_reply("start", b"\x0020261012085542")


def test_doctor_runs_without_bluetooth():
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["bluetooth_permission"].startswith("not_probed")


def test_captured_stop_reply_decodes_completed_file():
    # Actual new CLI recording on owned device, 2026-10-12.
    data = bytes.fromhex("0032303236313031323131323432390000de500101")
    result = parse_record_reply("stop", data)
    assert (result["name"], result["size"], result["need_sync"]) == ("20261012112429", 56912, True)
