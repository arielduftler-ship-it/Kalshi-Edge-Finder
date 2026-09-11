"""
run_daily_scan.py

Pulls live sportsbook odds + Kalshi market prices for NFL/NBA/MLB, and logs a
row to data/scan_log.csv only for games that are actual underpriced-favorite
signals (a real favorite per the sportsbook, priced by Kalshi below 50%,
clearing a 1% net edge after fees/spread). Every other matched game -- a
correctly-priced favorite, an overpriced underdog, anything below threshold
-- is evaluated but not written, so the log only ever contains bets worth
looking at. Run this daily (see .github/workflows/daily_scan.yml).

Usage:
    export ODDS_API_KEY=...
    python run_daily_scan.py
"""

import csv
import os
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

from kalshi_client import KalshiClient
from odds_client import OddsClient
from edge_engine import compute_signal, is_underpriced_favorite
import team_aliases

# --- VERIFY THESE against the live Kalshi API before relying on this script ---
# Check via: KalshiClient().get_events()  (no filter) and inspect the
# 'series_ticker' field on events that look like sports games.
SERIES_TICKERS = {
    "nfl": "KXNFLGAME",
    "nba": "KXNBAGAME",
    "mlb": "KXMLBGAME",
}

# Only look at each sport's nearest upcoming week, not its whole remaining
# schedule. The Odds API returns every future game on a team's calendar --
# without this, we'd also be scanning games weeks or months out that Kalshi
# doesn't even have a market open for yet (and, worse, in sports where the
# same two teams play multiple times a season, filtering to the nearest week
# is what keeps this from ever considering a later rematch by mistake).
NEAREST_WEEK_DAYS = 8

LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"
LOG_FIELDS = [
    "scan_timestamp", "game_time", "sport", "game_label", "team", "book_fair_prob",
    "kalshi_price", "entry_price", "raw_edge", "fee_cost", "spread_cost",
    "net_edge", "side", "kalshi_ticker", "outcome",
]

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
)}


