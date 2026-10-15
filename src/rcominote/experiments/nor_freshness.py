"""Strict FW010004 fread text association in one complete physical printk ring.

Pure parser: callers own the fixed target allowlist, live code/identity guards,
Actions/transport proof and independent read/oracle policy. This proves one
coherent retained text chain, not hardware read correctness by itself.
"""

import hashlib
import re

CAPACITY = 4096
LOG_PREFIX = b"\r\n[logsrv][I][679]: "  # Actual20-byte prefix before both command echoes.
COMPOSER_FPS2 = b"[composer][I][742]: post fps 2\n\r\n"  # Exact observed33-byte notice.
DUMP = re.compile(r"dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rc[0-9a-f]{10}\.mp3")
PRODUCER = re.compile(rb"logsrv: cmd\(([0-9]+)\) (dbg fread[^\r\n]*)\n\r\n")
STATUS = re.compile(rb"\r\nfread 512b: offset=0x([0-9a-f]{1,8}), buf=0x([0-9a-f]{1,8})\r\n")
FAILURE = re.compile(rb"fail(?:ed|ure)?|\berror\b", re.IGNORECASE)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump_command(command: str) -> bytes:
    if not isinstance(command, str) or DUMP.fullmatch(command) is None:
        raise ValueError("Requires exact fixed4096 ring dump with a scratch nonce")
    return command.encode("ascii")


def _echo(command: bytes) -> bytes:
    return b"logsrv: cmd(" + str(len(command) + 1).encode() + b") " + command + b"\n\r\n"


def _unique_dump(data: bytes, command: bytes) -> tuple[int, int]:
    pattern = re.compile(rb"logsrv: cmd\(([0-9]+)\) " + re.escape(command) + rb"\n\r\n")
    matches = [match for match in pattern.finditer(data + data) if match.start() < CAPACITY]
    if len(matches) != 1:
        raise ValueError("Requires one complete current/previous dump echo in physical ring")
    match = matches[0]
    if match[0] != _echo(command):
        raise ValueError("Dump echo command length differs from actual newline-terminated command")
    return match.start(), match.end()


def _rows(data: bytes, start: int, end: int) -> bytes:
    if end - start != 32 * 60:
        raise ValueError("Requires exactly32 complete contiguous fixed-width NOR rows")
    sector = bytearray()
    for index in range(32):
        line = data[start + index * 60 : start + (index + 1) * 60]
        try:
            values = bytes(int(token, 16) for token in line[10:58].split())
        except ValueError as error:
            raise ValueError("Invalid hex bytes in NOR row") from error
        if len(values) != 16:
            raise ValueError("NOR row must contain exactly16 bytes")
        canonical = (f"{index * 16:8x}: " + "".join(f"{value:2x} " for value in values) + "\r\n").encode()
        if line != canonical:
            raise ValueError("NOR row offset, width, hex format or delimiter differs from FW010004")
        sector.extend(values)
    return bytes(sector)


