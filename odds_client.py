"""
odds_client.py

Wrapper around The Odds API (https://the-odds-api.com/) — free tier gives
500 requests/month, plenty for daily polling of a few sports. Sign up for
a key, then set ODDS_API_KEY in config.py or as an env var.

Alternative providers if you outgrow the free tier: OddsJam, SportsDataIO.
"""

import os
from typing import Optional

import requests

BASE_URL = "https://api.the-odds-api.com/v4"

SPORT_KEYS = {
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "mlb": "baseball_mlb",
}


class OddsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set ODDS_API_KEY (env var or constructor arg) — get one free at the-odds-api.com")
        self.session = requests.Session()

    def get_odds(self, sport: str, regions: str = "us", markets: str = "h2h", bookmakers: Optional[str] = None) -> list:
        """Returns a list of games, each with a list of bookmakers and their current lines.
        markets='h2h' = moneyline (what we want for a straight de-vig comparison to a Kalshi
        win/lose contract). Use 'spreads' or 'totals' for those contract types instead."""
        sport_key = SPORT_KEYS.get(sport.lower(), sport)
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "american",
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        resp = self.session.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def american_to_implied_prob(american_odds: int) -> float:
        if american_odds > 0:
            return 100 / (american_odds + 100)
        return -american_odds / (-american_odds + 100)
