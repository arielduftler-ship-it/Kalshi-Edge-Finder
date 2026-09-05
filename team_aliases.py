"""
team_aliases.py

Central table mapping sportsbook team names (as returned by The Odds API,
full "City Name" format) to a standard abbreviation, used to match against
Kalshi market tickers and ESPN scoreboard data.

WHY THIS EXISTS
----------------
The original matching logic took the last word of a team's name (e.g. "Red
Sox" -> "Sox") and searched for it inside the Kalshi market's *title* field.
Two problems, both confirmed against real logged data:

1. Nickname collisions: "Boston Red Sox" and "Chicago White Sox" both reduce
   to "Sox". On any day both play, substring matching can't tell them apart.

2. The bigger bug: Kalshi's `title` field describes the whole matchup (e.g.
   "Detroit Tigers at Minnesota Twins") and is IDENTICAL across both
   per-team markets in that event. Searching for a nickname inside `title`
   matches every market in the event, so the function just returned
   whichever one came first in Kalshi's list -- regardless of which team was
   being searched for. This produced a real bad row in scan_log.csv: team
   was logged as "Minnesota Twins" but the attached kalshi_ticker
   (KXMLBGAME-...-DET) was actually the Tigers' contract.

THE FIX
-------
Kalshi's own ticker suffix (the segment after the final "-", e.g. "DET" or
"MIN" in KXMLBGAME-26SEP021940DETMIN-DET) reliably identifies which team a
specific market belongs to. Match on that directly instead of fuzzy text.

VERIFY the abbreviations below against live Kalshi tickers and ESPN team
codes before fully trusting this -- they're standard sports-reference
abbreviations, and matched the one real ticker seen so far (DET/MIN), but
Kalshi doesn't publicly guarantee the convention won't drift.
"""

from typing import Optional, Tuple