def parse_ring(
    data: bytes,
    *,
    nor_offset: int,
    producer_command: str,
    dump_command: str,
    previous_dump: str | None = None,
    allow_composer_fps2: bool = False,
) -> tuple[bytes, dict]:
    """Return sector512 and spans; any declared previous marker is mandatory.

    Spans start at physical ring indices0..4095; an end above4096 denotes wrap.
    Exact observed formatter/prefix bytes are deliberate fail-closed boundaries.
    No salvage, nearest-old-candidate search, partial assembly or oracle filling.
    The explicit option permits one exact notice only after the producer echo;
    it never removes bytes or relaxes status/rows/failure/previous-marker checks.
    """
    if type(allow_composer_fps2) is not bool:
        raise ValueError("allow_composer_fps2 must be bool")
    if not isinstance(data, bytes) or len(data) != CAPACITY:
        raise ValueError("Requires complete4096-byte physical printk ring")
    if type(nor_offset) is not int or not 0 <= nor_offset < 0x400000 or nor_offset % 512:
        raise ValueError("NOR target must be an aligned512-byte offset within actual4MiB")
    literal = "0" if nor_offset == 0 else hex(nor_offset)
    if producer_command != f"dbg fread spi_flash {literal}":
        raise ValueError("Producer text differs from exact declared NOR target")
    command = _dump_command(dump_command)
    if previous_dump == dump_command:
        raise ValueError("Previous and current dump nonces must differ")
    _, physical_end = _unique_dump(data, command)
    # One4096-byte circle ends at the complete current echo. All accepted
    # status/rows/producer bytes must occur in this same linearized circle.
    origin = physical_end
    linear = (data * 3)[origin : origin + CAPACITY]
    dump_start = CAPACITY - len(_echo(command))
    if linear[dump_start:] != _echo(command):
        raise ValueError("Current dump echo crosses an inconsistent circle boundary")
    echoes = list(PRODUCER.finditer(linear[:dump_start]))
    if not echoes:
        raise ValueError("No complete producer before current dump")
    producer = echoes[-1]  # Most recent producer of ANY target, not just desired text.
    if producer[0] != _echo(producer_command.encode("ascii")):
        raise ValueError("Most recent producer/length differs from current target")
    gap = linear[producer.end() : dump_start]
    notice = allow_composer_fps2 and gap == b"\n" + COMPOSER_FPS2 + LOG_PREFIX
    if gap != b"\n" + LOG_PREFIX and not notice:
        raise ValueError("Unexpected text/status/failure between current producer and dump")
    statuses = list(STATUS.finditer(linear[: producer.start()]))
    if not statuses:
        raise ValueError("No complete fread status before current producer")
    status = statuses[-1]
    if status[1] != f"{nor_offset:x}".encode():
        raise ValueError("Most recent fread status differs from target offset")
    row_start = status.end() + 6
    row_end = producer.start() - len(LOG_PREFIX)
    if linear[status.end() : row_start] != b"\r\n" * 3 or linear[row_end : producer.start()] != LOG_PREFIX:
        raise ValueError("Status/rows/producer formatter boundaries differ from actual FW010004")
    sector = _rows(linear, row_start, row_end)
    scope_start = status.start()
    previous_span = None
    if previous_dump is not None:
        previous_command = _dump_command(previous_dump)
        previous_start, previous_end = _unique_dump(data, previous_command)
        at = (previous_start - origin) % CAPACITY
        after = at + previous_end - previous_start
        if after > status.start() or linear[at:after] != _echo(previous_command):
            raise ValueError("Previous dump must fully precede current status inside this same circle")
        scope_start = after
        previous_span = [previous_start, previous_end]
    scope = linear[scope_start:dump_start]
    if len(list(STATUS.finditer(scope))) != 1 or len(list(PRODUCER.finditer(scope))) != 1:
        raise ValueError("Another fread status/producer interrupts the bounded current acquisition")
    if FAILURE.search(scope):
        raise ValueError("Failure/error text inside bounded current acquisition")

    def span(start: int, end: int) -> list[int]:
        physical = (origin + start) % CAPACITY
        return [physical, physical + end - start]

    proof = {
        "rule": "nearest-producer-exact-status32rows-prefix-dump-v1",
        "ring_sha256": _sha(data),
        "sector_sha256": _sha(sector),
        "nor_offset": nor_offset,
        "bytes": 512,
        "rows": 32,
        "status_span": span(status.start(), status.end()),
        "rows_span": span(row_start, row_end),
        "producer_span": span(producer.start(), producer.end()),
        "dump_span": span(dump_start, CAPACITY),
        "bounded_chain_bytes": CAPACITY - status.start(),
        "previous_dump_required": previous_dump is not None,
        "previous_dump_span": previous_span,
        "one_status_one_producer": True,
        "failure_text_absent": True,
    }
    if notice:
        notice_start = producer.end() + 1
        proof["rule"] = "nearest-producer-exact-status32rows-prefix-dump-composer-fps2-v1"
        proof["composer_notice"] = {
            "hex": COMPOSER_FPS2.hex(),
            "span": span(notice_start, notice_start + len(COMPOSER_FPS2)),
            "sha256": _sha(COMPOSER_FPS2),
        }
    return sector, proof
