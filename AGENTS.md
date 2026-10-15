# AGENTS.md

Repo-specific rules for agents working on the CoMi Note firmware research. Read `README.md` and `docs/roadmap.md` first; `CONTEXT.md` holds the vocabulary.

## Goal and progress measure

Four milestones, in order, each with a one-line physical completion test (see `docs/roadmap.md`). Progress is measured only by milestones. Commit count, test count, document count and "coverage bytes" are not progress.

## Working rules

- One agent owns the device at a time. No second agent acting as a review gate; use a one-shot subagent for code review when wanted.
- Before any hardware experiment write three lines in the milestone doc: question it answers, steps, stop condition. On failure stop and write one paragraph on cause. Never auto-retry.
- No NOR/MMIO write, ROM-mode entry or flash erase before a full 4 MiB dump exists and passes `tools/verify_full_dump.py` with two identical reads.
- Hardware steps the agent cannot do (open case, clip, probe) are handed to the user as a short checklist; everything else (commands, verification, analysis) the agent does itself.
- Do not resume the BLE per-page NOR export (`src/rcominote/experiments/`). It is retained as evidence only.
- Do not re-search the web for an ATS3085L / LARK M4 BSP; `docs/platform-source-followup.md` records that search as exhausted. Only follow a concrete new link the user supplies.

## Documents

- `README.md`: one page, device summary, status, where to read.
- `docs/roadmap.md`: milestones, checklists, command drafts. The only plan.
- `docs/device-platform-map.md`: knowledge map, updated in place when a fact changes.
- `docs/adr/`: decisions that are hard to reverse, surprising, and a real trade-off. Nothing else.
- One page per completed milestone under `docs/`. No live receipts, checkpoints, frozen source snapshots, nonce ledgers or "do not re-judge" clauses.
- `docs/archive/`: historical reports. Link to them, do not rewrite them.
- Docs are telegraphic Chinese or English; one fact once; no restating old results in new pages.

## Code

- Python 3.13, `uv run`, `ruff format` then `ruff check --fix`; `just check` green before commit.
- Tests need an oracle independent of the code (captured bytes, spec table, hand-computed value). Delete tests that only re-assert their own setup.
- Keep files under ~500 lines. New device-facing code goes in `src/rcominote/`; one-off analysis in `tools/`.
- Never commit anything under `artifacts/`, device serials, factory keys, nonces or raw NVRAM content.
