"""No radio: current-handle binding, update gating and retained transfer failures."""

import asyncio
import io
import json
import signal
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from test_hci_interval import HANDLE, LOCAL, packets, parsed, record
from test_sd_nor_probe import info

from rcominote.experiments import hci_interval as H
from rcominote.experiments import hci_interval_io as I
from rcominote.experiments import sd_interval_download as D
from rcominote.linux_client import LinuxClient

LINK = {"handle": HANDLE, "local": LOCAL, "peer": H.PEER, "controller": "hci0"}


def test_active_socket_bound_by_kernel_conninfo_and_both_addresses():
    sock = MagicMock()
    sock.getsockopt.return_value = struct.pack("<H", HANDLE) + bytes(4)
    client = MagicMock(spec=LinuxClient)
    client._link = SimpleNamespace(_check=lambda: None, _socket=sock, address=H.PEER)
    conn = SimpleNamespace(client=client, _check_failure=lambda: None)
    with patch.object(I, "socket_address", side_effect=[H.PEER, LOCAL]):
        assert I.active_link(conn) == LINK
    sock.getsockopt.assert_called_once_with(6, 2, 6)
    with (
        patch.object(I, "socket_address", side_effect=["00:00:00:00:00:01", LOCAL]),
        pytest.raises(ValueError),
    ):
        I.active_link(conn)


