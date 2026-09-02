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
    "kalshi_price", "raw_edge", "net_edge", "side", "kalshi_ticker",
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


def match_kalshi_market(team_name: str, markets: list):
    """Very simple substring match between a team name and Kalshi market
    titles. Sportsbook team names ('Kansas City Chiefs') and Kalshi market
    titles won't always line up cleanly — inspect misses and extend this
    (e.g. a manual alias dict) as you find them."""
    target = normalize(team_name)
    for m in markets:
        title = normalize(m.get("title", "") + m.get("subtitle", ""))
        # try last word of team name (usually the nickname, e.g. "Chiefs")
        nickname = normalize(team_name.split()[-1])
        if nickname and nickname in title:
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

                market = match_kalshi_market(home, kalshi_markets)
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
                    "raw_edge": round(sig.raw_edge, 4), "net_edge": round(sig.net_edge, 4),
                    "side": sig.side, "kalshi_ticker": sig.kalshi_ticker,
                })
                rows_written += 1
                if sig.net_edge >= 0.03:
                    print(f"SIGNAL  {sig.game_label:30s} {sig.side:8s} net_edge={sig.net_edge:+.3f}")

    print(f"Scan complete: {rows_written} rows written to {LOG_PATH}")


if __name__ == "__main__":
    run_scan()
