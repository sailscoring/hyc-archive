# CLAUDE.md

Guidance for Claude Code working in this repo. **Read `README.md` first** — it has
the mission, the layout, and the status tracker. This file covers the working
conventions.

## What this repo is

A data archive, not an application. It holds Howth Yacht Club club-racing
reference data, a maintained capture of the club's published results site
(`sources/reshyc/`, originally vendored from the public `markmc/reshyc` repo —
the capture automation now runs here), and the **as-published** ingest pipeline
(app ADR-010) that feeds that history into Sail Scoring: display names from the
admin-DB backup joined to the captured Sailwave pages, emitted as
`as-published.config.json`, generated and pushed by CI via the app's
archive-kit. The goal is to feed the **cross-series identity & ranking**
features (see the app repo's `docs/design/horizon.md`) with real multi-year
HYC history — ingested faithfully, never re-scored.

It is the HYC counterpart of the sibling `dbsc-archive` and `iodai-archive`
repos; the same spirit applies. Domain background (handicap systems, fleets)
lives in the app repo under `../sailscoring/docs/` and `../sailscoring/reference/`.

## Rules that are easy to get wrong

1. **Source pages are verbatim and third-party.** The captured HTML under
   `sources/reshyc/` is unmodified HYC results-site output, kept for
   reproducibility; do not edit it, and do not relicense it (see README
   "Licensing"). Our own artifacts (the as-published config, normalised
   catalogues) are the deliverables. New capture lands via the backup
   workflows, not by hand.

2. **Only real published data.** If a result is missing from the capture, leave
   it missing — do not fabricate, interpolate, or guess. Partial coverage is fine.

3. **Record coverage gaps and approximations** in
   [`CLARIFICATIONS.md`](CLARIFICATIONS.md). Under as-published, results are
   never recomputed so a results delta can't arise — but skipped pages,
   unresolvable admin rows, and naming/date approximations must be recorded,
   not papered over. That mistake on the IODAI archive is the reason this rule
   exists.

4. **Never rename an emitted series `key`.** Series ids are deterministic
   UUIDv5 over `hyc-archive/series/<key>`; renaming a key re-mints the id and
   orphans the ingested series (and its identity links). The key derives from
   the admin event title — a title fix upstream changes the key, so treat that
   as a migration, not a rename.

## Relationship to the app repo

This repo assumes the sibling app checkout at `../sailscoring`. The Sailwave
importer-behaviour reference and the NHC1 reverse-engineering write-up stay in
the app (next to the code they document); this repo points at them rather than
forking them. The generic FTP-path threading also lives in the app
(`scripts/update-ftp-paths.ts`); `scripts/ftp-paths.ts` here is the HYC caller
that resolves the catalogue and feeds it.

Reconstruction tooling, when added, should reuse the app's scoring engine and
types by relative import (`../sailscoring/lib/scoring`, `../sailscoring/lib/types`)
rather than forking them — one canonical engine, as dbsc-archive does.

## Git conventions

- Commit logically (one coherent change per commit). Keep the tree consistent.
- Commit as `markbmc@gmail.com`, unsigned (`commit.gpgsign=false`).
- **End every commit message with:**
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Do not push unless asked.** Commit locally; let the human review and push.
