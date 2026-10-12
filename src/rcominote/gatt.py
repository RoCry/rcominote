"""Enumerate services without characteristic reads, writes or subscriptions."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from bleak import BleakClient

from .ble_target import OWNED_SERIAL, find_device

OTA_SERVICE = "e49a25f8-f69a-11e8-8eb2-f2801f1b9fd1"
LOG_SERVICE = "e49a3001-f69a-11e8-8eb2-f2801f1b9fd1"


async def snapshot(*, serial: str, seconds: float = 12) -> dict:
    device = await find_device(serial=serial, seconds=seconds)
    async with BleakClient(device, timeout=20) as client:
        services = [
            {
                "uuid": service.uuid,
                "characteristics": [
                    {
                        "uuid": char.uuid,
                        "handle": char.handle,
                        "properties": char.properties,
                        "descriptors": [{"uuid": d.uuid, "handle": d.handle} for d in char.descriptors],
                    }
                    for char in service.characteristics
                ],
            }
            for service in client.services
        ]
        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "selection": {"advertised_serial": serial, "address": device.address, "name": device.name},
            "method": "BLE connect and GATT discovery only; no application characteristic operations",
            "mtu": client.mtu_size,
            "actions_log_service_present": client.services.get_service(LOG_SERVICE) is not None,
            "actions_ota_service_present": client.services.get_service(OTA_SERVICE) is not None,
            "services": services,
        }


def main(
    serial: str = OWNED_SERIAL,
    seconds: float = 12.0,
    out: Annotated[Path | None, typer.Option(help="Create a new JSON snapshot; refuses overwrite")] = None,
):
    """Enumerate GATT services without application characteristic operations."""
    if out is not None and out.exists():
        raise FileExistsError(f"Output already exists: {out}; choose a new snapshot path")

    result = (
        json.dumps(asyncio.run(snapshot(serial=serial, seconds=seconds)), ensure_ascii=False, indent=2) + "\n"
    )
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x") as handle:
            handle.write(result)
    print(result, end="")


if __name__ == "__main__":
    typer.run(main)
