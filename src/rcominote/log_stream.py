"""Strict incremental Actions diagnostic stream decoder."""

from .log_probe import ACK


class Stream:
    """GATT notifications are fragments of the SDK byte stream, not message boundaries."""

    def __init__(self):
        self.pending = bytearray()
        self.frames: list[dict] = []
        self.acks = 0
        self.ended = False

    def feed(self, data: bytes):
        self.pending.extend(data)
        while len(self.pending) >= 5:
            if self.pending[0] != 0x1D or self.pending[2] != 0x81:
                raise ValueError(f"Unexpected Actions log header: {self.pending[:5].hex()}")
            length = int.from_bytes(self.pending[3:5], "little")
            if length > 4096:
                raise ValueError(f"Unexpected Actions log payload size {length}")
            if len(self.pending) < 5 + length:
                return
            frame = bytes(self.pending[: 5 + length])
            del self.pending[: 5 + length]
            command, payload = frame[1], frame[5:]
            row = {"command": command, "hex": frame.hex()}
            if command == 0x10:
                if frame != ACK:
                    raise ValueError(f"Unexpected ACK: {frame.hex()}")
                self.acks += 1
            elif command == 0xF1:
                if payload:
                    raise ValueError("Nonempty log end frame")
                self.ended = True
            elif command == 0xF0:
                if len(payload) < 3 or int.from_bytes(payload[1:3], "little") != len(payload) - 3:
                    raise ValueError("Invalid log TLV length")
                row |= {"log_type": payload[0], "text": payload[3:].decode("utf-8", errors="replace")}
            else:
                raise ValueError(f"Unexpected log command {command:#x}")
            self.frames.append(row)
