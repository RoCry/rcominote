"""Two closed pinned discovery timeouts; preserve each original failed whole job.

This offline ownership node adds no NOR coverage and proves no new healthy link.
The copied file/identity come only from the last independently accepted page.
"""

import json
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments.hci_monitor import Snoop

PROFILE = "pinned-prefilled-preproducer-link-failure-prefix-checkpoint-v1"
ERROR = "TimeoutError: [Errno 110] Connection timed out"
PAGE = "page3-1ec800"
PINS = {
    "report.json": "5c8d1b61681f1a8fce3f7d1bfb0c4185d644f90f87d2a0351b7fdc79ee0269a0",
    "plan.json": "96ad9ddeb5768af833cb7f88eb57bb570f7e69a067b1e288ede475ce96f709fc",
    f"{PAGE}/report.json": "468ab327dc0b7a9cb1bb4944f6bc50253b1b7890000f0e1ed3aed3f9d0751720",
    f"{PAGE}/session.btsnoop": "23c57119fb9f6a1718d8d0c8cebd329c27d1d88a4243596a8390d12f8a63892d",
}
MANIFEST_SHA = "ab996996de7b2da0c35153fd79b872da95a6c7fe1ca6d97f15f513b465198635"
CODE = {
    "prefilled_nor_pages.py": "9b04a67afea80d45d63b3d47372dc3e5a2e23bad915bcff5a51f2789bf3d6f9c",
    "prefilled_nor_runtime.py": "b2b86213cbc370f9a02f337c0241706683f71dac7ddcc27375e6dc30014dcae7",
    "paired_nor_plan.py": "4bf165c18254d7ec4c04a721e5c5bd3d75fa8c1be7f50bdae5ee6f4f6e4606f4",
    "paired_nor_audit.py": "a30b6a4ad593fcbad2c84a8065b3e081c67a16d7e7fd347f04f9588cef6bc918",
    "paired_nor_runtime.py": "47b27c4506d7d690c65751c312a3c77da37f157822fe64eb2c25c82c8893ad70",
    "paired_nor_sources.py": "36bac394b16e0b32f35192ea5d68b4ff18517d46bc5a75a472ad467552835727",
    "scratch_reuse_parser.py": "a69a8bdd243a0c786d9602806412986712c11dae21bfff00c41054ace63177fb",
}
# Full host trace, including the last unanswered Find Information request.
ATT = (
    ("tx", "02f700"),
    ("rx", "03f700"),
    ("tx", "100100ffff0028"),
    ("rx", "110601000800011809000f000018100013000f18"),
    ("rx", "02f700"),
    ("tx", "03f700"),
    ("tx", "101400ffff0028"),
    ("rx", "111414001900d19f1b1f80f2b28ee8119af601309ae4"),
    ("tx", "101a00ffff0028"),
    ("rx", "11061a001f00f0f520002b00e0e5"),
    ("tx", "102c00ffff0028"),
    ("rx", "01102c000a"),
    ("tx", "0820002b000328"),
    ("rx", "09072100042200e1e52300102400e2e52600102700e3e52900102a00e4e5"),
    ("tx", "082b002b000328"),
    ("rx", "01082b000a"),
    ("tx", "0425002500"),
    ("rx", "050125000229"),
    ("tx", "0428002800"),
    ("rx", "050128000229"),
    ("tx", "042b002b00"),
)
LINK = {"controller": "hci0", "local": "AC:19:8E:26:2B:F8", "peer": "50:C0:F0:AE:7C:0E", "handle": 2048}
NEXT_PAGE = "page1-1ed800"
NEXT_PINS = {
    "report.json": "b8a3ee5051e3e815c99ceb2096766923be3f80945a853e5524530f603784a1c1",
    "plan.json": "8b42920a0da2d8aa6f940911c2cd2d4d2a61b2c265a93302c6054dbf4ac68ee6",
    f"{NEXT_PAGE}/report.json": "dc0144b22f8035784b91e077f74b0423a9b39c4e40b3d74787399ce9d66c1714",
    f"{NEXT_PAGE}/session.btsnoop": "6e850776414bd8bc9ba6e122a33e6a12c7ef5d797ca8f03cf63f3ce46f7022e3",
}
NEXT_CODE = {
    "prefilled_nor_pages.py": "d3ddb9a2e3b3ee5627e6f7f7cb3a7c091d7f76540095e0576f11fa548a4d27f8",
    "prefilled_nor_runtime.py": "20ba7bcea1eebb64f3abdf605f5ba9560c74dd3e188e737004d5eec268db7d1f",
    "paired_nor_plan.py": "cf715c10b5346451de59ceaf61078b1d847a9d7ea9efc5e0442ec0c55d426010",
    "paired_nor_audit.py": CODE["paired_nor_audit.py"],
    "paired_nor_runtime.py": CODE["paired_nor_runtime.py"],
    "paired_nor_sources.py": "fdc38b68bb5fd53e1cadab3074881922f024d3399cf206cfc4211bec19504c54",
    "scratch_reuse_parser.py": "449359eeb72d4705304b503dd864a5dab843cfa1e3c24f7235f67f970b0c1383",
}
NEXT_MANIFEST_SHA = "aa5a0b4faf2bc4c49db74e08ecf50b9124f929d7c8c9a02d25cb5bc30b58818e"
# Actual directional traces agree; cross-direction scheduling differs. Never sort.
NEXT_HOST_ATT = ATT[:3] + (ATT[4], ATT[5], ATT[3]) + ATT[6:]
NEXT_HCI_ATT = ATT[:3] + (ATT[4], ATT[3], ATT[5]) + ATT[6:]


