import json
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from rcominote import protocol as Boyi
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import param_window as P
from rcominote.experiments import scratch_reuse_audit as shared
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state


def inventory(report, plan):
    count = common.file_list(report)
    forbidden = {F.NAME, *(C.nonces(plan) if C.is_control(plan) else plan["future_nonces"])}
    for row in E.rows(report, *report["file_list_span"])[1:]:
        _, data = Boyi.parse(bytes.fromhex(row["hex"])[3:])
        if data[:1] == b"\0" and Boyi.parse_file_entry(data).name in forbidden:
            raise ValueError("Visible inventory collides with dedicated scratch/fresh nonces")
    return count


def envelope(report, directory, transactions):
    if report.get("monitor_exit") != 0 or report.get("monitor_stop") != {
        "signal": "SIGINT",
        "requested": True,
        "delivery": "sent",
    }:
        raise ValueError("Capture requires clean owned SIGINT stop")
    rows = report["att_packets"]
    if any(type(row["monotonic_ns"]) is not int for row in rows) or any(
        a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows)
    ):
        raise ValueError("Original ATT timestamps must remain complete and monotonic")
    _, event_proof = E.verify(report)
    raw = (directory / "session.btsnoop").read_bytes()
    observed = P.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        observed["pending"]
        or len(observed["transactions"]) != transactions
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
    ):
        raise ValueError(
            f"Requires full GATT/ATT/HCI and exactly {transactions} complete parameter transactions"
        )
    wire = common.wire_positions(report, raw)
    disconnects = observed["disconnects"]
    start_us, end_us = [
        P.H.EPOCH_US + int(datetime.fromisoformat(report[key]).timestamp() * 1_000_000)
        for key in ("started_at", "ended_at")
    ]
    if any(not start_us <= point[2] <= end_us for point in wire) or any(
        not start_us <= event["timestamp_us"] <= end_us for event in disconnects
    ):
        raise ValueError("Original owned ATT/disconnect timestamps lie outside declared page epoch")
    if (
        len(disconnects) != 1
        or disconnects[0]["status"] != 0
        or disconnects[0]["reason"] != 0x16
        or disconnects[0]["record"] <= max(p[1] for p in wire)
        or report.get("disconnect_observation")
        != {"observed": True, "event": disconnects[0], "max_wait_seconds": 8}
    ):
        raise ValueError("Requires sole actual normal local disconnect after final ATT")
    requested, completed, recorded = [
        report[key] for key in ("close_requested_us", "close_completed_us", "disconnect_observed_us")
    ]
    if (
        any(type(value) is not int for value in (requested, completed, recorded))
        or not requested <= completed <= recorded <= completed + 8_000_000
        or not requested <= disconnects[0]["timestamp_us"] <= completed + 8_000_000
    ):
        raise ValueError("Original actual disconnect observation exceeds bounded close")
    E.bridge(report, report["setup_end"], report["before_span"][0])
    A.identity(report, report, "before")
    return observed, wire, event_proof


def transfer_group(
    report,
    owner,
    page_plan,
    group_directory,
    observed,
    wire,
    context,
    *,
    operation_count=2,
    baseline_required=True,
):
    state, boundary, previous_tx, cursor, baseline = [
        context[k] for k in ("state", "boundary", "previous_tx", "cursor", "previous")
    ]
    ended, previous = context.get("ended_at"), baseline
    if baseline_required:
        warm = owner["baseline"]
        E.bridge(report, boundary, warm["download_start"])
        normal, slow = observed["transactions"][cursor : cursor + 2]
        if warm["before"] != state:
            raise ValueError("Readonly baseline state differs from actual predecessor")
        if cursor != 1 and not (
            wire[boundary - 1][1] < normal["request"]["record"]
            and wire[boundary - 1][2] < normal["request"]["timestamp_us"]
        ):
            raise ValueError("Continuation host normalization precedes prior final identity response")
        shared.baseline_window(report, warm, wire, previous_tx, normal, slow)
        previous = shared.download(report, warm, group_directory)
        if previous != baseline:
            raise ValueError("Live baseline differs from full latest verified predecessor current file")
        F.absent(previous, page_plan["future_nonces"])
        shared.barrier(report, warm, state, writing=False)
        state, boundary, previous_tx, cursor, ended = (
            warm["after"],
            warm["verified_end"],
            warm["slow_settlement"],
            cursor + 2,
            warm["ended_at"],
        )
    transfers = []
    for slot, op in zip(
        page_plan["operations"][:operation_count], owner["operations"][:operation_count], strict=True
    ):
        if (
            any(op.get(key) != value for key, value in slot.items())
            or op["before"] != state
            or op.get("sd_write_attempted") is not True
            or op.get("producer_attempted") is not True
        ):
            raise ValueError("Original overwrite recipe/predecessor/producer/SD attempt changed")
        J.time_order(ended, op["started_at"])
        E.bridge(report, boundary, op["actions_start"])
        E.bridge(report, op["actions_end"], op["download_start"])
        if C.actions(report, op) != op["actions_verification"]:
            raise ValueError("Original exact six-ACK/F1/all-F0 receipt changed")
        normal, slow, cursor = W.parameter_stage(
            observed["transactions"], cursor, op, previous_tx, first_fast_required=True
        )
        if op["activity_fast_verification"] != W.default_activity_fast(
            report, op, previous_tx, op["pre_download_fast"][0], wire
        ):
            raise ValueError("Actual FAST request precedes current Actions or prior SLOW")
        W.download_window(wire, op, normal, slow, report=report)
        data = shared.download(report, op, group_directory)
        if op["operation_id"] == "first":
            F.absent(data, page_plan["future_nonces"][1:])
        if op["operation_id"] == "second":
            F.absent(data, page_plan["future_nonces"][2:])
        shared.barrier(report, op, state, writing=True)
        transfers.append(data)
        previous, state, boundary, previous_tx, ended = (
            data,
            op["after"],
            op["verified_end"],
            slow,
            op["ended_at"],
        )
    return transfers, {
        "state": state,
        "boundary": boundary,
        "previous_tx": previous_tx,
        "cursor": cursor,
        "previous": previous,
        "ended_at": ended,
    }