def test_password_only_enters_sudo_stdin_never_argv(capsys):
    password = "unit-test-credential-only"
    with (
        patch.object(I.sys, "stdin", io.StringIO(password + "\n")),
        patch.object(I.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run,
    ):
        I.authorize(password_stdin=True)
    args, kwargs = run.call_args
    assert args == (["sudo", "-S", "-p", "", "-v"],)
    assert kwargs["input"] == (password + "\n").encode()
    assert password not in repr(args)
    assert not capsys.readouterr().out
    assert D.app.pretty_exceptions_show_locals is False


def test_single_update_preserves_timeout_and_has_no_arbitrary_command():
    async def run():
        process = SimpleNamespace(returncode=0, wait=AsyncMock(return_value=0))
        with patch.object(I.asyncio, "create_subprocess_exec", AsyncMock(return_value=process)) as spawn:
            await I.request_once(HANDLE, 600)
            spawn.assert_awaited_once()
            args = spawn.call_args.args
            assert args == (
                "sudo",
                "-n",
                "timeout",
                "--kill-after=1s",
                "6s",
                "hcitool",
                "-i",
                "hci0",
                "lecup",
                "--handle=2048",
                "--min=6",
                "--max=6",
                "--latency=0",
                "--timeout=600",
            )

    asyncio.run(run())


@pytest.mark.parametrize("fault", [None, "update", "transfer", "after"])
def test_connected_requires_applied_gate_then_one_full_download(tmp_path, fault):
    events = parsed()
    monitor = SimpleNamespace(poll=lambda: events)
    report = {"sd_write_attempted": False}
    conn = object()

    async def full(actual_conn, actual_monitor, actual_report, oracle, out):
        assert actual_conn is conn and actual_monitor is monitor and out == tmp_path
        assert actual_report["applied"]["interval"] == 6
        if fault == "transfer":
            raise RuntimeError("Short download")

    identity = AsyncMock(
        side_effect=[
            info(),
            OSError("same-link final info failed") if fault in ("after", "transfer") else info(),
        ]
    )
    with (
        patch.object(D, "read_info", identity),
        patch.object(D, "active_link", return_value=LINK),
        patch.object(D, "baseline", AsyncMock(return_value=events[1])),
        patch.object(D.H, "timestamp_us", return_value=102),
        patch.object(
            D,
            "request_once",
            AsyncMock(side_effect=RuntimeError("update rejected") if fault == "update" else None),
        ) as request,
        patch.object(D, "guarded_download", AsyncMock(side_effect=full)) as download,
    ):
        if fault:
            with pytest.raises((RuntimeError, OSError)) as error:
                asyncio.run(D.connected(conn, monitor, report, bytes(4096), tmp_path))
            if fault == "transfer":
                assert str(error.value) == "Short download"
                assert "same-link" in report["after_error"]
        else:
            asyncio.run(D.connected(conn, monitor, report, bytes(4096), tmp_path))
        assert request.await_count == 1
        assert download.await_count == (0 if fault == "update" else 1)
        assert identity.await_count == 2
        assert report["sd_write_attempted"] is False


def test_watchdog_cancels_download_and_preserves_partial(tmp_path):
    conn = object()
    report = {}

    async def partial(_conn, out, actual, phase, oracle):
        assert phase == "full"
        try:
            await asyncio.sleep(10)
        finally:
            (out / "full.bin").write_bytes(b"partial")

    async def change(*_args):
        await asyncio.sleep(0.01)
        raise ValueError("Second update")

    with (
        patch.object(D, "transfer", side_effect=partial),
        patch.object(D, "watch", side_effect=change),
        pytest.raises(ValueError, match="Second update"),
    ):
        asyncio.run(D.guarded_download(conn, object(), report, bytes(4096), tmp_path))
    assert (tmp_path / "full.bin").read_bytes() == b"partial"
    assert report["download_start_us"] <= report["download_end_us"]


def test_main_auth_failure_has_no_radio_or_secret_in_report(tmp_path):
    output = tmp_path / "new"
    with (
        patch.object(D, "validate_inputs", return_value=(bytes(4096), {})),
        patch.object(D, "authorize", side_effect=PermissionError("sudo credential validation failed")),
        patch.object(D, "capture", AsyncMock()) as capture,
    ):
        with pytest.raises(PermissionError):
            D.main(tmp_path, tmp_path, output, sudo_password_stdin=True)
        capture.assert_not_called()
    report = json.loads((output / "report.json").read_bytes())
    assert not report["ok"] and not report["update_attempted"] and not report["sd_write_attempted"]


@pytest.mark.parametrize("handle", [0, 0xEFF])
def test_valid_handle_range_includes_zero(handle):
    async def run():
        process = SimpleNamespace(returncode=0, wait=AsyncMock(return_value=0))
        with patch.object(I.asyncio, "create_subprocess_exec", AsyncMock(return_value=process)) as spawn:
            await I.request_once(handle, 500)
            assert f"--handle={handle}" in spawn.call_args.args

    asyncio.run(run())


@pytest.mark.parametrize("handle", [True, False, -1, 0xF00, "2048"])
def test_invalid_handles_never_launch_privileged_child(handle):
    with patch.object(I.asyncio, "create_subprocess_exec", AsyncMock()) as spawn:
        with pytest.raises(ValueError):
            asyncio.run(I.request_once(handle, 500))
        spawn.assert_not_called()


@pytest.mark.parametrize("exit_code", [0, 124, 130, 1])
def test_monitor_private_user_capture_fixed_timeout_and_reaped_child(tmp_path, exit_code):
    monitor = I.Monitor(tmp_path)
    process = SimpleNamespace(returncode=None, send_signal=MagicMock())

    async def wait():
        process.returncode = exit_code
        return exit_code

    process.wait = AsyncMock(side_effect=wait)

    async def spawn(*args, **kwargs):
        assert monitor.path.stat().st_mode & 0o777 == 0o600
        assert monitor.path.read_bytes() == b""
        assert args == (
            "sudo",
            "-n",
            "timeout",
            "--signal=INT",
            "--kill-after=2s",
            "55s",
            "btmon",
            "-i",
            "0",
            "-w",
            str(monitor.path.resolve()),
        )
        # Model BlueZ's O_TRUNC write into the newly precreated user artifact.
        monitor.path.write_bytes(H.HEADER + record(packets()[0][1], 0))
        return process

    async def run():
        with patch.object(I.asyncio, "create_subprocess_exec", side_effect=spawn):
            await monitor.start()
            if exit_code != 1:
                assert await monitor.close() == exit_code
            else:
                with pytest.raises(RuntimeError, match="exit 1"):
                    await monitor.close()
        process.wait.assert_awaited_once()
        process.send_signal.assert_called_once_with(signal.SIGINT)
        assert monitor.stop == {"signal": "SIGINT", "requested": True, "delivery": "sent"}
        assert monitor.error_file.closed
        assert monitor.snoop.records == 1

    asyncio.run(run())


def test_existing_capture_is_never_overwritten(tmp_path):
    monitor = I.Monitor(tmp_path)
    monitor.path.write_bytes(b"prior evidence")
    with patch.object(I.asyncio, "create_subprocess_exec", AsyncMock()) as spawn:
        with pytest.raises(FileExistsError):
            asyncio.run(monitor.start())
        spawn.assert_not_called()
    assert monitor.path.read_bytes() == b"prior evidence"


def test_final_gate_excludes_cleanup_disconnect_but_not_data_phase_change():
    events = parsed()
    report = {"link": LINK, "baseline": events[1], "update_requested_us": 102}
    events.append({"kind": "disconnect", "handle": HANDLE, "record": 6, "timestamp_us": 110})
    monitor = SimpleNamespace(poll=lambda: events)
    assert D.gate(monitor, report, through=109) == events[4]
    with pytest.raises(ConnectionError):
        D.gate(monitor, report, through=110)


@pytest.mark.parametrize("fault", ["exited", "race", "denied", "truncated"])
def test_monitor_stop_races_and_final_validation(tmp_path, fault):
    monitor = I.Monitor(tmp_path)
    monitor.path.write_bytes(H.HEADER + record(packets()[0][1], 0))
    monitor.error_file = monitor.errors.open("xb")
    process = SimpleNamespace(returncode=130 if fault == "exited" else None)
    process.send_signal = MagicMock(
        side_effect={"race": ProcessLookupError(), "denied": PermissionError()}.get(fault)
    )

    async def wait():
        process.returncode = 124 if fault in ("race", "denied") else 130
        return process.returncode

    process.wait = AsyncMock(side_effect=wait)
    monitor.process = process
    if fault == "truncated":
        monitor.path.write_bytes(monitor.path.read_bytes()[:-1])
    if fault in ("exited", "truncated"):
        with pytest.raises((RuntimeError, ValueError)):
            asyncio.run(monitor.close())
    else:
        assert asyncio.run(monitor.close()) == 124
    assert monitor.error_file.closed
    process.wait.assert_awaited_once()
    assert process.send_signal.call_count == (0 if fault == "exited" else 1)
    assert monitor.stop["requested"] is (fault == "truncated")
