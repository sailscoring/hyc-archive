# Sailwave series files

HYC's native Sailwave `.blw` files for the seasons scored in Sailwave — the
source `pnpm merge-club-series` builds the blocked club-racing series from.
Unlike `sources/reshyc/`, these are **not** captured automatically: they come
from the club's scorer and land here by hand.

```
2026/<group>/series-{1,2,3}.blw
```

The group directories match the `key` of each entry in `GROUPS` in
`../../scripts/merge-club-series.ts`:

- `wednesday-cruisers`
- `tuesday-one-designs`
- `tuesday-saturday-howth-17`
- `saturday-one-designs`
- `saturday-cruisers`
- `dinghies`

A block whose file isn't here yet is skipped with a note rather than failing
the group, so a part-season merges fine and grows as later series arrive.

## Scrub before committing

`.blw` files carry competitor PII — dates of birth, email addresses, phone
numbers. Run the app's scrubber over them **before** the first commit:

```sh
cd ../sailscoring && pnpm blw-scrub ../hyc-archive/sources/blw/2026/*/*.blw
```

It rewrites in place. Sail numbers, boat and helm names stay — they're the
published record, and the merge joins boats across series files on them.
