# HYC results → Sail Scoring

Howth Yacht Club club-racing **reference data** and a verbatim **capture** of the
club's published results site — kept out of the [Sail Scoring](https://app.sailscoring.ie)
app repo, where `reference/data/` is for small illustrative fixtures.

It is the HYC counterpart of the sibling [`dbsc-archive`](https://github.com/sailscoring/dbsc-archive)
and [`iodai-archive`](https://github.com/sailscoring/iodai-archive) repos: the
same shape of work — reconstruct *published* race history into importable
`.sailscoring` files — and the same payoff.

> 📋 **[CLARIFICATIONS.md](CLARIFICATIONS.md)** — known divergences between a
> reconstruction and the original published results. Anything we can't reproduce
> exactly is recorded here, with a link to the original.

## Why

The payoff is the **cross-series identity and ranking** work on the Sail Scoring
horizon (`docs/design/horizon.md` in the app repo — the competitor-identity
spine, the workspace season ladder, the per-competitor multi-year career-arc
page). Those features only come alive with *years of real history* in one
workspace, and HYC's multi-season club racing — Howth 17s, Puppeteers, Squibs,
cruisers under HPH/IRC, dinghies — is exactly that fuel.

It also keeps a bulky scraped corpus (~50 MB of published HTML) out of the app
repo.

## What's here

```
2026-club-racing/         HYC's 2026 spring/summer reference data (see its README)
  2016_club.csv             the club's publishing catalogue (series × fleet → FTP path)
  2026_club.csv
  2026 Tues Series 1- …xls  Howth's working NHC1 spreadsheet (the reverse-eng source)
  compare-results.py        diff Sailwave-published vs Sail Scoring-published pages
  sailwave-nhc1-reverse.py  reverse-engineer Sailwave's NHC1 NewRating formula
scripts/
  ftp-paths.ts            resolve the catalogue → JSON for the app's update-ftp-paths
sources/
  reshyc/                 vendored backup of the published results site (see SOURCES.md)
    results.hyc.ie/reshyc/  the FTP-site backup, seasons 2011–2026
    admin/                  the site's navigation overlay (per-year catalogues)
```

## Relationship to the app repo

This repo assumes the sibling app checkout exists at `../sailscoring`. Two
things deliberately stay **in the app**, next to the code they document:

- the **Sailwave importer behaviour** reference
  (`../sailscoring/docs/notes/sailwave/import-behaviour.md`) — it documents
  shipped behaviour of `lib/sailwave-import.ts`;
- the **NHC1 reverse-engineering** write-up
  (`../sailscoring/docs/notes/sailwave/nhc1-reverse-engineering.md`) — distilled
  docs; it points back at the `.xls` / `.py` sources here.

The generic FTP-path threading lives in the app
(`../sailscoring/scripts/update-ftp-paths.ts`, which owns the DB layer);
`scripts/ftp-paths.ts` here is the HYC-specific caller that feeds it.

## Status

- ✅ Reference data + reshyc capture vendored (this extraction, app issue #233).
- ⬜ Reconstruct the published HTML under `sources/reshyc/` into `.sailscoring`
  files (future — mirror dbsc-archive's `to-sailscoring` / `compare` loop).
- ⬜ Thread the 2026 live-series FTP paths into the HYC workspace.

## Licensing

Our own code and derived artifacts are MIT ([`LICENSE`](LICENSE)); normalised
data we produce is CC0 ([`LICENSE-DATA`](LICENSE-DATA)). The verbatim captured
pages under `sources/reshyc/` are third-party HYC output, kept for
reproducibility and not relicensed.
