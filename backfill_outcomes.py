"""
backfill_outcomes.py

Fills in the 'outcome' column of data/scan_log.csv using ESPN's public
scoreboard API. 'outcome' = 'yes' if the logged team (always the home team —
see match_kalshi_market in run_daily_scan.py) won, 'no' if they lost, left
blank if the game hasn't finished yet. This matches Kalshi's own YES = home
team wins convention used when the signal was originally computed.

Uses team_aliases.py for matching rather than a bare last-word nickname
(see run_daily_scan.py's match_kalshi_market docstring for why the naive
approach is unsafe — "Red Sox" and "White Sox" both reduce to "Sox").

Run periodically (daily is fine — settled games don't un-settle):
    python backfill_outcomes.py
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

from espn_client import ESPNClient
import team_aliases

LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"


def _team_matches(logged_team: str, sport: str, espn_team_name: str) -> bool:
    """True if espn_team_name (ESPN's displayName, e.g. 'Boston Red Sox')
    refers to the same team as logged_team (The Odds API's name for it)."""
    alias = team_aliases.lookup(sport, logged_team)
    if alias:
        _, nickname_key = alias
        return nickname_key in team_aliases.normalize(espn_team_name)
    # Not in the table — fall back to a loud, fragile last-word match.
    print(f"WARNING: '{logged_team}' not in team_aliases.py during backfill — "
          f"falling back to fragile last-word matching. Add this team to team_aliases.py.")
    nickname = team_aliases.normalize(logged_team.split()[-1])
    return bool(nickname) and nickname in team_aliases.normalize(espn_team_name)


def find_result(espn: ESPNClient, sport: str, date_str: str, team_name: str):
    """Search the scan date and the following day (a night game can finish
    after midnight UTC) for a completed game involving team_name."""
    scan_date = datetime.strptime(date_str, "%Y%m%d")
    for offset in (0, 1):
        date = (scan_date + timedelta(days=offset)).strftime("%Y%m%d")
        try:
            games = espn.get_scoreboard(sport, date)
        except Exception as e:
            print(f"ESPN fetch failed for {sport} {date}: {e}")
            continue
        for g in games:
            if not g["completed"]:
                continue
            if _team_matches(team_name, sport, g["home_team"]):
                return "yes" if g["home_won"] else "no"
            if _team_matches(team_name, sport, g["away_team"]):
                # we only ever log the HOME team as 'team' — this branch is a
                # safety net in case that assumption ever changes.
                return "yes" if g["away_won"] else "no"
    return None


def backfill():
    if not LOG_PATH.exists():
        print(f"No log file at {LOG_PATH} yet — run run_daily_scan.py first.")
        return

    with open(LOG_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Log file is empty.")
        return

    espn = ESPNClient()
    updated = 0

    for row in rows:
        if row.get("outcome"):
            continue  # already backfilled

        # Use the actual game date when we have it (game_time -- added once
        # we started scanning up to a week ahead, so scan_timestamp and the
        # game's real date can now be days apart). Older rows logged before
        # this column existed fall back to scan_timestamp, which is only
        # reliable for same-day signals.
        date_source = row.get("game_time") or row["scan_timestamp"]
        search_date = date_source[:10].replace("-", "")  # 'YYYY-MM-DD...' -> 'YYYYMMDD'
        result = find_result(espn, row["sport"], search_date, row["team"])
        if result:
            row["outcome"] = result
            updated += 1

    if updated:
        with open(LOG_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print(f"Backfilled {updated} outcome(s) out of {len(rows)} logged rows.")


if __name__ == "__main__":
    backfill()