def final_identity(report, wire, context, transactions):
    state, boundary, cursor = [context[k] for k in ("state", "boundary", "cursor")]
    E.bridge(report, boundary, report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(report["att_packets"]))
    if cursor != transactions or report["state_verification"] != verify_state(
        state, report["after"], sd_write=False
    ):
        raise ValueError("Final identity or fully consumed parameter ledger changed")


def session_communication(report, directory, plan, baseline, groups, *, operation_count=2):
    control = C.is_control(plan)
    (C.validate_plan if control else C.validate_page)(plan)
    C.policy_gate(report, page=not control)
    common.no_errors(report)
    if (
        any(report.get(key) != plan[key] for key in (C.CONTROL_FIELDS if control else C.fields(plan)))
        or "operation" in report
        or (not control and len(report["operations"]) != 2)
    ):
        raise ValueError("Actual fixed two-producer report differs from immutable plan")
    if type(operation_count) is not int or operation_count not in (1, 2):
        raise ValueError("Only one or two complete original producer communications permitted")
    for index, (owner, page_plan, _path) in enumerate(groups):
        C.validate_page(page_plan)
        if len(owner["operations"]) != 2:
            raise ValueError("Each group requires exactly two producer slots")
        stages = owner["operations"][:operation_count]
        if not (C.is_continuous(plan) and index == 1):
            warm = owner["baseline"]
            if (
                warm.get("name") != F.NAME
                or warm.get("operation_id") != "baseline"
                or any(k in warm for k in ("actions_start", "producer", "sd_write_attempted"))
            ):
                raise ValueError("Baseline must remain exact readonly dedicated-file download")
            stages = [warm, *stages]
        for stage in stages:
            J.time_order(report["started_at"], stage["started_at"], stage["ended_at"], report["ended_at"])
            if (
                datetime.fromisoformat(stage["ended_at"]) - datetime.fromisoformat(stage["started_at"])
            ).total_seconds() > 18:
                raise ValueError("Original post-startup stage exceeds18-second deadline")
    J.time_order(
        plan["parent"]["ended_at"] if control else plan["predecessor_ended_at"], report["started_at"]
    )
    J.time_order(plan["planned_at"], report["started_at"])
    transactions = C.control_budget(plan)["parameter_transactions"] if control else 3 + 3 * operation_count
    observed, wire, event_proof = envelope(report, directory, transactions)
    if report["predecessor_state_verification"] != verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Initial actual state differs from latest verified predecessor predecessor")
    E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    if inventory(report, plan) != report["listed_count"]:
        raise ValueError("Actual complete visible inventory changed")
    startup_tx = observed["transactions"][0]
    if report["startup_settlement"] != startup_tx or report["startup_classification"] != startup.classify(
        startup_tx
    ):
        raise ValueError("Session requires exactly one original strict startup FAST")
    context = {
        "state": report["before"],
        "boundary": report["file_list_span"][1],
        "previous_tx": startup_tx,
        "cursor": 1,
        "previous": baseline,
    }
    all_transfers = []
    for index, (owner, page_plan, path) in enumerate(groups):
        continuation = C.is_continuous(plan) and index == 1
        if continuation and (
            "baseline" in owner or owner.get("continuation") != C.continuation(groups[0][0]["operations"][-1])
        ):
            raise ValueError("Continuation must bind actual previous second download/state/ATT/SLOW")
        transfers, context = transfer_group(
            report,
            owner,
            page_plan,
            path,
            observed,
            wire,
            context,
            operation_count=operation_count,
            baseline_required=not continuation,
        )
        all_transfers.append(transfers)
    final_identity(report, wire, context, transactions)
    return all_transfers, event_proof


