#!/usr/bin/env python3
"""
Reverse-engineering Sailwave's NHC1 NewRating calculation.

Compares predictions from many candidate NHC/ECHO formulas against Sailwave's
output for five single-race fleets at Howth YC One Designs S1, 2026-05-05/06:

  Puppeteer HPH (n=14, start 19:15:00, 5 May)
  Squib HPH      (n=4 + 1 RET, start 19:20:00, 5 May)
  Division A HPH (n=5 + 1 DNC, start 19:15:00, 6 May)
  Division B HPH (n=3 + 8 DNC, start 19:20:00, 6 May)
  Division C HPH (n=8 + 2 DNF + 1 DNC, start 19:25:00, 6 May)

Source data — the One Designs S1 Sailwave export and the published HPH result
pages it was checked against — is transcribed inline below (owner names
anonymised); the original files are no longer kept in the repo.

All races share alpha=0.15. Non-finishers (DNC/RET/DNF) keep their TCF unchanged
and are excluded from the per-race fair-handicap inputs (we only feed
finishers in here).
"""

from math import exp, log
from statistics import mean, median, pstdev


# Each race: (label, start_time, competitors)
# Competitors: (sail#, boat, owner, initial_TCF, finish_time,
#               exp_ET_s, exp_CT_s, exp_NewRating)
RACE_PUPPETEER = (
    "Puppeteer HPH (n=14)",
    "19:15:00",
    [
        ("2021", "Harlequin",      "Deirdre Barlow",                       1.350, "19:43:46", 1726, 2330, 1.385),
        ("385",  "Ibis",           "Grainne Barlow",                         1.350, "19:43:56", 1736, 2344, 1.383),
        ("310",  "Nefertari",      "Hannah Barlow",                       1.350, "19:46:55", 1915, 2585, 1.382),
        ("15",   "Trick or Treat", "Aoife Barlow",           1.350, "19:48:16", 1996, 2695, 1.365),
        ("187",  "Flycatcher",     "Tara Barlow",                     1.250, "19:51:20", 2180, 2725, 1.259),
        ("5526", "Blue Velvet",    "Micheal Barlow",                     1.275, "19:51:16", 2176, 2774, 1.277),
        ("22",   "Weyhey",         "Paula Barlow",                        1.350, "19:49:54", 2094, 2827, 1.345),
        ("20",   "No Strings",     "Aoife Considine",                       1.320, "19:51:00", 2160, 2851, 1.312),
        ("254",  "Gold Dust",      "Eoin Barlow",                      1.345, "19:52:22", 2242, 3015, 1.326),
        ("101",  "Eclipse",        "Oisin Barlow",                      1.200, "19:57:54", 2574, 3089, 1.179),
        ("245",  "Cara",           "Bridget Barlow", 1.150, "20:00:22", 2722, 3130, 1.128),
        ("219",  "Geppetto",       "Adam Barlow",                  1.250, "19:57:10", 2530, 3163, 1.233),
        ("79",   "Mojo",           "Laura Barlow",                 1.175, "19:59:58", 2698, 3170, 1.159),
        ("6413", "Yelllow Peril",  "Vincent Barlow",       1.350, "19:54:20", 2360, 3186, 1.331),
    ],
)

RACE_SQUIB = (
    "Squib HPH (n=4)",
    "19:20:00",
    # Aurora RET and 5 DNC boats are excluded — they keep their TCF unchanged.
    [
        ("881", "Kaizen",    "Emmet Barlow",                  1.057, "19:54:58", 2098, 2218, 1.071),
        ("37",  "Kerfuffle", "Iarla Barlow",                     1.068, "19:56:08", 2168, 2315, 1.070),
        ("148", "Halloween", "Niamh Barlow",  0.911, "20:03:22", 2602, 2370, 0.909),
        ("872", "Treborth",  "Roisin Barlow",           0.990, "20:13:18", 3198, 3166, 0.976),
    ],
)

