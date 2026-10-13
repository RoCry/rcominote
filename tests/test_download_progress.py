"""Replay literal BLE replies through the CLI to check progress/JSON separation."""

import json
import sys
from unittest.mock import AsyncMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from rcominote.cli import app
from rcominote.connection import Connection
from rcominote.protocol import FileEntry

# Independent wire fixtures: GET_FILE_DATA declares three bytes, then explicit EOF.
SIZE_THREE = bytes.fromhex("d22d010b0500000000035f6a")
DOWNLOAD_END = bytes.fromhex("d22d010b01024e1b")


@pytest.mark.parametrize(("command", "offset"), [("download", 1), ("sync", 0)])
@pytest.mark.parametrize("terminal", [False, True])
def test_download_progress_keeps_json_clean_and_counts_requested_range(tmp_path, command, offset, terminal):
    result = replay_cli(tmp_path, command, offset=offset, terminal=terminal)
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    if command == "sync":
        report = report[0]
    assert report["bytes"] == 3 - offset
    assert report["transfer_seconds"] >= 0
    assert report["average_bytes_per_second"] >= 0
    if terminal:
        assert f"{3 - offset}/{3 - offset} bytes" in result.stderr
        assert "100%" in result.stderr
        assert "ETA" in result.stderr
        assert "Saved" in result.stderr
    else:
        assert result.stderr == ""


def test_all_bytes_received_but_list_size_changed_never_shows_saved(tmp_path):
    result = replay_cli(tmp_path, "download", listed_size=4, terminal=True)
    assert isinstance(result.exception, ValueError)
    assert "Failed" in result.stderr
    assert "Saved" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def replay_cli(out, command, *, offset=0, listed_size=3, terminal):
    client = AsyncMock()
    client.services.get_service = lambda _uuid: object()
    with patch("rcominote.connection.BleakClient", return_value=client):
        conn = Connection("progress-replay")

    def on_write(_uuid, packet, **_kwargs):
        if packet[3] == 0x0B:
            conn._received("cmd", SIZE_THREE)
            for chunk in b"bc" if offset else b"abc":
                conn._received("off", bytes([chunk]))
            conn._received("cmd", DOWNLOAD_END)

    client.write_gatt_char.side_effect = on_write
    with (
        patch("rcominote.device_commands.find_device", new=AsyncMock(return_value="progress-replay")),
        patch("rcominote.device_commands.read_info", new=AsyncMock()),
        patch("rcominote.device_commands.Connection", return_value=conn),
        patch.object(
            conn, "file_list", new=AsyncMock(return_value=[FileEntry("recording", listed_size, "note")])
        ),
        patch(
            "rcominote.download_progress.Console",
            side_effect=lambda **_: Console(
                file=sys.stderr, force_terminal=terminal, width=140, color_system=None
            ),
        ),
    ):
        args = [command, "--out", str(out)]
        if command == "download":
            args[1:1] = ["recording", "--offset", str(offset)]
        return CliRunner().invoke(app, args)