def communication(report, directory, plan, baseline, *, operation_count=2):
    transfers, events = session_communication(
        report, directory, plan, baseline, [(report, plan, directory)], operation_count=operation_count
    )
    return transfers[0], events


def validate_page(report, directory, plan, baseline):
    if plan["profile"] == C.PREFILLED_PAGE:
        from rcominote.experiments import prefilled_nor_pages

        return prefilled_nor_pages.validate(report, directory, plan, baseline)
    if any(stage.get("live_complete") is not True for stage in [report["baseline"], *report["operations"]]):
        raise ValueError("All three original stages must complete before pair acceptance")
    transfers, event_proof = communication(report, directory, plan, baseline)
    sectors, observations, previous = [], [], baseline
    for op, data in zip(report["operations"], transfers, strict=True):
        decoded = C.payload(op, data, previous)
        sector = bytes.fromhex(decoded["sector_hex"])
        if (
            decoded != op["verification"]
            or (directory / op["operation_id"] / "sector.bin").read_bytes() != sector
        ):
            raise ValueError("Saved sector differs from its own complete current retained file")
        sectors.append(sector)
        observations.append(
            {
                "operation": op["operation_id"],
                "nonce": op["nonce"],
                "ring_sha256": A.sha(data),
                "sector_sha256": A.sha(sector),
            }
        )
        previous = data
    if any(len(sector) != 512 for sector in sectors) or sectors[0] != sectors[1]:
        raise ValueError("Two independent complete unknown NOR sectors differ; no oracle filling")
    return {
        "verified": True,
        "pair_verified": True,
        "connections": 1,
        "downloads": 3,
        "producers": 2,
        "sd_writes": 2,
        "new_files": 0,
        "raw_range": [plan["nor_offset"], plan["nor_offset"] + 512],
        "bytes": 512,
        "sha256": A.sha(sectors[0]),
        "parameter_transactions": 9,
        "observations": observations,
        "independent_oracle": False,
        "paired_bytes": 512,
        "status_events": event_proof,
    }


def oracle_proof(plan, index, sector):
    if sector != C.oracle(plan, index):
        raise ValueError("Known control current512 differs from independent physical raw oracle")
    return {"known_offset": plan["offsets"][index], "sha256": A.sha(sector), "independent_oracle": True}


def validate_control(report, directory, plan, baseline, *, archived=False):
    C.validate_plan(plan)
    if not C.is_control(plan) or (archived and report.get("ok") is not True):
        raise ValueError("Original failed known control cannot be promoted/adopted")
    if (
        report["plan"]["file"] != "plan.json"
        or json.loads(J.check_reference(directory, report["plan"]).read_bytes()) != plan
        or len(report["groups"]) != 2
    ):
        raise ValueError("Known control differs from original immutable two-group plan")
    J.time_order(plan["parent"]["ended_at"], plan["planned_at"], report["started_at"], report["ended_at"])
    groups, state, ended = [], plan["expected_before"], plan["parent"]["ended_at"]
    for index, group in enumerate(report["groups"]):
        if (
            group.get("group_index") != index
            or group.get("nor_offset") != plan["offsets"][index]
            or group.get("candidate") is not True
            or group.get("live_complete") is not True
            or any(k in group for k in ("disconnect", "disconnect_observation", "ok"))
        ):
            raise ValueError("Groups require complete candidates, never separate sessions or success flags")
        stages = [*([group["baseline"]] if "baseline" in group else []), *group["operations"]]
        if any(op.get("ok") is not True or op.get("live_complete") is not True for op in stages):
            raise ValueError("All six original stages must be live complete")
        J.time_order(ended, stages[0]["started_at"])
        page_plan = C.page_plan(plan, index, state, ended)
        groups.append((group, page_plan, directory / plan["pages"][index]["directory"]))
        state, ended = group["operations"][-1]["after"], group["operations"][-1]["ended_at"]
    transfers, events = session_communication(report, directory, plan, baseline, groups)
    previous, proofs = baseline, []
    for index, ((group, _page_plan, path), data_pair) in enumerate(zip(groups, transfers, strict=True)):
        sectors, observations = [], []
        for op, data in zip(group["operations"], data_pair, strict=True):
            decoded = C.payload(op, data, previous)
            sector = bytes.fromhex(decoded["sector_hex"])
            if (
                decoded != op["verification"]
                or (path / op["operation_id"] / "sector.bin").read_bytes() != sector
                or oracle_proof(plan, index, sector) != op["oracle_verification"]
            ):
                raise ValueError("Known control retained chain/sector/oracle receipt changed")
            sectors.append(sector)
            observations.append(
                {"nonce": op["nonce"], "ring_sha256": A.sha(data), "sector_sha256": A.sha(sector)}
            )
            previous = data
        if sectors[0] != sectors[1]:
            raise ValueError("Known control requires two equal independent512 reads in each group")
        proofs.append(
            {
                "known_offset": plan["offsets"][index],
                "bytes": 512,
                "sha256": A.sha(sectors[0]),
                "observations": observations,
            }
        )
    proof = {
        "verified": True,
        "known_control": True,
        "connections": 1,
        "downloads": C.control_budget(plan)["downloads"],
        "producers": 4,
        "sd_writes": 4,
        "new_files": 0,
        "parameter_transactions": C.control_budget(plan)["parameter_transactions"],
        "groups": proofs,
        "independent_oracle": True,
        "new_raw_nor_coverage_bytes": 0,
        "status_events": events,
    }
    if archived and report.get("verification") != proof:
        raise ValueError("Original complete known-control proof changed")
    return proof


