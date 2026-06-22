#!/usr/bin/env python3
"""Compare HYC 2026 club racing results between Sailwave and Sail Scoring.

Both publishers push HTML to HYC's FTP tree under old.hyc.ie:
  - Sailwave-produced results live under /reshyc/2026/club/   (per 2026_club.csv)
  - Sail Scoring "SC TESTING" results live under /reshyc/sc-test/   (per 2016_club.csv)

For each (Sailwave fleet, SC fleet) pair below, this script fetches both
HTMLs, parses the standings/race tables, and reports MEANINGFUL differences in:

  * net points and rank per competitor (any difference in net points)
  * the NHC TCF used for each race per competitor (> RATING_TOLERANCE)
  * the post-most-recent-race NHC TCF (SC only — Sailwave's 2026 template
    doesn't render a NewRating column in the summary)

Identical pairings produce a single "OK" line. Pass --verbose to see every
matched row regardless of difference.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://old.hyc.ie"

# (label, sw_path, sw_fleet_anchor, sc_path)
#
# sw_fleet_anchor matches the slug in <h3 class="summarytitle" id="summaryX">.
# Several fleets share one Sailwave HTML (e.g. tue_pup contains Puppeteer HPH
# and Puppeteer Scr), so we disambiguate by anchor. Sail Scoring publishes one
# fleet per HTML.
PAIRINGS: list[tuple[str, str, str, str]] = [
    ("Tue Puppeteer HPH",        "/reshyc/2026/club/series1_tue_pup.htm",      "puppeteer_hph",  "/reshyc/sc-test/series1_tue_pup_hph.htm"),
    ("Tue Puppeteer Scratch",    "/reshyc/2026/club/series1_tue_pup.htm",      "puppeteer_scr",  "/reshyc/sc-test/series1_tue_pup_scr.htm"),
    ("Tue Squib HPH",            "/reshyc/2026/club/series1_tue_squib.htm",    "squib_hph",      "/reshyc/sc-test/series1_tue_squib_hph.htm"),
    ("Tue Squib Scratch",        "/reshyc/2026/club/series1_tue_squib.htm",    "squib_scr",      "/reshyc/sc-test/series1_tue_squib_scr.htm"),
    ("Tue/Sat Howth 17 HPH",     "/reshyc/2026/club/series1_tuesat_h17.htm",   "howth_17_hph",   "/reshyc/sc-test/series1_tuesat_h17_hph.htm"),
    ("Tue/Sat Howth 17 Scratch", "/reshyc/2026/club/series1_tuesat_h17.htm",   "howth_17_scr",   "/reshyc/sc-test/series1_tuesat_h17_scr.htm"),
    ("Wed Division A HPH",       "/reshyc/2026/club/series1_classa.htm",       "division_a_hph", "/reshyc/sc-test/series1_seriesa_hph.htm"),
    ("Wed Division A IRC",       "/reshyc/2026/club/series1_classa.htm",       "division_a_irc", "/reshyc/sc-test/series1_seriesa_irc.htm"),
    ("Wed Division B HPH",       "/reshyc/2026/club/series1_classb.htm",       "division_b_hph", "/reshyc/sc-test/series1_seriesb_hph.htm"),
    ("Wed Division B IRC",       "/reshyc/2026/club/series1_classb.htm",       "division_b_irc", "/reshyc/sc-test/series1_seriesb_irc.htm"),
    ("Wed Division C HPH",       "/reshyc/2026/club/series1_classc.htm",       "division_c_hph", "/reshyc/sc-test/series1_seriesc_hph.htm"),
    ("Wed Division C IRC",       "/reshyc/2026/club/series1_classc.htm",       "division_c_irc", "/reshyc/sc-test/series1_seriesc_irc.htm"),
    ("Sat Puppeteer HPH",        "/reshyc/2026/club/series1_satpups.htm",      "puppeteer_hph",  "/reshyc/sc-test/series1_sat_pup_hph.htm"),
    ("Sat Puppeteer Scratch",    "/reshyc/2026/club/series1_satpups.htm",      "puppeteer_scr",  "/reshyc/sc-test/series1_sat_pup_scr.htm"),
    ("Sat Squib HPH",            "/reshyc/2026/club/series1_satsquibs.htm",    "squib_hph",      "/reshyc/sc-test/series1_sat_squib_hph.htm"),
    ("Sat Squib Scratch",        "/reshyc/2026/club/series1_satsquibs.htm",    "squib_scr",      "/reshyc/sc-test/series1_sat_squib_scr.htm"),
    ("Sat Cruisers Div B HPH",   "/reshyc/2026/club/series1_satcruisers.htm",  "division_b_hph", "/reshyc/sc-test/series1_sat_divb_hph.htm"),
    ("Sat Cruisers Div B IRC",   "/reshyc/2026/club/series1_satcruisers.htm",  "division_b_irc", "/reshyc/sc-test/series1_sat_divb_irc.htm"),
    ("Sat Cruisers Div C HPH",   "/reshyc/2026/club/series1_satcruisers.htm",  "division_c_hph", "/reshyc/sc-test/series1_sat_divc_hph.htm"),
    ("Sat Cruisers Div C IRC",   "/reshyc/2026/club/series1_satcruisers.htm",  "division_c_irc", "/reshyc/sc-test/series1_sat_divc_irc.htm"),
    ("Dinghy PY",                "/reshyc/2026/club/series1_dinghies_py.htm",  "py",             "/reshyc/sc-test/series1_dinghies_py.htm"),
    ("Dinghy Optimist",          "/reshyc/2026/club/series1_dinghies_opt.htm", "optimist",       "/reshyc/sc-test/series1_dinghies_opt.htm"),
]

# NHC TCFs are rendered to 3dp. Anything smaller is noise from rounding /
# display formatting; only flag deltas above this threshold.
RATING_TOLERANCE = 0.005

@dataclass
class Competitor:
    rank: int
    sail: str
    boat: str
    helm: str
    seed_rating: Optional[float]
    # rating value rendered in each race summary cell, indexed by race
    # position 0 = R1. None when the cell rendered no inline rating (Sailwave's
    # summary never does; Sail Scoring renders one for R2+).
    race_summary_ratings: list[Optional[float]]
    race_text: list[str]
    net_points: float
    total_points: float


@dataclass
class FleetResult:
    label: str
    source_url: str
    race_count: int
    competitors: list[Competitor]
    # rating used FOR each race (= post-prior-race rating), keyed (sail -> [rating]).
    # Pulled from per-race detail tables; covers both Sailwave (NHC1 column) and
    # Sail Scoring (TCF column).
    race_used_rating: dict[str, list[Optional[float]]]
    # post-each-race rating (SC's "New TCF" column). Empty dict for Sailwave —
    # the 2026 template doesn't render an equivalent.
    race_new_rating: dict[str, list[Optional[float]]]


# ---------- fetching ----------

def fetch(url: str) -> str:
    # old.hyc.ie's WAF 403s requests with the default urllib UA; mimic curl.
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compare-results.py; +hyc-sc-test)",
            "Cache-Control": "no-cache, no-store",
        },
    )
    with urlopen(req, timeout=30) as resp:
        body = resp.read()
    # Sailwave declares ISO-8859-1; Sail Scoring declares utf-8. Try utf-8
    # first since latin-1 always succeeds and would silently mojibake.
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("latin-1")


# ---------- HTML parsing primitives ----------

_TD_RE = re.compile(r"<td([^>]*)>(.*?)</td>", re.DOTALL)
_COL_RE = re.compile(r'<col\s+class="([^"]*)"')
_RATING_SPAN_RE = re.compile(r'<span class="rating">([0-9.]+)</span>')
_TAG_RE = re.compile(r"<[^>]+>")
_CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')
_SUMMARY_HEADING_RE = re.compile(
    r'<h3 class="summarytitle"\s+id="summary([^"]+)"[^>]*>',
)


def _strip(s: str) -> str:
    return html.unescape(_TAG_RE.sub("", s)).replace("\xa0", " ").strip()


def _td_cells(row_html: str) -> list[tuple[str, set[str], Optional[float]]]:
    cells: list[tuple[str, set[str], Optional[float]]] = []
    for attrs, content in _TD_RE.findall(row_html):
        cm = _CLASS_ATTR_RE.search(attrs)
        classes = set(cm.group(1).split()) if cm else set()
        rating: Optional[float] = None
        rm = _RATING_SPAN_RE.search(content)
        if rm:
            rating = float(rm.group(1))
            content = _RATING_SPAN_RE.sub("", content)
        cells.append((_strip(content), classes, rating))
    return cells


def _col_classes(table_html: str) -> list[str]:
    # Each <col class="X[ Y]"> may carry multiple classes; pick the first
    # token, which is the structural role (rank/sailno/race/...).
    return [m.group(1).split()[0] for m in _COL_RE.finditer(table_html)]


def _parse_summary_table(table_html: str) -> list[Competitor]:
    cols = _col_classes(table_html)
    if not cols:
        return []
    race_idx = [i for i, c in enumerate(cols) if c == "race"]
    # First occurrence per role suffices — these columns are unique within a
    # summary table.
    idx_by_role: dict[str, int] = {}
    for i, c in enumerate(cols):
        idx_by_role.setdefault(c, i)
    rows_html = re.findall(
        r'<tr[^>]*\bsummaryrow\b[^>]*>(.*?)</tr>', table_html, re.DOTALL,
    )
    competitors: list[Competitor] = []
    for r in rows_html:
        cells = _td_cells(r)
        if len(cells) != len(cols):
            continue  # unexpected layout; skip rather than misalign
        def cell(role: str):
            i = idx_by_role.get(role)
            return cells[i] if i is not None else (None, set(), None)
        rank_text = cell("rank")[0] or ""
        sail = cell("sailno")[0] or ""
        boat = (cell("boatname")[0] if "boatname" in idx_by_role else cell("boat")[0]) or ""
        helm = cell("helmname")[0] or ""
        seed: Optional[float] = None
        for role in ("seedrating", "rating"):
            if role in idx_by_role:
                txt = cell(role)[0] or ""
                try:
                    seed = float(txt)
                except ValueError:
                    seed = None
                break
        # Sail Scoring renders 'nett' only when discards apply; Sailwave always
        # renders both. Prefer nett.
        net_text = (cell("nett")[0] if "nett" in idx_by_role else cell("total")[0]) or ""
        total_text = cell("total")[0] or ""
        try:
            net_points = float(net_text)
        except ValueError:
            net_points = float("nan")
        try:
            total_points = float(total_text)
        except ValueError:
            total_points = float("nan")
        race_summary_ratings: list[Optional[float]] = []
        race_text_list: list[str] = []
        for ri in race_idx:
            text, _, rating = cells[ri]
            race_summary_ratings.append(rating)
            race_text_list.append(text or "")
        rank_int = 0
        m = re.match(r"(\d+)", rank_text)
        if m:
            rank_int = int(m.group(1))
        competitors.append(Competitor(
            rank=rank_int,
            sail=sail,
            boat=boat,
            helm=helm,
            seed_rating=seed,
            race_summary_ratings=race_summary_ratings,
            race_text=race_text_list,
            net_points=net_points,
            total_points=total_points,
        ))
    return competitors


def _parse_race_table(table_html: str) -> dict[str, tuple[Optional[float], Optional[float]]]:
    """Return {sail -> (rating_used_for_race, new_rating_after_race)}.

    rating_used_for_race comes from the column class 'rating' (Sailwave) or
    'tcf' (Sail Scoring). new_rating_after_race comes from 'newtcf' (Sail
    Scoring only); Sailwave's per-race tables don't render it.
    """
    cols = _col_classes(table_html)
    if not cols:
        return {}
    idx_by_role: dict[str, int] = {}
    for i, c in enumerate(cols):
        idx_by_role.setdefault(c, i)
    sail_idx = idx_by_role.get("sailno")
    used_idx = idx_by_role.get("tcf", idx_by_role.get("rating"))
    new_idx = idx_by_role.get("newtcf")
    if sail_idx is None:
        return {}
    rows_html = re.findall(
        r'<tr[^>]*\bracerow\b[^>]*>(.*?)</tr>', table_html, re.DOTALL,
    )
    out: dict[str, tuple[Optional[float], Optional[float]]] = {}
    for r in rows_html:
        cells = _td_cells(r)
        if len(cells) != len(cols):
            continue
        sail = cells[sail_idx][0] or ""
        used: Optional[float] = None
        new: Optional[float] = None
        if used_idx is not None:
            try:
                used = float(cells[used_idx][0])
            except (ValueError, TypeError):
                used = None
        if new_idx is not None:
            try:
                new = float(cells[new_idx][0])
            except (ValueError, TypeError):
                new = None
        if sail:
            out[sail.strip()] = (used, new)
    return out


# ---------- per-source parsers ----------

def parse_sailwave(html_text: str, fleet_anchor: str, label: str, url: str) -> Optional[FleetResult]:
    headings = list(_SUMMARY_HEADING_RE.finditer(html_text))
    target = next((m for m in headings if m.group(1) == fleet_anchor), None)
    if not target:
        return None
    end = len(html_text)
    for m in headings:
        if m.start() > target.start():
            end = m.start()
            break
    section = html_text[target.end():end]
    tbl = re.search(r'<table class="summarytable"[^>]*>.*?</table>', section, re.DOTALL)
    if not tbl:
        return None
    competitors = _parse_summary_table(tbl.group(0))

    # Per-race tables for this fleet have id matching r<N><fleet_anchor>.
    # Collect them in race-number order from the whole document (race tables
    # all share the document and use fleet-scoped anchors).
    race_pat = re.compile(
        rf'<h3 class="racetitle"[^>]*\bid="r(\d+){re.escape(fleet_anchor)}"[^>]*>.*?'
        rf'(<table class="racetable"[^>]*>.*?</table>)',
        re.DOTALL,
    )
    races: list[tuple[int, str]] = [(int(num), tbl_html) for num, tbl_html in race_pat.findall(html_text)]
    races.sort(key=lambda x: x[0])
    used_by_sail: dict[str, list[Optional[float]]] = {c.sail: [] for c in competitors}
    new_by_sail: dict[str, list[Optional[float]]] = {c.sail: [] for c in competitors}
    for _, race_table in races:
        per_sail = _parse_race_table(race_table)
        for sail in used_by_sail:
            used, new = per_sail.get(sail, (None, None))
            used_by_sail[sail].append(used)
            new_by_sail[sail].append(new)
    return FleetResult(
        label=label,
        source_url=url + "#summary" + fleet_anchor,
        race_count=len(races),
        competitors=competitors,
        race_used_rating=used_by_sail,
        race_new_rating=new_by_sail,
    )


def parse_sailscoring(html_text: str, label: str, url: str) -> Optional[FleetResult]:
    tbl = re.search(r'<table class="summarytable"[^>]*>.*?</table>', html_text, re.DOTALL)
    if not tbl:
        return None
    competitors = _parse_summary_table(tbl.group(0))
    # Race detail tables: one fleet per file so anchors are r1, r2, ...
    race_pat = re.compile(
        r'<h3 class="racetitle"[^>]*\bid="r(\d+)"[^>]*>.*?'
        r'(<table class="racetable"[^>]*>.*?</table>)',
        re.DOTALL,
    )
    races: list[tuple[int, str]] = [(int(num), tbl_html) for num, tbl_html in race_pat.findall(html_text)]
    races.sort(key=lambda x: x[0])
    used_by_sail: dict[str, list[Optional[float]]] = {c.sail: [] for c in competitors}
    new_by_sail: dict[str, list[Optional[float]]] = {c.sail: [] for c in competitors}
    for _, race_table in races:
        per_sail = _parse_race_table(race_table)
        for sail in used_by_sail:
            used, new = per_sail.get(sail, (None, None))
            used_by_sail[sail].append(used)
            new_by_sail[sail].append(new)
    return FleetResult(
        label=label,
        source_url=url,
        race_count=len(races),
        competitors=competitors,
        race_used_rating=used_by_sail,
        race_new_rating=new_by_sail,
    )


# ---------- diff reporting ----------

def _label_for(c: Competitor) -> str:
    parts = [c.sail.strip()]
    if c.boat.strip():
        parts.append(c.boat.strip())
    return " ".join(parts)


def _rating_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return b - a


def compare_pair(
    label: str, sw: FleetResult, sc: FleetResult,
    verbose: bool, show_final_ratings: bool,
) -> int:
    """Print diffs, return 1 if any meaningful diff found else 0.

    Meaningful = roster, race count, net points, or per-race NHC TCF used.
    Post-last-race ratings are informational only (Sailwave doesn't expose
    them) and never trigger DIFF status.
    """
    diffs: list[str] = []
    info: list[str] = []

    sw_by_sail = {c.sail.strip(): c for c in sw.competitors}
    sc_by_sail = {c.sail.strip(): c for c in sc.competitors}

    sw_only = sorted(set(sw_by_sail) - set(sc_by_sail))
    sc_only = sorted(set(sc_by_sail) - set(sw_by_sail))
    common = sorted(set(sw_by_sail) & set(sc_by_sail))

    if sw_only:
        diffs.append(
            "  ROSTER: in Sailwave but not Sail Scoring: "
            + ", ".join(f"{s} ({sw_by_sail[s].boat})" for s in sw_only)
        )
    if sc_only:
        diffs.append(
            "  ROSTER: in Sail Scoring but not Sailwave: "
            + ", ".join(f"{s} ({sc_by_sail[s].boat})" for s in sc_only)
        )

    if sw.race_count != sc.race_count:
        diffs.append(
            f"  RACES: Sailwave shows {sw.race_count}, Sail Scoring shows {sc.race_count}"
        )

    for sail in common:
        a = sw_by_sail[sail]
        b = sc_by_sail[sail]
        np_a = a.net_points
        np_b = b.net_points
        a_nan = np_a != np_a
        b_nan = np_b != np_b
        if a_nan or b_nan:
            if a_nan != b_nan or np_a != np_b:
                diffs.append(
                    f"  POINTS: {_label_for(a):30s} SW net={a.net_points} ({a.race_text}) "
                    f"SC net={b.net_points} ({b.race_text})"
                )
            continue
        if np_a != np_b:
            diff = np_b - np_a
            diffs.append(
                f"  POINTS: {_label_for(a):30s} SW net={np_a:g} rank={a.rank}  "
                f"SC net={np_b:g} rank={b.rank}  Δ={diff:+g}"
            )
        elif verbose:
            info.append(
                f"  ok-pts: {_label_for(a):30s} net={np_a:g} rank={a.rank}"
            )

    # NHC TCF used for each race = post-prior-race rating going INTO race N.
    # Compared only when both sides render a value for that race.
    nhc = any(c.seed_rating is not None for c in sc.competitors) or any(
        c.seed_rating is not None for c in sw.competitors
    )
    if nhc:
        race_max = min(sw.race_count, sc.race_count)
        for sail in common:
            sw_used = sw.race_used_rating.get(sail, [])
            sc_used = sc.race_used_rating.get(sail, [])
            label_str = _label_for(sw_by_sail[sail])
            for ri in range(race_max):
                a = sw_used[ri] if ri < len(sw_used) else None
                b = sc_used[ri] if ri < len(sc_used) else None
                d = _rating_diff(a, b)
                if d is None:
                    continue
                if abs(d) > RATING_TOLERANCE:
                    diffs.append(
                        f"  TCF R{ri+1}: {label_str:30s} SW={a:.3f}  SC={b:.3f}  Δ={d:+.3f}"
                    )
                elif verbose:
                    info.append(
                        f"  ok-tcf R{ri+1}: {label_str:30s} SW={a:.3f} SC={b:.3f}"
                    )

        # Sailwave's 2026 template doesn't render post-last-race rating, so we
        # can't diff it. Just dump SC's final values when explicitly asked.
        if show_final_ratings and sc.race_count > 0:
            ri = sc.race_count - 1
            final_lines: list[str] = []
            for c in sc.competitors:
                ratings = sc.race_new_rating.get(c.sail.strip(), [])
                if ri < len(ratings) and ratings[ri] is not None:
                    final_lines.append(
                        f"    {_label_for(c):30s} New TCF after R{ri+1} = {ratings[ri]:.3f}"
                    )
            if final_lines:
                info.append(
                    f"  NOTE: Sail Scoring post-R{ri+1} ratings (Sailwave's 2026 template "
                    "doesn't expose an equivalent):"
                )
                info.extend(final_lines)

    status = "DIFF" if diffs else "OK"
    print(f"{status:4s}  {label}")
    if diffs or verbose:
        print(f"    SW: {sw.source_url}")
        print(f"    SC: {sc.source_url}")
    for d in diffs:
        print(d)
    for line in info:
        print(line)
    return 1 if diffs else 0


# ---------- orchestration ----------

def run(verbose: bool, only: Optional[list[str]], show_final_ratings: bool) -> int:
    any_diffs = 0
    for (label, sw_path, sw_anchor, sc_path) in PAIRINGS:
        if only and not any(s.lower() in label.lower() for s in only):
            continue
        sw_url = BASE + sw_path
        sc_url = BASE + sc_path
        try:
            sw_html = fetch(sw_url)
        except (HTTPError, URLError) as e:
            print(f"FAIL  {label}: Sailwave fetch failed ({e})")
            any_diffs = 1
            continue
        try:
            sc_html = fetch(sc_url)
        except (HTTPError, URLError) as e:
            print(f"FAIL  {label}: Sail Scoring fetch failed ({e})")
            any_diffs = 1
            continue
        sw = parse_sailwave(sw_html, sw_anchor, label, sw_url)
        if not sw:
            print(f"FAIL  {label}: Sailwave fleet anchor 'summary{sw_anchor}' not found at {sw_url}")
            any_diffs = 1
            continue
        sc = parse_sailscoring(sc_html, label, sc_url)
        if not sc:
            print(f"FAIL  {label}: Sail Scoring summary table not found at {sc_url}")
            any_diffs = 1
            continue
        any_diffs |= compare_pair(label, sw, sc, verbose, show_final_ratings)
    return any_diffs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", "-v", action="store_true", help="show matched rows too, not just diffs")
    ap.add_argument(
        "--final-ratings", action="store_true",
        help="also print Sail Scoring's post-last-race NHC TCFs (informational; Sailwave doesn't render them)",
    )
    ap.add_argument(
        "--only", action="append", default=[],
        help="restrict to pairings whose label contains this substring (case-insensitive); repeatable",
    )
    args = ap.parse_args()
    sys.exit(run(args.verbose, args.only or None, args.final_ratings))


if __name__ == "__main__":
    main()
