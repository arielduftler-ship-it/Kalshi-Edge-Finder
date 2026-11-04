"""
research_price_paths.py

Research question
-----------------
Once a game starts, how far do Kalshi prices move away from their pregame
("opening") price, and does that movement look like fair game volatility or
like crowd overreaction that tends to snap back?

That decides whether a convergence strategy (enter when Kalshi disagrees with
the sharp line, exit when Kalshi comes back to it) can work at all.

Data
----
Kalshi keeps 1-minute candlesticks for finished games, free and without auth:
  live tier:       GET /series/{series}/markets/{ticker}/candlesticks
  historical tier: GET /historical/markets/{ticker}/candlesticks
(markets that settled more than ~3 months ago move to the historical tier).
Game start times come from the Kalshi ticker when it has an HHMM time, and
otherwise from ESPN's public scoreboard. Outcomes come from Kalshi's own
settled `result` field. No Odds API credits are used.

Price used: the bid/ask midpoint at each minute's close (minutes with a
missing side or a spread wider than MAX_SPREAD are skipped). Using minute
closes slightly understates how deep intra-minute dips went.

The three tests
---------------
1. Descriptive (your original question): how often does a team drop 3/5/10/15
   points below its opening price, how often does it never drop below at all,
   and how often do eventual WINNERS dip along the way.

2. Dip rate vs. a fair market. If prices were fair (no overreaction), the
   chance of ever touching level L from opening price p0 is at most
       (1 - p0) / (1 - L)
   It is exact for smooth paths and an upper bound when prices jump (a
   touchdown can skip past L). So real dip rates ABOVE this bound are strong
   evidence of overreaction; rates below it are inconclusive by themselves.

3. Snap-back test (the cleanest one). In a fair market, a team whose price
   first touches a dip level wins exactly as often as the price it touched
   at. So among games that touched each dip level we compare:
       actual win rate   vs.   average price at first touch
   Win rate higher than the touch price = dips overshoot and come back
   (buy-the-dip / convergence edge). Lower = momentum (dips keep going).
   We also report the hold-to-settlement P&L of buying at the ASK at first
   touch, which is what a real trade would have earned before fees.

Because each game has two mirrored markets (team A's dip is team B's rally),
favorites and underdogs are analysed as separate sets with one market per
game in each, so no game is double counted inside a set.

Optional: for signals already in data/scan_log.csv that carry a
kalshi_ticker, it checks whether Kalshi ever reached the book's fair price
after the scan, and compares selling there against holding to settlement.

Outputs (data/research/):
  market_summary.csv    one row per market (team contract) studied
  research_summary.md   all tables plus a plain-language read
  dip_rate_vs_fair.png, snapback.png, opening_calibration.png, example_paths.png
  debug.txt             counts of what was skipped and why
  paths.csv.gz          minute-by-minute mids (uploaded as an Actions artifact,
                        not committed, to keep the repo small)

Config via environment variables (the workflow sets these from its inputs):
  RESEARCH_SPORTS        default "nba,nhl,nfl"
  MAX_GAMES_PER_SPORT    default 500 (random sample, fixed seed)
  LOOKBACK_DAYS          default 450
  RESEARCH_SEED          default 42
"""

import csv
import gzip
import math
import os
import random
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from kalshi_client import KalshiClient  # noqa: E402

# ---------------------------------------------------------------- config

SERIES_TICKERS = {"nfl": "KXNFLGAME", "nba": "KXNBAGAME", "nhl": "KXNHLGAME"}
ESPN_PATHS = {"nfl": "football/nfl", "nba": "basketball/nba", "nhl": "hockey/nhl"}

SPORTS = [s.strip().lower() for s in os.environ.get("RESEARCH_SPORTS", "nba,nhl,nfl").split(",") if s.strip()]
MAX_GAMES_PER_SPORT = int(os.environ.get("MAX_GAMES_PER_SPORT", "500"))
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "450"))
SEED = int(os.environ.get("RESEARCH_SEED", "42"))

