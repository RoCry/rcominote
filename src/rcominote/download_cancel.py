"""Explicit cancellation outcome; a stop acknowledgment does not prove worker exit."""

import asyncio


class DownloadCancelled(asyncio.CancelledError):
    """Keep asyncio cancellation semantics and the observed transfer boundary."""

    def __init__(
        self,
        *,
        name: str,
        offset: int,
        received: int,
        declared_size: int | None,
        stop_result: dict,
    ):
        super().__init__(f"Recording download canceled: {name}; reconnect before another request")
        self.name = name
        self.offset = offset
        self.received = received
        self.declared_size = declared_size
        self.stop_result = stop_result
        self.export_result: dict | None = None
