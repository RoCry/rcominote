"""Fixed six-sector NOR contract with independently proven download windows.

Download windows opt into one audited producer-gap composer line. Shared
target, producer and fresh-ring parsing retain actual profile and parent chains.
No device access, producer implementation, pairing or freshness duplication.
"""

import json
from datetime import datetime
from pathlib import Path

from rcominote.experiments import boot_tail_contract as C
from rcominote.experiments import window_ram_probe as R

PROFILE = "fixed-fw1-boot-tail-window-pair"
POLICY = "per-download-window6-ce1"
OFFSETS = C.OFFSETS
WINDOW_PARENT_SHA = "8ffa203974b1f939ba3365186c771bc4128fa37aeba8efbb5133f9c5ab8aaa6e"
WINDOW_HCI_SHA = "248e57886ca3d61e02ba5694d310fefe6194e7f709c921a0b4baf6ab12da7277"


def _pin(value: dict, report_sha: str, hci_sha: str) -> None:
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("directory"), str)
        or not value["directory"]
        or value.get("report_sha256") != report_sha
        or value.get("hci_sha256") != hci_sha
    ):
        raise ValueError("Fixed early/window parent identity pins changed")


def window_parent_gate(directory: Path, image: Path) -> dict:
    receipt = (directory / "report.json").read_bytes()
    capture = (directory / "session.btsnoop").read_bytes()
    if C.session.audit.sha(receipt) != WINDOW_PARENT_SHA or C.session.audit.sha(capture) != WINDOW_HCI_SHA:
        raise ValueError("Requires exact successful two-download RAM window parent")
    result = R.replay(directory, image)
    return {
        "directory": str(directory.resolve()),
        "report_sha256": WINDOW_PARENT_SHA,
        "hci_sha256": WINDOW_HCI_SHA,
        "verification": result,
    }


def recipe(report: dict) -> None:
    if report.get("profile") != PROFILE or report.get("transport", {}).get("policy") != POLICY:
        raise ValueError("Requires fixed boot-tail per-download-window profile and policy")
    _pin(report.get("parent"), C.PARENT_SHA, C.PARENT_HCI_SHA)
    _pin(report.get("window_parent"), WINDOW_PARENT_SHA, WINDOW_HCI_SHA)
    C.common_recipe(report)


def payload(report: dict, operation: dict, ring: bytes) -> dict:
    recipe(report)
    return C.parse_payload(report, operation, ring, allow_composer_fps2=True)


def prepare(image: Path, early_parent: Path, window_parent: Path, offset: int) -> dict:
    report = C.prepare(image, early_parent, offset)
    parent = window_parent_gate(window_parent, image)
    report["profile"] = PROFILE
    report["transport"]["policy"] = POLICY
    report["window_parent"] = parent
    report["policy"] = "Two fresh fixed-sector reads; independently verified per-download parameter windows"
    recipe(report)
    return report


def validate_parents(report: dict, image: Path) -> dict:
    recipe(report)
    early = C.parent_gate(Path(report["parent"]["directory"]), image)
    window = window_parent_gate(Path(report["window_parent"]["directory"]), image)
    if early != report["parent"] or window != report["window_parent"]:
        raise ValueError("Replayed early/window parent chains differ from retained receipts")
    started = datetime.fromisoformat(report["started_at"])
    for parent in (early, window):
        original = json.loads((Path(parent["directory"]) / "report.json").read_bytes())
        if datetime.fromisoformat(original["ended_at"]) > started:
            raise ValueError("Window NOR acquisition predates a required successful parent")
    return {"parent": early, "window_parent": window}
