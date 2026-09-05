"""
espn_client.py

Thin wrapper around ESPN's public scoreboard JSON API. Undocumented by ESPN
officially, but widely used and stable for years — no API key needed.
Reference: https://github.com/pseudo-r/Public-ESPN-API
"""

import requests

BASE_URL = "http://site.api.espn.com/apis/site/v2/sports"

SPORT_PATHS = {
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "mlb": "baseball/mlb",
}


class ESPNClient:
    def __init__(self):
        self.session = requests.Session()

    def get_scoreboard(self, sport: str, date: str) -> list:
        """date: 'YYYYMMDD' string. Returns a list of game dicts: home/away
        team names, scores, whether the game is completed, and who won."""
        path = SPORT_PATHS.get(sport.lower())
        if not path:
            raise ValueError(f"Unknown sport '{sport}' — add it to SPORT_PATHS")
        url = f"{BASE_URL}/{path}/scoreboard"
        resp = self.session.get(url, params={"dates": date}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        games = []
        for event in data.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors", [])
            if len(competitors) != 2:
                continue

            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            status = (event.get("status") or {}).get("type", {})
            games.append({
                "home_team": (home.get("team") or {}).get("displayName", ""),
                "away_team": (away.get("team") or {}).get("displayName", ""),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
                "completed": bool(status.get("completed", False)),
                "home_won": bool(home.get("winner", False)),
                "away_won": bool(away.get("winner", False)),
            })
        return games
