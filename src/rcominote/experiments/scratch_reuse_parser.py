"""Independent same-file nonce parser; never changes historical NOR grammar."""

import re

from rcominote.experiments import nor_freshness as F

NAME = "rc52cc41f671"
DUMP = f"dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-{NAME}.mp3"
NONCE = re.compile(r"rc[0-9a-f]{10}")
STRICT_POLICY = "all-critical-chain-bytes-in-difference-prefix-v2"
PADDING_POLICY = "canonical-row-address-leading-spaces-only-v3"
STATUS_POLICY = "canonical-row-padding-and-status-interior-literals-v4"
FORMAT_POLICY = "canonical-row-and-status-formatter-constants-v5"
PREFILL_GAP_POLICY = "prefill-exact-three-producer-dump-layouts-v2"
PREFILL_WAKE_GAP_POLICY = "prefill-exact-four-layouts-wake-lock-zero-v3"
WAKE_GAP = b"\n[os][I][1145]: Ble wake lock 0\r\n\r\n[logsrv][I][679]: "


def markers(data: bytes, pattern: re.Pattern) -> list:
    return [m for m in pattern.finditer(data + data) if m.start() < F.CAPACITY]


def absent(data: bytes, nonces: list[str]) -> None:
    if len(data) != F.CAPACITY or any(nonce.encode() in data + data for nonce in nonces):
        raise ValueError("Requires complete4096 predecessor with every future nonce absent")


def _status_literals(status):
    # Independent fixed template; both variable %x captures and CRLF stay strict.
    offset, pointer = status[1], status[2]
    expected = b"\r\nfread 512b: offset=0x" + offset + b", buf=0x" + pointer + b"\r\n"
    if expected != status[0]:
        raise ValueError("Status differs from exact audited formatter template")
    captures = [(status.start(n) - status.start(), status.end(n) - status.start()) for n in (1, 2)]
    return {i: expected[i] for i in range(2, len(expected) - 2) if not any(a <= i < b for a, b in captures)}


def _row_constant(row, column):
    # Exactly the fixed %8x address/framing and each trailing %2x separator.
    # Neither data-token character is fixed, including a high-nibble space.
    if not 0 <= row < 32:
        return None
    if 0 <= column < 10:
        return "row-address-framing", f"{row * 16:8x}: ".encode()[column]
    if column in (58, 59):
        return "row-crlf", b"\r\n"[column - 58]
    if 12 <= column <= 57 and (column - 12) % 3 == 0:
        return "row-byte-separator", 0x20
    return None


