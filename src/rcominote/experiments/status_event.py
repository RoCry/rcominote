"""Explicit unchanged FW010004 status events, bound to original ATT indices.

Actual builder1000ac78..1000ad10 emits20 bytes. This policy additionally fixes
power-off byte4=0 and USB-connected byte10=1; GET_INFO does not expose those
two fields. A status event never substitutes for a transaction response.
"""

from rcominote import protocol as P
from rcominote.experiments.sd_bootstrap import verify_state

POLICY = "unchanged-status20-usb-connected-max8"
LIMIT = 8
FIELDS = (
    "charging",
    "battery",
    "usb_mode",
    "mode",
    "noise_reduction",
    "voice_control",
    "indicator_light",
    "segment_duration",
    "screen_backlight",
)


def enabled(report: dict) -> bool:
    if "status_event_policy" not in report:
        if "status_events" in report:
            raise ValueError("Status ledger requires explicit status_event_policy")
        return False
    if report["status_event_policy"] != POLICY:
        raise ValueError("Unknown status_event_policy")
    return True


def _template(report: dict) -> bytes:
    expected = report.get("expected_before")
    if not isinstance(expected, dict):
        raise TypeError("Status policy requires complete expected_before identity")
    verify_state(expected, expected, sd_write=False)
    raw = bytes.fromhex(expected["device"]["raw"])
    if raw[40] != 255:
        raise ValueError("Status builder voice sentinel must match expected INFO ff")
    return bytes((raw[8], raw[9], raw[14], raw[15], 0, raw[39], 255, raw[16], raw[41], raw[42], 1)) + bytes(9)


def init(report: dict) -> None:
    if enabled(report):
        _template(report)
        if "status_events" in report:
            raise ValueError("Do not overwrite an existing status ledger")
        report["status_events"] = []


def _bounds(report: dict, start: int, end: int) -> None:
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(report["att_packets"]):
        raise ValueError("Invalid original ATT index range")


def _event(report: dict, index: int, row: dict, template: bytes) -> dict | None:
    _bounds(report, index, index + 1)
    if row != report["att_packets"][index]:
        raise ValueError("Status observation differs from its original ATT row")
    packet = bytes.fromhex(row["hex"])
    if row["direction"] != "rx" or packet[:3] != b"\x1b\x24\0":
        return None
    command, payload = P.parse(packet[3:])
    if command != P.DEVICE_STATUS_CHANGE:
        return None
    if payload != template:
        raise ValueError("Status20 layout, reserved fields or expected state changed")
    fields = P.parse_event(command, payload)
    if any(fields[key] != report["expected_before"]["device"][key] for key in FIELDS):
        raise ValueError("Status event differs from expected device state")
    return {"index": index, "frame_hex": packet[3:].hex(), "payload_hex": payload.hex(), "fields": fields}


def observe(report: dict, index: int, row: dict) -> dict | None:
    """Called after the actual row was appended; no queue consumption or rewrite."""
    if not enabled(report):
        return None
    event = _event(report, index, row, _template(report))
    ledger = report.get("status_events")
    if not isinstance(ledger, list):
        raise TypeError("Status observer requires initialized ledger")
    if event is not None:
        if len(ledger) >= LIMIT or (ledger and ledger[-1]["index"] >= index):
            raise ValueError("Status event bound exceeded or duplicate/out-of-order observation")
        ledger.append(event)
    return event


def verify(report: dict) -> tuple[set[int], dict]:
    """Rebuild every event from original rows; never trust a cached ledger alone."""
    if not enabled(report):
        return set(), {"enabled": False, "events": 0, "indices": []}
    template = _template(report)
    events = []
    for index, row in enumerate(report["att_packets"]):
        if (event := _event(report, index, row, template)) is not None:
            events.append(event)
            if len(events) > LIMIT:
                raise ValueError("Status event bound exceeded")
    ledger = report.get("status_events")
    if (
        not isinstance(ledger, list)
        or any(not isinstance(item, dict) or type(item.get("index")) is not int for item in ledger)
        or ledger != events
    ):
        raise ValueError("Status ledger differs from complete original ATT events")
    selected = [event["index"] for event in events]
    return set(selected), {"policy": POLICY, "events": len(events), "indices": selected}


def indices(report: dict, start: int, end: int) -> list[int]:
    """Original transaction indices, with individually validated events diverted."""
    _bounds(report, start, end)
    if not enabled(report):
        return list(range(start, end))
    template = _template(report)
    return [i for i in range(start, end) if _event(report, i, report["att_packets"][i], template) is None]


def rows(report: dict, start: int, end: int) -> list[dict]:
    return [report["att_packets"][i] for i in indices(report, start, end)]


def edge(report: dict, start: int, end: int) -> tuple[int, int]:
    values = indices(report, start, end)
    if not values:
        raise ValueError("Transaction range contains no actual transaction packets")
    return values[0], values[-1]


def bridge(report: dict, start: int, end: int) -> None:
    if indices(report, start, end):
        raise ValueError("Only verified status events may bridge transaction ranges")
