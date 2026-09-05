# HYC results → Sail Scoring

Howth Yacht Club club-racing **reference data**, a maintained **capture** of the
club's published results site, and the **as-published ingest pipeline** that
feeds that history into [Sail Scoring](https://app.sailscoring.ie) — kept out of
the app repo, where `reference/data/` is for small illustrative fixtures.

It is the HYC counterpart of the sibling [`dbsc-archive`](https://github.com/sailscoring/dbsc-archive)
and [`iodai-archive`](https://github.com/sailscoring/iodai-archive) repos, and
the first archive built natively on the **as-published** model (app ADR-010,
`docs/design/decisions/010-as-published-archives.md`): the originally-published
results are ingested and displayed faithfully — structured ranks plus verbatim
display cells — never re-scored.

> 📋 **[CLARIFICATIONS.md](CLARIFICATIONS.md)** — known coverage gaps and
> approximations between the archive and the original published record.

## Why

The payoff is the **cross-series identity and ranking** work on the Sail Scoring
horizon (`docs/design/horizon.md` in the app repo — the competitor-identity
spine, the workspace season ladder, the per-competitor multi-year career-arc
page). Those features only come alive with *years of real history* in one
workspace, and HYC's multi-season club racing — Howth 17s, Puppeteers, Squibs,
cruisers under HPH/IRC, dinghies — is exactly that fuel.

It also keeps a bulky scraped corpus (~70 MB of published HTML and PDFs) out of
the app repo.

## What's here

```
2026-club-racing/         HYC's 2026 spring/summer reference data (see its README)
halsail-2025/             Puppeteer pilot — HalSail-import CSVs + build guide
scripts/
  ftp-paths.ts            resolve the catalogue → JSON for the app's update-ftp-paths
  emit-as-published-config.ts  admin CSVs + capture → as-published.config.json
  merge-club-series.ts    HYC's per-series .blw files → one blocked .sailscoring
  verify-club-merge.ts    prove a merged series scores as its sources did
  admin/                  hyc.ie admin scrapers (the capture tooling, from reshyc)
sources/
  blw/                    HYC's native Sailwave series files (see its README)
  reshyc/                 the published results-site capture (see SOURCES.md)
    results.hyc.ie/reshyc/  the FTP-site backup, seasons 2011–2026
    admin/                  per-year (event, class) → page catalogues, with the
                            display names the club published under
    summaries/              yearly prize-winner summary PDFs, 1996–
Makefile                  the capture targets: backup / admin-backup / summaries-backup
as-published.config.json  generated ingest config (committed; input to the app's
                          archive-generate)
as-published-skips.json   series the archive-kit can't ingest yet, with reasons
                          (empty since app #355)
as-published-race-results.json  one-off events published as a race result, not
                          a series table (app #347) — curated, see CLARIFICATIONS
as-published-race-sections.json  race-only pages whose race tables are several
                          fleets, not several races (app #355) — curated
as-published-display-only.json  pages re-presenting racing another page of the
                          same event already carries (app #363) — curated
club-2026/                the blocked club-racing series (committed: the build is
                          reproducible, so the diff shows what a merge changed)
.github/workflows/
  backup-ftp.yml          daily FTP-site capture → PR → auto-merge
  backup-admin.yml        daily admin-DB capture → PR → auto-merge
  backup-summaries.yml    on-demand summaries capture → PR → auto-merge
  as-published.yml        emit → generate → push to the hyc workspace
  club-2026.yml           merge → check reproducible → import into the workspace
                          (⚠️ uses a privileged token — see its header, app #370)
```

The capture automation moved here from [`markmc/reshyc`](https://github.com/markmc/reshyc)
(which pre-dates Sail Scoring); the origin repo retains the pre-2026 history.

## The pipeline

1. **Capture** — daily workflows mirror the FTP results site and the admin DB
   into `sources/reshyc/` (verbatim, third-party, never edited).
2. **Emit** — `pnpm emit-as-published` joins the admin catalogues (display
   names) to the captured pages: one as-published series per (year, club/open,
   event), one fleet page per class at `/p/hyc/{year}/{event}/{class}`, with
   deterministic UUIDv5 series ids that can never re-mint. Coverage gaps are
   reported, never papered over. The URL shape is the app's publication tree
   (app ADR-011): each year slug is a season folder — the public workspace
   index shows the current season expanded, earlier ones collapsed, split
   Open Events / Club Racing — each event segment resolves to its own folder
   index, and every page carries the navigation cascade (season → event →
   class). Where title-casing the event segment would mangle the club's own
   name ("1720's Easterns", "Tue + Sat Series 1"), the config pins a
   `folders` label with the admin DB's display name, re-asserted on every
   ingest like the slugs.
3. **Ingest** — CI checks out the app repo, runs `pnpm archive-generate` over
   the config (parsing the Sailwave HTML), and pushes the documents with
   `pnpm cli as-published push … --workspace hyc`, authenticated by a
   workspace- and capability-scoped archivist token. Ingest is idempotent —
   unchanged documents are no-ops by content hash. **Armed**: every push to
   `main` re-ingests.

Currently: **386 series / 1,346 fleet pages / ~18,000 competitor rows** across
2013–2025 plus the finished 2026 club series and open events emit and generate
cleanly; see
[CLARIFICATIONS.md](CLARIFICATIONS.md) for what doesn't (and why).

## Relationship to the app repo

This repo assumes the sibling app checkout exists at `../sailscoring`. Two
things deliberately stay **in the app**, next to the code they document:

- the **Sailwave importer behaviour** reference
  (`../sailscoring/docs/notes/sailwave/import-behaviour.md`) — it documents
  shipped behaviour of `lib/sailwave-import.ts`;
- the **NHC1 reverse-engineering** write-up
  (`../sailscoring/docs/notes/sailwave/nhc1-reverse-engineering.md`) — distilled
  docs; it points back at the `.xls` / `.py` sources here.

The as-published toolkit (parsers, generator, ingest client) lives in the app's
`lib/archive-kit/` and is driven from here via config; the generic FTP-path
threading also lives in the app (`../sailscoring/scripts/update-ftp-paths.ts`),
with `scripts/ftp-paths.ts` here as the HYC-specific caller.

## Status

- ✅ Reference data + reshyc capture vendored (this extraction, app issue #233).
- ✅ Capture automation (FTP, admin DB, summaries) moved here from reshyc.
- ✅ As-published config emission + clean `archive-generate` run over 2013–2025
  and the finished 2026 club series.
- ✅ Ingest armed: the archivist token and CI secrets are configured, and
  every push to `main` re-ingests.
- ⬜ Extend coverage: single-race pages (the skip-list); the ~1,170 captured
  pages the admin catalogue never linked (all of 2011–2014 plus later
  revision/overall pages), which need display names sourced some other way;
  the identity manifest; prize-winner (summaries/) data — mirror
  dbsc-archive's `yearbook/`.
- ⬜ Thread the 2026 live-series FTP paths into the HYC workspace.
- ✅ 2026 as-published: the ten finished club series (Series 1 and 2 of each
  racing group) plus five finished open events — Fireball Nationals, Dinghy
  F'bite Spring, Brass Monkeys, New Year's Day Dinghies, Round the Island —
  emit and generate cleanly alongside 2013–2025.
- ✅ 2026 club racing, blocked demo: `pnpm merge-club-series` builds one series
  per racing group with Series 1/2/3 as sub-series, from the club's own
  Sailwave files (`sources/blw/`) — a demonstration of the shape proposed for
  future seasons, labelled "(DEMO)" and knowingly not a match for the published
  tables (see CLARIFICATIONS). All six groups build.
- ⬜ Add to `CURRENT_SEASON_EVENTS` as they finish: 2026 club Series 3, the
  Fingal Cruiser Challenge (still being updated), the Puppeteer 22
  Championships and Howth 17 Nationals (entry lists, no racing sailed yet).
  The Double-Handed Race is a coverage gap instead — admin row 2265 names a
  page that has never appeared in the capture.
- ✅ The club-2026 import runs on every push, via `cli series import --replace`
  (app `PUT /api/v1/series/:id/file`): each file upserts at the id it carries,
  so a re-run updates the series rather than adding a second copy. That id is
  UUIDv5 over a stable key, which is what makes the merge re-runnable at all.
- ⚠️ **Temporary privilege, to be removed** (app #370). That import writes
  *full-fidelity* series, which needs `manage-series` — far more than the
  archivist key's `read` + `archive-ingest`, which by design *"can touch
  nothing but its workspace's already-public archive"* (ADR-010). So it runs
  under a **separate** secret, `SAILSCORING_PRIVILEGED_IMPORTER_TOKEN`, kept
  apart from `SAILSCORING_ARCHIVIST_TOKEN` so the blast radius stays visible
  and revoking it costs nothing else. Accepted while 2026 is a one-off demo;
  revoke it once the demo stops being refreshed.

## Licensing

Our own code and derived artifacts are MIT ([`LICENSE`](LICENSE)); normalised
data we produce is CC0 ([`LICENSE-DATA`](LICENSE-DATA)). The verbatim captured
pages and PDFs under `sources/reshyc/` are third-party HYC output, kept for
reproducibility and not relicensed.
