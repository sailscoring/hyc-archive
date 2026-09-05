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

/**
 * Events from the current season that are nonetheless archived as-published:
 * club series that have **finished**, so their pages will not change again.
 *
 * 2026 club racing is also imported full-fidelity as one blocked series per
 * racing group (`pnpm merge-club-series`), but that import is a *demo* of the
 * sub-series method and diverges from the published tables. These entries are
 * the faithful record of the same racing, and the two are kept apart by the
 * demo's " (DEMO)" name suffix.
 *
 * Series 3 is deliberately absent: it is still being sailed. Add it — and the
 * dinghies' Series 3, once it starts — when the club stops updating the pages.
 * An event only ever joins this list after its last race, because an
 * as-published series key can never be renamed (CLAUDE.md rule 4).
 */
const CURRENT_SEASON_EVENTS = new Set([
  // Open events that are over. Held back until they were: the Fingal Cruiser
  // Challenge is still being updated, and the Puppeteer 22 Championships and
  // Howth 17 Nationals have published entry lists with no racing sailed yet.
  // The Double-Handed Race is a coverage gap, not a timing one — admin row
  // 2265 points at a page that has never appeared in the capture.
  'hyc-2026-open-fireball-nationals',
  'hyc-2026-open-dinghy-f-bite-spring-2026',
  'hyc-2026-open-tadg-riordan-brass-monkeys',
  // One race, published as a race result rather than a standings table — see
  // as-published-race-results.json.
  'hyc-2026-open-new-year-s-day-dinghies',
  // Also one race, but it keeps its standings table: HYC published the two
  // ILCA fleets summary-only, with no race-detail table to promote in its
  // place, and `detail` is a per-series setting.
  'hyc-2026-open-dinghy-round-the-island',
  // Club series, finished.
  'hyc-2026-club-wednesday-series-1',
  'hyc-2026-club-wednesday-series-2',
  'hyc-2026-club-tuesday-series-1',
  'hyc-2026-club-tuesday-series-2',
  'hyc-2026-club-tuesday-saturday-series-1',
  'hyc-2026-club-tuesday-saturday-series-2',
  'hyc-2026-club-saturday-series-1',
  'hyc-2026-club-saturday-series-2',
  'hyc-2026-club-dinghy-series-1',
  'hyc-2026-club-dinghy-series-2',
]);

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

/** Index of the capture tree, keyed both ways.
 *
 *  `exact` is the FTP path as it appears on disk; `lower` is the lowercased
 *  path to **every** file that shares it. The admin DB's paths were written
 *  against a case-insensitive Windows server, so a lowercased lookup is the
 *  right default — but the capture is a case-*sensitive* mirror and holds 13
 *  pairs differing only in case (`rti_PY.htm` vs `rti_py.htm`,
 *  `2024/open/Lambay/Class3.htm` vs `class3.htm`, …), usually with different
 *  content. Folding those together and keeping whichever the walk saw last
 *  silently substitutes one page for another, so both keys are kept and the
 *  exact one wins. */
interface CaptureIndex {
  exact: Map<string, string>;
  lower: Map<string, string[]>;
}

