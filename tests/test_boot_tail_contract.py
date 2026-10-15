"""Pure contracts and explicitly synthetic formatter fixtures; no device I/O."""

import copy
import gzip
from pathlib import Path
from unittest.mock import patch

import pytest

from rcominote.experiments import boot_tail_contract as C


def fixture(offset=0x2400):
    operations = []
    for index, operation_id in enumerate(("first", "second")):
        name = f"rc{index:010x}"
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        operations.append(
            {
                "operation_id": operation_id,
                "phase": C.PHASE,
                "name": name,
                "device_path": path,
                "source_address": hex(C.probe.BUFFER),
                "source_bytes": 4096,
                "dump_command": f"dbg dumpbuf {C.probe.BUFFER} 4096 {path}",
                "producer": f"dbg fread spi_flash {hex(offset)}",
                "transport_profile": "interval6-ce1",
                "independent_oracle": False,
                "pair_verified": False,
            }
        )
    return {
        "profile": C.PROFILE,
        "serial": C.OWNED_SERIAL,
        "source_image_sha256": C.probe.IMAGE_SHA,
        "coverage_basis": C.coverage_basis(),
        "nor_offset": offset,
        "independent_oracle": False,
        "transport": {"policy": C.condition.POLICY},
        "operations": operations,
    }


def echo(command):
    return f"logsrv: cmd({len(command) + 1}) {command}\n\r\n".encode()


def synthetic_ring(operation, sector, offset, *, previous=None):
    """Formatter-only test data, never a captured hardware observation."""
    status = f"\r\nfread 512b: offset={hex(offset)}, buf=0x18010000\r\n".encode()
    rows = b"".join(
        (f"{i:8x}: " + "".join(f"{b:2x} " for b in sector[i : i + 16]) + "\r\n").encode()
        for i in range(0, 512, 16)
    )
    prefix = b"\r\n[logsrv][I][679]: "
    body = status + b"\r\n" * 3 + rows + prefix + echo(operation["producer"])
    body += b"\n" + prefix + echo(operation["dump_command"])
    if previous:
        body = echo(previous) + bytes(100) + body
    return body.ljust(4096, b"\0")


def test_coverage_uses_actual_acpt_and_existing_chunk_without_tail_oracle():
    basis = C.coverage_basis()
    assert C.OFFSETS == (0x2400, 0x2600, 0x2800, 0x2A00, 0x2C00, 0x2E00)
    assert (basis["entry"]["name"], basis["entry"]["offset"], basis["entry"]["size_bytes"]) == (
        "fw1_boot",
        "0x2000",
        4096,
    )
    assert basis["previously_covered"] == [0x2000, 0x2400]
    assert basis["new_range"] == [0x2400, 0x3000] and basis["bytes"] == 3072
    assert basis["chunk2200"]["sha256"] == C.CHUNK_SHA
    assert basis["independent_oracle"] is False


@pytest.mark.parametrize("replacement", [bytes(512), bytes([255]) * 511])
def test_changed_public_chunk_rejected(replacement):
    original = Path.read_bytes

    def changed(path):
        return replacement if path == C.CHUNK else original(path)

    with patch.object(Path, "read_bytes", changed), pytest.raises(ValueError, match="chunk changed"):
        C.coverage_basis()


@pytest.mark.parametrize("offset", [True, False, -512, 0x2200, 0x3000, 0x2401, "0x2400", None])
def test_wrong_range_fails_before_reading_image_or_parent(offset, tmp_path):
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError, match="fixed aligned"):
        C.prepare(tmp_path / "missing.bin", tmp_path, offset)
    parent.assert_not_called()
    report = fixture()
    report["nor_offset"] = offset
    with pytest.raises(ValueError, match="fixed aligned"):
        C.recipe(report)


@pytest.mark.parametrize("offset", C.OFFSETS)
def test_all_six_offsets_parse_two_fresh_synthetic_observations(offset):
    report = fixture(offset)
    C.recipe(report)
    # Deliberately non-FF data: old public FF chunks cannot fill the unknown tail.
    sector = bytes(range(256)) * 2
    for index, operation in enumerate(report["operations"]):
        previous = report["operations"][0]["dump_command"] if index else None
        result = C.payload(report, operation, synthetic_ring(operation, sector, offset, previous=previous))
        assert result["nor_offset"] == offset and bytes.fromhex(result["sector_hex"]) == sector
        assert result["freshness"]["previous_dump_required"] == bool(index)
        assert result["verification_level"] == "fresh-complete-single-read-no-independent-oracle"
        assert operation["pair_verified"] is False and operation["independent_oracle"] is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("producer", "dbg fread spi_flash 0x2200"),
        ("producer", "dbg fread spi_flash 0x2600"),
        ("producer", "dbg fread spi_flash 9216"),
        ("phase", "backup-boot-block1"),
        ("source_address", "0x1803ee0a"),
        ("source_bytes", 512),
        ("source_bytes", True),
        ("transport_profile", "other"),
        ("independent_oracle", True),
        ("pair_verified", True),
        ("oracle", {}),
        ("operation_id", "../first"),
        ("name", "rc1234"),
        ("device_path", "/SD:/RECORDER/Call-other.mp3"),
        ("dump_command", "dbg dumpbuf 0 4096 /SD:/RECORDER/Call-rc0000000000.mp3"),
    ],
)
def test_operation_scope_and_nonce_contract_rejects_mutations(key, value):
    report = fixture()
    report["operations"][0][key] = value
    with pytest.raises(ValueError):
        C.recipe(report)


