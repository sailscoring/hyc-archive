# Clarifications

Known gaps and divergences between what this archive feeds Sail Scoring and
HYC's original published record — things that come down to a modelling
decision or a gap in the captured data, not a Sail Scoring bug.

Under the as-published regime (app ADR-010) nothing is recomputed, so a
*results* delta can't arise by construction. What can still go wrong — and
belongs here — is **coverage**: pages the capture never caught, admin rows
pointing nowhere, and page shapes the archive-kit can't ingest yet.

Each entry should capture: which series/season/fleet, what's missing or
differs, the most likely cause, and a pointer to the source row/page under
`sources/reshyc/`.

## Coverage gaps (2026-07)

The emit run (`pnpm emit-as-published`) reports these counts; the details are
reproducible by re-running it.

- **~212 admin rows have no `ftp_path`.** The hyc.ie admin DB lists the
  (year, event, class) result but no published page was ever linked — mostly
  older years. Nothing to ingest; left missing.
- **~32 admin `ftp_path`s are absent from the FTP capture.** The path is
  recorded but the file wasn't on the FTP site when the daily backup ran
  (pages deleted or renamed before the capture began, e.g. `tuesday_s1/squib_hcap.htm`
  in 2016 where only a `squib_hcap_1.htm` neighbour survives). Per the
  no-guessing rule, near-miss filenames are **not** substituted.
- **15 malformed admin rows.** The CSV dump is unquoted; rows whose event or
  class names contain commas can't be split unambiguously. All current cases
  are `SC TESTING` rows for the publishing test pages (`/reshyc/sc-test/`),
  which we exclude anyway.
- **33 open events on the skip-list**
  ([`as-published-skips.json`](as-published-skips.json)): Lambay Races,
  Double Handed, Round the Island, Howth→Drogheda, etc. Most are genuine
  Sailwave pages that publish race results only, with no series summary
  section, and the app's archive-kit Sailwave parser requires a summary.
  Tracked as app #355; remove entries from the skip-list as it lands.

  The recorded reason is a blanket one and **is wrong for about eight of
  them** — `hyc-2015-open-dinghy-regatta`, `hyc-2022-open-autumn-league`,
  `hyc-2023-open-lambay-races` and `hyc-2024-open-autumn-league-offshore`
  among them carry no race-only page at all; every captured page has its
  summary table, so something else blocks those. Re-diagnose per entry when
  #355 lands rather than assuming the whole list clears. By page shape the
  split is: 10 events race-only throughout, ~12 mixed, ~8 with no race-only
  page.

## Presentation decisions

- **20 one-off events publish as a race result, not a series table**
  ([`as-published-race-results.json`](as-published-race-results.json)): the
  Gibney Classic, the Lambay Race, Round the Island, the Double Handed Race,
  the New Year's Day races, Howth→Drogheda, the Brass Monkey, the Autumn
  League passage race, the Howth 17 125th-year race. Sailwave published each
  of these with a standings table *and* the race table; the standings add a
  Total and a Nett equal to the race score, under a caption reading
  `Sailed: 1, Discards: 0, To count: 1`. The archive drops that table (app
  #347) and publishes the race result the event actually produced.

  This is the one place the archive departs from the source page's shape. It
  is a presentation decision, not a results one — every score, rank and
  display cell is as published, and the standings rows are still ingested
  (the identity spine reads them), just not rendered.

- **The list is curated, never derived from the race count.** Several HYC
  series sailed exactly one race and are still series — `End of Summer Series
  Sat./Sun. 2020`, `Wed. Mini Series 2021`, `Saturday Series 3 2023`, and the
  `IDRA Eastern Championship 2019` (one entry, one race). Those keep their
  standings table: a league abandoned after its first day is a league, and
  the published record should say so.

## Naming approximations

- **Series display names** are `"<admin event title> <year>"` (e.g. “Wave
  Regatta 2022”), taken verbatim from the admin DB backup (trimmed of stray
  whitespace). Typos in the admin DB pass through as published.
- **Start dates are approximate.** The admin DB carries no dates; every
  series gets `<year>-04-01` so the app's per-year grouping reads correctly.
  Real dates would need to be read from the result pages themselves.