def capture_case(failed):
    if A.A.sha((failed / "report.json").read_bytes()) == NEXT_PINS["report.json"]:
        return {
            "pins": NEXT_PINS,
            "page": NEXT_PAGE,
            "parent_profile": C.PREFILLED_PROFILE,
            "offsets": [0x1ED600, 0x1ED800, 0x1EDA00, 0x1EDC00],
            "prefix": 1,
            "names": 90,
            "counts": (153, 140),
            "manifest": NEXT_MANIFEST_SHA,
            "code": NEXT_CODE,
            "host_att": NEXT_HOST_ATT,
            "hci_att": NEXT_HCI_ATT,
        }
    return {
        "pins": PINS,
        "page": PAGE,
        "parent_profile": C.PREFILL_PROFILE_V2,
        "offsets": [0x1EC200, 0x1EC400, 0x1EC600, 0x1EC800],
        "prefix": 3,
        "names": 62,
        "counts": (146, 132),
        "manifest": MANIFEST_SHA,
        "code": CODE,
        "host_att": ATT,
        "hci_att": ATT,
    }


def iso(stamp):
    seconds, microseconds = divmod(stamp - A.P.H.EPOCH_US, 1_000_000)
    return datetime.fromtimestamp(seconds, UTC).replace(microsecond=microseconds).isoformat()


def link_failure(report, raw, *, host_att=ATT, hci_att=ATT):
    parser = Snoop()
    parser.feed(raw, final=True)
    observed = A.P.inspect(raw, link=LINK, final=True)
    events = parser.events
    packets = A.dual_hci.att_packets(raw, LINK["handle"])
    rows = report["att_packets"]
    if (
        [(e["kind"], e["record"]) for e in events] != [("controller", 3), ("connect", 18), ("disconnect", 57)]
        or events[0]["address"] != LINK["local"]
        or any(
            events[1][k] != v
            for k, v in {
                "status": 0,
                "role": 0,
                "address_type": 0,
                "address": LINK["peer"],
                "interval": 48,
                "latency": 4,
                "timeout": 600,
            }.items()
        )
        or any(events[2][k] != v for k, v in {"status": 0, "handle": 2048, "reason": 8}.items())
        or observed["records"] != 58
        or observed["transactions"]
        or observed["pending"]
        or [(p["direction"], p["hex"]) for p in packets] != list(hci_att)
        or [(p["direction"], p["hex"]) for p in rows] != list(host_att)
        or any(
            set(p) != {"direction", "hex", "monotonic_ns"} or type(p["monotonic_ns"]) is not int for p in rows
        )
        or any(a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows))
        or report["hci_capture"] != {"bytes": len(raw), "records": 58, "sha256": A.A.sha(raw)}
    ):
        raise ValueError("Requires exact partial21ATT/58HCI discovery-only failed owned epoch")
    C.J.time_order(
        report["started_at"], *(iso(stamp) for _n, _op, stamp, _p in A.P.records(raw, 58)), report["ended_at"]
    )
    C.J.time_order(iso(events[2]["timestamp_us"]), iso(report["close_completed_us"]), report["ended_at"])
    return {
        "verified": True,
        "att_packets": 21,
        "parameter_transactions": 0,
        "pending": 0,
        "connection": observed["connection"],
        "disconnect": events[2],
        "hci_capture": report["hci_capture"],
        "application_writes": 0,
        "identity_observed": False,
    }