RACE_DIV_A = (
    "Division A HPH (n=5)",
    "19:15:00",
    [
        ("9202",  "Insider Again",  "Quentin Barlow",   0.920, "20:39:39", 5079, 4673, 0.924),
        ("1840",  "The Big Picture", "Una Barlow",              1.073, "20:29:08", 4448, 4773, 1.075),
        ("6697",  "Jeneral Lee",    "Brendan Barlow",          0.972, "20:37:45", 4965, 4826, 0.971),
        ("9970",  "Lambay Rules",   "Isla Barlow",                   0.978, "20:37:57", 4977, 4868, 0.976),
        ("1543",  "Indian",         "Hugh Barlow",  1.012, "20:36:48", 4908, 4967, 1.009),
    ],
)

RACE_DIV_B = (
    "Division B HPH (n=3)",
    "19:20:00",
    [
        ("7115",  "Gecko",     "Sean Barlow",     0.905, "20:27:13", 4033, 3650, 0.911),
        ("2507",  "Impetuous", "Wendy Barlow",   0.942, "20:26:08", 3968, 3738, 0.943),
        ("7495",  "Maximus",   "Conor Barlow",        0.940, "20:40:17", 4817, 4528, 0.933),
    ],
)

RACE_DIV_C = (
    "Division C HPH (n=8)",
    "19:25:00",
    [
        ("1343",  "Arcturus",        "Dervla Barlow",          0.895, "20:34:48", 4188, 3748, 0.921),
        ("3335C", "Bite the Bullet", "Cian Barlow",                1.046, "20:25:58", 3658, 3826, 1.069),
        ("1793",  "Mistoffelees",    "Jenny Barlow",                 0.832, "20:44:31", 4771, 3969, 0.841),
        ("8151",  "Jokers Wild",     "Kevin Barlow",    0.915, "20:40:57", 4557, 4170, 0.912),
        ("2070",  "Out & About",     "Brendan Considine",                    0.890, "20:45:02", 4802, 4274, 0.884),
        ("1430",  "Mary Ellen",      "Yvonne Barlow",         0.912, "20:46:18", 4878, 4449, 0.901),
        ("633",   "Pepsi",           "Garret Barlow", 0.903, "20:51:10", 5170, 4669, 0.886),
        ("1411t", "Toughnut",        "Fiona Barlow",                  1.015, "20:56:56", 5516, 5599, 0.995),
    ],
)

RACES = [RACE_PUPPETEER, RACE_SQUIB, RACE_DIV_A, RACE_DIV_B, RACE_DIV_C]
ALPHA = 0.15


