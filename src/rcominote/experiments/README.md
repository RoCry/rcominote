# Retired: BLE per-page NOR export

Everything here implements the 2026-10-12..15 campaign that pulled NOR 512 B at a time through the
firmware debug shell, SD scratch files and the recording download protocol. It stopped at ~47 KiB of
4 MiB (ideal 81 h per full chip). Historical receipts in `docs/evidence/` pin these files by SHA-256,
so they stay in place unmodified. Do not extend or run against the device; see `docs/roadmap.md`.
