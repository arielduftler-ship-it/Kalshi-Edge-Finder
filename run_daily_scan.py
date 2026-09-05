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


def match_kalshi_market(home_team: str, away_team: str, sport: str, markets: list):
    """Matches a specific game (home_team vs away_team) to its Kalshi
    'home team wins' market.

    Two separate bugs, both confirmed against real logged data, are fixed here:

    1. Kalshi's `title` field describes the whole matchup and is IDENTICAL
       across every per-team market in that event -- searching for a
       nickname inside `title` matches all of them. Fixed by matching on
       the ticker suffix (the segment after the final "-", e.g. "DET" in
       KXMLBGAME-26SEP021940DETMIN-DET) instead.

    2. The ticker-suffix fix above is necessary but NOT sufficient: The Odds
       API returns every game on a team's schedule (the whole season), while
       Kalshi only has ONE open market per team at a time (their next game).
       Matching on the team abbreviation alone means every future scheduled
       game for, say, the Chiefs gets attached to whichever single Chiefs
       market happens to be open right now -- confirmed in real data, where
       four different "away team @ Kansas City Chiefs" rows all got stapled
       to the same KXNFLGAME-26SEP14DENKC-KC ticker (the Broncos game), even
       though only the Broncos game was real. Fixed by also requiring the
       AWAY team's abbreviation to appear in the ticker's event segment
       (the part between the series prefix and the final "-TEAM" suffix,
       e.g. "26SEP14DENKC" must contain both DEN and KC) -- i.e. verifying
       the whole matchup, not just one side of it.
    """
    home_alias = team_aliases.lookup(sport, home_team)
    away_alias = team_aliases.lookup(sport, away_team)
    away_abbr = away_alias[0] if away_alias else None

    if home_alias:
        home_abbr, home_nick = home_alias
        for m in markets:
            parts = m.get("ticker", "").split("-")
            if len(parts) < 3:
                continue
            suffix = parts[-1].upper()
            event_segment = parts[-2].upper()
            if suffix != home_abbr:
                continue
            if away_abbr and away_abbr not in event_segment:
                # Right team, wrong game -- this Kalshi market belongs to a
                # different matchup for the same team. Keep looking rather
                # than silently attaching the wrong game's price.
                continue
            return m

        # No ticker matched both teams. Fall back to a subtitle nickname
        # search, but only accept it if the away team's name also shows up
        # in the shared title -- otherwise we're back to matching one side
        # of a different game.
        for m in markets:
            subtitle = normalize(m.get("subtitle", ""))
            title = normalize(m.get("title", ""))
            if home_nick not in subtitle:
                continue
            away_ok = (not away_alias) or (away_alias[1] in title) or (normalize(away_team) in title)
            if away_ok:
                print(f"WARNING: {home_team} vs {away_team} matched via subtitle fallback, not ticker "
                      f"(no market ticker matched both teams) -- verify this game manually.")
                return m
        return None  # no open Kalshi market for this specific matchup right now

    # home team not in team_aliases.py at all -- old, fragile last-word
    # heuristic, kept only as a last resort. Loudly flagged so it's never silent.
    print(f"WARNING: '{home_team}' not in team_aliases.py -- falling back to fragile "
          f"last-word nickname matching. Add this team to team_aliases.py.")
    target_nickname = normalize(home_team.split()[-1])
    for m in markets:
        subtitle = normalize(m.get("subtitle", ""))
        if target_nickname and target_nickname in subtitle:
            return m
    return None


def run_scan():
    odds_client = OddsClient()  # reads ODDS_API_KEY from env
    kalshi_client = KalshiClient()  # public endpoints, no auth needed

    LOG_PATH.parent.mkdir(exist_ok=True)
    file_exists = LOG_PATH.exists()

    rows_written = 0
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if not file_exists:
            writer.writeheader()

        for sport, series_ticker in SERIES_TICKERS.items():
            try:
                games = odds_client.get_odds(sport)
            except Exception as e:
                print(f"[{sport}] odds fetch failed: {e}")
                continue

            try:
                events = kalshi_client.get_events(series_ticker=series_ticker)
            except Exception as e:
                print(f"[{sport}] kalshi events fetch failed (check SERIES_TICKERS): {e}")
                continue

            kalshi_markets = []
            for ev in events:
                try:
                    kalshi_markets.extend(kalshi_client.get_markets(event_ticker=ev["event_ticker"]))
                except Exception:
                    continue

            for game in games:
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

                market = match_kalshi_market(home, away, sport, kalshi_markets)
                if not market:
                    continue  # no open Kalshi market for this specific matchup right now

                try:
                    sig = compute_signal(
                        game_label=f"{away} @ {home}", team=home,
                        book_odds_a=out_home["price"], book_odds_b=out_away["price"],
                        kalshi_yes_bid=price_cents(market, "yes_bid"), kalshi_yes_ask=price_cents(market, "yes_ask"),
                        kalshi_ticker=market["ticker"],
                    )
                except Exception as e:
                    print(f"signal calc failed for {home} vs {away}: {e}")
                    continue

                # We're only trading underpriced favorites right now (a real
                # favorite that Kalshi's crowd has priced below 50%) clearing
                # a 1% net edge -- not every matched game or every edge sign.
                # Correctly-priced favorites and overpriced underdogs are
                # skipped entirely so real signals don't get buried.
                if not (sig.net_edge >= 0.01 and is_underpriced_favorite(sig)):
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
                print(f"SIGNAL  {sig.game_label:30s} {sig.side:8s} net_edge={sig.net_edge:+.3f} "
                      f"(favorite @ {sig.kalshi_price:.2f})")

    print(f"Scan complete: {rows_written} rows written to {LOG_PATH}")


if __name__ == "__main__":
    run_scan()
