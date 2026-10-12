"""Captured header plus interrupted-transfer, conflict and corruption sequences.

No synthetic body is represented as a successful complete firmware image.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from rcominote.code_references import read_block
from rcominote.image_store import ImageStore, _publish_image, validate_body_checksum

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/image-header-first-2026-10-12.json"


@pytest.fixture
def header():
    capture = json.loads(EVIDENCE.read_text())
    return b"".join(read_block(capture, address, 16) for address in range(0x10000000, 0x10000200, 16))


def test_resume_after_committed_chunk_and_lost_ack(tmp_path, header):
    root = tmp_path / "chunks"
    store = ImageStore(root, header)
    store.add_chunk(0, b"\xaa" * 512)
    resumed = ImageStore(root, header)
    retry = resumed.add_chunk(0, b"\xaa" * 512)
    assert retry["status"] == "already_present"
    # 927120 = 1810*512 +400: first committed chunk excluded on resume.
    missing = resumed.missing_chunks()
    assert (len(missing), missing[0], missing[-1]) == (1810, (512, 512), (0xE2400, 400))


def test_conflicting_retry_cannot_replace_committed_record(tmp_path, header):
    store = ImageStore(tmp_path / "chunks", header)
    store.add_chunk(0, b"\xaa" * 512)
    before = (store.root / "00000000.json").read_bytes()
    with pytest.raises(ValueError, match="Conflicting immutable"):
        store.add_chunk(0, b"\xbb" * 512)
    assert (store.root / "00000000.json").read_bytes() == before


def test_failed_publication_has_no_resume_progress(tmp_path, header):
    store = ImageStore(tmp_path / "chunks", header)
    with (
        patch("rcominote.image_store.os.link", side_effect=OSError("lost storage")),
        pytest.raises(OSError, match="lost storage"),
    ):
        store.add_chunk(0, b"\xaa" * 512)
    # Also model an abrupt process exit leaving an incomplete unlinked file.
    (store.root / ".part-interrupted").write_bytes(b'{"offset":0')
    assert ImageStore(store.root, header).missing_chunks()[0] == (0, 512)
    assert not (store.root / "00000000.json").exists()


def test_corrupt_saved_bytes_fail_when_resuming(tmp_path, header):
    store = ImageStore(tmp_path / "chunks", header)
    store.add_chunk(0, b"\xaa" * 512)
    path = store.root / "00000000.json"
    row = json.loads(path.read_text())
    row["hex"] = "bb" + row["hex"][2:]
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="length/hash mismatch"):
        ImageStore(store.root, header)


@pytest.mark.parametrize("offset,length", [(-512, 512), (1, 512), (927120, 512), (0, 511), (0xE2400, 512)])
def test_invalid_fixed_chunk_range_or_size_never_commits(tmp_path, header, offset, length):
    store = ImageStore(tmp_path / "chunks", header)
    with pytest.raises(ValueError, match="offset|requires exactly"):
        store.add_chunk(offset, bytes(length))
    assert list(store.root.iterdir()) == [store.root / "header.json"]


def test_wrong_header_rejected_before_creating_store(tmp_path, header):
    changed = bytes([header[0] ^ 1]) + header[1:]
    with pytest.raises(ValueError, match="validated CoMi"):
        ImageStore(tmp_path / "chunks", changed)
    assert not (tmp_path / "chunks").exists()


def test_changed_persisted_header_rejected(tmp_path, header):
    store = ImageStore(tmp_path / "chunks", header)
    row = json.loads((store.root / "header.json").read_text())
    row["hex"] = "00" * 512
    (store.root / "header.json").write_text(json.dumps(row))
    with pytest.raises(ValueError, match="length/hash mismatch"):
        ImageStore(store.root, header)


def test_incomplete_image_cannot_publish_output(tmp_path, header):
    store = ImageStore(tmp_path / "chunks", header)
    store.add_chunk(0, b"\xaa" * 512)
    out = tmp_path / "image.bin"
    with pytest.raises(ValueError, match="1810 chunks missing; first=0x200"):
        store.finalize(out)
    assert not out.exists()


def test_zero_filled_full_body_fails_actual_stored_checksum():
    # All u32 words sum to0; 0+4e7a894a !=ffffffff. Not a fabricated good dump.
    with pytest.raises(ValueError, match="sum=0x00000000"):
        validate_body_checksum(bytes(927120))


def test_publication_retry_after_lost_result_verifies_existing_file(tmp_path):
    # Exercise publication alone; abc is not claimed to be a valid firmware.
    out = tmp_path / "mapped-system.bin"
    _publish_image(out, b"abc")
    committed = out.stat()
    assert _publish_image(out, b"abc") == "existing_verified"
    assert (out.stat().st_ino, out.stat().st_mtime_ns) == (committed.st_ino, committed.st_mtime_ns)


@pytest.mark.parametrize("conflict", [b"xyz", b"ab"])
def test_publication_retry_refuses_conflicting_existing_bytes(tmp_path, conflict):
    out = tmp_path / "mapped-system.bin"
    _publish_image(out, conflict)
    with pytest.raises(ValueError, match="differs from verified chunks"):
        _publish_image(out, b"abc")
    assert out.read_bytes() == conflict


def test_publication_retry_refuses_symlink_even_if_target_matches(tmp_path):
    target = tmp_path / "other.bin"
    target.write_bytes(b"abc")
    out = tmp_path / "mapped-system.bin"
    out.symlink_to(target)
    with pytest.raises(ValueError, match="regular file"):
        _publish_image(out, b"abc")
    assert out.is_symlink()