def normalize(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


# name -> (kalshi/espn-style abbreviation, disambiguating nickname key)
# The nickname key is the FULL nickname (never just the last word), so
# "Red Sox" -> "redsox" and "White Sox" -> "whitesox" never collide.
NFL = {
    "Arizona Cardinals": ("ARI", "cardinals"),
    "Atlanta Falcons": ("ATL", "falcons"),
    "Baltimore Ravens": ("BAL", "ravens"),
    "Buffalo Bills": ("BUF", "bills"),
    "Carolina Panthers": ("CAR", "panthers"),
    "Chicago Bears": ("CHI", "bears"),
    "Cincinnati Bengals": ("CIN", "bengals"),
    "Cleveland Browns": ("CLE", "browns"),
    "Dallas Cowboys": ("DAL", "cowboys"),
    "Denver Broncos": ("DEN", "broncos"),
    "Detroit Lions": ("DET", "lions"),
    "Green Bay Packers": ("GB", "packers"),
    "Houston Texans": ("HOU", "texans"),
    "Indianapolis Colts": ("IND", "colts"),
    "Jacksonville Jaguars": ("JAX", "jaguars"),
    "Kansas City Chiefs": ("KC", "chiefs"),
    "Las Vegas Raiders": ("LV", "raiders"),
    "Los Angeles Chargers": ("LAC", "chargers"),
    "Los Angeles Rams": ("LAR", "rams"),
    "Miami Dolphins": ("MIA", "dolphins"),
    "Minnesota Vikings": ("MIN", "vikings"),
    "New England Patriots": ("NE", "patriots"),
    "New Orleans Saints": ("NO", "saints"),
    "New York Giants": ("NYG", "giants"),
    "New York Jets": ("NYJ", "jets"),
    "Philadelphia Eagles": ("PHI", "eagles"),
    "Pittsburgh Steelers": ("PIT", "steelers"),
    "San Francisco 49ers": ("SF", "49ers"),
    "Seattle Seahawks": ("SEA", "seahawks"),
    "Tampa Bay Buccaneers": ("TB", "buccaneers"),
    "Tennessee Titans": ("TEN", "titans"),
    "Washington Commanders": ("WAS", "commanders"),
}

NBA = {
    "Atlanta Hawks": ("ATL", "hawks"),
    "Boston Celtics": ("BOS", "celtics"),
    "Brooklyn Nets": ("BKN", "nets"),
    "Charlotte Hornets": ("CHA", "hornets"),
    "Chicago Bulls": ("CHI", "bulls"),
    "Cleveland Cavaliers": ("CLE", "cavaliers"),
    "Dallas Mavericks": ("DAL", "mavericks"),
    "Denver Nuggets": ("DEN", "nuggets"),
    "Detroit Pistons": ("DET", "pistons"),
    "Golden State Warriors": ("GSW", "warriors"),
    "Houston Rockets": ("HOU", "rockets"),
    "Indiana Pacers": ("IND", "pacers"),
    "LA Clippers": ("LAC", "clippers"),
    "Los Angeles Clippers": ("LAC", "clippers"),
    "Los Angeles Lakers": ("LAL", "lakers"),
    "Memphis Grizzlies": ("MEM", "grizzlies"),
    "Miami Heat": ("MIA", "heat"),
    "Milwaukee Bucks": ("MIL", "bucks"),
    "Minnesota Timberwolves": ("MIN", "timberwolves"),
    "New Orleans Pelicans": ("NOP", "pelicans"),
    "New York Knicks": ("NYK", "knicks"),
    "Oklahoma City Thunder": ("OKC", "thunder"),
    "Orlando Magic": ("ORL", "magic"),
    "Philadelphia 76ers": ("PHI", "76ers"),
    "Phoenix Suns": ("PHX", "suns"),
    "Portland Trail Blazers": ("POR", "trailblazers"),
    "Sacramento Kings": ("SAC", "kings"),
    "San Antonio Spurs": ("SAS", "spurs"),
    "Toronto Raptors": ("TOR", "raptors"),
    "Utah Jazz": ("UTA", "jazz"),
    "Washington Wizards": ("WAS", "wizards"),
}

MLB = {
    "Arizona Diamondbacks": ("ARI", "diamondbacks"),
    "Atlanta Braves": ("ATL", "braves"),
    "Athletics": ("ATH", "athletics"),  # officially just "Athletics" since leaving Oakland; verify if this changes
    "Baltimore Orioles": ("BAL", "orioles"),
    "Boston Red Sox": ("BOS", "redsox"),
    "Chicago Cubs": ("CHC", "cubs"),
    "Chicago White Sox": ("CWS", "whitesox"),
    "Cincinnati Reds": ("CIN", "reds"),
    "Cleveland Guardians": ("CLE", "guardians"),
    "Colorado Rockies": ("COL", "rockies"),
    "Detroit Tigers": ("DET", "tigers"),
    "Houston Astros": ("HOU", "astros"),
    "Kansas City Royals": ("KC", "royals"),
    "Los Angeles Angels": ("LAA", "angels"),
    "Los Angeles Dodgers": ("LAD", "dodgers"),
    "Miami Marlins": ("MIA", "marlins"),
    "Milwaukee Brewers": ("MIL", "brewers"),
    "Minnesota Twins": ("MIN", "twins"),
    "New York Mets": ("NYM", "mets"),
    "New York Yankees": ("NYY", "yankees"),
    "Philadelphia Phillies": ("PHI", "phillies"),
    "Pittsburgh Pirates": ("PIT", "pirates"),
    "San Diego Padres": ("SD", "padres"),
    "San Francisco Giants": ("SF", "giants"),
    "Seattle Mariners": ("SEA", "mariners"),
    "St. Louis Cardinals": ("STL", "cardinals"),
    "Tampa Bay Rays": ("TB", "rays"),
    "Texas Rangers": ("TEX", "rangers"),
    "Toronto Blue Jays": ("TOR", "bluejays"),
    "Washington Nationals": ("WSH", "nationals"),
}

ALL_TEAMS = {"nfl": NFL, "nba": NBA, "mlb": MLB}


def lookup(sport: str, team_name: str) -> Optional[Tuple[str, str]]:
    """Returns (abbreviation, nickname_key) for a known team, or None if the
    exact name isn't in the table (e.g. The Odds API used an unexpected
    naming variant -- extend the table above rather than silently guessing)."""
    return ALL_TEAMS.get(sport.lower(), {}).get(team_name)
