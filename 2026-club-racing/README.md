# 2026 HYC Club Racing — reference data

Reference material from HYC's 2026 spring/summer club racing, used while
building and validating the Sail Scoring scoring engine and the Sailwave
importer. Moved here from the app repo's `reference/data/2026-hyc-club-racing/`
(see `sailscoring/sailscoring` issue #233).

The Sailwave 2.38 series files this work was built against now live — with helm
and crew names anonymised — as `.blw` test fixtures under
`../sailscoring/tests/fixtures/sailwave/`. Importing a Sailwave file is done
in-app (Series list → **Import Series** → **Sailwave file**), which parses the
native `.blw` series file directly (a flat four-column CSV) in the TypeScript
importer `lib/sailwave-import.ts` — no intermediate JSON export step.

## Contents

- **`2016_club.csv` / `2026_club.csv`** — HYC's bilge-publishing catalogue: one
  row per (series × fleet × scoring-system), FTP path in the last comma-separated
  field. The SC TESTING rows (IDs 2198–2214) point at the `/reshyc/sc-test/...`
  tree the app writes to during the cutover. The same catalogue (verbatim) is
  vendored under `../sources/reshyc/admin/`.
- **`2026 Tues Series 1- Pup HPH R1.xls`** — Howth's working NHC1 spreadsheet;
  the source the NHC1 algorithm in the app's `lib/scoring.ts` was
  reverse-engineered against (see
  `../sailscoring/docs/notes/sailwave/nhc1-reverse-engineering.md`).
- **`compare-results.py`** — fetches HYC's Sailwave-published result pages and
  Sail Scoring's published pages over HTTP and diffs them, fleet by fleet.
- **`sailwave-nhc1-reverse.py`** — reverse-engineers Sailwave's NHC1 NewRating
  formula from the One Designs S1 results (data transcribed inline, owner names
  anonymised; it reads no external files).

## Threading FTP paths from `2016_club.csv`

The 2026 *live* series need the correct per-fleet FTP upload path so a scorer
adopting Sail Scoring publishes to the right place on the club results site.
The catalogue here is the source of those paths; `../scripts/ftp-paths.ts`
resolves them and emits the generic JSON payload the app's `update-ftp-paths`
script threads onto the workspace series rows (matched by series name):

```sh
# In the app, list HYC series + fleet names as the server sees them:
cd ../sailscoring && pnpm update-ftp-paths inspect --workspace hyc

# Back here, resolve the catalogue to a payload:
pnpm ftp-paths > paths.json

# In the app, preview then apply (fills empty slots only; --overwrite to replace):
cd ../sailscoring && pnpm update-ftp-paths plan  --input ../hyc-archive/paths.json
cd ../sailscoring && pnpm update-ftp-paths apply --input ../hyc-archive/paths.json
```

The series-name → fleet → CSV-row-ID mapping is hard-coded in
`../scripts/ftp-paths.ts`; update it (and re-run) whenever a Sailwave re-import
changes series/fleet naming, fleets are added, or the CSV grows new SC TESTING
rows. `ftpHost` is left empty — the catalogue records paths only, so set the
host once per series in **Settings** in the app.

## Sailwave import behaviour

The authoritative description of what the importer does with a real HYC Sailwave
2.38 export now lives **in the app repo**, next to the code it documents:
`../sailscoring/docs/notes/sailwave/import-behaviour.md` (source of truth:
`lib/sailwave-import.ts`).
