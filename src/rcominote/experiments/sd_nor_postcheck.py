"""One read-only identity postcheck for a complete context trial with final ENOSYS.

Offline validation precedes the sole identity call. Original files remain untouched;
copied28-byte context is historical data, not a new download or runtime snapshot.
"""

import asyncio
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote.experiments import sd_bootstrap
from rcominote.experiments import sd_nor_probe as probe

POSTINFO_ERROR = "OSError: [Errno 38] LE ATT connect failed"


def validate_original(directory: Path, image: bytes) -> tuple[dict, bytes, bytes]:
    report, raw = probe.load(directory)
    if (
        report.get("phase") != "context"
        or report.get("serial") != probe.OWNED_SERIAL
        or report.get("ok") is not False
        or report.get("error") != POSTINFO_ERROR
        or report.get("after_error") != POSTINFO_ERROR
        or "after" in report
        or report.get("source_image_sha256") != probe.IMAGE_SHA
        or report.get("source_address") != hex(probe.CONTEXT)
        or report.get("source_bytes") != 28
        or report.get("sd_write_attempted") is not True
        or "postcheck_parent" in report
        or any(
            value
            for key, value in report.items()
            if key.endswith("error") and key not in {"error", "after_error"}
        )
    ):
        raise ValueError("Only a complete original context with final identity ENOSYS can be postchecked")
    probe.same_identity({"before": report["before"], "after": report["before"], "sd_write_attempted": False})
    refs = report["guards"]
    parents = [row["write_parent"] for row in refs if row.get("write_parent") is not None]
    if len(parents) > 1 or any(row["source"] != "handler" and row.get("write_parent") for row in refs):
        raise ValueError("Unexpected guard write-parent chain")
    parent = Path(parents[0]["directory"]) if parents else None
    guards = probe.validate_guards([Path(row["directory"]) for row in refs], image, parent)
    if guards != refs:
        raise ValueError("Original context guard receipt/hash chain changed")
    probe.command(report, probe.CONTEXT, 28)
    probe.validate_actions(report)
    data = probe.downloaded(report, directory, 28)
    if probe.context_fields(data) != report.get("verification"):
        raise ValueError("Original context struct verification differs from retained bytes")
    return report, raw, data


def validate_derived(report: dict, directory: Path, image: bytes) -> None:
    """Bind successful derived receipt to its still-failed immutable original."""
    parent = report["postcheck_parent"]
    original, raw, data = validate_original(Path(parent["directory"]), image)
    if parent != {"directory": str(Path(parent["directory"]).resolve()), "report_sha256": probe.sha(raw)}:
        raise ValueError("Postcheck original parent hash/path changed")
    unchanged = {
        key: value for key, value in original.items() if key not in {"ok", "error", "after_error", "ended_at"}
    }
    if (
        any(report.get(key) != value for key, value in unchanged.items())
        or report.get("origin_error") != original["error"]
        or report.get("origin_ended_at") != original["ended_at"]
        or report.get("download_reused") is not True
        or report.get("ok") is not True
        or report.get("error")
        or report.get("after_error")
        or probe.downloaded(report, directory, 28) != data
    ):
        raise ValueError("Postcheck changed original acquisition evidence")
    probe.same_identity(report)


async def postcheck(report: dict) -> None:
    # identity() performs the already-audited read-only info/list operation once.
    report["after"], report["files_after"] = await sd_bootstrap.identity()
    probe.same_identity(report)


def main(image: Path, original_context_dir: Path, new_out: Path) -> None:
    original, raw, data = validate_original(original_context_dir, image.read_bytes())
    # Exclusive output creation also rejects aliasing the original directory.
    new_out.mkdir(parents=True, exist_ok=False)
    report = copy.deepcopy(original)
    report.pop("error")
    report.pop("after_error")
    report.update(
        ok=False,
        origin_error=original["error"],
        origin_ended_at=original["ended_at"],
        postcheck_parent={"directory": str(original_context_dir.resolve()), "report_sha256": probe.sha(raw)},
        postcheck_started_at=datetime.now(UTC).isoformat(),
        download_reused=True,
        download_provenance="Original context download.bin copied; no new download or SD/Actions/NOR write",
        postcheck_scope="One later identity check; context/Actions remain original historical observations",
    )
    try:
        with (new_out / "download.bin").open("xb") as out:
            out.write(data)
        asyncio.run(postcheck(report))
        if (original_context_dir / "report.json").read_bytes() != raw or (
            original_context_dir / "download.bin"
        ).read_bytes() != data:
            raise ValueError("Original context changed during postcheck")
        report["ok"] = True
    except BaseException as error:
        report["error"] = report["after_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["postcheck_ended_at"] = report["ended_at"] = datetime.now(UTC).isoformat()
        with (new_out / "report.json").open("x") as out:
            out.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": True, "download_reused": True, "postcheck_parent": report["postcheck_parent"]}))


if __name__ == "__main__":
    typer.run(main)
