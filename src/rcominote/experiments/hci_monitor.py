"""Monitor queue timestamps: preserve event and directional ACL timestamp order.

Historical hci_interval.Snoop stays byte-identical for pinned public receipts.
Only monitor ingestion changes; decoding and all ownership/parameter gates are
shared with that module. No sorting, timestamp repair or dropped-byte salvage.
"""

import struct

from rcominote.experiments import hci_interval as H


class Snoop:
    """Incremental records: incomplete live tail waits; truncated final input fails."""

    def __init__(self):
        self.buffer = bytearray()
        self.started = False
        self.total = self.records = self.last_stamp = 0
        self.events: list[dict] = []
        self.timestamp_inversions: list[dict] = []
        self._stream_stamps: dict[tuple[int, str | int], int] = {}
        self._previous_record: tuple[int, int, int] | None = None

    def feed(self, data: bytes, *, final: bool = False) -> None:
        self.total += len(data)
        if self.total > H.LIMIT:
            raise ValueError("HCI capture exceeds 8 MiB bound")
        self.buffer.extend(data)
        if not self.started and len(self.buffer) >= 16:
            if self.buffer[:16] != H.HEADER:
                raise ValueError("Requires BlueZ monitor btsnoop version1/type2001")
            del self.buffer[:16]
            self.started = True
        while self.started and len(self.buffer) >= 24:
            original, size, flags, drops, stamp = struct.unpack_from(">IIIIQ", self.buffer)
            if original != size or size > 65535 or drops:
                raise ValueError("Truncated/dropped HCI record")
            if len(self.buffer) < 24 + size:
                break
            packet = bytes(self.buffer[24 : 24 + size])
            controller, opcode = flags >> 16, flags & 0xFFFF
            event = H.decode(opcode, packet)
            # RX timestamps precede rx_work/monitor delivery, unlike TX's
            # immediate monitor copy. Preserve queue order and original stamps;
            # only gate events and each directional ACL stream must be monotonic.
            stream = (controller, "event") if event is not None else None
            if opcode in (4, 5):
                stream = (controller, opcode)
            if stream is not None and stamp < self._stream_stamps.get(stream, 0):
                raise ValueError("Nonmonotonic gating-event or directional ACL timestamp")
            # Commit only complete, structurally valid records. last_stamp is a
            # capture-wide upper bound, not the preceding record's timestamp.
            if self._previous_record is not None:
                previous, previous_flags, previous_stamp = self._previous_record
                if stamp < previous_stamp:
                    self.timestamp_inversions.append(
                        {
                            "previous_record": previous,
                            "record": self.records + 1,
                            "previous_flags": previous_flags,
                            "flags": flags,
                            "delta_us": stamp - previous_stamp,
                        }
                    )
            del self.buffer[: 24 + size]
            self.records += 1
            self.last_stamp = max(self.last_stamp, stamp)
            self._previous_record = (self.records, flags, stamp)
            if stream is not None:
                self._stream_stamps[stream] = stamp
            if event is not None and controller == 0:  # Only hci0 events prove the owned gate.
                self.events.append(event | {"record": self.records, "timestamp_us": stamp})
        if final and (not self.started or self.buffer):
            raise ValueError("Incomplete final btsnoop header/record")
