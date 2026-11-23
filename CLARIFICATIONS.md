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
- **The skip-list is empty.** All 33 open events it held — the Lambay Races,
  Double Handed, Round the Island, Howth→Drogheda, the Gibney Classics — now
  ingest: app #355 taught the archive-kit to build a fleet's standings from a
  race-only Sailwave page, and the 18 pages below are dropped per class rather
  than failing their whole event. 229 fleet pages joined the archive, 211 of
  them results.

  The recorded reason had been a blanket one, and was wrong for a third of the
  list: eight of those events carry no race-only page at all. What actually
  blocked them is in the next entry.

- **18 captured pages are not results, and are dropped.** The emit run reports
  each one (`! not a results page`). They resolve from a real admin row and
  the file is in the capture, but there is nothing an archive can hold:

  | Shape | Pages | Where |
  |---|---|---|
  | Sailwave **Competitor List** (`table.entry`) — an entry list, published before racing | 10 | 2023 ILCA Nationals `Competitors.htm`; the Lambay Inshore J80 / Squib / Howth 17 / B211 / Taste of Racing pages, 2016–2019; 2015 Dinghy Regatta Mirror; 2016 Brassed Off Cup Regatta Fleet; 2016 Mermaid Nationals Crew Race |
  | **Team Ranking Table** (`table.prize`) — the Autumn League's team competition, a scoring shape the archive has no home for | 2 | 2022 + 2024 Autumn League `AL_teams.htm` |
  | A note and no table — "There are no IRC divisions in 2020/21 Brass Monkeys" | 3 | 2021 Brass Monkeys Class 1/2/3 IRC |
  | No table at all, or an empty file | 3 | 2022 Lambay `open_lambay_j24.htm`, `open_lambay_j80.htm`; 2023 Lambay `ruffian.htm` (0 bytes) |

  A single one of these used to fail the entire event, which is what really
  kept 2015 Dinghy Regatta, 2016 Brassed Off Cup, 2016 Mermaid Nationals, 2021
  Brass Monkeys, 2022 Autumn League, 2023 ILCA Nationals, 2023 Lambay Races
  and 2024 Autumn League Offshore off the archive. The entry lists would be
  ingestible if the archive-kit grows an entry-list page (the app publishes
  one for live series, app #423); the rest have no obvious home.

## Race-only pages, and what a place means on one

Many of HYC's one-off events were published as a race result and nothing else
— a Sailwave page carrying race tables and no summary section. The archive
builds the fleet's standings out of the race table itself (app #355), so the
published page and the ingested record are the same table. 186 fleets across
the corpus come in this way.

Two curated files say what the markup cannot:

- [`as-published-race-sections.json`](as-published-race-sections.json) — pages
  whose race tables are several **fleets** rather than several races of one.
  2022's Lambay pages carry each class's IRC and ECHO results side by side,
  and the 2024 New Year's Day race put PY, ILCA 6 and ILCA 7 on one page. In
  2026 the Gibney Classic (12 fleets), the Double Handed Race (5) and the
  Lambay Puppeteer 22 and Howth 17 pages (Scratch and HPH) are the same shape;
  each fleet is named by its race heading less the event prefix and date
  (`Gibney - Div A IRC Fleet - Aug 15` → `Div A IRC Fleet`), the form the
  2024–25 editions' summary sections used. Each
  named table becomes a fleet of its own, published together as one page, so
  each states the places its own table published.
- [`as-published-display-only.json`](as-published-display-only.json) — pages
  that re-present racing another page of the same event already accounts for.
  The 2022 J24 Europeans published a day-by-day race result beside the
  championship's Overall standings; the day pages still publish, but their
  boats are the Overall page's boats (34 sailors, not 204) and their lines
  take no place in a career arc.

Where a race-only page carries **several races of one fleet** and no
standings, its rows rank nowhere. Two races and no published standing state no
place between them, and inventing one would put a position in a sailor's
record that the club never published.

## Capture paths that fold together by case

The admin DB's paths were written against a case-insensitive Windows server,
so the emit resolves them case-insensitively — but the capture is a
case-*sensitive* mirror, and holds **13 pairs of files differing only in
case**, usually with different content and sizes:

```
2018/Club_wednesday_s1_class2_irc.htm   32,573 b
2018/club_wednesday_s1_class2_irc.htm   21,388 b
2024/open/Lambay/Class3.htm             48,664 b
2024/open/Lambay/class3.htm             28,684 b
2026/open/rti_PY.htm                    18,522 b
2026/open/rti_py.htm                    11,486 b
```

The resolver takes the file matching the admin DB's own spelling, falling back
to a case-insensitive match only when that is unambiguous; a fold with several
candidates and no exact match is reported and left unresolved rather than
guessed at (none currently). Before that, the index kept whichever file the
directory walk happened to see last — which had silently substituted
`rti_py.htm` (an entry list, `Sailed: 0`) for the `rti_PY.htm` the catalogue
names (`Sailed: 1`, and the only one of the two carrying a race table). The
other twelve pairs happened to resolve correctly by luck.

## Presentation decisions

- **24 one-off events publish as a race result, not a series table**
  ([`as-published-race-results.json`](as-published-race-results.json)): the
  Gibney Classic, the Lambay Race, Round the Island, the Double Handed Race,
  the New Year's Day races, Howth→Drogheda, the Brass Monkey, the Autumn
  League passage race, the Howth 17 125th-year race. Sailwave published each
  of these with a standings table *and* the race table; the standings add a
  Total and a Nett equal to the race score, under a caption reading
  `Sailed: 1, Discards: 0, To count: 1`. The archive drops that table (app
  #347) and publishes the race result the event actually produced. (The
  2026 Gibney and Double Handed pages, and Lambay's one-design pages, carry
  no standings table at all, so for those there is nothing to drop. The
  2026 Lambay Race joins the list because every class sailed the single
  race on 30 May, as in 2024. In 2025 it was a two-day event and stays a
  series.)

  This is the one place the archive departs from the source page's shape. It
  is a presentation decision, not a results one — every score, rank and
  display cell is as published, and the standings rows are still ingested
  (the identity spine reads them), just not rendered.

- **The 2026 Round the Island Race keeps its standings table**, despite being
  a one-race event of exactly the kind the list above covers. HYC published the
  two ILCA fleets summary-only — no race-detail table to promote in the
  standings' place — while the PY fleet has one. `detail` is a per-series
  setting, so the event publishes as standings throughout rather than as a race
  result for one fleet and a standings table for the others.

- **The 2026 Dinghy F'bite Spring ILCA 4 fleet publishes with no racing.** Its
  page reads `Sailed: 0, Discards: 0, To count: 0, Entries: 4` — an entry list
  for a fleet that never got away. It is ingested as published: four boats, no
  races. Dropping it would be the archive editing the record rather than
  reflecting it.

- **The list is curated, never derived from the race count.** Several HYC
  series sailed exactly one race and are still series — `End of Summer Series
  Sat./Sun. 2020`, `Wed. Mini Series 2021`, `Saturday Series 3 2023`, and the
  `IDRA Eastern Championship 2019` (one entry, one race). Those keep their
  standings table: a league abandoned after its first day is a league, and
  the published record should say so.

## 2026 season

2026 is the first season HYC scored partly in Sail Scoring, so the archive
holds only part of it. The dividing line is the published page. Where the
club published Sailwave HTML (and linked it from the admin DB), the event is
ingested as-published, listed in `CURRENT_SEASON_EVENTS` in
`scripts/emit-as-published-config.ts` once the club stops updating its pages.
Nothing is recomputed, so the coverage rules at the top of this file apply
and no results delta can arise. Where the club published Sail Scoring HTML,
the event is a live series in the workspace and isn't this archive's to
ingest: the Autumn League, Puppeteer 22 Championships, Dinghy Regatta, GP14
Leinsters, ILCA Masters, Melges 15 Northerns, Women at the Helm and the Dinghy
Frostbite Winter series.

- **Held back while racing continues:** Brass Monkeys – Winter
  (`open_bm_overall.htm`, first published 22 Nov). An as-published key can
  never be renamed (CLAUDE.md rule 4), so an event joins only after its last
  race.
- **Captured 2026 pages deliberately not ingested.** None is linked from the
  admin DB, and none is a separate result:
  - `open/doublehanded_overall.htm` is a standings page reading `Sailed: 0`
    for every fleet. The admin DB links `open/doublehanded.htm`, the race
    result, instead.
  - `open/dinghyregatta.htm` is a Sailwave entry list for the Dinghy Regatta,
    which was then scored and published in Sail Scoring.
  - `open_ilcamasters_ilca{6,7}_{sw,sc}.htm` are the ILCA Masters scored
    side by side in Sailwave and Sail Scoring on 24 May, before the Sail
    Scoring pages became the published result.
  - `open/autumnleague/pup22.htm` ("TESTING PURPOSES ONLY") and
    `open/the-brassed-off-cup.htm` ("test (2) at test") are Sail Scoring test
    publishes.
  - 16 alternate filenames (`series2_tue_xxxxx.htm`, `lambay_n45.htm`,
    `bmspring_class1.htm`, `rti_icla.htm`, …) carrying the same fleets as
    pages the admin DB does link. Per the no-guessing rule, the admin DB's
    choice of page stands.

Until 2026-11, 2026 club racing was also imported full-fidelity, as a blocked
demo built from the club's own `.blw` files: one series per racing group with
Series 1/2/3 as sub-series, labelled "(DEMO)". It was never the record and was
knowingly not a match for the published tables. It has been withdrawn (the
build, its CI import and its privileged token are gone, and so are the series).
Its divergence notes are in git history before that removal.

## Naming approximations

- **Series display names** are `"<admin event title> <year>"` (e.g. “Wave
  Regatta 2022”), taken verbatim from the admin DB backup (trimmed of stray
  whitespace). Typos in the admin DB pass through as published, and so does
  a title that already carries the year: `Dinghy F'bite Spring 2026 2026`,
  `Double-Handed Race 2026 2026`.
- **Start dates are approximate.** The admin DB carries no dates; every
  series gets `<year>-04-01` so the app's per-year grouping reads correctly.
  Real dates would need to be read from the result pages themselves.
