"""Single installed CLI; machine-readable results and nonzero errors."""

import importlib.metadata
import json
import platform
import sys

from bleak.exc import BleakError

from . import diagnostics, gatt, settings, usb_inventory, verification
from .device_commands import app
from .output import emit

app.info.help = "CoMi Note control, recording export, and bounded firmware diagnostics."
app.pretty_exceptions_enable = False
app.add_typer(settings.app, name="settings", help="Read settings or explicitly change one with readback.")
app.add_typer(diagnostics.app, name="diag", help="Fixed diagnostic profiles and offline code comparison.")
app.add_typer(usb_inventory.app, name="usb", help="Host descriptor snapshots/diffs; no device writes.")
app.command("gatt")(gatt.main)
app.command("verify")(verification.main)


@app.command()
def doctor():
    """Offline environment report; does not scan, connect or repair the host."""
    emit(
        {
            "python": platform.python_version(),
            "platform": platform.system(),
            "versions": {
                name: importlib.metadata.version(name) for name in ("rcominote", "bleak", "typer", "capstone")
            },
            "bluetooth_permission": "not_probed; run scan to test host access",
            "usb_snapshot": "available" if sys.platform == "darwin" else "macOS only; diff remains offline",
            "firmware_backup": "not_available; only fixed mapped-code sample",
            "flash_recovery": "not_verified",
        }
    )


@app.command()
def capabilities():
    """Distinguish current implementation, observed proof and unavailable capabilities."""
    emit(
        {
            "observed": [
                "BLE discovery/GATT",
                "device info",
                "recording list/export",
                "record start/pause/resume/stop",
                "noise setting write/readback/restore",
                "log/version/help",
                "NVRAM fixed name getter",
                "69-byte fixed mapped code/literal/reference readback",
            ],
            "implemented_requires_explicit_selection": [
                "record start/pause/resume/stop",
                "clock synchronization",
                "settings with readback",
            ],
            "not_implemented": [
                "arbitrary shell/memory",
                "bind/unbind/delete/format",
                "full firmware dump",
                "flash",
                "ADFU switch",
                "official firmware restore",
            ],
            "limits": [
                "ACK is not proof of command semantics",
                "mapped code is not physical flash backup",
                "see docs/cli-capabilities.md for source-only setting support",
            ],
        }
    )


def main():
    try:
        app()
    except (ValueError, TypeError, RuntimeError, OSError, BleakError) as error:
        print(
            json.dumps(
                {"ok": False, "error": str(error) or type(error).__name__, "type": type(error).__name__},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