def _parse_ring(
    data: bytes,
    previous: bytes,
    *,
    nonce: str,
    nor_offset: int,
    prefix_policy: str = STRICT_POLICY,
    marker_previous: bytes | None = None,
    gap_policy: str | None = None,
) -> tuple[bytes, dict]:
    """One new physical dump marker anchors one circle, without oracle selection.

    An unchanged predecessor marker is historical and must precede the nonce.
    Reusing its exact physical location conservatively fails; no retry/salvage.
    """
    if gap_policy is not None and gap_policy not in (PREFILL_GAP_POLICY, PREFILL_WAKE_GAP_POLICY):
        raise ValueError("Unknown explicit producer/dump gap policy")
    if type(prefix_policy) is not str or prefix_policy not in (
        STRICT_POLICY,
        PADDING_POLICY,
        STATUS_POLICY,
        FORMAT_POLICY,
    ):
        raise ValueError("Unknown explicit difference-prefix policy")
    if any(not isinstance(value, bytes) or len(value) != F.CAPACITY for value in (data, previous)):
        raise ValueError("Requires two complete4096 physical rings")
    if not isinstance(nonce, str) or NONCE.fullmatch(nonce) is None:
        raise ValueError("Requires fixed rc10hex uptime nonce")
    if type(nor_offset) is not int or not 0 <= nor_offset < 0x400000 or nor_offset % 512:
        raise ValueError("Private grammar requires aligned512-byte actual NOR offset")
    absent(previous, [nonce])
    marker_history = previous if marker_previous is None else marker_previous
    if marker_previous is not None:
        absent(marker_history, [nonce])
    dump = DUMP.encode()
    pattern = re.compile(rb"logsrv: cmd\(([0-9]+)\) " + re.escape(dump) + rb"\n\r\n")
    old = {(m.start(), m.end()) for m in markers(marker_history, pattern) if m[0] == F._echo(dump)}
    current = markers(data, pattern)
    if any(m[0] != F._echo(dump) for m in current):
        raise ValueError("Dump echo length differs from exact63-byte command")
    fresh = [m for m in current if (m.start(), m.end()) not in old]
    if len(fresh) != 1:
        raise ValueError("Requires exactly one new physical current dump marker")
    origin = fresh[0].end()
    linear = (data * 3)[origin : origin + F.CAPACITY]
    dump_start = F.CAPACITY - len(F._echo(dump))
    uptime = f"kernel uptime {nonce}".encode()
    nonce_pattern = re.compile(rb"logsrv: cmd\(([0-9]+)\) " + re.escape(uptime) + rb"\n\r\n")
    echoes = markers(data, nonce_pattern)
    if len(echoes) != 1 or echoes[0][0] != F._echo(uptime):
        raise ValueError("Requires unique complete exact27-byte uptime echo")
    if sum(m.start() < F.CAPACITY for m in re.finditer(re.escape(nonce.encode()), data + data)) != 1:
        raise ValueError("Nonce must occur exactly once in physical ring")
    start = (echoes[0].start() - origin) % F.CAPACITY
    end = start + len(F._echo(uptime))
    if end >= dump_start or linear[start:end] != F._echo(uptime):
        raise ValueError("Complete fresh nonce must precede current chain within one circle")
    historical = []
    for marker in current:
        if marker is fresh[0]:
            continue
        at = (marker.start() - origin) % F.CAPACITY
        if at + len(marker[0]) > start:
            raise ValueError("Historical same dump must fully precede current nonce")
        historical.append([marker.start(), marker.end()])
    scope = linear[end:dump_start]
    statuses, producers = list(F.STATUS.finditer(scope)), list(F.PRODUCER.finditer(scope))
    if len(statuses) != 1 or len(producers) != 1 or F.FAILURE.search(scope):
        raise ValueError("Fresh nonce scope requires one status/producer and no failure/error")
    if b"kernel uptime" in scope or b"dbg dumpbuf" in scope:
        raise ValueError("Another uptime or dump interrupts current acquisition")
    status, producer = statuses[0], producers[0]
    literal = "0" if nor_offset == 0 else hex(nor_offset)
    if status[1] != f"{nor_offset:x}".encode() or producer[0] != F._echo(
        f"dbg fread spi_flash {literal}".encode()
    ):
        raise ValueError("Current status/nearest producer differs from exact known target")
    row_start, row_end = status.end() + 6, producer.start() - len(F.LOG_PREFIX)
    if scope[status.end() : row_start] != b"\r\n" * 3 or scope[row_end : producer.start()] != F.LOG_PREFIX:
        raise ValueError("Status/rows/producer formatter differs from actual firmware")
    sector = F._rows(scope, row_start, row_end)
    gap = scope[producer.end() :]
    notice = gap == b"\n" + F.COMPOSER_FPS2 + F.LOG_PREFIX
    new_notice = gap == b"\n\r\n" + F.COMPOSER_FPS2 + F.LOG_PREFIX[2:]
    wake_notice = gap_policy == PREFILL_WAKE_GAP_POLICY and gap == WAKE_GAP
    if (
        gap != b"\n" + F.LOG_PREFIX
        and not notice
        and not (gap_policy in (PREFILL_GAP_POLICY, PREFILL_WAKE_GAP_POLICY) and new_notice)
        and not wake_notice
    ):
        raise ValueError("Unexpected text after current producer before dump")

    def span(a, b):
        physical = (origin + a) % F.CAPACITY
        return [physical, physical + b - a]

    prefix = max((i + 1 for i, (a, b) in enumerate(zip(data, previous, strict=True)) if a != b), default=0)
    critical = [
        (start, end),
        (end + status.start(), end + status.end()),
        (end + row_start, end + row_end),
        (end + producer.start(), end + producer.end()),
        (dump_start, F.CAPACITY),
    ]
    if gap_policy == PREFILL_WAKE_GAP_POLICY:
        critical.append((end + producer.end(), dump_start))
    exemptions, status_exemptions, formatter_exemptions = [], [], []
    status_literals = _status_literals(status) if prefix_policy in (STATUS_POLICY, FORMAT_POLICY) else {}
    for a, b in critical:
        for i in range(a, b):
            physical = (origin + i) % F.CAPACITY
            if physical < prefix:
                continue
            relative = i - (end + row_start)
            row, column = divmod(relative, 60)
            status_relative = i - (end + status.start())
            if prefix_policy == FORMAT_POLICY:
                role = _row_constant(row, column)
                if status_relative in status_literals:
                    role = "status-interior-literal", status_literals[status_relative]
                    position = {"status_relative_index": status_relative}
                else:
                    position = {"row_index": row, "column": column}
                if role is not None:
                    kind, expected = role
                    if data[physical] != expected or previous[physical] != expected:
                        raise ValueError("Unproven formatter constant differs from template/predecessor")
                    formatter_exemptions.append(
                        {
                            "kind": kind,
                            "physical_index": physical,
                            **position,
                            "expected": f"{expected:02x}",
                            "current": f"{data[physical]:02x}",
                            "previous": f"{previous[physical]:02x}",
                        }
                    )
                    continue
                raise ValueError("Current chain depends on tail outside difference-proven written prefix")
            if prefix_policy == STATUS_POLICY and status_relative in status_literals:
                expected = status_literals[status_relative]
                if data[physical] != expected or previous[physical] != expected:
                    raise ValueError("Unproven status literal differs from exact template/predecessor")
                status_exemptions.append(
                    {
                        "kind": "status-interior-literal",
                        "physical_index": physical,
                        "status_relative_index": status_relative,
                        "expected": f"{expected:02x}",
                        "current": f"{data[physical]:02x}",
                        "previous": f"{previous[physical]:02x}",
                    }
                )
                continue
            if (
                prefix_policy not in (PADDING_POLICY, STATUS_POLICY)
                or not 0 <= row < 32
                or column >= 8 - len(f"{row * 16:x}")
                or data[physical] != 0x20
                or previous[physical] != 0x20
            ):
                raise ValueError("Current chain depends on tail outside difference-proven written prefix")
            exemptions.append(
                {
                    "physical_index": physical,
                    "row_index": row,
                    "column": column,
                    "current": "20",
                    "previous": "20",
                }
            )
    proof = {
        "rule": "same-scratch-unique-fresh-nonce-new-physical-dump-status32rows-v1",
        "previous_ring_sha256": F._sha(previous),
        "ring_sha256": F._sha(data),
        "sector_sha256": F._sha(sector),
        "nonce": nonce,
        "nor_offset": nor_offset,
        "bytes": 512,
        "rows": 32,
        "nonce_span": span(start, end),
        "status_span": span(end + status.start(), end + status.end()),
        "rows_span": span(end + row_start, end + row_end),
        "producer_span": span(end + producer.start(), end + producer.end()),
        "dump_span": span(dump_start, F.CAPACITY),
        "historical_dump_spans": historical,
        "composer_fps2": notice,
        "new_physical_dump_required": True,
        "oracle_used_to_select_chain": False,
        "difference_proven_written_prefix_bytes": prefix,
        "critical_chain_inside_written_prefix": True,
    }
    if prefix_policy in (PADDING_POLICY, STATUS_POLICY):
        del proof["critical_chain_inside_written_prefix"]
        proof.update(
            prefix_policy=prefix_policy,
            address_padding_exemptions=exemptions,
            critical_nonpadding_chain_inside_written_prefix=True,
        )
    if prefix_policy == STATUS_POLICY:
        del proof["critical_nonpadding_chain_inside_written_prefix"]
        proof.update(
            status_literal_exemptions=status_exemptions,
            critical_variable_and_unexempted_chain_inside_written_prefix=True,
        )
    if prefix_policy == FORMAT_POLICY:
        del proof["critical_chain_inside_written_prefix"]
        proof.update(
            prefix_policy=prefix_policy,
            formatter_constant_exemptions=formatter_exemptions,
            critical_variable_and_unexempted_chain_inside_written_prefix=True,
        )
    if gap_policy is not None:
        proof["composer_fps2"] = notice or new_notice
        proof["producer_dump_gap"] = {
            "policy": gap_policy,
            "form": "wake-lock-zero"
            if wake_notice
            else "composer-before-crlf"
            if notice
            else "crlf-before-composer"
            if new_notice
            else "plain",
            "hex": gap.hex(),
            "span": span(end + producer.end(), dump_start),
        }
        if gap_policy == PREFILL_WAKE_GAP_POLICY:
            proof["producer_dump_gap"]["inside_written_prefix"] = True
    if marker_previous is not None:
        proof.update(
            marker_previous_ring_sha256=F._sha(marker_history),
            predecessor_roles={
                "difference_prefix": "verified-SD-RAM-prefill",
                "markers_and_nonce": "last-actual-retained-ring",
            },
        )
    return sector, proof


