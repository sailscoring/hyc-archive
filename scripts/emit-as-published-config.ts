/**
 * Emit `as-published.config.json` from the reshyc capture (ADR-010,
 * sailscoring#283) — the input to the app repo's `pnpm archive-generate`.
 *
 * The join is the hyc.ie admin results DB backup
 * (`sources/reshyc/admin/<year>_{club,open}.csv`): each row maps
 * (year, club/open, event, class) to an FTP path, and the event/class cells
 * carry the display names the club published under. One as-published series
 * per (year, club/open, event); each class becomes a fleet page at
 * `{event}/{class}` under the shared per-year slug
 * (`/p/hyc/2022/wave-regatta/class-0`).
 *
 *   pnpm emit-as-published            # writes ./as-published.config.json
 *
 * FTP paths resolve against `sources/reshyc/results.hyc.ie/` the way the
 * club's (Windows) server resolved them: case-insensitively, tolerating
 * backslashes and stray whitespace. Rows whose page is genuinely absent from
 * the capture are skipped and reported — never guessed at (partial coverage
 * is fine; fabrication is not).
 *
 * Ids are UUIDv5 over the stable per-series key, minted with the archive-kit
 * namespace, so regeneration can never mint duplicates.
 */

import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

/** Current season stays full-fidelity (scored in-app); archive what's before. */
const CUTOFF_YEAR = 2026;

const CAPTURE_ROOT = 'sources/reshyc/results.hyc.ie';
const ADMIN_DIR = 'sources/reshyc/admin';

// Matches lib/archive-kit/ids.ts in the app repo. Fixed forever: the derived
// ids are persisted, and the identity links hang off the competitor rows.
const ARCHIVE_NS = '7c1f9d54-3e82-5b17-9a60-2f4d8c5e0b39';
const REPO_KEY = 'hyc-archive';

function uuidv5(name: string, namespace: string = ARCHIVE_NS): string {
  const ns = Buffer.from(namespace.replace(/-/g, ''), 'hex');
  const hash = createHash('sha1')
    .update(ns)
    .update(Buffer.from(name, 'utf8'))
    .digest();
  const bytes = hash.subarray(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString('hex');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
}

function kebab(name: string): string {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'series'
  );
}

/** Case-insensitive index of the capture tree: lowercased FTP path → the
 *  real repo-relative file path. Mirrors the case-insensitive Windows server
 *  the admin DB's paths were written against. */