function buildCaptureIndex(): CaptureIndex {
  const exact = new Map<string, string>();
  const lower = new Map<string, string[]>();
  const walk = (dir: string, ftpPrefix: string) => {
    for (const entry of readdirSync(join(CAPTURE_ROOT, dir), {
      withFileTypes: true,
    })) {
      const rel = dir ? `${dir}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        walk(rel, `${ftpPrefix}/${entry.name}`);
        continue;
      }
      const ftpPath = `${ftpPrefix}/${entry.name}`;
      const file = join(CAPTURE_ROOT, rel);
      exact.set(ftpPath, file);
      const bucket = lower.get(ftpPath.toLowerCase()) ?? [];
      bucket.push(file);
      lower.set(ftpPath.toLowerCase(), bucket);
    }
  };
  walk('', '');
  return { exact, lower };
}

/** Normalise an admin-DB ftp_path the way the club's server would have —
 *  slashes and a leading `/`, but **not** case: see `resolveCapture`. */
function normFtpPath(raw: string): string {
  let p = raw.trim().replace(/\\/g, '/');
  if (!p.startsWith('/')) p = `/${p}`;
  return p;
}

/** Resolve an admin path to a captured file: the exact-case file if there is
 *  one, else the unique case-insensitive match. An ambiguous fold — several
 *  candidates and none matching the admin DB's own spelling — is reported and
 *  left unresolved rather than guessed at. */
function resolveCapture(
  index: CaptureIndex,
  ftpPath: string,
): { file?: string; ambiguous?: string[] } {
  const exact = index.exact.get(ftpPath);
  if (exact) return { file: exact };
  const candidates = index.lower.get(ftpPath.toLowerCase()) ?? [];
  if (candidates.length === 1) return { file: candidates[0] };
  if (candidates.length === 0) return {};
  return { ambiguous: candidates };
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

interface ConfigSection {
  sectionTitle: string;
  includeRaces?: true;
}

interface ConfigFleet {
  name: string;
  subPath: string;
  file: string;
  /** Carry the page's per-race detail tables, not just the standings. Set
   *  only when the captured page actually publishes race tables (most do; a
   *  handful — e-sailing ladders, participation lists — are standings-only). */
  includeRaces?: true;
  /** When the capture publishes several summary sections on one page (a class
   *  scored two ways — HPH + Scratch — or a class group), list them so the
   *  app emits one combined page (#321) with a section per summary rather than
   *  dropping all but the first. */
  sections?: ConfigSection[];
  /** The race-only counterpart (app #355): a page whose race tables are
   *  several fleets rather than several races of one class. Curated in
   *  as-published-race-sections.json. */
  raceSections?: Array<{ raceTitle: string; name?: string }>;
  /** This page is a second presentation of racing another page of the same
   *  event already accounts for (app #363). Curated in
   *  as-published-display-only.json. */
  displayOnly?: true;
}

/** The summary-section headings of a capture, in document order, normalised
 *  the way the app's parser reads them (`textContent`, collapsed). Scripts and
 *  styles are stripped first: Sailwave's page carries a `summarytitle` heading
 *  inside a `<script>` template that isn't a real rendered section. */
function sectionsOf(html: string): { titles: string[]; tableCount: number; hasRaces: boolean } {
  const body = html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '');
  const titles = [...body.matchAll(/<h3 class="summarytitle"[^>]*>([\s\S]*?)<\/h3>/g)].map(
    (m) =>
      m[1]
        .replace(/<[^>]*>/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/\s+/g, ' ')
        .trim(),
  );
  return {
    titles,
    tableCount: (body.match(/class="summarytable"/g) ?? []).length,
    hasRaces: body.includes('class="racetable"'),
  };
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
  /** Publish this event's fleets as race results alone (app #347) — a one-off
   *  trophy race, not a series. Curated in as-published-race-results.json. */
  detail?: 'races';
  category: string;
  fleets: ConfigFleet[];
  /** Pinned display labels for the event folder (ADR-011): the admin DB's
   *  event name, emitted only where humanising the URL segment would mangle
   *  it ("1720's Easterns" vs "1720 S Easterns"). */
  folders?: Array<{ path: string; label: string }>;
}

/** How the app labels a folder with no pin: title-cased segment words.
 *  Mirrors `humanizeSlug` (app repo, lib/publishing.ts) so the emitter can
 *  pin only the labels the derivation would get wrong. */
function humanizeSegment(segment: string): string {
  return segment
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
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

/** Events that publish as a race result rather than a series table (app
 *  #347) — a one-off trophy race, where a standings table would be one race
 *  column, a total equal to that race's score, and meaningless discards.
 *
 *  Curated by hand, never derived from the race count. Plenty of HYC series
 *  sailed exactly one race and are still series: a league abandoned after its
 *  first day, a championship that never got away. Those keep their standings
 *  table, which is what the club published and what the record should say. */
function loadRaceResults(): Record<string, string> {
  try {
    return JSON.parse(readFileSync('as-published-race-results.json', 'utf8'));
  } catch {
    return {};
  }
}

/** Race-only pages (app #355) whose race tables are several *fleets* rather
 *  than several races of one class — 2022's Lambay pages carry each class's
 *  IRC and ECHO results side by side, and the 2024 New Year's Day race put
 *  PY, ILCA 6 and ILCA 7 on one page. Keyed `<series key>|<class name>`,
 *  valued by the race-table headings to split on, so each fleet states the
 *  places its own table published. Un-split, such a page is one fleet whose
 *  rows rank nowhere.
 *
 *  Hand-curated: whether two tables are two fleets or two races of one is a
 *  fact about the event, and the page's markup does not say which. */
function loadRaceSections(): Record<
  string,
  Array<{ raceTitle: string; name?: string }>
> {
  try {
    return JSON.parse(readFileSync('as-published-race-sections.json', 'utf8'));
  } catch {
    return {};
  }
}

/** Pages that re-present racing another page of the same event already
 *  accounts for (app #363) — the J24 Europeans' per-day race results beside
 *  the championship's own overall standings. Keyed `<series key>|<class
 *  name>`, valued by the reason. Their tables still publish; their rows join
 *  the competitors the structural page minted rather than minting a second
 *  set, and they take no place in a career arc. */
function loadDisplayOnly(): Record<string, string> {
  try {
    return JSON.parse(readFileSync('as-published-display-only.json', 'utf8'));
  } catch {
    return {};
  }
}

function run(): number {
  const captureIndex = buildCaptureIndex();
  const skips = loadSkips();
  const raceResults = loadRaceResults();
  const raceResultKeys = new Set<string>();
  const raceSections = loadRaceSections();
  const displayOnly = loadDisplayOnly();
  const usedRaceSections = new Set<string>();
  const usedDisplayOnly = new Set<string>();

  const catalogues = readdirSync(ADMIN_DIR)
    .map((f) => /^(\d{4})_(club|open)\.csv$/.exec(f))
    .filter((m): m is RegExpExecArray => m !== null)
    .map((m) => ({ file: join(ADMIN_DIR, m[0]), year: m[1], type: m[2] }))
    // Current-season catalogues come through too; the per-event gate below
    // keeps all but the finished series out.
    .filter((c) => Number(c.year) <= CUTOFF_YEAR)
    .sort((a, b) => a.year.localeCompare(b.year) || a.type.localeCompare(b.type));

  const series: ConfigSeries[] = [];
  // The admin DB's event display name per series, for the folder-label pins
  // (whitespace-normalised; the CSVs carry stray trailing spaces).
  const eventLabelBySeries = new Map<ConfigSeries, string>();
  let emptyPath = 0;
  const skippedKeys = new Set<string>();
  const missing: string[] = [];
  const ambiguousPaths: string[] = [];
  const skippedMalformed: string[] = [];
  const notResults: string[] = [];

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
      if (Number(cat.year) >= CUTOFF_YEAR && !CURRENT_SEASON_EVENTS.has(key)) continue;
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
        const { file, ambiguous } = resolveCapture(captureIndex, ftpPath);
        if (ambiguous) {
          ambiguousPaths.push(
            `${cat.year} ${cat.type} | ${event} | ${row.className} | ${row.ftpPath.trim()} ` +
              `→ ${ambiguous.length} files differing only in case, none matching: ` +
              ambiguous.map((f) => f.split('/').pop()).join(', '),
          );
          continue;
        }
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
        const { titles, tableCount, hasRaces } = sectionsOf(readFileSync(file, 'utf8'));
        if (tableCount === 0 && !hasRaces) {
          // Not a result at all: an entry list, a team ranking table, a note
          // saying the divisions were dropped, or an empty file. The page is
          // real and captured, but there is nothing for the archive to hold —
          // dropping the class keeps the rest of the event ingestible, where
          // failing on it used to cost the whole series. CLARIFICATIONS.md
          // carries the inventory.
          notResults.push(
            `${cat.year} ${cat.type} | ${event} | ${row.className} | ${file}`,
          );
          usedNames.delete(name);
          usedSubPaths.delete(subPath);
          continue;
        }
        const curationKey = `${key}|${name}`;
        const sectioned = raceSections[curationKey];
        if (sectioned) usedRaceSections.add(curationKey);
        if (displayOnly[curationKey]) usedDisplayOnly.add(curationKey);
        const extras = {
          ...(sectioned ? { raceSections: sectioned } : {}),
          ...(displayOnly[curationKey] ? { displayOnly: true as const } : {}),
        };
        if (tableCount > 1 && titles.length === tableCount) {
          // A single page publishing several summary sections — publish it as
          // one combined page (#321), a member fleet per section.
          fleets.push({
            name,
            subPath,
            file,
            sections: titles.map((sectionTitle) => ({
              sectionTitle,
              ...(hasRaces ? { includeRaces: true as const } : {}),
            })),
            ...extras,
          });
        } else {
          fleets.push({
            name,
            subPath,
            file,
            ...(hasRaces ? { includeRaces: true as const } : {}),
            ...extras,
          });
        }
      }
      if (fleets.length === 0) continue;
      const entry: ConfigSeries = {
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
        ...(raceResults[key] ? { detail: 'races' as const } : {}),
        // Initial in-app filing: the club/open split the admin catalogues
        // already carry, so the public picker reads Year -> Open/Club ->
        // Series -> Fleet — the year axis comes from the start date, so a
        // per-year category would just shadow it.
        category: cat.type === 'open' ? 'Open Events' : 'Club Racing',
        fleets,
      };
      if (raceResults[key]) raceResultKeys.add(key);
      series.push(entry);
      eventLabelBySeries.set(entry, event.replace(/\s+/g, ' ').trim());
    }
  }

  // Page paths are a per-year namespace shared by club and open events: a
  // same-named event on both sides would collide, so the open side yields.
  const seen = new Map<string, ConfigSeries>();
  const suffixed = new Set<ConfigSeries>();
  for (const s of series) {
    for (const f of s.fleets) {
      let k = `${s.publishedSlug}|${f.subPath}`;
      if (seen.has(k)) {
        const [eventSeg, ...rest] = f.subPath.split('/');
        f.subPath = [`${eventSeg}-${s.key.includes('-open-') ? 'open' : 'club'}`, ...rest].join('/');
        k = `${s.publishedSlug}|${f.subPath}`;
        suffixed.add(s);
      }
      if (seen.has(k)) {
        console.error(`  ! duplicate page path: /p/hyc/${s.publishedSlug}/${f.subPath} (${s.key} vs ${seen.get(k)?.key})`);
        return 1;
      }
      seen.set(k, s);
    }
  }

  // Folder labels (ADR-011): pin the admin DB's event display name on the
  // event folder wherever the app's derived label (title-cased segment
  // words) would mangle it — "1720's Easterns" vs "1720 S Easterns",
  // "Dinghy F'bite Spring 2025" vs "Dinghy F Bite Spring 2025". The rest
  // derive correctly and need no pin. A club/open-suffixed segment keeps
  // the side in its label so the two folders stay distinguishable.
  for (const s of series) {
    const base = eventLabelBySeries.get(s) ?? '';
    const label = suffixed.has(s)
      ? `${base} (${s.key.includes('-open-') ? 'Open' : 'Club'})`
      : base;
    const folders = [...new Set(s.fleets.map((f) => f.subPath.split('/')[0]))]
      .filter((segment) => humanizeSegment(segment) !== label)
      .map((segment) => ({ path: segment, label }));
    if (folders.length > 0) s.folders = folders;
  }

  for (const line of skippedMalformed) console.error(`  ! malformed row: ${line}`);
  for (const line of notResults) console.error(`  ! not a results page: ${line}`);
  for (const line of missing) console.error(`  ! not in capture: ${line}`);
  for (const line of ambiguousPaths) console.error(`  ! ambiguous case fold: ${line}`);

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
      `${notResults.length} pages that aren't results, ${skippedMalformed.length} malformed rows, ` +
      `${skippedKeys.size} series on the skip-list, ${raceResultKeys.size} single-race events)`,
  );
  for (const k of Object.keys(skips)) {
    if (!skippedKeys.has(k)) console.error(`  ! stale skip-list entry (no such series): ${k}`);
  }
  for (const k of Object.keys(raceResults)) {
    if (!raceResultKeys.has(k)) console.error(`  ! stale race-results entry (no such series): ${k}`);
  }
  for (const k of Object.keys(raceSections)) {
    if (!usedRaceSections.has(k)) console.error(`  ! stale race-sections entry (no such page): ${k}`);
  }
  for (const k of Object.keys(displayOnly)) {
    if (!usedDisplayOnly.has(k)) console.error(`  ! stale display-only entry (no such page): ${k}`);
  }
  return 0;
}

process.exit(run());
