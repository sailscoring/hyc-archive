/**
 * HYC FTP-path resolver.
 *
 * Resolves Howth Yacht Club's per-fleet FTP upload paths from the club
 * catalogue (`2026-club-racing/2016_club.csv`) and emits the generic JSON
 * payload consumed by the app's `pnpm update-ftp-paths` script. The threading
 * itself — matching series by name, writing the workspace rows — lives in the
 * app (`../sailscoring/scripts/update-ftp-paths.ts`), which owns the DB layer.
 * This file is the HYC-specific *caller*: it knows where the paths come from.
 *
 * Why these paths matter: a scorer adopting Sail Scoring needs each live (2026)
 * series carrying the correct FTP upload location so published results land in
 * the right place on the club's results site.
 *
 * Workflow:
 *   1. cd ../sailscoring && pnpm update-ftp-paths inspect --workspace hyc
 *      # readonly: list HYC series + fleet names as the app sees them
 *   2. confirm SERIES_MAPPING below matches those series/fleet names
 *   3. pnpm ftp-paths > paths.json          # resolve CSV → JSON payload
 *   4. cd ../sailscoring && pnpm update-ftp-paths plan  --input ../hyc-archive/paths.json
 *   5. cd ../sailscoring && pnpm update-ftp-paths apply --input ../hyc-archive/paths.json
 *
 * Pass `--out <file>` to write the payload to disk instead of stdout.
 */
import fs from 'node:fs';
import path from 'node:path';

const HYC_SLUG = 'hyc';

const CSV_PATH = path.resolve(
  __dirname,
  '../2026-club-racing/2016_club.csv',
);

/**
 * Per-series mapping of fleet name → CSV row ID. Series are matched by name
 * within the HYC workspace: Sailwave re-imports mint a fresh series UUID each
 * time, so the name is the only stable handle. `seriesName` must match
 * `series.name` exactly — confirm against an `update-ftp-paths inspect` run in
 * the app. Update this (and re-run) whenever a Sailwave re-import changes
 * series/fleet naming, fleets are added, or the CSV grows new rows.
 *
 * CSV row 2212 (Saturday Cruisers IRC) currently points at the HPH path —
 * looks like a typo in the source CSV. Pass through unchanged; fix in the
 * CSV if/when HYC corrects it.
 */
interface SeriesMapping {
  seriesName: string; // matched against `series.name`
  fleetCsvIds: Record<string, number>; // fleet name → CSV row id
}

const SERIES_MAPPING: SeriesMapping[] = [
  {
    seriesName: "Tuesdays & Saturdays - Howth 17's - Series 1",
    fleetCsvIds: {
      'Howth 17 HPH': 2202,
      'Howth 17 Scr': 2203,
    },
  },
  {
    seriesName: 'Tuesdays - One Designs - Series 1',
    fleetCsvIds: {
      'Puppeteer HPH': 2198,
      'Puppeteer Scr': 2199,
      'Squib HPH': 2200,
      'Squib Scr': 2201,
    },
  },
  {
    seriesName: 'Wednesdays - Cruisers - Series 1',
    fleetCsvIds: {
      'Division A HPH': 2205,
      'Division A IRC': 2206,
      'Division B HPH': 2207,
      'Division B IRC': 2208,
      'Division C HPH': 2209,
      'Division C IRC': 2210,
    },
  },
  {
    seriesName: 'Thursdays - Dinghies - Series 1',
    fleetCsvIds: {
      PY: 2213,
      Optimist: 2214,
    },
  },
  {
    seriesName: 'Saturday - Cruisers - Series 1',
    fleetCsvIds: {
      'Division B HPH': 2211,
      'Division B IRC': 2212,
      'Division C HPH': 2219,
      'Division C IRC': 2220,
    },
  },
  {
    seriesName: 'Saturdays - One Designs - Series 1',
    fleetCsvIds: {
      'Puppeteer HPH': 2215,
      'Puppeteer Scr': 2216,
      'Squib HPH': 2217,
      'Squib Scr': 2218,
    },
  },
];

function loadPathsByCsvId(csvPath: string): Map<number, string> {
  const text = fs.readFileSync(csvPath, 'utf-8');
  const out = new Map<number, string>();
  for (const line of text.split(/\r?\n/)) {
    const row = line.split(',');
    const idCell = row[0]?.trim();
    if (!idCell || !/^\d+$/.test(idCell)) continue;
    const id = Number.parseInt(idCell, 10);
    const ftpPath = row[row.length - 1]?.trim();
    if (!ftpPath) continue;
    out.set(id, ftpPath);
  }
  return out;
}

interface SeriesPaths {
  name: string;
  fleetPaths: Record<string, string>;
}

interface Payload {
  workspace: string;
  series: SeriesPaths[];
}

function buildPayload(): Payload {
  const pathsByCsvId = loadPathsByCsvId(CSV_PATH);
  const series: SeriesPaths[] = [];
  for (const m of SERIES_MAPPING) {
    const fleetPaths: Record<string, string> = {};
    for (const [fleetName, csvId] of Object.entries(m.fleetCsvIds)) {
      const ftpPath = pathsByCsvId.get(csvId);
      if (!ftpPath) {
        console.error(`! CSV row ${csvId} (fleet "${fleetName}") has no path`);
        continue;
      }
      fleetPaths[fleetName] = ftpPath;
    }
    series.push({ name: m.seriesName, fleetPaths });
  }
  return { workspace: HYC_SLUG, series };
}

function main(): void {
  const args = process.argv.slice(2);
  const outIdx = args.indexOf('--out');
  const out = outIdx >= 0 ? args[outIdx + 1] : undefined;
  const json = `${JSON.stringify(buildPayload(), null, 2)}\n`;
  if (out) {
    fs.writeFileSync(out, json);
    console.error(`wrote ${out}`);
  } else {
    process.stdout.write(json);
  }
}

main();