def failed_prefix(failed, source, baseline):
    case = capture_case(failed)
    references = {name: C.pins.pinned(failed / name, digest)[1] for name, digest in case["pins"].items()}
    job = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, job["plan"]).read_bytes())
    if (
        set(job) != {"profile", "budget", "started_at", "plan", "completed", "ok", "ended_at", "error"}
        or job.get("ok") is not False
        or job["error"] != ERROR
        or plan["profile"] != C.PREFILLED_PROFILE
        or plan["parent"] != source
        or source["profile"] != case["parent_profile"]
        or plan["offsets"] != case["offsets"]
        or len(job["completed"]) != case["prefix"]
    ):
        raise ValueError(
            "Only closed pinned four-page job with its exact complete prefix and discovery timeout admitted"
        )
    C.pins.pinned(failed / "source-snapshot/manifest.json", case["manifest"])
    snapshot = K.snapshot(failed, code=case["code"])
    manifest = json.loads((failed / "source-snapshot/manifest.json").read_bytes())
    if (len(manifest["source_files"]), len(manifest["test_files"])) != case["counts"]:
        raise ValueError("Original complete frozen source/test snapshot changed")
    C.J.time_order(manifest["created_at"], plan["planned_at"], job["started_at"])
    proofs, current, state = A.completed_prefix(job, plan, failed, baseline)
    last = job["completed"][-1]
    page = C.page_plan(plan, case["prefix"], state, last["ended_at"])
    directory = failed / case["page"]
    report = json.loads((directory / "report.json").read_bytes())
    expected = C.report(page) | {
        k: report[k]
        for k in ("started_at", "ended_at", "plan", "att_packets", "close_completed_us", "hci_capture")
    }
    expected.update(
        status_events=[],
        capture_error=ERROR,
        error=ERROR,
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
    )
    if (
        report != expected
        or report["ok"] is not False
        or report["transport"] != {}
        or type(report["monitor_exit"]) is not int
        or type(report["close_completed_us"]) is not int
        or report["plan"] != job["plan"]
        or any(
            s["ok"] is not False or s["live_complete"] is not False
            for s in [report["baseline"], *report["operations"]]
        )
        or any(p.is_file() for label in C.stages(page) for p in (directory / label).rglob("*"))
        or any(
            p.is_file()
            for slot in plan["pages"][case["prefix"] + 1 :]
            for p in (failed / slot["directory"]).rglob("*")
        )
    ):
        raise ValueError(
            "Failed discovery page must retain exact untouched stages and partial-capture fields"
        )
    C.J.time_order(last["ended_at"], report["started_at"], report["ended_at"], job["ended_at"])
    link = link_failure(
        report,
        (directory / "session.btsnoop").read_bytes(),
        host_att=case["host_att"],
        hci_att=case["hci_att"],
    )
    accepted_dir = failed / plan["pages"][case["prefix"] - 1]["directory"]
    accepted = json.loads((accepted_dir / "report.json").read_bytes())
    wire = A.common.wire_positions(accepted, (accepted_dir / "session.btsnoop").read_bytes())
    identity_at = iso(wire[accepted["after_span"][1] - 1][2])
    C.J.time_order(identity_at, last["ended_at"], report["started_at"])
    names = sorted(set(source["prior_names"]) | set(C.nonces(plan)))
    if len(names) != case["names"]:
        raise ValueError(
            "Every historical/planned nonce, including all unattempted pairs, must remain reserved"
        )
    return (
        current,
        state,
        {
            "directory": str(failed.resolve()),
            "references": references | {"snapshot": snapshot},
            "latest_identity_response_at": identity_at,
            "last_successful_page_ended_at": last["ended_at"],
            "failed_ended_at": job["ended_at"],
            "prior_names": names,
            "latest_info": state,
            "current_ring_sha256": A.A.sha(current),
            "original_completed_prefix": proofs,
            "failure": link,
        },
    )


