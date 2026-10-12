# Rejected boot decode: reset32

Status: **invalid after first32 bytes; never use as executable/disassembly input**.

Original experiment applied the system-header32 B codec reset to boot. Magic/name
looked plausible but complete boot body checksum failed. Correct boot reset is512 B,
independently checked against stored body checksum. Retain this file only to explain
the failed hypothesis; no active code consumes it.

Authoritative replacement: [verified boot image](../../evidence/boot-complete-2026-10-12/decoded.bin),
[verification and candidate comparison](../../boot-complete.md).
