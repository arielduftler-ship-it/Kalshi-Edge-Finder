"""
run_daily_scan.py

Pulls live sportsbook odds + Kalshi market prices for NFL/NBA/MLB, computes
a signal for every game where we can match the two sources, and appends the
results to data/scan_log.csv. Run this daily (see .github/workflows/daily_scan.yml)
to build the historical dataset a real backtest needs.

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
from edge_engine import compute_signal
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


def match_kalshi_market(team_name: str, sport: str, markets: list):
    """Matches a team to its Kalshi 'this team wins' market.

    Kalshi's `title` field describes the whole matchup (e.g. "Detroit Tigers
    at Minnesota Twins") and is IDENTICAL across every per-team market in
    that event -- searching for a nickname inside `title` matches all of
    them, not just the one you want. This produced a confirmed bad row in
    scan_log.csv where "Minnesota Twins" was logged against the Tigers'
    market by accident.

    Fix: Kalshi's ticker suffix (the segment after the final "-", e.g. "DET"
    in KXMLBGAME-26SEP021940DETMIN-DET) reliably identifies which team a
    specific market belongs to. Match on that. Falls back to a disambiguated
    full-nickname search of `subtitle` (never `title`, and never just the
    last word) if the team isn't in team_aliases yet or no ticker matches --
    and prints a warning so a silent/fragile match is never invisible.
    """
    alias = team_aliases.lookup(sport, team_name)

    if alias:
        abbr, nickname_key = alias
        for m in markets:
            ticker_suffix = m.get("ticker", "").split("-")[-1].upper()
            if ticker_suffix == abbr:
                return m
        # Abbreviation didn't hit any ticker -- fall through to nickname
        # search on subtitle only, using the FULL disambiguated nickname.
        for m in markets:
            subtitle = normalize(m.get("subtitle", ""))
            if nickname_key in subtitle:
                print(f"WARNING: {team_name} matched via subtitle fallback, not ticker suffix "
                      f"(no market ticker ended in -{abbr}) -- verify this game manually.")
                return m
        print(f"WARNING: no Kalshi market found for {team_name} ({sport}) via ticker or subtitle.")
        return None

    # Team not in team_aliases.py at all -- old, fragile last-word heuristic,
    # kept only as a last resort. Loudly flagged so it's never silent.
    print(f"WARNING: '{team_name}' not in team_aliases.py -- falling back to fragile "
          f"last-word nickname matching. Add this team to team_aliases.py.")
    target_nickname = normalize(team_name.split()[-1])
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

                market = match_kalshi_market(home, sport, kalshi_markets)
                if not market:
                    continue  # no matching Kalshi market found for this game

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
                if sig.net_edge >= 0.01:
                    print(f"SIGNAL  {sig.game_label:30s} {sig.side:8s} net_edge={sig.net_edge:+.3f}")

    print(f"Scan complete: {rows_written} rows written to {LOG_PATH}")


if __name__ == "__main__":
    run_scan()
