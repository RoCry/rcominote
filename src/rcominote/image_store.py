"""Immutable, resumable chunks of the one evidenced mapped-system image.

This is offline storage, not a flash reader. JSON chunk records atomically bind
bytes and their SHA-256; incomplete temporary records never count as progress.
"""

import hashlib
import json
import os
import re
import struct
import tempfile
from pathlib import Path

BASE = 0x10000000
HEADER_BYTES = 512
HEADER_SHA256 = "911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5"
BODY_BASE = BASE + HEADER_BYTES
BODY_BYTES = 927120
IMAGE_BYTES = HEADER_BYTES + BODY_BYTES
CHUNK_BYTES = 512
STORED_BODY_CHECKSUM = 0x4E7A894A
CHUNKS = tuple(
    (offset, min(CHUNK_BYTES, BODY_BYTES - offset)) for offset in range(0, BODY_BYTES, CHUNK_BYTES)
)
CHUNK_LENGTHS = dict(CHUNKS)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _publish(path: Path, data: bytes) -> None:
    """Atomic no-replacement publication; crash remnants remain uncommitted."""
    descriptor, name = tempfile.mkstemp(prefix=".part-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _record(offset: int, data: bytes) -> bytes:
    return (
        json.dumps(
            {"offset": offset, "length": len(data), "sha256": _sha(data), "hex": data.hex()},
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _publish_image(path: Path, data: bytes) -> str:
    """Recover publication followed by interruption; never replace conflicting output."""
    try:
        _publish(path, data)
    except FileExistsError:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Existing mapped image must be a regular file: {path}") from None
        existing = path.read_bytes()
        if len(existing) != len(data) or _sha(existing) != _sha(data):
            raise ValueError(f"Existing mapped image differs from verified chunks: {path}") from None
        return "existing_verified"
    return "published"


def _read_record(path: Path, offset: int, length: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Image record must be a regular file: {path}")
    row = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(row, dict) or set(row) != {"offset", "length", "sha256", "hex"}:
        raise ValueError(f"Invalid image record: {path}")
    if row["offset"] != offset or row["length"] != length or not isinstance(row["hex"], str):
        raise ValueError(f"Image record range mismatch: {path}")
    try:
        data = bytes.fromhex(row["hex"])
    except ValueError as error:
        raise ValueError(f"Invalid image record bytes: {path}") from error
    if len(data) != length or _sha(data) != row["sha256"]:
        raise ValueError(f"Image record length/hash mismatch: {path}")
    return data


def validate_body_checksum(body: bytes) -> int:
    """Fixed ACTH image checksum: little-endian u32 sum plus stored field."""
    if len(body) != BODY_BYTES:
        raise ValueError(f"Mapped body must contain exactly {BODY_BYTES} bytes")
    checksum = sum(word for (word,) in struct.iter_unpack("<I", body)) & 0xFFFFFFFF
    if (checksum + STORED_BODY_CHECKSUM) & 0xFFFFFFFF != 0xFFFFFFFF:
        raise ValueError(f"Mapped body checksum mismatch: sum={checksum:#010x}")
    return checksum


def _validate_header(header: bytes) -> None:
    if len(header) != HEADER_BYTES or _sha(header) != HEADER_SHA256:
        raise ValueError("Header is not the validated CoMi mapped-system header")


def inspect_image(image: bytes) -> dict:
    """Validate the one evidenced complete mapped image, entirely offline."""
    if len(image) != IMAGE_BYTES:
        raise ValueError(f"Mapped image must contain exactly {IMAGE_BYTES} bytes; got {len(image)}")
    _validate_header(image[:HEADER_BYTES])
    body_sum = validate_body_checksum(image[HEADER_BYTES:])
    return {
        "scope": "mapped-system image; not a raw Flash backup",
        "base": hex(BASE),
        "bytes": len(image),
        "sha256": _sha(image),
        "header_sha256": HEADER_SHA256,
        "body_word_sum": hex(body_sum),
        "stored_body_checksum": hex(STORED_BODY_CHECKSUM),
        "checksum_verified": True,
        "limits": ["No physical Flash mapping proven", "No complete device backup or restore validation"],
    }


class ImageStore:
    """Store only aligned chunks of the fixed, validated CoMi mapped image.

    Offsets are relative to its body. Addresses are derived from BODY_BASE;
    callers cannot select a different image or an arbitrary memory region.
    """

    def __init__(self, root: Path, header: bytes):
        _validate_header(header)
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.header = header
        self._header_path = self.root / "header.json"
        if not self._header_path.exists() and not self._header_path.is_symlink():
            if any(not path.name.startswith(".part-") for path in self.root.iterdir()):
                raise ValueError("Existing image store has no committed header")
            try:
                _publish(self._header_path, _record(-HEADER_BYTES, header))
            except FileExistsError:
                pass  # Another initializer won; validate its immutable record below.
        self._load()

    def _load(self) -> dict[int, bytes]:
        if _read_record(self._header_path, -HEADER_BYTES, HEADER_BYTES) != self.header:
            raise ValueError("Persisted header differs from validated CoMi header")
        chunks = {}
        for path in self.root.iterdir():
            if path.name == "header.json" or path.name.startswith(".part-"):
                continue
            if not re.fullmatch(r"[0-9a-f]{8}\.json", path.name):
                raise ValueError(f"Unexpected file in image store: {path}")
            offset = int(path.stem, 16)
            if offset not in CHUNK_LENGTHS:
                raise ValueError(f"Image chunk outside fixed body range: {path}")
            chunks[offset] = _read_record(path, offset, CHUNK_LENGTHS[offset])
        return chunks

    def missing_chunks(self) -> list[tuple[int, int]]:
        """Body-relative offsets and exact lengths; reread records before resuming."""
        saved = self._load()
        return [(offset, length) for offset, length in CHUNKS if offset not in saved]

    def add_chunk(self, offset: int, data: bytes) -> dict:
        """Commit one fixed chunk; identical retries are safe, conflicts fail."""
        if type(offset) is not int or offset not in CHUNK_LENGTHS:
            raise ValueError("Chunk offset must select an aligned chunk of the fixed mapped body")
        if not isinstance(data, bytes) or len(data) != CHUNK_LENGTHS[offset]:
            raise ValueError(f"Chunk at {offset:#x} requires exactly {CHUNK_LENGTHS[offset]} bytes")
        if _read_record(self._header_path, -HEADER_BYTES, HEADER_BYTES) != self.header:
            raise ValueError("Persisted header differs from validated CoMi header")
        path = self.root / f"{offset:08x}.json"
        try:
            _publish(path, _record(offset, data))
            status = "stored"
        except FileExistsError:
            if _read_record(path, offset, len(data)) != data:
                raise ValueError(f"Conflicting immutable image chunk at {offset:#x}") from None
            status = "already_present"
        return {
            "offset": offset,
            "address": hex(BODY_BASE + offset),
            "bytes": len(data),
            "sha256": _sha(data),
            "status": status,
        }

    def finalize(self, out: Path) -> dict:
        """Publish only a complete checksum-valid mapped image outside the store."""
        out = Path(out)
        if out.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Final image output must be outside the chunk store")
        chunks = self._load()
        missing = [offset for offset, _ in CHUNKS if offset not in chunks]
        if missing:
            raise ValueError(f"Mapped image incomplete: {len(missing)} chunks missing; first={missing[0]:#x}")
        image = self.header + b"".join(chunks[offset] for offset, _ in CHUNKS)
        report = inspect_image(image)
        out.parent.mkdir(parents=True, exist_ok=True)
        publication = _publish_image(out, image)
        return report | {"path": str(out), "publication": publication}
