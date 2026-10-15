# Minimal safe slot-trial evidence

Eight samples,284 bytes: layout32, copy48, fresh pointer4/context32, trial global4/metadata32, exact random test-path completion marker53, already-public known code row79. Marker/row offsets refer to slot body starting at byte8; complete private slot512 represented only by SHA256 in the compact receipt. No other body or stale-tail bytes published.

[Result and reproduction](../../archive/logsrv-slot-live-2026-10-14.md). [Pinned receipt](../logsrv-slot-live-2026-10-14.json). One historical trial; no atomicity, still-partial, general512B reliability or NOR/firmware claim.