def parse_ring(data: bytes, previous: bytes, *, nonce: str, nor_offset: int) -> tuple[bytes, dict]:
    """Historical known controls remain restricted to boot0 and4200."""
    if type(nor_offset) is not int or nor_offset not in (0, 0x4200):
        raise ValueError("Only independent known boot0 and4200 targets permitted")
    return _parse_ring(data, previous, nonce=nonce, nor_offset=nor_offset)


def parse_prefilled_ring(
    data: bytes,
    prefill: bytes,
    marker_history: bytes,
    *,
    nonce: str,
    nor_offset: int,
    gap_policy: str | None = None,
):
    """Only structural known0/4200: separate full SD seed from ring history."""
    if type(nor_offset) is not int or nor_offset not in (0, 0x4200):
        raise ValueError("Prefilled parser is restricted to known0 and4200")
    if gap_policy == PREFILL_WAKE_GAP_POLICY:
        raise ValueError("Known prefilled controls retain original three-layout policy")
    if (
        any(
            not isinstance(value, bytes) or len(value) != F.CAPACITY
            for value in (data, prefill, marker_history)
        )
        or prefill[-1] != 0x48
        or data[-1] == 0x48
    ):
        raise ValueError("Requires complete prefill ending48 and changed full current file tail")
    sector, proof = _parse_ring(
        data,
        prefill,
        nonce=nonce,
        nor_offset=nor_offset,
        marker_previous=marker_history,
        gap_policy=gap_policy,
    )
    if proof["difference_proven_written_prefix_bytes"] != F.CAPACITY:
        raise ValueError("Structural control requires strict complete4096 difference prefix")
    return sector, proof


def parse_system_ring(data: bytes, previous: bytes, *, nonce: str) -> tuple[bytes, dict]:
    """Only the fixed unknown physical system24200 page; no address argument."""
    sector, proof = _parse_ring(data, previous, nonce=nonce, nor_offset=0x24200)
    return sector, proof | {"target_profile": "fixed-unknown-system24200"}
