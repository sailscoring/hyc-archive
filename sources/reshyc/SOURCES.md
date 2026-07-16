# reshyc — the HYC results-site capture

Verbatim capture of Howth Yacht Club's published results site, the capture
corpus for reconstructing HYC's race history into Sail Scoring.

- **Origin:** [`github.com/markmc/reshyc`](https://github.com/markmc/reshyc)
  (public), initially vendored at commit `9e47e6f2`, synced to
  `9527ade7` and **maintained here since** — the capture automation
  (`Makefile` targets + `.github/workflows/backup-*.yml` + `scripts/admin/`)
  moved from reshyc to this repo, so new backups land here directly.
- **`results.hyc.ie/reshyc/`** — full backup of the club's published FTP results
  site (the Sailwave-published HTML pages), seasons 2011–2026 plus `sc-test/`.
  Refreshed daily by the `backup-ftp` workflow (`make backup`).
- **`admin/`** — the navigation overlay for that backup: per-year `*_club.csv`
  and `*_open.csv` catalogues dumped from the hyc.ie admin results DB, mapping
  `(id, event, class)` to an FTP path. These carry the **display names** the
  club published each result under. Refreshed daily by the `backup-admin`
  workflow (`make admin-backup`). The 2016/2026 club catalogues here are
  identical to the operational copies under `../../2026-club-racing/`.
- **`summaries/`** — the club's yearly prize-winner summary PDFs (1996–),
  downloaded from the hyc.ie admin resources area. Refreshed on demand by the
  `backup-summaries` workflow (`make summaries-backup`); the club publishes
  roughly one per year.

Still in the origin repo and deliberately **not** vendored: the 2022 Autumn
League page-chunking tooling, the `transftp/` AWS bits, and the Sailwave
user-guide PDFs — none are needed to reconstruct results.

These pages and PDFs are verbatim third-party output kept for reproducibility —
do not edit them. Our own derived artifacts (reconstructed `.sailscoring`
files, as-published ingest configs, normalised catalogues) are the
deliverables.
