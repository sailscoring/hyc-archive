# reshyc — vendored HYC results-site backup

Verbatim capture of Howth Yacht Club's published results site, vendored here as
the capture corpus for reconstructing HYC's race history into Sail Scoring.

- **Origin:** [`github.com/markmc/reshyc`](https://github.com/markmc/reshyc)
  (public), commit `9e47e6f297511aabaa3cbc14bb389af28b29a055`.
- **`results.hyc.ie/reshyc/`** — full backup of the club's published FTP results
  site (the Sailwave-published HTML pages), seasons 2011–2026 plus `sc-test/`.
- **`admin/`** — the navigation overlay for that backup (per-year `*_club.csv`
  and `*_open.csv` catalogues). The 2016/2026 club catalogues here are identical
  to the operational copies under `../../2026-club-racing/`.

What was **not** vendored from reshyc: the `summaries/` rollups, the capture
tooling (`scripts/`, `Makefile`, `transftp/`), and the Sailwave user-guide PDFs
— none are needed to reconstruct results. Re-pull from the origin repo if a
future task needs them.

These pages are verbatim third-party output kept for reproducibility — do not
edit them. Our own derived artifacts (reconstructed `.sailscoring` files,
normalised catalogues) are the deliverables.
