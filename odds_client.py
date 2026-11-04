"""
odds_client.py

Wrapper around The Odds API (https://the-odds-api.com/) -- free tier gives
500 credits/month. Set ODDS_API_KEY as an env var (a GitHub Actions secret
in production).

By default every request asks for a fixed list of bookmakers (see
devig.BOOK_WEIGHTS) instead of a whole region. That list is weighted toward
exchanges and sharp-leaning books, and is capped at 10 books so each call
still costs 1 credit per sport.
"""

import os
from typing import Optional

import requests

from devig import BOOK_WEIGHTS, american_to_implied_prob

BASE_URL = "https://api.the-odds-api.com/v4"

SPORT_KEYS = {
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
}

# Comma-separated list passed to the API's `bookmakers` parameter.
BENCHMARK_BOOKS = ",".join(BOOK_WEIGHTS.keys())


class OddsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set ODDS_API_KEY (env var or constructor arg) -- get one free at the-odds-api.com")
        self.session = requests.Session()
        self.last_requests_remaining: Optional[str] = None
        self.last_requests_used: Optional[str] = None

    def get_odds(self, sport: str, markets: str = "h2h", bookmakers: Optional[str] = BENCHMARK_BOOKS,
                 regions: str = "us") -> list:
        """Returns a list of games, each with a list of bookmakers and their current lines.
        When `bookmakers` is set (the default), The Odds API ignores `regions`.
        markets='h2h' = moneyline, the right comparison for a Kalshi win/lose contract."""
        sport_key = SPORT_KEYS.get(sport.lower(), sport)
        params = {
            "apiKey": self.api_key,
            "markets": markets,
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        else:
            params["regions"] = regions
        resp = self.session.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=15)
        resp.raise_for_status()
        # Track credit usage so the debug file shows how close we are to the monthly cap.
        self.last_requests_remaining = resp.headers.get("x-requests-remaining")
        self.last_requests_used = resp.headers.get("x-requests-used")
        return resp.json()

    @staticmethod
    def american_to_implied_prob(american_odds: int) -> float:
        return american_to_implied_prob(american_odds)