function buildCaptureIndex(): Map<string, string> {
  const index = new Map<string, string>();
  const walk = (dir: string, ftpPrefix: string) => {
    for (const entry of readdirSync(join(CAPTURE_ROOT, dir), {
      withFileTypes: true,
    })) {
      const rel = dir ? `${dir}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(rel, `${ftpPrefix}/${entry.name}`);
      else index.set(`${ftpPrefix}/${entry.name}`.toLowerCase(), join(CAPTURE_ROOT, rel));
    }
  };
  walk('', '');
  return index;
}

/** Normalise an admin-DB ftp_path the way the club's server would have. */
function normFtpPath(raw: string): string {
  let p = raw.trim().replace(/\\/g, '/');
  if (!p.startsWith('/')) p = `/${p}`;
  return p.toLowerCase();
}

interface AdminRow {
  id: string;
  event: string;
  className: string;
  ftpPath: string;
}

/** The CSVs are unquoted `id,event,class,ftp_path` dumps; a handful of rows
 *  carry commas inside the name cells and can't be split unambiguously —
 *  those are reported and skipped. */
function parseAdminCsv(file: string): { rows: AdminRow[]; malformed: string[] } {
  const rows: AdminRow[] = [];
  const malformed: string[] = [];
  for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
    if (!line.trim()) continue;
    const cells = line.split(',');
    if (cells.length !== 4) {
      malformed.push(line);
      continue;
    }
    rows.push({
      id: cells[0].trim(),
      event: cells[1].trim(),
      className: cells[2].trim(),
      ftpPath: cells[3],
    });
  }
  return { rows, malformed };
}

interface ConfigFleet {
  name: string;
  subPath: string;
  file: string;
}

interface ConfigSeries {
  key: string;
  id: string;
  publishedSlug: string;
  name: string;
  venue: string;
  startDate: string;
  venueUrl: string;
  venueLogoUrl: string;
  source: 'sailwave';
  category: string;
  fleets: ConfigFleet[];
}

/** Series the app's archive-kit can't ingest yet, excluded from the emitted
 *  config so CI stays green — each with its reason. The gap is real, not
 *  silent: the emit run reports the count, and CLARIFICATIONS.md carries the
 *  story. Remove entries as archive-kit grows support. */
function loadSkips(): Record<string, string> {
  try {
    return JSON.parse(readFileSync('as-published-skips.json', 'utf8'));
  } catch {
    return {};
  }
}

function run(): number {
  const captureIndex = buildCaptureIndex();
  const skips = loadSkips();

  const catalogues = readdirSync(ADMIN_DIR)
    .map((f) => /^(\d{4})_(club|open)\.csv$/.exec(f))
    .filter((m): m is RegExpExecArray => m !== null)
    .map((m) => ({ file: join(ADMIN_DIR, m[0]), year: m[1], type: m[2] }))
    .filter((c) => Number(c.year) < CUTOFF_YEAR)
    .sort((a, b) => a.year.localeCompare(b.year) || a.type.localeCompare(b.type));

  const series: ConfigSeries[] = [];
  let emptyPath = 0;
  const skippedKeys = new Set<string>();
  const missing: string[] = [];
  const skippedMalformed: string[] = [];

  for (const cat of catalogues) {
    const { rows, malformed } = parseAdminCsv(cat.file);
    skippedMalformed.push(...malformed.map((l) => `${cat.file}: ${l}`));

    // Group rows into one series per event, preserving catalogue order.
    const byEvent = new Map<string, AdminRow[]>();
    for (const row of rows) {
      const list = byEvent.get(row.event) ?? [];
      list.push(row);
      byEvent.set(row.event, list);
    }

    for (const [event, eventRows] of byEvent) {
      const key = `hyc-${cat.year}-${cat.type}-${kebab(event)}`;
      if (skips[key]) {
        skippedKeys.add(key);
        continue;
      }
      const usedSubPaths = new Set<string>();
      const usedNames = new Set<string>();
      const fleets: ConfigFleet[] = [];
      for (const row of eventRows) {
        if (!row.ftpPath.trim()) {
          emptyPath++;
          continue;
        }
        const ftpPath = normFtpPath(row.ftpPath);
        if (ftpPath.includes('sc-test')) continue; // publishing test pages
        const file = captureIndex.get(ftpPath);
        if (!file) {
          missing.push(`${cat.year} ${cat.type} | ${event} | ${row.className} | ${row.ftpPath.trim()}`);
          continue;
        }
        let name = row.className;
        let n = 2;
        while (usedNames.has(name)) name = `${row.className} (${n++})`;
        usedNames.add(name);
        let subPath = kebab(`${event}`) + `/${kebab(name)}`;
        n = 2;
        const base = subPath;
        while (usedSubPaths.has(subPath)) subPath = `${base}-${n++}`;
        usedSubPaths.add(subPath);
        fleets.push({ name, subPath, file });
      }
      if (fleets.length === 0) continue;
      series.push({
        key,
        id: uuidv5(`${REPO_KEY}/series/${key}`),
        // One shared slug per season year: /p/hyc/{year}/{event}/{class}.
        publishedSlug: cat.year,
        name: `${event} ${cat.year}`,
        venue: 'Howth',
        venueUrl: 'https://www.hyc.ie',
        venueLogoUrl: 'https://logos.sailscoring.ie/hyc.png',
        // The admin DB carries no dates; HYC club racing starts in April,
        // and the year is what the app's grouping reads.
        startDate: `${cat.year}-04-01`,
        source: 'sailwave',
        // Initial in-app filing: one category per season year.
        category: cat.year,
        fleets,
      });
    }
  }

  // Page paths are a per-year namespace shared by club and open events: a
  // same-named event on both sides would collide, so the open side yields.
  const seen = new Map<string, ConfigSeries>();
  for (const s of series) {
    for (const f of s.fleets) {
      let k = `${s.publishedSlug}|${f.subPath}`;
      if (seen.has(k)) {
        const [eventSeg, ...rest] = f.subPath.split('/');
        f.subPath = [`${eventSeg}-${s.key.includes('-open-') ? 'open' : 'club'}`, ...rest].join('/');
        k = `${s.publishedSlug}|${f.subPath}`;
      }
      if (seen.has(k)) {
        console.error(`  ! duplicate page path: /p/hyc/${s.publishedSlug}/${f.subPath} (${s.key} vs ${seen.get(k)?.key})`);
        return 1;
      }
      seen.set(k, s);
    }
  }

  for (const line of skippedMalformed) console.error(`  ! malformed row: ${line}`);
  for (const line of missing) console.error(`  ! not in capture: ${line}`);

  const config = {
    version: 1,
    out: 'as-published',
    series,
  };
  writeFileSync(
    'as-published.config.json',
    `${JSON.stringify(config, null, 2)}\n`,
  );
  const fleetCount = series.reduce((n, s) => n + s.fleets.length, 0);
  console.log(
    `as-published.config.json: ${series.length} series, ${fleetCount} fleet pages ` +
      `(${emptyPath} rows had no ftp_path, ${missing.length} pages not in capture, ` +
      `${skippedMalformed.length} malformed rows, ${skippedKeys.size} series on the skip-list)`,
  );
  for (const k of Object.keys(skips)) {
    if (!skippedKeys.has(k)) console.error(`  ! stale skip-list entry (no such series): ${k}`);
  }
  return 0;
}

process.exit(run());
