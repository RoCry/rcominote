"""Select the owned Boyi unit by advertised serial, never first manufacturer match."""

from bleak import BleakScanner
from protocol import COMPANY_ID

OWNED_SERIAL = "C261CF0430"


def advertised_serial(raw: bytes) -> str | None:
    if len(raw) < 16:
        return None
    try:
        return raw[6:16].split(b"\0", 1)[0].decode("ascii")
    except UnicodeDecodeError:
        return None


async def find_device(*, serial: str, seconds: float):
    if not serial or len(serial) > 10 or not serial.isascii():
        raise ValueError("Expected a nonempty ASCII serial of at most 10 characters")
    device = await BleakScanner.find_device_by_filter(
        lambda _device, adv: advertised_serial(adv.manufacturer_data.get(COMPANY_ID, b"")) == serial,
        timeout=seconds,
    )
    if device is None:
        raise RuntimeError(f"CoMi {serial} not advertising; wake it and disconnect the vendor app")
    return device
