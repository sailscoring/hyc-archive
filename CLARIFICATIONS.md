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

## 2026 club racing (full-fidelity, not as-published)

2026 club racing is **not** as-published: Series 1/2/3 are sub-series of one
series per racing group, and as-published has no sub-series concept (it
deliberately replaced DBSC's sub-series-composed reconstruction). The blocked
series are built by `pnpm merge-club-series` from HYC's per-series Sailwave
files and scored by our engine, so — unlike everything above — a **results**
delta *can* arise here. What follows is where we know we diverge.

- **Discards follow the SIs, not the `.blw`.** The SIs allow "one discard for
  every three races completed" (dinghies) and "every four" (keelboats); the
  merge sets `proportionalDiscard` accordingly (`{firstAt: 3, everyRaces: 3}`
  and `{firstAt: 4, everyRaces: 4}`), which replaces the threshold ladder each
  Sailwave file carries.

  Those ladders are hand-entered and **disagree with each other and with the
  SIs**, so this is a real divergence, not a re-statement:

  | Sailwave file | ladder in the `.blw` | matches `floor(sailed/N)`? |
  |---|---|---|
  | Tues & Sat (Howth 17s) | 4→1, 8→2 | yes |
  | Tues (One Designs) | 4→1, 9→2 | diverges from 8 races |
  | Wed (Cruisers) | 5→1 | diverges from 4 races |
  | Sat (Cruisers) | 5→1 | diverges from 4 races |
  | Dinghies | 3→1, 6→2, 9→3, 13→4, 16→5, 19→6, 22→7 | diverges from 12 races |

  At **every race count actually sailed in 2026 they agree**, so no published
  standing changes today; the divergence would only show in a longer series.
  Verify with `pnpm verify-club-merge`, which scores each block against its
  source file and prints the allowance ladder.

- **Boats are joined across blocks** on sail number + boat name, falling back
  to boat name + helm and then helm alone — the same boat carries a different
  Sailwave handle in each series file. Joins on sail number alone aren't
  reported for classes that don't name their boats (all of the dinghies), where
  the sail number *is* the identity. Two joins on helm name alone stand out in
  the dinghy files: sail 741 (Harry George) and 1519 (Eliana Duffy) changed sail
  number between Series 1 and 2.

- **Per-block entry lists don't survive the merge — blocks rank only boats that
  sailed.** This is the open divergence, and it is a *results* one.

  Each Sailwave file has its own entry list, and Sailwave ranks a boat that
  entered a series but never sailed it as all-DNC. A merged series has one
  competitor set, so "entered Series 1" is not expressible. The blocks
  therefore carry `excludeDncOnlyCompetitors`, which ranks only boats that
  actually raced — and because DNC is scored off the entry count, dropping
  those boats lowers every DNC score in the block:

  | | published / source | merged |
  |---|---|---|
  | Wed Series 1, Division A HPH | DNC = 7 (6 entries) | DNC = 6 (5 sailed) |
  | Dinghy Series 1, Optimist | DNC = 19 | DNC = 12 |

  Finishing positions are untouched; only DNC values, and the net points and
  ranks derived from them, move. Turning the flag off is worse, not better: the
  block would then also carry boats that only ever raced a *later* series,
  pushing DNC the other way.

- **A boat entered twice in one file, once per division, merges into one.**
  HYC's Saturday Series 2 file carries Chinook (17793) as two competitor
  records — one in Division B HPH, one in B IRC — where Series 1 carries it
  once in both. Joined on sail number + boat name, the merged boat holds both
  records' finishes, so a race counts for a division that didn't sail it. The
  merge re-applies each source file's own answer as `raceFleetExclusions`,
  which fixes the whole-fleet cases; two rows in Saturday Series 2 (Toughnut
  and Helm's Deep, Division C HPH) still differ.

  Both of these are visible in `pnpm verify-club-merge`, which reports rows
  scored differently, rows only in the source, and rows only in the merge.

- **Race dates come from Sailwave's `racedate`,** which several HYC files leave
  empty (the 2026 Wednesday file labels its races only in `racename`, e.g.
  "6th May"). Those races fall back to the per-block `defaultRaceDate` in
  `scripts/merge-club-series.ts` — approximate, and flagged rather than guessed
  per race.

## Naming approximations

- **Series display names** are `"<admin event title> <year>"` (e.g. “Wave
  Regatta 2022”), taken verbatim from the admin DB backup (trimmed of stray
  whitespace). Typos in the admin DB pass through as published.
- **Start dates are approximate.** The admin DB carries no dates; every
  series gets `<year>-04-01` so the app's per-year grouping reads correctly.
  Real dates would need to be read from the result pages themselves.