@pytest.mark.parametrize(
    "fault", ["profile", "serial", "image", "policy", "basis", "oracle", "independent", "count"]
)
def test_top_recipe_cannot_expand_or_claim_an_oracle(fault):
    report = fixture()
    match fault:
        case "profile" | "serial":
            report[fault] = "other"
        case "image":
            report["source_image_sha256"] = "0" * 64
        case "policy":
            report["transport"]["policy"] = "other"
        case "basis":
            report["coverage_basis"]["new_range"][1] = 0x4000
        case "oracle":
            report["oracle"] = {}
        case "independent":
            report["independent_oracle"] = True
        case "count":
            report["operations"].append(copy.deepcopy(report["operations"][0]))
    with pytest.raises(ValueError):
        C.recipe(report)


def test_second_requires_first_marker_and_rejects_a_foreign_operation():
    report = fixture()
    first, second = report["operations"]
    for ring in (synthetic_ring(first, bytes(512), 0x2400), synthetic_ring(second, bytes(512), 0x2400)):
        with pytest.raises(ValueError):
            C.payload(report, second, ring)
    foreign = second | {"producer": "dbg fread spi_flash 0x2600"}
    with pytest.raises(ValueError, match="actual fixed-sector"):
        C.payload(report, foreign, bytes(4096))


def test_legacy_payload_keeps_composer_option_disabled():
    report = fixture()
    with patch.object(C, "parse_ring", return_value=(bytes(512), {})) as parse:
        C.payload(report, report["operations"][0], bytes(4096))
    assert parse.call_args.kwargs["allow_composer_fps2"] is False


@pytest.mark.parametrize("allowed", [False, True])
def test_parse_payload_forwards_explicit_composer_option_and_previous_anchor(allowed):
    report = fixture()
    with patch.object(C, "parse_ring", return_value=(bytes(512), {})) as parse:
        C.parse_payload(report, report["operations"][1], bytes(4096), allow_composer_fps2=allowed)
    assert parse.call_args.kwargs["allow_composer_fps2"] is allowed
    assert parse.call_args.kwargs["previous_dump"] == report["operations"][0]["dump_command"]


@pytest.mark.parametrize("same_size", [False, True])
def test_wrong_image_never_checks_parent(tmp_path, same_size):
    image = tmp_path / "image.bin"
    image.write_bytes(bytes(927632) if same_size else b"wrong")
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError, match="complete FW"):
        C.prepare(image, tmp_path, 0x2400)
    parent.assert_not_called()


@pytest.mark.parametrize("fault", ["report", "capture"])
def test_wrong_parent_hash_never_replays_the_chain(tmp_path, fault):
    (tmp_path / "report.json").write_bytes(b"{}")
    (tmp_path / "session.btsnoop").write_bytes(b"invalid")
    # Isolate each pinned digest boundary; neither mock is a hardware fixture.
    hashes = ["0" * 64, C.PARENT_HCI_SHA] if fault == "report" else [C.PARENT_SHA, "0" * 64]
    with (
        patch.object(C.session.audit, "sha", side_effect=hashes),
        patch.object(C.unknown_pair, "replay") as replay,
        pytest.raises(ValueError, match="exact successful early"),
    ):
        C.parent_gate(tmp_path, tmp_path)
    replay.assert_not_called()


def test_prepare_requires_two_unique_names_without_retry_or_preclassified_success(tmp_path):
    image = tmp_path / "image.bin"
    image.write_bytes(
        gzip.decompress(Path("docs/evidence/minimal-image-2026-10-13/original-system.bin.gz").read_bytes())
    )
    with patch.object(C, "parent_gate", return_value={"unit_test_stub": True}):
        with patch.object(C.secrets, "token_hex", side_effect=["0000000000", "1111111111"]):
            report = C.prepare(image, tmp_path, 0x2E00)
        assert report["ok"] is False and report["pair_verified"] is False
        assert report["transport"]["update_attempted"] is False
        assert [op["producer"] for op in report["operations"]] == ["dbg fread spi_flash 0x2e00"] * 2
        with (
            patch.object(C.secrets, "token_hex", return_value="0000000000") as nonce,
            pytest.raises(ValueError, match="different new SD"),
        ):
            C.prepare(image, tmp_path, 0x2400)
        assert nonce.call_count == 2