PREGAME_MINUTES = 60          # look this far before start for the opening price
GAME_WINDOW_HOURS = {"nfl": 4.5, "nba": 3.5, "nhl": 3.5}
MAX_SPREAD = 0.10             # skip minutes with a wider bid/ask than this
MIN_INGAME_MINUTES = 30       # skip markets with too few usable in-game minutes
DIPS = [0.03, 0.05, 0.10, 0.15, 0.20]
NEVER_BELOW_TOL = 0.01        # "never went below open" allows a 1-cent wobble
PAIR_SUM_MIN, PAIR_SUM_MAX = 0.90, 1.10  # both teams' opening prices must add to about $1
REQUEST_PAUSE = 0.12          # ~8 requests/sec, well under Kalshi's basic tier

ET = ZoneInfo("America/New_York")
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}

# ESPN abbreviation -> the code Kalshi most likely uses. Matching only needs ONE
# of the two teams to line up (a team plays at most once a day), so a missing
# entry here rarely matters.
ESPN_TO_KALSHI = {
    "nba": {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"},
    "nhl": {"NJ": "NJD", "SJ": "SJS", "TB": "TBL", "LA": "LAK", "UTAH": "UTA"},
    "nfl": {"WSH": "WAS"},
}

OUT_DIR = Path(__file__).parent / "data" / "research"
LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"

debug = []


def log(msg):
    print(msg, flush=True)
    debug.append(msg)


# ---------------------------------------------------------------- API helpers

kalshi = KalshiClient()
http = requests.Session()


def kget(path, params=None):
    """Kalshi GET with pacing. Returns None on 404/400 so callers can fall back
    from the live tier to the historical tier."""
    time.sleep(REQUEST_PAUSE)
    try:
        return kalshi._get(path, params=params)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        if code in (400, 404):
            return None
        raise


def paginate(path, params, key):
    out, cursor = [], None
    while True:
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        data = kget(path, p)
        if not data:
            break
        out.extend(data.get(key, []) or [])
        cursor = data.get("cursor")
        if not cursor:
            break
    return out


def dollars(obj, key):
    """Price in dollars from a candle sub-object, or None.

    Kalshi is inconsistent here, confirmed against real data (Nov 2026):
    the live tier returns '<key>_dollars' strings, but the historical tier
    returns DOLLARS under the plain '<key>' field (e.g. close: "0.2400"),
    which an earlier version of this script divided by 100 by mistake.
    Rule: a '_dollars' field is dollars; a plain field is dollars if it has a
    decimal point (string) or a fractional value (float), and cents only if
    it is a whole number (e.g. 24)."""
    if not obj:
        return None
    v = obj.get(f"{key}_dollars")
    if v not in (None, ""):
        return float(v)
    v = obj.get(key)
    if v is None or v == "":
        return None
    if isinstance(v, str):
        return float(v) if "." in v else float(v) / 100.0
    if isinstance(v, float) and not v.is_integer():
        return v
    return float(v) / 100.0


# ---------------------------------------------------------------- tickers & start times

TICKER_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(\d{4})?([A-Z]+)$")


def parse_event_segment(event_ticker):
    """'KXNBAGAME-26OCT20BOSDET' -> (date, 'HHMM' or None, 'BOSDET')."""
    seg = event_ticker.split("-", 1)[1] if "-" in event_ticker else event_ticker
    m = TICKER_RE.match(seg)
    if not m or m.group(2) not in MONTHS:
        return None
    yy, mon, dd, hhmm, teams = m.groups()
    try:
        d = date(2000 + int(yy), MONTHS[mon], int(dd))
    except ValueError:
        return None
    return d, hhmm, teams


_espn_cache = {}


def espn_games(sport, d):
    key = (sport, d)
    if key in _espn_cache:
        return _espn_cache[key]
    games = []
    try:
        resp = http.get(f"https://site.api.espn.com/apis/site/v2/sports/{ESPN_PATHS[sport]}/scoreboard",
                        params={"dates": d.strftime("%Y%m%d")}, timeout=15)
        resp.raise_for_status()
        for ev in resp.json().get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            abbrs = set()
            for c in comp.get("competitors", []):
                a = ((c.get("team") or {}).get("abbreviation") or "").upper()
                if a:
                    abbrs.add(ESPN_TO_KALSHI.get(sport, {}).get(a, a))
                    abbrs.add(a)
            start = ev.get("date")
            if start:
                games.append({"id": ev.get("id"), "abbrs": abbrs,
                              "start": datetime.fromisoformat(start.replace("Z", "+00:00"))})
    except Exception as e:
        log(f"[{sport}] ESPN scoreboard {d} failed: {e}")
    _espn_cache[key] = games
    return games


def resolve_start(sport, event_ticker, team_codes):
    """Returns (start_utc, source, espn_id) or (None, reason, None)."""
    parsed = parse_event_segment(event_ticker)
    if not parsed:
        return None, "ticker_unparsed", None
    d, hhmm, _ = parsed
    espn_id = None
    hits = [g for g in espn_games(sport, d) if g["abbrs"] & set(team_codes)]
    if len(hits) == 1:
        espn_id = hits[0]["id"]
    if hhmm:
        local = datetime(d.year, d.month, d.day, int(hhmm[:2]), int(hhmm[2:]), tzinfo=ET)
        return local.astimezone(timezone.utc), "ticker", espn_id
    if len(hits) == 1:
        return hits[0]["start"], "espn", espn_id
    return None, ("espn_ambiguous" if hits else "espn_no_match"), None


# ---------------------------------------------------------------- data collection

def sample_events(sport, series):
    events = paginate("/events", {"series_ticker": series, "status": "settled", "limit": 200}, "events")
    today = datetime.now(timezone.utc).date()
    keep = []
    for ev in events:
        t = ev.get("event_ticker", "")
        p = parse_event_segment(t)
        if p and today - timedelta(days=LOOKBACK_DAYS) <= p[0] < today:
            keep.append(t)
    keep = sorted(set(keep))
    rng = random.Random(f"{SEED}-{sport}")
    sampled = keep if len(keep) <= MAX_GAMES_PER_SPORT else rng.sample(keep, MAX_GAMES_PER_SPORT)
    log(f"[{sport}] {len(events)} settled events listed, {len(keep)} in lookback window, sampling {len(sampled)}")
    return sorted(sampled)


def event_markets(event_ticker):
    data = kget("/markets", {"event_ticker": event_ticker, "limit": 100})
    mk = (data or {}).get("markets") or []
    if not mk:
        data = kget("/historical/markets", {"event_ticker": event_ticker, "limit": 100})
        mk = (data or {}).get("markets") or []
    return mk


_raw_logged = set()


def _log_raw(tier, cs):
    if cs and tier not in _raw_logged:
        _raw_logged.add(tier)
        mid = cs[len(cs) // 2]
        log(f"raw {tier} candle sample: yes_bid={mid.get('yes_bid')} yes_ask={mid.get('yes_ask')}")


def candles(series, ticker, start_ts, end_ts):
    params = {"start_ts": start_ts, "end_ts": end_ts, "period_interval": 1,
              "include_latest_before_start": "true"}
    data = kget(f"/series/{series}/markets/{ticker}/candlesticks", params)
    cs = (data or {}).get("candlesticks") or []
    if cs:
        _log_raw("live", cs)
        return cs
    data = kget(f"/historical/markets/{ticker}/candlesticks", params)
    cs = (data or {}).get("candlesticks") or []
    _log_raw("historical", cs)
    return cs


def to_path(cs):
    """[(ts, mid, bid, ask)] for minutes with a usable two-sided quote."""
    out = []
    for c in cs:
        ts = c.get("end_period_ts")
        bid = dollars(c.get("yes_bid"), "close")
        ask = dollars(c.get("yes_ask"), "close")
        if ts is None or bid is None or ask is None:
            continue
        if bid <= 0 or ask >= 1 or ask < bid or ask - bid > MAX_SPREAD:
            continue
        out.append((int(ts), (bid + ask) / 2, bid, ask))
    out.sort()
    return out


def summarize(path, start_ts):
    pre = [p for p in path if start_ts - PREGAME_MINUTES * 60 <= p[0] <= start_ts]
    game = [p for p in path if p[0] > start_ts]
    if not pre:
        return None, "no_pregame_quote"
    if len(game) < MIN_INGAME_MINUTES:
        return None, "thin_ingame"
    p0 = pre[-1][1]
    mids = [g[1] for g in game]
    row = {
        "p0": round(p0, 4),
        "open_spread": round(pre[-1][3] - pre[-1][2], 4),
        "n_ingame_min": len(game),
        "min_mid": round(min(mids), 4),
        "max_mid": round(max(mids), 4),
        "max_dip": round(p0 - min(mids), 4),
        "max_rise": round(max(mids) - p0, 4),
        "pct_min_below_open": round(sum(m < p0 - NEVER_BELOW_TOL for m in mids) / len(mids), 4),
        "never_below_open": int(min(mids) >= p0 - NEVER_BELOW_TOL),
    }
    for d in DIPS:
        lvl = p0 - d
        k = f"d{int(round(d * 100)):02d}"
        first = next((g for g in game if g[1] <= lvl), None) if lvl > 0 else None
        row[f"hit_{k}"] = int(first is not None)
        row[f"touch_mid_{k}"] = round(first[1], 4) if first else ""
        row[f"touch_ask_{k}"] = round(first[3], 4) if first else ""
        row[f"touch_min_{k}"] = round((first[0] - start_ts) / 60) if first else ""
    return row, None


def collect():
    rows, paths_out, skips = [], [], defaultdict(int)
    for sport in SPORTS:
        series = SERIES_TICKERS.get(sport)
        if not series:
            log(f"Unknown sport '{sport}', skipping")
            continue
        try:
            events = sample_events(sport, series)
        except Exception as e:
            log(f"[{sport}] event listing FAILED: {e}")
            continue
        for i, ev in enumerate(events, 1):
            if i % 50 == 0:
                log(f"[{sport}] {i}/{len(events)} events processed")
            try:
                mk = [m for m in event_markets(ev) if (m.get("result") or "").lower() in ("yes", "no")]
            except Exception as e:
                skips[f"{sport}:market_fetch_error"] += 1
                log(f"[{sport}] {ev} market fetch error: {e}")
                continue
            if len(mk) != 2 or {m["result"].lower() for m in mk} != {"yes", "no"}:
                skips[f"{sport}:not_two_settled_markets(tie/void)"] += 1
                continue
            codes = [m["ticker"].rsplit("-", 1)[-1] for m in mk]
            start, src, espn_id = resolve_start(sport, ev, codes)
            if start is None:
                skips[f"{sport}:start_time_{src}"] += 1
                continue
            s_ts = int(start.timestamp())
            e_ts = s_ts + int(GAME_WINDOW_HOURS[sport] * 3600)
            pair, pair_paths, bad = [], [], None
            for m in mk:
                try:
                    path = to_path(candles(series, m["ticker"], s_ts - PREGAME_MINUTES * 60 - 60, e_ts))
                except Exception as e:
                    bad = "candle_error"
                    log(f"[{sport}] {m['ticker']} candle error: {e}")
                    break
                summ, why = summarize(path, s_ts)
                if summ is None:
                    bad = why
                    break
                pair.append({"sport": sport, "event_ticker": ev, "ticker": m["ticker"],
                             "team": m["ticker"].rsplit("-", 1)[-1],
                             "start_utc": start.isoformat(), "start_source": src, "espn_id": espn_id or "",
                             "won": int(m["result"].lower() == "yes"), **summ})
                pair_paths += [(m["ticker"], ts, round((ts - s_ts) / 60), round(mid, 4))
                               for ts, mid, bid, ask in path]
            # Safety check: the two teams' opening prices must roughly add to $1.
            # If they don't, prices were mis-parsed or the start time is wrong.
            if bad is None and not (PAIR_SUM_MIN <= pair[0]["p0"] + pair[1]["p0"] <= PAIR_SUM_MAX):
                bad = "pair_prices_dont_sum_to_1"
                if skips[f"{sport}:{bad}"] < 5:
                    log(f"[{sport}] {ev} opening prices {pair[0]['p0']} + {pair[1]['p0']} don't sum to ~1, skipped")
            if bad:
                skips[f"{sport}:{bad}"] += 1
                continue
            rows.extend(pair)
            paths_out.extend(pair_paths)
    for k, v in sorted(skips.items()):
        log(f"skipped {k}: {v}")
    return rows, paths_out


# ---------------------------------------------------------------- stats helpers

def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def se(xs):
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def pct(x):
    return "—" if x != x else f"{100 * x:.1f}%"


def split_sides(rows):
    """One favorite and one underdog market per game."""
    by_ev = defaultdict(list)
    for r in rows:
        by_ev[r["event_ticker"]].append(r)
    fav, dog = [], []
    for ev, rs in by_ev.items():
        if len(rs) != 2:
            continue
        a, b = sorted(rs, key=lambda r: r["p0"], reverse=True)
        fav.append(a)
        dog.append(b)
    return fav, dog


def bucket(p):
    edges = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.01]
    for lo, hi in zip(edges, edges[1:]):
        if lo <= p < hi:
            return f"{int(lo * 100)}–{min(int(hi * 100), 100)}¢"
    return "?"


def fair_hit_prob(p0, d):
    lvl = p0 - d
    if lvl <= 0:
        return 0.0
    return min(1.0, (1 - p0) / (1 - lvl))


# ---------------------------------------------------------------- analysis

def analyse(rows):
    md = ["# In-game Kalshi price paths: dip and snap-back research", "",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
          f"Sports: {', '.join(SPORTS)}. Up to {MAX_GAMES_PER_SPORT} games per sport, "
          f"lookback {LOOKBACK_DAYS} days, seed {SEED}.", ""]
    sports = sorted({r["sport"] for r in rows})
    groups = {}
    for s in sports:
        fav, dog = split_sides([r for r in rows if r["sport"] == s])
        groups[(s, "favorite")] = fav
        groups[(s, "underdog")] = dog
    allfav, alldog = split_sides(rows)
    groups[("all", "favorite")] = allfav
    groups[("all", "underdog")] = alldog

    md += ["## Sample", "", "| Sport | Games | Median in-game minutes | Median opening spread |", "|---|---|---|---|"]
    for s in sports + ["all"]:
        g = groups[(s, "favorite")]
        if g:
            mins = sorted(r["n_ingame_min"] for r in g)
            spr = sorted(r["open_spread"] for r in g)
            md.append(f"| {s} | {len(g)} | {mins[len(mins) // 2]} | {spr[len(spr) // 2] * 100:.1f}¢ |")
    md.append("")

    # 1. descriptive
    md += ["## 1. How far do prices move below the opening price?", "",
           "\"Never below open\" allows a 1¢ wobble. \"Winners\" columns only count teams that went on to win, "
           "since a losing team always ends near 0.", "",
           "| Sport | Side | Games | Never below open | Dip ≥3 | Dip ≥5 | Dip ≥10 | Dip ≥15 | Winners: never below | Winners: dip ≥5 | Winners: dip ≥10 |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for (s, side), g in groups.items():
        if not g:
            continue
        w = [r for r in g if r["won"]]
        md.append(f"| {s} | {side} | {len(g)} | {pct(mean([r['never_below_open'] for r in g]))} | "
                  + " | ".join(pct(mean([r[f'hit_d{k:02d}'] for r in g])) for k in (3, 5, 10, 15))
                  + f" | {pct(mean([r['never_below_open'] for r in w]))} | {pct(mean([r['hit_d05'] for r in w]))}"
                  f" | {pct(mean([r['hit_d10'] for r in w]))} |")
    md.append("")

    md += ["### By opening price (all sports, one market per game per side)", "",
           "| Opening price | Games | Win rate | Never below open | Dip ≥5 | Dip ≥10 | Winners: dip ≥5 |", "|---|---|---|---|---|---|---|"]
    by_b = defaultdict(list)
    for r in allfav + alldog:
        by_b[bucket(r["p0"])].append(r)
    for b in sorted(by_b, key=lambda x: int(x.split("–")[0])):
        g = by_b[b]
        w = [r for r in g if r["won"]]
        md.append(f"| {b} | {len(g)} | {pct(mean([r['won'] for r in g]))} | {pct(mean([r['never_below_open'] for r in g]))} | "
                  f"{pct(mean([r['hit_d05'] for r in g]))} | {pct(mean([r['hit_d10'] for r in g]))} | {pct(mean([r['hit_d05'] for r in w]))} |")
    md.append("")

    # 2. dip rate vs fair bound
    md += ["## 2. Do prices dip more often than a fair market would?", "",
           "Fair bound = average of (1 − p0) / (1 − (p0 − dip)). Real rates clearly ABOVE the bound mean overreaction. "
           "Rates below it are expected even in a fair market, because prices jump and minute closes miss some lows. "
           "A losing team counts as reaching every level, because it settles at $0 even when the last quote was higher.", "",
           "| Sport | Side | Dip | Games | Actual dip rate (95% CI) | Fair bound | Actual − bound |", "|---|---|---|---|---|---|---|"]
    test2 = []
    for (s, side), g in groups.items():
        for d in DIPS:
            k = f"d{int(round(d * 100)):02d}"
            n = len(g)
            if n < 20:
                continue
            # A team that lost settles at $0, so it "reached" every positive level
            # even if Kalshi stopped quoting before the price got there (close games
            # often jump from ~30c to 0 at the buzzer). The fair bound counts those,
            # so the actual rate must too, or the test is biased low.
            hits = sum(1 for r in g if r[f"hit_{k}"] or (not r["won"] and r["p0"] - d > 0))
            lo, hi = wilson(hits, n)
            bound = mean([fair_hit_prob(r["p0"], d) for r in g])
            test2.append((s, side, d, hits / n, lo, hi, bound))
            flag = " ⬆" if lo > bound else ""
            md.append(f"| {s} | {side} | {int(d * 100)}¢ | {n} | {pct(hits / n)} ({pct(lo)}–{pct(hi)}) | {pct(bound)} | "
                      f"{100 * (hits / n - bound):+.1f} pts{flag} |")
    md += ["", "⬆ = the whole confidence interval sits above the fair bound.", ""]

    # 3. snap-back
    md += ["## 3. Snap-back test: after a dip, does the team win more often than its price said?", "",
           "For games whose price touched each dip level: win rate vs. the average price at first touch. "
           "In a fair market these match. \"Buy-the-dip P&L\" = buy YES at the ask at first touch and hold to "
           "settlement, per contract, before fees.", "",
           "| Sport | Side | Dip | Touches | Win rate after touch | Avg touch price | Win rate − price | Buy-the-dip P&L (±1.96 SE) |",
           "|---|---|---|---|---|---|---|---|"]
    test3 = []
    for (s, side), g in groups.items():
        for d in DIPS:
            k = f"d{int(round(d * 100)):02d}"
            t = [r for r in g if r[f"hit_{k}"]]
            if len(t) < 20:
                continue
            wr = mean([r["won"] for r in t])
            tp = mean([r[f"touch_mid_{k}"] for r in t])
            pnl = [r["won"] - r[f"touch_ask_{k}"] for r in t]
            m, e = mean(pnl), 1.96 * se(pnl)
            test3.append((s, side, d, len(t), wr, tp, m, e))
            md.append(f"| {s} | {side} | {int(d * 100)}¢ | {len(t)} | {pct(wr)} | {pct(tp)} | {100 * (wr - tp):+.1f} pts | "
                      f"{100 * m:+.1f}¢ (±{100 * e:.1f}¢) |")
    md.append("")

    # 4. opening calibration
    md += ["## 4. Is the opening price itself well calibrated?", "",
           "If Kalshi's pregame price is biased (e.g. favorites too cheap), the in-game tests above inherit that bias.", "",
           "| Opening price | Games | Avg opening price | Win rate | Win rate − price |", "|---|---|---|---|---|"]
    calib = []
    for b in sorted(by_b, key=lambda x: int(x.split("–")[0])):
        g = by_b[b]
        mp, wr = mean([r["p0"] for r in g]), mean([r["won"] for r in g])
        calib.append((mp, wr, len(g)))
        md.append(f"| {b} | {len(g)} | {pct(mp)} | {pct(wr)} | {100 * (wr - mp):+.1f} pts |")
    md.append("")

    # plain-language read
    md += ["## Plain-language read", ""]
    above = [t for t in test2 if t[0] == "all" and t[4] > t[6]]
    md.append(f"- Dip-rate test: {len(above)} of {len([t for t in test2 if t[0] == 'all'])} all-sport dip levels show "
              "dips significantly more often than a fair market allows." if test2 else "- Dip-rate test: not enough data.")
    sig_pos = [t for t in test3 if t[0] == "all" and t[6] - t[7] > 0]
    sig_neg = [t for t in test3 if t[0] == "all" and t[6] + t[7] < 0]
    all3 = [t for t in test3 if t[0] == "all"]
    md.append(f"- Snap-back test: of {len(all3)} all-sport dip levels, {len(sig_pos)} show a buy-the-dip profit "
              f"clearly above zero, {len(sig_neg)} clearly below zero, the rest are inside the noise.")
    md.append("- If both tests come back near zero, in-game swings are ordinary game volatility. A convergence exit "
              "would then mostly sell winners early, and holding the pregame edge to settlement is the better rule.")
    md.append("- If snap-back is clearly positive, Kalshi overreacts in-game, and buying dips (or exiting at the "
              "sharp number) has its own edge worth testing against fees and depth.")
    md.append("- Fees are not included. Kalshi's taker fee is largest near 50¢, so any edge under ~2¢ per contract "
              "is unlikely to survive taking liquidity.")
    md.append("")
    return md, groups, test2, test3, calib


# ---------------------------------------------------------------- scan_log tie-in

def scan_log_check():
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH, newline="") as f:
        sig = [r for r in csv.DictReader(f) if (r.get("kalshi_ticker") or "").startswith("KX")]
    if not sig:
        return ["## 5. Your logged signals", "", "No scan_log rows carry a kalshi_ticker yet.", ""]
    md = ["## 5. Your logged signals: did Kalshi ever reach the book's fair price?", "",
          "Entry = logged entry price. Target = logged book fair probability. Touch uses the bid/ask midpoint, "
          "so a real sell would land slightly lower. Before fees.", "",
          "| Ticker | Entry | Target | Touched target? | Won? | Sell-at-target P&L | Hold P&L |", "|---|---|---|---|---|---|---|"]
    tot_sell, tot_hold, n = 0.0, 0.0, 0
    for r in sig:
        t = r["kalshi_ticker"]
        series = t.split("-", 1)[0]
        try:
            scan_ts = int(datetime.fromisoformat(r["scan_timestamp"].replace("Z", "+00:00")).timestamp())
            entry, target = float(r["entry_price"]), float(r["book_fair_prob"])
        except (ValueError, KeyError):
            continue
        mk = kget(f"/markets/{t}") or kget(f"/historical/markets/{t}")
        res = ((mk or {}).get("market") or {}).get("result", "").lower()
        if res not in ("yes", "no"):
            continue
        won = int(res == "yes")
        side = (r.get("side") or "buy_yes").lower()
        path = to_path(candles(series, t, scan_ts, scan_ts + 3 * 86400))
        if side == "buy_no":
            touched = any((1 - p[1]) >= (1 - target) for p in path)
            won = 1 - won
            target_px = 1 - target
        else:
            touched = any(p[1] >= target for p in path)
            target_px = target
        sell = (target_px - entry) if touched else (won - entry)
        hold = won - entry
        tot_sell, tot_hold, n = tot_sell + sell, tot_hold + hold, n + 1
        md.append(f"| {t} | {entry:.2f} | {target_px:.2f} | {'yes' if touched else 'no'} | {'yes' if won else 'no'} | "
                  f"{100 * sell:+.1f}¢ | {100 * hold:+.1f}¢ |")
    if n:
        md.append(f"| **Average ({n})** | | | | | **{100 * tot_sell / n:+.1f}¢** | **{100 * tot_hold / n:+.1f}¢** |")
    md += ["", "Too few rows to conclude anything yet; this table grows as the scanner logs more signals.", ""]
    return md


# ---------------------------------------------------------------- charts

def charts(groups, test2, test3, calib, rows, paths_out):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # dip rate vs fair bound, per sport
    sports = sorted({t[0] for t in test2 if t[0] != "all"}) + ["all"]
    fig, axes = plt.subplots(1, len(sports), figsize=(4.2 * len(sports), 4), squeeze=False)
    for ax, s in zip(axes[0], sports):
        for side, color in (("favorite", "#1f77b4"), ("underdog", "#d62728")):
            pts = [t for t in test2 if t[0] == s and t[1] == side]
            if not pts:
                continue
            x = [100 * t[2] for t in pts]
            ax.plot(x, [100 * t[3] for t in pts], "o-", color=color, label=f"{side}: actual")
            ax.fill_between(x, [100 * t[4] for t in pts], [100 * t[5] for t in pts], color=color, alpha=0.15)
            ax.plot(x, [100 * t[6] for t in pts], "--", color=color, label=f"{side}: fair bound")
        ax.set_title(s.upper())
        ax.set_xlabel("dip below opening price (¢)")
        ax.set_ylabel("% of games")
        ax.grid(alpha=0.3)
    axes[0][0].legend(fontsize=8)
    fig.suptitle("How often prices dip vs. what a fair market allows")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "dip_rate_vs_fair.png", dpi=130)
    plt.close(fig)

    # snap-back
    fig, ax = plt.subplots(figsize=(6, 6))
    for t in test3:
        if t[0] == "all":
            continue
        ax.errorbar(100 * t[5], 100 * t[4], yerr=100 * 1.96 * math.sqrt(max(t[4] * (1 - t[4]), 1e-9) / t[3]),
                    fmt="o" if t[1] == "favorite" else "s", alpha=0.7,
                    label=f"{t[0]} {t[1]} {int(t[2] * 100)}¢")
    ax.plot([0, 100], [0, 100], "k--", lw=1, label="fair (win rate = price)")
    ax.set_xlabel("average price at first touch (¢)")
    ax.set_ylabel("win rate after touch (%)")
    ax.set_title("Snap-back: above the line = dips overshoot")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=6, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "snapback.png", dpi=130)
    plt.close(fig)

    # opening calibration
    if calib:
        fig, ax = plt.subplots(figsize=(5.5, 5.5))
        ax.scatter([100 * c[0] for c in calib], [100 * c[1] for c in calib], s=[max(10, c[2] / 3) for c in calib])
        ax.plot([0, 100], [0, 100], "k--", lw=1)
        ax.set_xlabel("Kalshi opening price (¢)")
        ax.set_ylabel("actual win rate (%)")
        ax.set_title("Opening-price calibration (dot size = games)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT_DIR / "opening_calibration.png", dpi=130)
        plt.close(fig)

    # example paths
    fav = groups.get(("all", "favorite"), [])
    if fav:
        ex = random.Random(SEED).sample(fav, min(6, len(fav)))
        by_t = defaultdict(list)
        want = {r["ticker"] for r in ex}
        for t, ts, mins, mid in paths_out:
            if t in want:
                by_t[t].append((mins, mid))
        fig, axes = plt.subplots(2, 3, figsize=(13, 7), squeeze=False)
        for ax, r in zip(axes.flat, ex):
            pts = sorted(by_t[r["ticker"]])
            ax.plot([p[0] for p in pts], [100 * p[1] for p in pts], lw=1)
            ax.axhline(100 * r["p0"], color="gray", ls="--", lw=1)
            ax.axvline(0, color="k", lw=0.8)
            ax.set_title(f"{r['ticker']}  ({'won' if r['won'] else 'lost'})", fontsize=8)
            ax.set_ylim(0, 100)
            ax.set_xlabel("minutes from start")
            ax.set_ylabel("Kalshi mid (¢)")
        fig.suptitle("Example favorite price paths (dashed = opening price)")
        fig.tight_layout()
        fig.savefig(OUT_DIR / "example_paths.png", dpi=130)
        plt.close(fig)


# ---------------------------------------------------------------- main

def write_outputs(rows, paths_out):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if rows:
        fields = list(rows[0].keys())
        with open(OUT_DIR / "market_summary.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    with gzip.open(OUT_DIR / "paths.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "end_period_ts", "minutes_from_start", "mid"])
        w.writerows(paths_out)


def main():
    log(f"Research run at {datetime.now(timezone.utc).isoformat()}")
    rows, paths_out = collect()
    log(f"{len(rows)} markets kept across {len({r['event_ticker'] for r in rows})} games")
    write_outputs(rows, paths_out)
    if not rows:
        md = ["# In-game Kalshi price paths", "", "No usable games were collected. See debug.txt."]
    else:
        md, groups, test2, test3, calib = analyse(rows)
        md += scan_log_check()
        md += ["## Charts", "", "![dip rates](dip_rate_vs_fair.png)", "", "![snap-back](snapback.png)", "",
               "![calibration](opening_calibration.png)", "", "![examples](example_paths.png)", ""]
        charts(groups, test2, test3, calib, rows, paths_out)
    (OUT_DIR / "research_summary.md").write_text("\n".join(md))
    (OUT_DIR / "debug.txt").write_text("\n".join(debug) + "\n")
    log("Done.")


if __name__ == "__main__":
    main()