def normalize(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def parse_commence_date(commence_time: str):
    """The Odds API gives commence_time as ISO8601 UTC, e.g. '2026-09-14T20:00:00Z'."""
    try:
        return datetime.fromisoformat(commence_time.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def parse_ticker_date(event_segment: str, pair_index: int):
    """Kalshi's ticker event segment leads with a date -- 2-digit year + 3-letter
    month + 2-digit day (e.g. '26SEP14'), sometimes followed by a 4-digit
    'HHMM' time before the team codes (e.g. '26SEP091310'). `pair_index` is
    where the matched team-code pair starts, so everything before it is the
    date/time prefix. Returns None if it doesn't parse -- callers should treat
    that as "can't verify" rather than "definitely wrong", since we've
    already been burned twice by over-trusting ticker format assumptions."""
    prefix = event_segment[:pair_index]
    if len(prefix) < 7:
        return None
    yy, mon, dd = prefix[0:2], prefix[2:5], prefix[5:7]
    if not (yy.isdigit() and dd.isdigit()) or mon not in _MONTHS:
        return None
    try:
        return date(2000 + int(yy), _MONTHS[mon], int(dd))
    except ValueError:
        return None


def price_cents(market: dict, side: str) -> int:
    """Kalshi's current API returns prices as dollar strings
    (e.g. yes_bid_dollars: "0.5600"), not plain integer cents.
    Falls back to the older cents-integer field if present."""
    dollars_key = f"{side}_dollars"
    if dollars_key in market and market[dollars_key] is not None:
        return int(round(float(market[dollars_key]) * 100))
    return int(market[side])


def match_kalshi_market(home_team: str, away_team: str, sport: str, game_date, markets: list):
    """Matches a specific game (home_team vs away_team, on game_date) to its
    Kalshi 'home team wins' market.

    History of bugs found in this function, all confirmed against real data:

    1. Kalshi's `title` field describes the whole matchup and is IDENTICAL
       across every per-team market in that event -- searching for a
       nickname inside `title` matches all of them, not just one.

    2. Matching on the home team's abbreviation ALONE isn't enough: The
       Odds API returns a team's entire season schedule, while Kalshi only
       has ONE open market per team at a time. Confirmed: four different
       "@ Kansas City Chiefs" rows all got the same Broncos-game ticker.

    3. Tried verifying the opponent by checking if their abbreviation
       appeared anywhere in the ticker's date+teams segment (e.g.
       "26SEP14DENKC"). Backfires on letter-boundary coincidences --
       confirmed: "DETBUF" (Lions vs Bills) contains "T"+"B" back to back,
       false-matching as "TB" (Buccaneers).

    4. Tried verifying the opponent via the full team name in `title`
       instead. Also wrong -- confirmed against real Kalshi data dumped
       from a live run: Kalshi's title/subtitle/yes_sub_title fields use
       CITY names, not nicknames ("Minnesota wins", "Seattle", "A's" for
       the Athletics specifically) -- our nickname keys ("twins",
       "seahawks") never appear in that text at all, so literally 0% of
       games ever matched across every sport, every day.

    5. Fixed opponent verification via ticker abbreviation adjacency
       (AWAY+HOME or HOME+AWAY as one unit, e.g. "DENKC"). This confirms
       the right two TEAMS, but not the right DATE -- teams that play each
       other more than once a season (routine in MLB) would all resolve to
       whichever single market happens to be open, silently mixing up which
       meeting a signal actually belongs to.

    The fix here: once the team-pair matches, also parse the date embedded
    at the start of the ticker's event segment and require it to line up
    (within a day, to allow for UTC/ET timezone slop right around midnight)
    with the game's actual date from the sportsbook. If the ticker's date
    can't be parsed, we don't reject the match outright -- we've been burned
    twice now by over-trusting assumptions about Kalshi's field formats --
    but we also don't return the market silently; the caller is told the
    date is unverified so it can decide whether that's acceptable.

    Returns (market, date_verified: bool) -- market is None if no match at all.
    """
    home_alias = team_aliases.lookup(sport, home_team)
    away_alias = team_aliases.lookup(sport, away_team)

    if home_alias and away_alias:
        home_abbr, home_nick = home_alias
        away_abbr, _ = away_alias
        pair_variants = (away_abbr + home_abbr, home_abbr + away_abbr)
        for m in markets:
            parts = m.get("ticker", "").split("-")
            if len(parts) < 3:
                continue
            suffix = parts[-1].upper()
            event_segment = parts[-2].upper()
            if suffix != home_abbr:
                continue
            for pair in pair_variants:
                idx = event_segment.find(pair)
                if idx == -1:
                    continue
                ticker_date = parse_ticker_date(event_segment, idx)
                if ticker_date is None:
                    return m, False  # matched teams, date unverifiable
                if game_date is not None and abs((ticker_date - game_date).days) <= 1:
                    return m, True
                # Team pair matched but the date is clearly a different
                # meeting of the same two teams -- keep looking rather than
                # silently attaching the wrong week's price.
        return None, False  # no open Kalshi market for this specific matchup right now

    # One or both teams missing from team_aliases.py -- old, fragile
    # last-word heuristic, kept only as a last resort. Loudly flagged so a
    # silent/unreliable match is never invisible.
    missing = home_team if not home_alias else away_team
    print(f"WARNING: '{missing}' not in team_aliases.py -- matching on a fragile "
          f"last-word nickname instead of a verified abbreviation. Add this team to team_aliases.py.")
    target_nickname = normalize(home_team.split()[-1])
    for m in markets:
        subtitle = normalize(m.get("subtitle") or m.get("yes_sub_title") or "")
        if target_nickname and target_nickname in subtitle:
            return m, False
    return None, False


DEBUG_PATH = Path(__file__).parent / "data" / "last_run_debug.txt"


def run_scan():
    odds_client = OddsClient()  # reads ODDS_API_KEY from env
    kalshi_client = KalshiClient()  # public endpoints, no auth needed

    LOG_PATH.parent.mkdir(exist_ok=True)
    file_exists = LOG_PATH.exists()

    rows_written = 0
    debug_lines = [f"Run at {datetime.now(timezone.utc).isoformat()}"]

    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if not file_exists:
            writer.writeheader()

        for sport, series_ticker in SERIES_TICKERS.items():
            counts = {"games_from_book": 0, "outside_window": 0, "no_market_matched": 0,
                      "date_unverified": 0, "matched_not_signal": 0, "signals": 0}
            near_misses = []  # sample of matched-but-not-a-signal games, for visibility

            try:
                all_games = odds_client.get_odds(sport)
            except Exception as e:
                debug_lines.append(f"[{sport}] odds fetch FAILED: {e}")
                continue

            now = datetime.now(timezone.utc)
            window_end = now + timedelta(days=NEAREST_WEEK_DAYS)
            games = []
            for g in all_games:
                d = parse_commence_date(g.get("commence_time", ""))
                if d is None:
                    continue  # can't tell when it is -- skip rather than guess
                commence_dt = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                if now - timedelta(hours=12) <= commence_dt <= window_end:
                    games.append(g)
            counts["outside_window"] = len(all_games) - len(games)

            try:
                events = kalshi_client.get_events(series_ticker=series_ticker)
            except Exception as e:
                debug_lines.append(f"[{sport}] kalshi events fetch FAILED (check SERIES_TICKERS): {e}")
                continue

            kalshi_market_groups = []
            for ev in events:
                try:
                    kalshi_market_groups.append(kalshi_client.get_markets(event_ticker=ev["event_ticker"]))
                except Exception:
                    continue
            all_markets = [m for group in kalshi_market_groups for m in group]

            for game in games:
                counts["games_from_book"] += 1
                home, away = game.get("home_team"), game.get("away_team")
                game_date = parse_commence_date(game.get("commence_time", ""))
                books = game.get("bookmakers", [])
                if not books:
                    continue
                book = books[0]  # first available book; consider filtering to a specific sharp book
                h2h = next((m for m in book.get("markets", []) if m["key"] == "h2h"), None)
                if not h2h or len(h2h.get("outcomes", [])) != 2:
                    continue

                out_home = next((o for o in h2h["outcomes"] if o["name"] == home), None)
                out_away = next((o for o in h2h["outcomes"] if o["name"] == away), None)
                if not out_home or not out_away:
                    continue

                market, date_verified = match_kalshi_market(home, away, sport, game_date, all_markets)
                if not market:
                    counts["no_market_matched"] += 1
                    continue  # no open Kalshi market for this specific matchup right now
                if not date_verified:
                    counts["date_unverified"] += 1

                try:
                    sig = compute_signal(
                        game_label=f"{away} @ {home}", team=home,
                        book_odds_a=out_home["price"], book_odds_b=out_away["price"],
                        kalshi_yes_bid=price_cents(market, "yes_bid"), kalshi_yes_ask=price_cents(market, "yes_ask"),
                        kalshi_ticker=market["ticker"],
                    )
                except Exception as e:
                    debug_lines.append(f"[{sport}] signal calc failed for {home} vs {away}: {e}")
                    continue

                # We're only trading underpriced favorites right now (a real
                # favorite that Kalshi's crowd has priced below 50%) clearing
                # a 1% net edge -- not every matched game or every edge sign.
                # Correctly-priced favorites and overpriced underdogs are
                # skipped entirely so real signals don't get buried.
                if not (sig.net_edge >= 0.01 and is_underpriced_favorite(sig)):
                    counts["matched_not_signal"] += 1
                    if len(near_misses) < 8:
                        near_misses.append(
                            f"    {sig.game_label:35s} fair={sig.book_fair_prob:.3f} "
                            f"kalshi={sig.kalshi_price:.3f} net_edge={sig.net_edge:+.3f}"
                        )
                    continue

                writer.writerow({
                    "scan_timestamp": datetime.now(timezone.utc).isoformat(),
                    "game_time": game.get("commence_time", ""),
                    "sport": sport, "game_label": sig.game_label, "team": sig.team,
                    "book_fair_prob": round(sig.book_fair_prob, 4),
                    "kalshi_price": round(sig.kalshi_price, 4),
                    "entry_price": round(sig.entry_price, 4),
                    "raw_edge": round(sig.raw_edge, 4),
                    "fee_cost": round(sig.fee_cost, 4),
                    "spread_cost": round(sig.spread_cost, 4),
                    "net_edge": round(sig.net_edge, 4),
                    "side": sig.side, "kalshi_ticker": sig.kalshi_ticker,
                    "outcome": "",
                })
                rows_written += 1
                counts["signals"] += 1
                print(f"SIGNAL  {sig.game_label:30s} {sig.side:8s} net_edge={sig.net_edge:+.3f} "
                      f"(favorite @ {sig.kalshi_price:.2f})")

            debug_lines.append(
                f"[{sport}] {len(all_games)} games from book ({counts['outside_window']} outside the "
                f"next {NEAREST_WEEK_DAYS} days, skipped), {len(kalshi_market_groups)} Kalshi events open, "
                f"{counts['no_market_matched']} had no matching Kalshi event, "
                f"{counts['date_unverified']} matched but date unverified (ticker date didn't parse), "
                f"{counts['matched_not_signal']} matched but weren't underpriced-favorite signals, "
                f"{counts['signals']} signals."
            )
            if near_misses:
                debug_lines.append(f"[{sport}] sample of matched-but-not-signal games (favorite must have kalshi<0.5):")
                debug_lines.extend(near_misses)
            if kalshi_market_groups and counts["games_from_book"] > 0 and counts["no_market_matched"] == counts["games_from_book"]:
                # Every single game failed to match, even though Kalshi events
                # ARE open -- our assumption about the title/ticker format is
                # probably wrong. Dump the raw fields so we can see the real
                # format directly instead of guessing again.
                debug_lines.append(f"[{sport}] ZERO matches despite {len(kalshi_market_groups)} open events -- "
                                    f"raw sample of up to 3 Kalshi events (to check our title/ticker assumptions):")
                for group in kalshi_market_groups[:3]:
                    for m in group:
                        debug_lines.append(f"    ticker={m.get('ticker')!r} title={m.get('title')!r} "
                                            f"subtitle={m.get('subtitle')!r} yes_sub_title={m.get('yes_sub_title')!r}")
                debug_lines.append(f"[{sport}] raw sample of up to 3 games from the sportsbook (to compare team-name spelling):")
                for g in games[:3]:
                    debug_lines.append(f"    home={g.get('home_team')!r} away={g.get('away_team')!r}")

    debug_lines.append(f"Scan complete: {rows_written} signal row(s) written to {LOG_PATH}")
    DEBUG_PATH.write_text("\n".join(debug_lines) + "\n")
    print("\n".join(debug_lines))


if __name__ == "__main__":
    run_scan()