def header(checkpoint):
    A.common.no_errors(checkpoint)
    if (
        checkpoint.get("profile") != PROFILE
        or checkpoint.get("offline_ownership_verified") is not True
        or checkpoint.get("live_capture_performed") is not False
        or checkpoint.get("original_job_ok") is not False
        or checkpoint.get("original_failed_page_ok") is not False
        or "ok" in checkpoint
        or type(checkpoint.get("new_raw_nor_coverage_bytes")) is not int
        or checkpoint["new_raw_nor_coverage_bytes"] != 0
        or checkpoint["parent"]["profile"] not in (C.PREFILL_PROFILE_V2, C.PREFILLED_PROFILE)
    ):
        raise ValueError(
            "Requires distinct pinned offline preproducer-link ownership checkpoint, zero coverage"
        )
    C.J.time_order(checkpoint["failed"]["failed_ended_at"], checkpoint["created_at"])


def verify_admitted(checkpoint, directory, source, baseline):
    header(checkpoint)
    if checkpoint["parent"] != source:
        raise ValueError("Pinned link checkpoint differs from fully admitted knownV2 ancestor")
    failed = Path(checkpoint["failed"]["directory"]).resolve()
    if failed == directory.resolve() or failed == Path(source["directory"]).resolve():
        raise ValueError("Cycle in pinned failed-source evidence edge")
    current, state, result = failed_prefix(failed, source, baseline)
    if (
        result != checkpoint["failed"]
        or checkpoint["baseline"]["file"] != "baseline.bin"
        or C.J.check_reference(directory, checkpoint["baseline"]).read_bytes() != current
    ):
        raise ValueError("Pinned link checkpoint original evidence/current-file source changed")
    return (
        current,
        state,
        {
            "directory": str(directory.resolve()),
            "profile": PROFILE,
            "ended_at": result["last_successful_page_ended_at"],
            "created_at": checkpoint["created_at"],
            "latest_identity_response_at": result["latest_identity_response_at"],
            "failed_ended_at": result["failed_ended_at"],
            "latest_info": state,
            "baseline_sha256": A.A.sha(current),
            "prior_names": result["prior_names"],
            "references": {
                "checkpoint": C.J.reference(directory, directory / "checkpoint.json"),
                "baseline": checkpoint["baseline"],
            },
            "verification": {
                "verified": True,
                "new_raw_nor_coverage_bytes": 0,
                "device_io": 0,
                "original_failed_retained": True,
                "preproducer_failure": result["failure"],
            },
            "current_object_live_download_required_before_overwrite": True,
        },
    )


def create(image: Path, failed: Path, newout: Path):
    from rcominote.experiments.paired_nor_runtime import private_output

    private_output(newout)
    plan = json.loads(C.pins.pinned(failed / "plan.json", capture_case(failed)["pins"]["plan.json"])[0])
    baseline, _state, source = C.parent_gate(Path(plan["parent"]["directory"]), image)
    current, _state, result = failed_prefix(failed, source, baseline)
    checkpoint = {
        "profile": PROFILE,
        "created_at": C.S.now(),
        "parent": source,
        "failed": result,
        "offline_ownership_verified": True,
        "live_capture_performed": False,
        "original_job_ok": False,
        "original_failed_page_ok": False,
        "new_raw_nor_coverage_bytes": 0,
    }
    header(checkpoint)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "baseline.bin").write_bytes(current)
    checkpoint["baseline"] = C.J.reference(newout, newout / "baseline.bin")
    C.S.save(newout / "checkpoint.json", checkpoint)
    return verify_admitted(checkpoint, newout, source, baseline)
