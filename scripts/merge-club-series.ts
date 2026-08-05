/**
 * Merge HYC's per-series Sailwave files into one `.sailscoring` series per
 * racing group, with Series 1/2/3 as sub-series (blocks).
 *
 * HYC scores each series as its own `.blw` — "Wednesdays - Cruisers - Series 1"
 * and "- Series 2" are separate Sailwave files with separate competitor
 * handles. The app has no way to append one `.blw` onto an existing series
 * (`updateSeriesFromSailwave` calls `deleteSeriesChildren`, which drops the
 * sub-series and re-mints every race id), so the merge happens here, offline,
 * and the result imports in one shot:
 *
 *   pnpm merge-club-series                       # all groups in the config
 *   pnpm merge-club-series --group wednesday     # just one
 *   cd ../sailscoring && pnpm cli series import ../hyc-archive/build/club-2026/*.sailscoring --workspace hyc
 *
 * The conversion itself is not forked: `lib/sailwave-import.ts` in the app is a
 * pure module, so it's imported by relative path (as dbsc-archive does with the
 * scoring engine) and this script only does the union.
 *
 * What the merge has to reconcile:
 *
 *   fleets       union by name; the same fleet must score the same way in every
 *                block, or the group is mis-configured and we stop.
 *   competitors  union by sail number + boat name (helm name as a fallback):
 *                the same boat carries a different Sailwave handle in each
 *                file. Every merge decision that isn't an exact match is
 *                reported for CLARIFICATIONS.md — never silently joined.
 *   races        concatenated in block order and renumbered; each block becomes
 *                a sub-series over its own race ids.
 *   discards     one `proportionalDiscard` for the group, replacing the
 *                hand-entered threshold ladder in each `.blw` (see
 *                CLARIFICATIONS.md — the ladders disagree with each other and
 *                with the SIs). Blocks score independently, so the allowance is
 *                computed over the block's races, not the group's.
 *
 * Handicap carry: HYC's NHC1 ratings run on across the season, so each block
 * continues from the one before (`startingHandicapSource: 'continue'`). Set
 * `carryHandicaps: false` on a group whose SIs restart at base ratings.
 */
import { randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import {
  buildSeriesFileFromSailwave,
  parseSailwaveBlw,
} from '../../sailscoring/lib/sailwave-import';
import { FORMAT_VERSION, type SeriesFile } from '../../sailscoring/lib/series-file';

// ---- Configuration ----

interface BlockSpec {
  /** Sub-series name as it appears in the app and in the published URL. */
  name: string;
  /** `.blw` path, relative to the repo root. */
  file: string;
  /**
   * Fallback date for races whose Sailwave `racedate` is missing or carries no
   * year. Several HYC files label races only in `racename` ("6th May"), which
   * the importer can't read as a date — without this they all land on today.
   */
  defaultRaceDate: string;
}

interface GroupSpec {
  /** Output filename stem; also the `--group` selector. */
  key: string;
  /** Series name in the app. Drives the default published slug. */
  name: string;
  venue: string;
  /** One discard per `everyRaces` sailed, the first at `firstAt`. */
  proportionalDiscard: { firstAt: number; everyRaces: number };
  /** Each block continues the previous block's ratings. */
  carryHandicaps: boolean;
  blocks: BlockSpec[];
}

const BLW_ROOT = 'sources/blw/2026';

/**
 * The six groups HYC scores 2026 club racing under — one per Sailwave series
 * title. Fleets are constant across the blocks within a group; only the races
 * differ, which is exactly what a sub-series models.
 *
 * Discards come from the SIs, not from the `.blw`: "one discard for every three
 * races completed" for the dinghies, "every four" for the keelboats. With
 * `firstAt === everyRaces` the allowance is exactly `floor(sailed / everyRaces)`.
 */
const GROUPS: GroupSpec[] = [
  {
    key: 'wednesday-cruisers',
    name: 'Wednesdays - Cruisers 2026',
    venue: 'Howth Yacht Club',
    proportionalDiscard: { firstAt: 4, everyRaces: 4 },
    carryHandicaps: true,
    blocks: [
      { name: 'Series 1', file: `${BLW_ROOT}/wednesday-cruisers/series-1.blw`, defaultRaceDate: '2026-05-06' },
      { name: 'Series 2', file: `${BLW_ROOT}/wednesday-cruisers/series-2.blw`, defaultRaceDate: '2026-06-10' },
      { name: 'Series 3', file: `${BLW_ROOT}/wednesday-cruisers/series-3.blw`, defaultRaceDate: '2026-07-28' },
    ],
  },
  {
    key: 'tuesday-one-designs',
    name: 'Tuesdays - One Designs 2026',
    venue: 'Howth Yacht Club',
    proportionalDiscard: { firstAt: 4, everyRaces: 4 },
    carryHandicaps: true,
    blocks: [
      { name: 'Series 1', file: `${BLW_ROOT}/tuesday-one-designs/series-1.blw`, defaultRaceDate: '2026-05-05' },
      { name: 'Series 2', file: `${BLW_ROOT}/tuesday-one-designs/series-2.blw`, defaultRaceDate: '2026-06-09' },
      { name: 'Series 3', file: `${BLW_ROOT}/tuesday-one-designs/series-3.blw`, defaultRaceDate: '2026-07-21' },
    ],
  },
  {
    key: 'tuesday-saturday-howth-17',
    name: "Tuesdays & Saturdays - Howth 17's 2026",
    venue: 'Howth Yacht Club',
    proportionalDiscard: { firstAt: 4, everyRaces: 4 },
    carryHandicaps: true,
    blocks: [
      { name: 'Series 1', file: `${BLW_ROOT}/tuesday-saturday-howth-17/series-1.blw`, defaultRaceDate: '2026-05-05' },
      { name: 'Series 2', file: `${BLW_ROOT}/tuesday-saturday-howth-17/series-2.blw`, defaultRaceDate: '2026-06-09' },
      { name: 'Series 3', file: `${BLW_ROOT}/tuesday-saturday-howth-17/series-3.blw`, defaultRaceDate: '2026-07-21' },
    ],
  },
  {
    key: 'saturday-one-designs',
    name: 'Saturdays - One Designs 2026',
    venue: 'Howth Yacht Club',
    proportionalDiscard: { firstAt: 4, everyRaces: 4 },
    carryHandicaps: true,
    blocks: [
      { name: 'Series 1', file: `${BLW_ROOT}/saturday-one-designs/series-1.blw`, defaultRaceDate: '2026-05-16' },
      { name: 'Series 2', file: `${BLW_ROOT}/saturday-one-designs/series-2.blw`, defaultRaceDate: '2026-06-13' },
      { name: 'Series 3', file: `${BLW_ROOT}/saturday-one-designs/series-3.blw`, defaultRaceDate: '2026-08-01' },
    ],
  },
  {
    key: 'saturday-cruisers',
    name: 'Saturday - Cruisers 2026',
    venue: 'Howth Yacht Club',
    proportionalDiscard: { firstAt: 4, everyRaces: 4 },
    carryHandicaps: true,
    blocks: [
      { name: 'Series 1', file: `${BLW_ROOT}/saturday-cruisers/series-1.blw`, defaultRaceDate: '2026-05-09' },
      { name: 'Series 2', file: `${BLW_ROOT}/saturday-cruisers/series-2.blw`, defaultRaceDate: '2026-06-13' },
      { name: 'Series 3', file: `${BLW_ROOT}/saturday-cruisers/series-3.blw`, defaultRaceDate: '2026-07-25' },
    ],
  },
  {
    // No Series 3 in the admin catalogue yet — the block list grows when it
    // starts. Dinghy SIs allow one discard per three races, not four.
    key: 'dinghies',
    name: 'Howth YC Dinghy Racing 2026',
    venue: 'Howth YC',
    proportionalDiscard: { firstAt: 3, everyRaces: 3 },
    carryHandicaps: false,
    blocks: [
      { name: 'Series 1', file: `${BLW_ROOT}/dinghies/series-1.blw`, defaultRaceDate: '2026-05-07' },
      { name: 'Series 2', file: `${BLW_ROOT}/dinghies/series-2.blw`, defaultRaceDate: '2026-06-30' },
    ],
  },
];

// ---- Merge ----

type Competitor = SeriesFile['competitors'][number];
type Fleet = SeriesFile['fleets'][number];
type Race = SeriesFile['races'][number];

/** Collected for the run report — and for CLARIFICATIONS.md. */
interface Notes {
  /** Boats joined across blocks on something weaker than sail number + boat name. */
  weakMatches: string[];
  /** Fields that differed between blocks for the same boat; first block wins. */
  conflicts: string[];
  /** Anything dropped rather than guessed at. */
  dropped: string[];
}

const norm = (s: string | undefined): string =>
  (s ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '');

/**
 * Identity keys for one boat, strongest first. A boat is joined across blocks
 * on the strongest key both sides agree on; anything below the first is
 * reported, because a wrong join silently merges two boats' seasons.
 */
function competitorKeys(c: Competitor): { key: string; strength: number }[] {
  const sail = norm(c.sailNumber);
  const boat = norm(c.boatName);
  const helm = norm(c.names?.[0]);
  const keys: { key: string; strength: number }[] = [];
  if (sail && boat) keys.push({ key: `sail+boat:${sail}|${boat}`, strength: 0 });
  if (sail) keys.push({ key: `sail:${sail}`, strength: 1 });
  if (boat && helm) keys.push({ key: `boat+helm:${boat}|${helm}`, strength: 2 });
  if (helm) keys.push({ key: `helm:${helm}`, strength: 3 });
  return keys;
}

const STRENGTH_LABEL = ['sail number + boat name', 'sail number', 'boat name + helm', 'helm name'];

function mergeGroup(group: GroupSpec, repoRoot: string): { file: SeriesFile; notes: Notes } {
  const notes: Notes = { weakMatches: [], conflicts: [], dropped: [] };

  // A block whose `.blw` hasn't been handed over yet is skipped, not fatal:
  // mid-season the later series simply don't exist. Partial coverage is fine;
  // what matters is that the gap is stated rather than papered over.
  const present = group.blocks.filter((spec) => {
    if (existsSync(resolve(repoRoot, spec.file))) return true;
    notes.dropped.push(`${group.key}: no .blw for ${spec.name} yet (${spec.file}) — block omitted`);
    return false;
  });
  if (present.length === 0) throw new Error(`no .blw files present for any block`);

  const blocks = present.map((spec) => {
    const path = resolve(repoRoot, spec.file);
    const bytes = readFileSync(path);
    const raw = parseSailwaveBlw(
      bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer,
    );
    const file = buildSeriesFileFromSailwave(raw, {
      name: group.name,
      venue: group.venue,
      primaryLabel: 'helm',
      defaultRaceDate: spec.defaultRaceDate,
      fleetScoringOverrides: new Map(),
      includeScratchCompanions: true,
      includeResults: true,
    });
    return { spec, file };
  });

  // ---- Fleets: union by name ----
  const fleets: Fleet[] = [];
  const fleetIdByName = new Map<string, string>();
  for (const { spec, file } of blocks) {
    for (const f of file.fleets) {
      const existingId = fleetIdByName.get(f.name);
      if (!existingId) {
        const id = randomUUID();
        fleetIdByName.set(f.name, id);
        fleets.push({ ...f, id });
        continue;
      }
      const existing = fleets.find((x) => x.id === existingId)!;
      if (existing.scoringSystem !== f.scoringSystem) {
        throw new Error(
          `${group.key}: fleet "${f.name}" scores as ${existing.scoringSystem} in an earlier ` +
            `block but ${f.scoringSystem} in ${spec.name} — the group is mis-configured, ` +
            `or these are different fleets that share a name.`,
        );
      }
    }
  }

  // ---- Competitors: union across blocks ----
  const competitors: Competitor[] = [];
  const byKey = new Map<string, Competitor>();

  for (const { spec, file } of blocks) {
    for (const c of file.competitors) {
      const keys = competitorKeys(c);
      let match: Competitor | undefined;
      let matchedStrength = -1;
      for (const { key, strength } of keys) {
        const hit = byKey.get(key);
        if (hit) {
          match = hit;
          matchedStrength = strength;
          break;
        }
      }

      const label = `${c.sailNumber || '?'} ${c.boatName || ''} (${c.names?.[0] ?? '?'})`.trim();

      if (!match) {
        const merged: Competitor = {
          ...c,
          id: randomUUID(),
          fleetIds: c.fleetIds.map((id) => remapFleet(file, id, fleetIdByName)),
        };
        competitors.push(merged);
        for (const { key } of keys) if (!byKey.has(key)) byKey.set(key, merged);
        continue;
      }

      if (matchedStrength > 0) {
        notes.weakMatches.push(
          `${group.key} / ${spec.name}: joined "${label}" on ${STRENGTH_LABEL[matchedStrength]} ` +
            `(sail number + boat name did not match) — verify this is the same boat`,
        );
      }

      // Union the fleets the boat raced in; keep the first block's identity
      // fields but record anything that disagrees.
      for (const fid of c.fleetIds) {
        const mapped = remapFleet(file, fid, fleetIdByName);
        if (!match.fleetIds.includes(mapped)) match.fleetIds.push(mapped);
      }
      for (const field of ['boatName', 'boatClass', 'club', 'nationality'] as const) {
        const before = match[field];
        const now = c[field];
        if (before && now && before !== now) {
          notes.conflicts.push(
            `${group.key} / ${spec.name}: "${label}" has ${field} "${now}", ` +
              `earlier block had "${before}" — kept "${before}"`,
          );
        }
      }
      for (const { key } of keys) if (!byKey.has(key)) byKey.set(key, match);
    }
  }

  // ---- Races: concatenate, renumber, assign to blocks ----
  const races: Race[] = [];
  const subSeries: NonNullable<SeriesFile['subSeries']>[number][] = [];
  const tcfHistory: NonNullable<SeriesFile['tcfHistory']> = [];
  let raceNumber = 0;
  let previousBlockId: string | undefined;

  for (const [index, { spec, file }] of blocks.entries()) {
    const compIdMap = buildCompetitorIdMap(file, byKey, notes, group.key, spec.name);
    const raceIds: string[] = [];

    for (const r of file.races) {
      const id = randomUUID();
      raceIds.push(id);
      raceNumber += 1;
      races.push({
        ...r,
        id,
        raceNumber,
        // Keep Sailwave's own label when it has one; it's how the scorer and
        // the published page refer to the race.
        name: r.name ?? null,
        starts: r.starts.map((s) => ({
          ...s,
          id: randomUUID(),
          fleetIds: s.fleetIds.map((fid) => remapFleet(file, fid, fleetIdByName)),
        })),
        finishes: r.finishes.map((f) => ({
          ...f,
          id: randomUUID(),
          competitorId: f.competitorId ? (compIdMap.get(f.competitorId) ?? null) : null,
          penaltyOverrideByFleet: remapFleetKeyedRecord(file, f.penaltyOverrideByFleet, fleetIdByName),
          redressPointsByFleet: remapFleetKeyedRecord(file, f.redressPointsByFleet, fleetIdByName),
        })),
        ratingOverrides: r.ratingOverrides?.map((o) => ({
          ...o,
          id: randomUUID(),
          competitorId: compIdMap.get(o.competitorId) ?? o.competitorId,
        })),
      });

      for (const t of file.tcfHistory ?? []) {
        if (t.raceId !== r.id) continue;
        const competitorId = compIdMap.get(t.competitorId);
        if (!competitorId) {
          notes.dropped.push(
            `${group.key} / ${spec.name}: dropped an NHC rating record for an unresolvable competitor`,
          );
          continue;
        }
        tcfHistory.push({
          ...t,
          raceId: id,
          competitorId,
          fleetId: remapFleet(file, t.fleetId, fleetIdByName),
        });
      }
    }

    const blockId = randomUUID();
    subSeries.push({
      id: blockId,
      name: spec.name,
      displayOrder: index,
      raceIds,
      ...(group.carryHandicaps && previousBlockId
        ? { startingHandicapSource: 'continue' as const, continueFromSubSeriesId: previousBlockId }
        : { startingHandicapSource: 'base' as const }),
    });
    previousBlockId = blockId;
  }

  // ---- Series ----
  const base = blocks[0].file;
  const dates = races.map((r) => r.date).filter(Boolean).sort();

  const file: SeriesFile = {
    ...base,
    formatVersion: FORMAT_VERSION,
    seriesId: randomUUID(),
    exportedAt: new Date().toISOString(),
    series: {
      ...base.series,
      name: group.name,
      venue: group.venue,
      startDate: dates[0] ?? base.series.startDate,
      endDate: dates[dates.length - 1] ?? base.series.endDate,
      // Replaces the `.blw` threshold ladder for scoring; the ladder stays so
      // the editor can switch back without losing it.
      proportionalDiscard: group.proportionalDiscard,
      // Fleet-keyed publishing state from the first block's file would point at
      // fleet ids that no longer exist. FTP paths are threaded separately.
      ftpPaths: {},
      ftpPath: '',
      defaultStartSequence: undefined,
      raceFleetExclusions: undefined,
    },
    fleets,
    competitors,
    races,
    subSeries,
    tcfHistory: tcfHistory.length ? tcfHistory : undefined,
    // Revision history belongs to the source files, not to the merge.
    revisions: undefined,
    revisionSnapshots: undefined,
  };

  if (base.series.raceFleetExclusions?.length) {
    notes.dropped.push(
      `${group.key}: dropped ${base.series.raceFleetExclusions.length} race/fleet exclusion(s) ` +
        `from the first block — re-apply per block in the app if they still apply`,
    );
  }

  return { file, notes };
}

function remapFleet(file: SeriesFile, id: string, byName: Map<string, string>): string {
  const name = file.fleets.find((f) => f.id === id)?.name;
  const mapped = name ? byName.get(name) : undefined;
  if (!mapped) throw new Error(`unresolvable fleet id ${id}`);
  return mapped;
}

function remapFleetKeyedRecord(
  file: SeriesFile,
  record: Record<string, number> | undefined,
  byName: Map<string, string>,
): Record<string, number> | undefined {
  if (!record) return undefined;
  return Object.fromEntries(
    Object.entries(record).map(([fid, v]) => [remapFleet(file, fid, byName), v]),
  );
}

function buildCompetitorIdMap(
  file: SeriesFile,
  byKey: Map<string, Competitor>,
  notes: Notes,
  groupKey: string,
  blockName: string,
): Map<string, string> {
  const map = new Map<string, string>();
  for (const c of file.competitors) {
    let merged: Competitor | undefined;
    for (const { key } of competitorKeys(c)) {
      merged = byKey.get(key);
      if (merged) break;
    }
    if (!merged) {
      notes.dropped.push(
        `${groupKey} / ${blockName}: could not resolve "${c.sailNumber} ${c.boatName}" — its results are omitted`,
      );
      continue;
    }
    map.set(c.id, merged.id);
  }
  return map;
}

// ---- CLI ----

function main(): void {
  const args = process.argv.slice(2);
  const repoRoot = resolve(__dirname, '..');
  const groupArg = args[args.indexOf('--group') + 1];
  const outDir = args.includes('--out-dir')
    ? args[args.indexOf('--out-dir') + 1]
    : join(repoRoot, 'build', 'club-2026');
  // Lets a scratch tree of `.blw` files stand in for the committed one — used
  // to exercise the merge against the app's HYC fixtures.
  const blwRoot = args.includes('--blw-root') ? args[args.indexOf('--blw-root') + 1] : null;
  if (blwRoot) {
    for (const g of GROUPS) {
      for (const b of g.blocks) b.file = b.file.replace(BLW_ROOT, blwRoot);
    }
  }

  const selected = args.includes('--group')
    ? GROUPS.filter((g) => g.key === groupArg)
    : GROUPS;
  if (selected.length === 0) {
    console.error(`No group "${groupArg}". Known: ${GROUPS.map((g) => g.key).join(', ')}`);
    process.exit(1);
  }

  mkdirSync(outDir, { recursive: true });
  const allNotes: string[] = [];
  let failed = 0;

  for (const group of selected) {
    let merged: { file: SeriesFile; notes: Notes };
    try {
      merged = mergeGroup(group, repoRoot);
    } catch (err) {
      failed += 1;
      console.error(`✗ ${group.key}: ${(err as Error).message}`);
      continue;
    }
    const { file, notes } = merged;
    const out = join(outDir, `${group.key}.sailscoring`);
    writeFileSync(out, JSON.stringify(file, null, 2));

    const blockSummary = (file.subSeries ?? [])
      .map((b) => `${b.name}=${b.raceIds?.length ?? 0}`)
      .join(' ');
    console.log(
      `✓ ${group.key}: ${file.fleets.length} fleets, ${file.competitors.length} boats, ` +
        `${file.races.length} races [${blockSummary}] → ${out}`,
    );
    allNotes.push(...notes.weakMatches, ...notes.conflicts, ...notes.dropped);
  }

  if (allNotes.length) {
    console.log(`\n${allNotes.length} thing(s) to record in CLARIFICATIONS.md:`);
    for (const n of allNotes) console.log(`  - ${n}`);
  }
  if (failed) process.exit(1);
}

main();
