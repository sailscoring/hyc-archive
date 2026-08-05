/**
 * Prove that merging HYC's per-series Sailwave files into one blocked series
 * changed nothing.
 *
 * The merge (`scripts/merge-club-series.ts`) is only safe if each block still
 * scores exactly as its source `.blw` did on its own. This scores both with the
 * app's own engine — imported by relative path, never forked — and diffs the
 * standings row by row: rank, boat, net and total points, per-race scores, and
 * how many races were discarded.
 *
 *   pnpm verify-club-merge build/club-2026/tuesday-one-designs.sailscoring \
 *     sources/blw/2026/tuesday-one-designs/series-1.blw \
 *     sources/blw/2026/tuesday-one-designs/series-2.blw
 *
 * Source files are given in block order and matched positionally; pass as many
 * as the merged file has blocks. It also reports the discard allowance the
 * proportional rule yields per block, which is the property that makes the
 * merge safe in the first place: blocks score independently, so a three-race
 * Series 3 gets a three-race allowance even though the merged series holds a
 * whole season.
 */
import { readFileSync } from 'node:fs';

import {
  calculateFleetStandings,
  calculateSubSeriesFleetStandings,
  getDiscardCount,
} from '../../sailscoring/lib/scoring';
import {
  buildSeriesFileFromSailwave,
  parseSailwaveBlw,
} from '../../sailscoring/lib/sailwave-import';
import type { SeriesFile } from '../../sailscoring/lib/series-file';

/* The scoring engine takes repository entities; a SeriesFile nests starts and
 * finishes inside each race. Flattening is all that separates them, so these
 * casts are the seam between the two shapes rather than a shortcut. */
/* eslint-disable @typescript-eslint/no-explicit-any */

/** Score every block the way the app does — not by scoring a race subset as if
 *  it were a whole series, which would miss `excludeDncOnlyCompetitors` and the
 *  handicap carry between blocks. */
function scoreBlocks(file: SeriesFile): any[] {
  const { races, finishes, starts } = flatten(file);
  return calculateSubSeriesFleetStandings(
    (file.subSeries ?? []) as any,
    file.fleets as any,
    file.competitors as any,
    races,
    finishes,
    [],
    file.series.dnfScoring as any,
    starts,
    [],
    (file.subSeries ?? []).some((b) => b.excludeDncOnlyCompetitors),
    file.series.proportionalDiscard as any,
  );
}

function flatten(file: SeriesFile, raceSubset?: Set<string>) {
  const races = file.races.filter((r) => !raceSubset || raceSubset.has(r.id));
  return {
    races: races.map((r) => ({ ...r, seriesId: 'merged', name: r.name ?? null })) as any,
    finishes: races.flatMap((r) =>
      r.finishes.map((f) => ({
        ...f,
        raceId: r.id,
        tiedWithPrevious: f.tiedWithPrevious ?? false,
      })),
    ) as any,
    starts: races.flatMap((r) => r.starts.map((s) => ({ ...s, raceId: r.id }))) as any,
  };
}

function score(file: SeriesFile, raceSubset?: Set<string>): any {
  const races = file.races.filter((r) => !raceSubset || raceSubset.has(r.id));
  return calculateFleetStandings(
    file.fleets as any,
    file.competitors as any,
    races.map((r) => ({ ...r, seriesId: 'merged', name: r.name ?? null })) as any,
    races.flatMap((r) =>
      r.finishes.map((f) => ({
        ...f,
        raceId: r.id,
        tiedWithPrevious: f.tiedWithPrevious ?? false,
      })),
    ) as any,
    [],
    file.series.dnfScoring as any,
    races.flatMap((r) => r.starts.map((s) => ({ ...s, raceId: r.id }))) as any,
    [],
    undefined,
    undefined,
    file.series.proportionalDiscard as any,
  );
}

/** One comparable line per standings row. Fleet ids differ between the merged
 *  file and its sources, so the fleet is identified by name. */
function project(result: any): string[] {
  const out: string[] = [];
  for (const entry of result.fleetStandings) {
    for (const r of entry.standings) {
      out.push(
        [
          entry.fleet.name,
          r.rank,
          r.competitor.sailNumber,
          r.competitor.boatName ?? '',
          r.netPoints,
          r.totalPoints,
          `discards=${(r.raceDiscards ?? []).filter(Boolean).length}`,
          (r.racePoints ?? []).join('/'),
        ].join(' | '),
      );
    }
  }
  return out.sort();
}

