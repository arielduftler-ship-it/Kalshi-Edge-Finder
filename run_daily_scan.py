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
from datetime import datetime, timezone
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

LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"
LOG_FIELDS = [
    "scan_timestamp", "sport", "game_label", "team", "book_fair_prob",
    "kalshi_price", "entry_price", "raw_edge", "fee_cost", "spread_cost",
    "net_edge", "side", "kalshi_ticker", "outcome",
]


def normalize(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def price_cents(market: dict, side: str) -> int:
    """Kalshi's current API returns prices as dollar strings
    (e.g. yes_bid_dollars: "0.5600"), not plain integer cents.
    Falls back to the older cents-integer field if present."""
    dollars_key = f"{side}_dollars"
    if dollars_key in market and market[dollars_key] is not None:
        return int(round(float(market[dollars_key]) * 100))
    return int(market[side])


def match_kalshi_market(home_team: str, away_team: str, sport: str, market_groups: list):
    """Matches a specific game (home_team vs away_team) to its Kalshi
    'home team wins' market. `market_groups` is a list of lists -- each
    inner list holds the markets belonging to ONE Kalshi event (so grouping
    is preserved, not flattened into one big pool).

    Three separate bugs, all confirmed against real logged data, are fixed here:

    1. Kalshi's `title` field describes the whole matchup and is IDENTICAL
       across every per-team market in that event -- searching for a
       nickname inside `title` alone (without also pinning down which
       market within the event) matches all of them.

    2. Matching on a team's abbreviation ALONE isn't enough either: The Odds
       API returns a team's entire season schedule, while Kalshi only has
       ONE open market per team at a time (their next game). Naive
       abbreviation matching attached every future Chiefs game to whichever
       single Chiefs market happened to be open (confirmed: four different
       "@ Kansas City Chiefs" rows all got the same Broncos-game ticker).

    3. The first fix for #2 tried to verify the opponent by checking whether
       their abbreviation appeared as a substring of the ticker's
       concatenated date+teams segment (e.g. "26SEP14DENKC"). This backfires
       when one team's short code is spelled out by the *boundary* between
       two other teams' codes -- confirmed: "DETBUF" (Lions vs Bills)
       contains the letters "T"+"B" back to back, which false-matched as
       "TB" (Buccaneers), silently logging a real Lions/Bills market as a
       Buccaneers/Lions signal, for the wrong week.

    The fix for all of this: identify the correct EVENT first, using the
    full, space-separated team names in `title` (e.g. "Detroit Lions at
    Buffalo Bills") rather than concatenated short codes -- multi-letter
    nicknames like "buccaneers" and "bills" don't collide the way 2-3 letter
    abbreviations do. Only once the event is confirmed to be the right
    matchup do we use the ticker suffix to pick between that event's two
    markets (which is safe, since there are only ever two, one per team).
    """
    home_alias = team_aliases.lookup(sport, home_team)
    away_alias = team_aliases.lookup(sport, away_team)
    home_nick = home_alias[1] if home_alias else normalize(home_team.split()[-1])
    home_abbr = home_alias[0] if home_alias else None
    away_nick = away_alias[1] if away_alias else normalize(away_team.split()[-1])

    if not home_alias:
        print(f"WARNING: '{home_team}' not in team_aliases.py -- matching on a fragile "
              f"last-word nickname instead of a verified abbreviation. Add this team to team_aliases.py.")

    for markets in market_groups:
        if not markets:
            continue
        # title is shared across every market in this event -- use it once
        # to confirm this is the right game before picking a specific market.
        title = normalize(markets[0].get("title", ""))
        if home_nick not in title or away_nick not in title:
            continue  # wrong event entirely

        if home_abbr:
            for m in markets:
                if m.get("ticker", "").split("-")[-1].upper() == home_abbr:
                    return m
        # Right event, but no ticker suffix matched the known abbreviation
        # (or we don't have one on file) -- fall back to the per-market
        # subtitle, which should name just this one team.
        for m in markets:
            if home_nick in normalize(m.get("subtitle", "")):
                print(f"WARNING: {home_team} vs {away_team} matched via subtitle fallback within "
                      f"the confirmed event, not ticker suffix -- verify this game manually.")
                return m

    return None  # no open Kalshi event found for this specific matchup right now


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
            counts = {"games_from_book": 0, "no_market_matched": 0, "matched_not_signal": 0, "signals": 0}
            near_misses = []  # sample of matched-but-not-a-signal games, for visibility

            try:
                games = odds_client.get_odds(sport)
            except Exception as e:
                debug_lines.append(f"[{sport}] odds fetch FAILED: {e}")
                continue

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

            for game in games:
                counts["games_from_book"] += 1
                home, away = game.get("home_team"), game.get("away_team")
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

                market = match_kalshi_market(home, away, sport, kalshi_market_groups)
                if not market:
                    counts["no_market_matched"] += 1
                    continue  # no open Kalshi market for this specific matchup right now

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
                f"[{sport}] {counts['games_from_book']} games from book, "
                f"{len(kalshi_market_groups)} Kalshi events open, "
                f"{counts['no_market_matched']} had no matching Kalshi event, "
                f"{counts['matched_not_signal']} matched but weren't underpriced-favorite signals, "
                f"{counts['signals']} signals."
            )
            if near_misses:
                debug_lines.append(f"[{sport}] sample of matched-but-not-signal games (favorite must have kalshi<0.5):")
                debug_lines.extend(near_misses)

    debug_lines.append(f"Scan complete: {rows_written} signal row(s) written to {LOG_PATH}")
    DEBUG_PATH.write_text("\n".join(debug_lines) + "\n")
    print("\n".join(debug_lines))


if __name__ == "__main__":
    run_scan()
