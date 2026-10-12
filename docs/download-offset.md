# Boyi recording byte offsets

`uv run comi download NAME --offset N --out DIR` exports a suffix of a listed
recording. Offset0 keeps normal `.mp3` output; nonzero offsets produce
`NAME.offset-N.bin`, explicitly **not a complete recording**. Atomic publication,
no overwrite, exact byte count and explicit device end required as before.

Wire request0b: name14 + offset u32 big-endian. Actual firmware declares full
file length **before** seeking offset; expected transfer length is total−offset.
See [actual worker](recording-download-path.md). Values outside unsigned32-bit
range fail before a write; offsets past listed/device-declared length fail;
EOF offset accepts only zero data and a valid terminator.

## Live proof — 2026-10-12

Owned C261CF0430, existing listed file20261012093123,1916 B. Full CLI export then
separate CLI export at deliberately unaligned offset17. Received1899 B, exactly
equal to full-file bytes `[17:]`; full/suffix hashes retained in
[evidence](evidence/download-offset-2026-10-12.json). No recording created,
deleted or changed; audio bytes remain in ignored local artifacts.

Tests use independent literal size3/end frames and hand-selected `abc`→`bc`,
assert actual transmitted offset bytes, reject overrun/short suffix/out-of-range,
and verify EOF semantics. Existing full-file and interleaved-event tests retained.

This establishes the device's offset primitive. It does not establish persistent
automatic resume: a local prefix still needs identity/integrity against the
current remote file. Size/name alone cannot prove unchanged content. Cancellation
is a separate protocol/state-machine problem; no cancel-success claim here.