def original_success(report):
    if report.get("ok") is not True or any(
        stage.get("ok") is not True or stage.get("live_complete") is not True
        for stage in [report["baseline"], *report["operations"]]
    ):
        raise ValueError("Original failed/incomplete page cannot be promoted by replay")


def ledger_entry(root, slot, page, proof):
    directory = root / slot["directory"]
    return {
        "page_index": slot["page_index"],
        "nor_offset": slot["nor_offset"],
        "report": J.reference(root, directory / "report.json"),
        "capture": J.reference(root, directory / "session.btsnoop"),
        "rings": [
            J.reference(root, directory / label / "download.bin")
            for label in C.stages({"profile": page["profile"]})
        ],
        "sectors": [J.reference(root, directory / label / "sector.bin") for label in ("first", "second")],
        "after": page["after"],
        "ended_at": page["ended_at"],
        "verification": proof,
    }


def job_gate(job, plan, root):
    C.validate_plan(plan)
    if (
        job.get("profile") != plan["profile"]
        or job.get("budget") != plan["budget"]
        or job["plan"]["file"] != "plan.json"
        or json.loads(J.check_reference(root, job["plan"]).read_bytes()) != plan
        or not isinstance(job.get("completed"), list)
        or len(job["completed"]) > len(plan["pages"])
    ):
        raise ValueError("Original job differs from frozen finite plan/completed ledger")
    J.time_order(plan["planned_at"], job["started_at"])


def completed_prefix(job, plan, root, baseline):
    job_gate(job, plan, root)
    state, ended, previous = plan["expected_before"], plan["parent"]["ended_at"], baseline
    verified = []
    for index, receipt in enumerate(job["completed"]):
        slot = plan["pages"][index]
        directory = root / slot["directory"]
        expected_report = str(Path(slot["directory"]) / "report.json")
        if receipt.get("report", {}).get("file") != expected_report:
            raise ValueError("Completed pages must be an exact original ordered prefix")
        page = json.loads(J.check_reference(root, receipt["report"]).read_bytes())
        original_success(page)
        page_plan = C.page_plan(plan, index, state, ended)
        if page.get("plan") != job["plan"]:
            raise ValueError("Page must bind exact original immutable job plan")
        J.time_order(job["started_at"], page["started_at"], page["ended_at"], job["ended_at"])
        proof = validate_page(page, directory, page_plan, previous)
        if proof != page.get("verification") or receipt != ledger_entry(root, slot, page, proof):
            raise ValueError("Completed page proof/raw references/state changed")
        previous = (directory / "second/download.bin").read_bytes()
        state, ended = page["after"], page["ended_at"]
        verified.append(proof)
    return verified, previous, state


def replay(directory: Path, image: Path):
    job = json.loads((directory / "report.json").read_bytes())
    if job.get("ok") is not True:
        raise ValueError("Original failed whole job cannot become successful/admissible parent")
    if job.get("profile") not in (C.PROFILE, C.PROFILE_V3, C.PREFILLED_PROFILE) and not C.is_control(job):
        raise ValueError("Replay requires original v2 whole-job profile")
    return C.parent_gate(directory, image)[2]["verification"]


def _replay_admitted(job, plan, directory, baseline):
    if job.get("ok") is not True:
        raise ValueError("Original failed whole job cannot become successful/admissible parent")
    job_gate(job, plan, directory)
    common.no_errors(job)
    if len(job["completed"]) != len(plan["pages"]):
        raise ValueError("Successful whole job requires every declared page")
    proofs, _ring, _state = completed_prefix(job, plan, directory, baseline)
    proof = job_proof(plan, proofs)
    if proof != job.get("verification"):
        raise ValueError("Whole job result differs from complete paired-page ledger")
    return proof


job_proof = C.sources.job_proof