def hms_to_s(t: str) -> int:
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def round_half_up(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


# -------------------------------------------------------------------
# Step 1: verify ET and CT against Sailwave's output
# -------------------------------------------------------------------
def verify_et_ct(race):
    label, start_time, comps = race
    print("=" * 80)
    print(f"Step 1 ({label}): verify Elapsed and Corrected times vs Sailwave")
    print(f"  Start time: {start_time}")
    print("=" * 80)
    print(f"{'Sail':>5} {'Boat':<16} {'TCF':>6} {'ET_calc':>8} {'ET_SW':>6} "
          f"{'CT_calc':>8} {'CT_SW':>6}  OK?")
    start = hms_to_s(start_time)
    all_ok = True
    for sail, boat, _, tcf, finish, exp_et, exp_ct, _ in comps:
        et = hms_to_s(finish) - start
        ct = round_half_up(et * tcf)
        ok = (et == exp_et) and (abs(ct - exp_ct) <= 1)
        all_ok = all_ok and ok
        print(f"{sail:>5} {boat:<16} {tcf:>6.3f} {et:>8d} {exp_et:>6d} "
              f"{ct:>8d} {exp_ct:>6d}  {'OK' if ok else 'FAIL'}")
    print(f"\n  All ET/CT match Sailwave: {'YES' if all_ok else 'NO'}\n")


def make_rows(race):
    _, _, comps = race
    return [
        {"sail": s, "boat": b, "tcf": t, "et": e, "ct": c, "nr_sw": n}
        for s, b, _, t, _, e, c, n in comps
    ]


def implied_q(tcf, nr, alpha=ALPHA):
    return (nr - (1 - alpha) * tcf) / alpha


def show_implied_q(race):
    label, _, _ = race
    rows = make_rows(race)
    print("=" * 80)
    print(f"Implied Q ({label}) from Sailwave NewRating, alpha=0.15")
    print("Q_imp = (NewRating - 0.85*TCF) / 0.15")
    print("=" * 80)
    sum_tcf = sum(r["tcf"] for r in rows)
    sum_nr  = sum(r["nr_sw"] for r in rows)
    print(f"  Sigma(TCF) = {sum_tcf:.3f}    Sigma(NR_SW) = {sum_nr:.3f}    "
          f"drift = {sum_nr - sum_tcf:+.4f}")
    print(f"  {'Sail':>5} {'Boat':<16} {'TCF':>6} {'ET':>5} {'CT':>5} "
          f"{'NR_SW':>6} {'Q_imp':>7} {'Q*ET':>6} {'Q/TCF':>7}")
    for r in rows:
        q = implied_q(r["tcf"], r["nr_sw"])
        print(f"  {r['sail']:>5} {r['boat']:<16} {r['tcf']:>6.3f} "
              f"{r['et']:>5d} {r['ct']:>5d} {r['nr_sw']:>6.3f} "
              f"{q:>7.4f} {q * r['et']:>6.0f} {q / r['tcf']:>7.4f}")
    print()


def round_q_to_nr(q_by_sail, rows, alpha=ALPHA):
    return {r["sail"]: round(r["tcf"] + alpha * (q_by_sail[r["sail"]] - r["tcf"]), 3)
            for r in rows}


def evaluate_one_race(race, nr_pred_by_sail, verbose=False):
    label, _, _ = race
    rows = make_rows(race)
    rmse_sum = 0.0
    diffs = []
    if verbose:
        print(f"\n  -- {label} --")
        print(f"  {'Sail':>5} {'Boat':<16} {'TCF':>6} {'NR_pred':>8} "
              f"{'NR_SW':>6} {'Delta':>8}")
    for r in rows:
        nrp = nr_pred_by_sail[r["sail"]]
        diff = nrp - r["nr_sw"]
        rmse_sum += diff * diff
        diffs.append(diff)
        if verbose:
            print(f"  {r['sail']:>5} {r['boat']:<16} {r['tcf']:>6.3f} "
                  f"{nrp:>8.3f} {r['nr_sw']:>6.3f} {diff:>+8.4f}")
    rmse = (rmse_sum / len(rows)) ** 0.5
    max_abs = max(abs(d) for d in diffs)
    if verbose:
        print(f"  Max|Delta|: {max_abs:.4f}    RMSE: {rmse:.4f}")
    return max_abs, rmse, len(rows), rmse_sum


# -------------------------------------------------------------------
# Q-formula candidates (return dict sail -> Q)
# -------------------------------------------------------------------
def q_ct_mean(rows):
    ct_avg = mean(r["ct"] for r in rows)
    return {r["sail"]: r["tcf"] * ct_avg / r["ct"] for r in rows}


def q_is_pi(rows):
    sum_tcf = sum(r["tcf"] for r in rows)
    sum_recip = sum(1 / r["et"] for r in rows)
    return {r["sail"]: sum_tcf / (r["et"] * sum_recip) for r in rows}


def q_ct_median(rows):
    ct_med = median(r["ct"] for r in rows)
    return {r["sail"]: r["tcf"] * ct_med / r["ct"] for r in rows}


def q_et_avg_scaled(rows):
    et_avg = mean(r["et"] for r in rows)
    return {r["sail"]: r["tcf"] * et_avg / r["et"] for r in rows}


def q_et_median(rows):
    et_med = median(r["et"] for r in rows)
    return {r["sail"]: r["tcf"] * et_med / r["et"] for r in rows}


def q_ct_winner(rows):
    ct_w = min(r["ct"] for r in rows)
    return {r["sail"]: r["tcf"] * ct_w / r["ct"] for r in rows}


def q_ct_geomean(rows):
    cts = [r["ct"] for r in rows]
    g = exp(sum(log(c) for c in cts) / len(cts))
    return {r["sail"]: r["tcf"] * g / r["ct"] for r in rows}


def q_swecho(rows):
    ct_w = min(r["ct"] for r in rows)
    bcrs = {r["sail"]: ct_w / r["ct"] for r in rows}
    echo_idx = mean(r["tcf"] for r in rows) / mean(bcrs.values())
    return {s: echo_idx * b for s, b in bcrs.items()}


def q_winsor_ctmean(rows, k=1.0):
    cts = [r["ct"] for r in rows]
    mu = mean(cts); sigma = pstdev(cts)
    lo, hi = mu - k * sigma, mu + k * sigma
    return {r["sail"]: r["tcf"] * mu / max(lo, min(hi, r["ct"])) for r in rows}


def q_inner_only_mean(rows, k=1.0):
    cts = [r["ct"] for r in rows]
    mu = mean(cts); sigma = pstdev(cts)
    lo, hi = mu - k * sigma, mu + k * sigma
    inner = [c for c in cts if lo <= c <= hi]
    mu_in = mean(inner) if inner else mu
    return {r["sail"]: r["tcf"] * mu_in / r["ct"] for r in rows}


def q_extreme_use_bound(rows, k=1.0):
    cts = [r["ct"] for r in rows]
    mu = mean(cts); sigma = pstdev(cts)
    lo, hi = mu - k * sigma, mu + k * sigma
    out = {}
    for r in rows:
        if r["ct"] < lo: ct_eff = lo
        elif r["ct"] > hi: ct_eff = hi
        else: ct_eff = r["ct"]
        out[r["sail"]] = r["tcf"] * mu / ct_eff
    return out


def q_winsor_is_pi(rows, k=1.0):
    ets = [r["et"] for r in rows]
    mu = mean(ets); sigma = pstdev(ets)
    lo, hi = mu - k * sigma, mu + k * sigma
    eff = {r["sail"]: max(lo, min(hi, r["et"])) for r in rows}
    sum_tcf = sum(r["tcf"] for r in rows)
    sum_recip = sum(1 / e for e in eff.values())
    return {r["sail"]: sum_tcf / (eff[r["sail"]] * sum_recip) for r in rows}


def q_blend_ctmean_ispi(rows, w=0.5):
    a = q_ct_mean(rows); b = q_is_pi(rows)
    return {s: w * a[s] + (1 - w) * b[s] for s in a}


def q_halsail_ext(rows, k=1.0):
    cts = [r["ct"] for r in rows]
    mu = mean(cts); sigma = pstdev(cts)
    lo, hi = mu - k * sigma, mu + k * sigma
    sum_tcf = sum(r["tcf"] for r in rows)
    sum_recip = sum(1 / r["et"] for r in rows)
    out = {}
    for r in rows:
        if r["ct"] < lo: tt = lo / r["tcf"]
        elif r["ct"] > hi: tt = hi / r["tcf"]
        else: tt = r["et"]
        out[r["sail"]] = sum_tcf / (tt * sum_recip)
    return out


def q_halsail_slow_only(rows, k=1.0):
    cts = [r["ct"] for r in rows]
    mu = mean(cts); sigma = pstdev(cts)
    hi = mu + k * sigma
    sum_tcf = sum(r["tcf"] for r in rows)
    sum_recip = sum(1 / r["et"] for r in rows)
    out = {}
    for r in rows:
        tt = hi / r["tcf"] if r["ct"] > hi else r["et"]
        out[r["sail"]] = sum_tcf / (tt * sum_recip)
    return out


def q_halsail_ext_recompute_sum(rows, k=1.0):
    cts = [r["ct"] for r in rows]
    mu = mean(cts); sigma = pstdev(cts)
    lo, hi = mu - k * sigma, mu + k * sigma
    sum_tcf = sum(r["tcf"] for r in rows)
    eff = {}
    for r in rows:
        if r["ct"] < lo: eff[r["sail"]] = lo / r["tcf"]
        elif r["ct"] > hi: eff[r["sail"]] = hi / r["tcf"]
        else: eff[r["sail"]] = r["et"]
    sum_recip = sum(1 / e for e in eff.values())
    return {r["sail"]: sum_tcf / (eff[r["sail"]] * sum_recip) for r in rows}


def q_ct_mean_then_renormalise(rows):
    base = q_ct_mean(rows)
    sum_tcf = sum(r["tcf"] for r in rows)
    factor = sum_tcf / sum(base.values())
    return {s: q * factor for s, q in base.items()}


def q_ispi_then_winsor_q(rows, k=1.0):
    base = q_is_pi(rows)
    qs = list(base.values())
    mu = mean(qs); sd = pstdev(qs)
    lo, hi = mu - k * sd, mu + k * sd
    capped = {s: max(lo, min(hi, q)) for s, q in base.items()}
    sum_tcf = sum(r["tcf"] for r in rows)
    factor = sum_tcf / sum(capped.values())
    return {s: q * factor for s, q in capped.items()}


# -------------------------------------------------------------------
# NewRating-formula candidates (return dict sail -> NewRating directly)
# -------------------------------------------------------------------
def nr_swnhc2015(rows, alpha_p=0.30, alpha_n=0.15):
    ct_avg = mean(r["ct"] for r in rows)
    out = {}
    for r in rows:
        q = r["tcf"] * ct_avg / r["ct"]
        a = alpha_p if q > r["tcf"] else alpha_n
        out[r["sail"]] = round(r["tcf"] + a * (q - r["tcf"]), 3)
    return out


def nr_capped_adj(rows, cap):
    ct_avg = mean(r["ct"] for r in rows)
    out = {}
    for r in rows:
        q = r["tcf"] * ct_avg / r["ct"]
        adj = max(-cap, min(cap, ALPHA * (q - r["tcf"])))
        out[r["sail"]] = round(r["tcf"] + adj, 3)
    return out


def nr_capped_q_diff(rows, cap):
    ct_avg = mean(r["ct"] for r in rows)
    out = {}
    for r in rows:
        q = r["tcf"] * ct_avg / r["ct"]
        d = max(-cap, min(cap, q - r["tcf"]))
        out[r["sail"]] = round(r["tcf"] + ALPHA * d, 3)
    return out


def nr_swnhc2015_full(rows,
                      alpha_p=0.30, alpha_n=0.15,
                      alpha_px=0.15, alpha_nx=0.075,
                      sd_over=1.5, sd_under=1.0,
                      min_fin=3):
    """The actual SWNHC2015 / Sailwave NHC1 formula, reverse-engineered from
    Jon Eskdale's SWNHC2015.xls (version 2014-01-05-0).

    Reproduces Sailwave's NewRating column to zero error on all 5 test races.
    See docs/design/notes/sailwave-nhc1-reverse-engineering.md sec.10."""
    n = len(rows)
    if n < min_fin:
        return {r["sail"]: round(r["tcf"], 3) for r in rows}

    L  = [r["tcf"] for r in rows]
    ET = [r["et"] for r in rows]

    # 1. Performance index and fleet-wide P50 multiplier
    O   = [100.0 / (et / 60.0) for et in ET]
    P50 = (sum(L) / n) / (sum(O) / n)
    Q   = [O[i] * P50 for i in range(n)]

    # 2. Comparative score and extreme classification
    S    = [Q[i] / L[i] for i in range(n)]
    Smu  = mean(S)
    Ssd  = pstdev(S)
    hi   = Smu + sd_over  * Ssd
    lo   = Smu - sd_under * Ssd
    extreme = [(s > hi) or (s < lo) for s in S]

    # 3. Extreme branch (uses original Q_i)
    T = [alpha_px * Q[i] + (1 - alpha_px) * L[i] if Q[i] > L[i]
         else alpha_nx * Q[i] + (1 - alpha_nx) * L[i] for i in range(n)]

    # 4. Non-extreme branch — recompute P50 from non-extremes
    Ln = [L[i] for i in range(n) if not extreme[i]]
    On = [O[i] for i in range(n) if not extreme[i]]
    W51 = (sum(Ln)/len(Ln)) / (sum(On)/len(On)) if Ln else P50
    X = [O[i] * W51 for i in range(n)]
    Y = [alpha_p * X[i] + (1 - alpha_p) * L[i] if X[i] > L[i]
         else alpha_n * X[i] + (1 - alpha_n) * L[i] for i in range(n)]

    # 5. Combine and 6. realign. The Step 6 numerator is Σ(base TCF) over the
    #    finishers — each boat's series-initial rating. Here it equals sum(L)
    #    because all five datasets are *first* races (input TCF == base); from
    #    race 2 on the two diverge and only the base sum matches Sailwave. See
    #    docs/notes/sailwave-nhc1-reverse-engineering.md §10.6 (issue #147 §3(b)).
    Z = [T[i] if extreme[i] else Y[i] for i in range(n)]
    Z51 = sum(L) / sum(Z)
    return {rows[i]["sail"]: round(Z[i] * Z51, 3) for i in range(n)}


def nr_swnhc2015_extreme(rows, ap=0.30, an=0.15, apx=0.15, anx=0.075,
                          k_pos=1.5, k_neg=1.0):
    ct_avg = mean(r["ct"] for r in rows)
    qs = {r["sail"]: r["tcf"] * ct_avg / r["ct"] for r in rows}
    comps = [qs[r["sail"]] / r["tcf"] for r in rows]
    mu_c = mean(comps); sd_c = pstdev(comps)
    out = {}
    for r in rows:
        q = qs[r["sail"]]; comp = q / r["tcf"]
        if comp > mu_c + k_pos * sd_c:
            adj = apx
        elif comp < mu_c - k_neg * sd_c:
            adj = anx
        elif q > r["tcf"]:
            adj = ap
        else:
            adj = an
        out[r["sail"]] = round(r["tcf"] + adj * (q - r["tcf"]), 3)
    return out


# -------------------------------------------------------------------
# Driver: run a candidate on each race, pool residuals, report
# -------------------------------------------------------------------
def run_q_candidate(name, q_fn, races, results):
    pooled_sq = 0.0; pooled_n = 0; pooled_max = 0.0
    per_race = []
    for race in races:
        rows = make_rows(race)
        q = q_fn(rows)
        nr = round_q_to_nr(q, rows)
        m, r, n, sq = evaluate_one_race(race, nr)
        pooled_sq += sq; pooled_n += n
        pooled_max = max(pooled_max, m)
        per_race.append((race[0], m, r))
    pooled_rmse = (pooled_sq / pooled_n) ** 0.5
    results.append((name, pooled_max, pooled_rmse, per_race))


def run_nr_candidate(name, nr_fn, races, results):
    pooled_sq = 0.0; pooled_n = 0; pooled_max = 0.0
    per_race = []
    for race in races:
        rows = make_rows(race)
        nr = nr_fn(rows)
        m, r, n, sq = evaluate_one_race(race, nr)
        pooled_sq += sq; pooled_n += n
        pooled_max = max(pooled_max, m)
        per_race.append((race[0], m, r))
    pooled_rmse = (pooled_sq / pooled_n) ** 0.5
    results.append((name, pooled_max, pooled_rmse, per_race))


def show_top_candidates_verbose(results, races, top_n=5):
    sorted_res = sorted(results, key=lambda x: x[2])
    print("\n" + "=" * 80)
    print(f"Per-row residuals for top {top_n} candidates")
    print("=" * 80)
    for name, m, r, per_race in sorted_res[:top_n]:
        print(f"\n### {name}    pooled Max|D|={m:.4f}  pooled RMSE={r:.4f}")
        for race_label, mr, rr in per_race:
            print(f"    {race_label}: Max|D|={mr:.4f}  RMSE={rr:.4f}")


def show_per_row_for_best(results, races, q_lookup):
    """Print per-row residuals for the top candidate on every race."""
    name, m, r, per_race = sorted(results, key=lambda x: x[2])[0]
    print("\n" + "=" * 80)
    print(f"Per-row residuals for best candidate: {name}")
    print(f"  Pooled Max|D|={m:.4f}  Pooled RMSE={r:.4f}")
    print("=" * 80)
    fn = q_lookup.get(name)
    if fn is None:
        print(f"(no replay function registered for '{name}')")
        return
    for race in races:
        rows = make_rows(race)
        nr = round_q_to_nr(fn(rows), rows) if fn[0] == "Q" else fn[1](rows)
        print(f"\n--- {race[0]} ---")
        print(f"  {'Sail':>5} {'Boat':<16} {'TCF':>6} {'NR_pred':>8} "
              f"{'NR_SW':>6} {'Delta':>8}")
        for ri in rows:
            nrp = nr[ri["sail"]]
            diff = nrp - ri["nr_sw"]
            print(f"  {ri['sail']:>5} {ri['boat']:<16} {ri['tcf']:>6.3f} "
                  f"{nrp:>8.3f} {ri['nr_sw']:>6.3f} {diff:>+8.4f}")


def main():
    for race in RACES:
        verify_et_ct(race)
        show_implied_q(race)

    results = []

    def Q(name, fn):  run_q_candidate(name, fn, RACES, results)
    def NR(name, fn): run_nr_candidate(name, fn, RACES, results)

    # Group A: classical formulas
    Q("ct-mean (TCF*CT_avg/CT_i)",          q_ct_mean)
    Q("IS-PI / P50 (sumTCF/(ET*sum1/ET))",  q_is_pi)
    Q("CT-median based",                    q_ct_median)
    Q("ET-avg scaled (TCF*ET_avg/ET)",      q_et_avg_scaled)
    Q("ET-median based",                    q_et_median)
    Q("CT-winner reference",                q_ct_winner)
    Q("CT-geomean based",                   q_ct_geomean)
    Q("SWECHO winner-relative",             q_swecho)
    Q("ct-mean then renormalise sum",       q_ct_mean_then_renormalise)

    # Group B: outlier handling on ct-mean / IS-PI
    for k in (0.5, 1.0, 1.5, 2.0):
        Q(f"Winsorized ct-mean (k={k}sigma)",
          lambda rs, k=k: q_winsor_ctmean(rs, k))
    for k in (1.0, 1.5):
        Q(f"ct-mean inner-sigma boats (k={k})",
          lambda rs, k=k: q_inner_only_mean(rs, k))
    for k in (1.0, 1.5):
        Q(f"ct-mean extremes clamped (k={k}sigma)",
          lambda rs, k=k: q_extreme_use_bound(rs, k))
    for k in (1.0, 1.5):
        Q(f"Winsorized IS-PI (k={k}sigma)",
          lambda rs, k=k: q_winsor_is_pi(rs, k))

    # Group C: capping / asymmetric alpha
    NR("SWNHC2015 (a+ = 0.30, a- = 0.15)",
       lambda rs: nr_swnhc2015(rs, 0.30, 0.15))
    NR("Asym (a+ = 0.10, a- = 0.15)",
       lambda rs: nr_swnhc2015(rs, 0.10, 0.15))
    NR("Asym (a+ = 0.20, a- = 0.15)",
       lambda rs: nr_swnhc2015(rs, 0.20, 0.15))
    for cap in (0.020, 0.025, 0.030, 0.035, 0.040):
        NR(f"adjustment capped at +/-{cap:.3f}",
           lambda rs, cap=cap: nr_capped_adj(rs, cap))
    for cap in (0.15, 0.20, 0.25):
        NR(f"(Q-TCF) capped at +/-{cap}",
           lambda rs, cap=cap: nr_capped_q_diff(rs, cap))
    NR("SWNHC2015 full extreme dampening",
       lambda rs: nr_swnhc2015_extreme(rs))
    NR("SWNHC2015 actual (Eskdale spreadsheet, 2014-01-05-0)",
       lambda rs: nr_swnhc2015_full(rs))

    # Group D: blends
    for w in (0.25, 0.5, 0.75):
        pa = int(w * 100); pb = 100 - pa
        Q(f"Blend: {pa}% ct-mean + {pb}% IS-PI",
          lambda rs, w=w: q_blend_ctmean_ispi(rs, w))

    # Group E: HalSail / RYA NHC 2015 extreme rule
    for k in (0.3, 0.5, 0.7, 1.0, 1.25, 1.5):
        Q(f"HalSail Tt for both (k={k}sigma)",
          lambda rs, k=k: q_halsail_ext(rs, k))
        Q(f"HalSail slow-only Tt (k={k}sigma)",
          lambda rs, k=k: q_halsail_slow_only(rs, k))
        Q(f"HalSail Tt + Sigma(1/Tt) (k={k}sigma)",
          lambda rs, k=k: q_halsail_ext_recompute_sum(rs, k))

    # Group F: post-hoc Q renormalisation
    for k in (1.0, 1.5):
        Q(f"IS-PI then winsor Q +/-{k}sd, renorm",
          lambda rs, k=k: q_ispi_then_winsor_q(rs, k))

    print("\n" + "=" * 80)
    print("Pooled summary across all races (best-to-worst by pooled RMSE)")
    print("=" * 80)
    short_labels = ["Pup", "Sqb", "DvA", "DvB", "DvC"]
    header_per_race = "  ".join(f"{lbl} Max|D| {lbl} RMSE" for lbl in short_labels)
    print(f"{'Formula':<42} {'Max|D|':>7} {'RMSE':>7}  {header_per_race}")
    for name, m, r, per_race in sorted(results, key=lambda x: x[2]):
        per_race_str = "  ".join(
            f"{pr[1]:>7.4f}  {pr[2]:>7.4f}" for pr in per_race
        )
        print(f"{name:<42} {m:>7.4f} {r:>7.4f}  {per_race_str}")

    show_top_candidates_verbose(results, RACES, top_n=5)

    # Per-row dump for the leading HalSail slow-only candidate on every race
    print("\n" + "=" * 80)
    print("Per-row residuals: HalSail slow-only Tt (k=1.0sigma) on every race")
    print("=" * 80)
    for race in RACES:
        rows = make_rows(race)
        q = q_halsail_slow_only(rows, k=1.0)
        nr = round_q_to_nr(q, rows)
        print(f"\n--- {race[0]} ---")
        print(f"  {'Sail':>5} {'Boat':<16} {'TCF':>6} {'NR_pred':>8} "
              f"{'NR_SW':>6} {'Delta':>8}  capped?")
        cts = [r["ct"] for r in rows]
        mu = mean(cts); sigma = pstdev(cts); hi = mu + sigma
        for r in rows:
            nrp = nr[r["sail"]]
            diff = nrp - r["nr_sw"]
            cap = "SLOW" if r["ct"] > hi else "-"
            print(f"  {r['sail']:>5} {r['boat']:<16} {r['tcf']:>6.3f} "
                  f"{nrp:>8.3f} {r['nr_sw']:>6.3f} {diff:>+8.4f}  {cap}")


if __name__ == "__main__":
    main()
