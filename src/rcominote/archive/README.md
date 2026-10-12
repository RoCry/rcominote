# Retired bulk NOR log exporters

`dsp_export.py`, `recovery_export.py`, `nor_export.py` are retained for offline
verification and provenance. **No default CLI registrations or runnable module
entry point.** Single-sector diagnosis and offline assemblers remain active.

Reason: about232 shell commands/~22 seconds per512 B; repeated log generation,
ring snapshots and re-reading. Useful evidence, unsuitable default bulk route.
Do not restore CLI merely to continue an old pending export. First compare native
SDK/host transfer options and demonstrate a bounded end-to-end efficiency gain.

See `docs/research-routes.md` and `docs/nor-efficiency.md`. Tests remain to preserve
the integrity of existing evidence and checksum validation, not to endorse resumption.