function loadBlw(path: string, proportionalDiscard: unknown): SeriesFile {
  const bytes = readFileSync(path);
  const raw = parseSailwaveBlw(
    bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer,
  );
  const file = buildSeriesFileFromSailwave(raw, {
    name: 'source',
    venue: 'source',
    primaryLabel: 'helm',
    fleetScoringOverrides: new Map(),
    includeScratchCompanions: true,
    includeResults: true,
  });
  // Score the source under the same rule as the merge, so the diff isolates
  // the merge itself rather than re-reporting the discard-rule change (which
  // is a deliberate, documented divergence — see CLARIFICATIONS.md).
  file.series.proportionalDiscard = proportionalDiscard as never;
  return file;
}

function main(): void {
  const [mergedPath, ...sourcePaths] = process.argv.slice(2);
  if (!mergedPath) {
    console.error('usage: pnpm verify-club-merge <merged.sailscoring> [source.blw …]');
    process.exit(1);
  }

  const merged: SeriesFile = JSON.parse(readFileSync(mergedPath, 'utf8'));
  const pd = merged.series.proportionalDiscard as any;
  const blocks = merged.subSeries ?? [];

  console.log(`${mergedPath}`);
  console.log(`  proportionalDiscard ${JSON.stringify(pd)}`);
  console.log(
    `  allowance  ${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
      .map((n) => `${n}→${getDiscardCount(n, [], pd)}`)
      .join('  ')}`,
  );

  const blockResults = scoreBlocks(merged);
  let mismatches = 0;
  for (const [i, block] of blocks.entries()) {
    const subset = new Set(block.raceIds ?? []);
    const blockResult = blockResults.find((r) => r.subSeries.id === block.id);
    if (!blockResult) {
      console.log(`\n  ${block.name}: no standings returned`);
      mismatches += 1;
      continue;
    }
    const applied = Math.max(
      0,
      ...blockResult.fleetStandings.flatMap((e: any) =>
        e.standings.map((r: any) => (r.raceDiscards ?? []).filter(Boolean).length),
      ),
    );
    console.log(
      `\n  ${block.name}: ${subset.size} races, ${applied} discard(s) applied to the deepest row`,
    );

    const sourcePath = sourcePaths[i];
    if (!sourcePath) {
      console.log(`    (no source .blw given — structure only)`);
      continue;
    }
    const a = project(blockResult);
    const b = project(score(loadBlw(sourcePath, pd)));
    if (a.length === b.length && a.every((x, j) => x === b[j])) {
      console.log(`    identical to ${sourcePath} scored on its own (${a.length} rows)`);
      continue;
    }
    mismatches += 1;
    // Key on fleet + boat so a row present on one side only is reported as
    // missing rather than smeared across the whole ordered diff.
    const key = (row: string) => row.split(' | ').slice(0, 1).concat(row.split(' | ')[2]).join(' | ');
    const am = new Map(a.map((r) => [key(r), r]));
    const bm = new Map(b.map((r) => [key(r), r]));
    const onlySource = [...bm.keys()].filter((k) => !am.has(k));
    const onlyMerged = [...am.keys()].filter((k) => !bm.has(k));
    const changed = [...am.keys()].filter((k) => bm.has(k) && am.get(k) !== bm.get(k));
    console.log(
      `    DIFFERS from ${sourcePath}: ${changed.length} row(s) scored differently, ` +
        `${onlySource.length} only in source, ${onlyMerged.length} only in merged`,
    );
    for (const k of changed.slice(0, 6)) {
      console.log(`      merged: ${am.get(k)}`);
      console.log(`      source: ${bm.get(k)}`);
    }
    for (const k of onlySource.slice(0, 4)) console.log(`      only in source: ${bm.get(k)}`);
    for (const k of onlyMerged.slice(0, 4)) console.log(`      only in merged: ${am.get(k)}`);
  }

  const whole = score(merged);
  const wholeApplied = Math.max(
    0,
    ...whole.fleetStandings.flatMap((e: any) =>
      e.standings.map((r: any) => (r.raceDiscards ?? []).filter(Boolean).length),
    ),
  );
  console.log(
    `\n  whole series (all ${merged.races.length} races, for contrast): ${wholeApplied} discard(s)`,
  );

  if (mismatches) {
    console.error(`\n${mismatches} block(s) differ from their source — do not import.`);
    process.exit(1);
  }
}

main();
