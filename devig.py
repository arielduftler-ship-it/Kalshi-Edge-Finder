"""
devig.py

Sportsbook moneyline odds embed a margin (the vig) -- the two implied
probabilities sum to more than 1.0. To compare a book's line to Kalshi's
price on equal footing, strip the vig out first.

Two single-book methods:

1. Multiplicative (basic): normalize both implied probabilities so they
   sum to 1. Fast, standard, but assumes the vig is spread proportionally
   across both sides -- often not true for lopsided favorites.

2. Shin's method: solves for a single "insider trading" parameter z that
   better handles favorite-longshot bias (books shade vig disproportionately
   onto longshots). More accurate on skewed lines, e.g. big favorites.
   Reference: Shin, H.S. (1993), "Measuring the Incidence of Insider Trading
   in a Market for State-Contingent Claims."

Plus a multi-book benchmark:

3. Sharp-weighted consensus (sharp_weighted_consensus): de-vig every book
   individually, then combine them into one fair probability with weights
   that lean heavily on sharp prices. Pinnacle's API is closed to the public,
   so the benchmark is built from the sharpest prices The Odds API carries:

     - Exchanges (Betfair, Matchbook, Smarkets, Novig, ProphetX): prices set
       by bettors trading against each other at low commission, including
       professionals -- the closest free stand-in for a sharp book.
     - Sharp-leaning books (BetOnline, LowVig): offshore books known for
       moving early with sharp money and running low margins.
     - Soft books (DraftKings, FanDuel, BetMGM): shade lines toward public
       money. Kept only at a token weight so they can't drag the benchmark
       toward the same fan bias we're trying to measure on Kalshi.

   Books are combined in log-odds space (a weighted average of logit(p)),
   which treats a move from 90% -> 92% as bigger than 50% -> 52%, the way
   the underlying odds actually behave.

   Prediction markets (Kalshi, Polymarket) are NEVER part of the benchmark:
   comparing Kalshi to a benchmark that includes Kalshi would be circular.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import math


# ---------------------------------------------------------------------------
# Single-book de-vig
# ---------------------------------------------------------------------------

def american_to_implied_prob(american_odds: float) -> float:
    if american_odds > 0:
        return 100 / (american_odds + 100)
    return -american_odds / (-american_odds + 100)


def multiplicative_devig(prob_a: float, prob_b: float) -> Tuple[float, float]:
    """prob_a, prob_b are the raw implied probabilities (with vig) for the two
    sides of a two-way market. Returns (fair_prob_a, fair_prob_b) summing to 1."""
    total = prob_a + prob_b
    return prob_a / total, prob_b / total


def shin_devig(prob_a: float, prob_b: float, tol: float = 1e-10, max_iter: int = 100) -> Tuple[float, float]:
    """Solve for Shin's z via bisection, then back out fair probabilities.

    Shin's formula for a two-outcome market:
        p_a = ( sqrt(z^2 + 4*(1-z)*z*prob_a^2/total) - z ) / (2*(1-z))
    where 'total' is the sum of raw implied probabilities (the overround).

    Falls back to multiplicative de-vig if the market has no overround
    (total <= 1) since Shin's method is only meaningful with a vig present.
    Exchange prices often sit at or just under 1.0 (commission is charged on
    winnings, not baked into the price), so this fallback matters there.
    """
    total = prob_a + prob_b
    if total <= 1.0:
        return multiplicative_devig(prob_a, prob_b)

    def implied_total(z: float) -> float:
        fa = (math.sqrt(z ** 2 + 4 * (1 - z) * z * prob_a ** 2 / total) - z) / (2 * (1 - z))
        fb = (math.sqrt(z ** 2 + 4 * (1 - z) * z * prob_b ** 2 / total) - z) / (2 * (1 - z))
        return fa + fb

    lo, hi = 1e-9, 0.2  # z is typically small (a few percent); widen hi if this fails to bracket
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if implied_total(mid) > 1.0:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    z = (lo + hi) / 2
    fa = (math.sqrt(z ** 2 + 4 * (1 - z) * z * prob_a ** 2 / total) - z) / (2 * (1 - z))
    fb = (math.sqrt(z ** 2 + 4 * (1 - z) * z * prob_b ** 2 / total) - z) / (2 * (1 - z))
    norm = fa + fb  # renormalize for numerical drift
    return fa / norm, fb / norm


def overround(prob_a: float, prob_b: float) -> float:
    """The book's total hold/vig, e.g. 0.045 = 4.5%."""
    return prob_a + prob_b - 1.0


# ---------------------------------------------------------------------------
# Sharp-weighted multi-book consensus
# ---------------------------------------------------------------------------

# The Odds API bookmaker keys -> (tier, weight). Keep this list at 10 books or
# fewer: The Odds API bills every group of 10 bookmakers like one region, so
# 10 books = 1 credit per sport per scan.
BOOK_WEIGHTS: Dict[str, Tuple[str, float]] = {
    # Exchanges -- heaviest weight
    "betfair_ex_eu": ("exchange", 3.0),
    "matchbook":     ("exchange", 3.0),
    "smarkets":      ("exchange", 3.0),
    "novig":         ("exchange", 3.0),
    "prophetx":      ("exchange", 3.0),
    # Sharp-leaning books
    "betonlineag":   ("sharp", 2.0),
    "lowvig":        ("sharp", 2.0),
    # Soft books -- token weight only, used mainly as a sanity check
    "draftkings":    ("soft", 0.25),
    "fanduel":       ("soft", 0.25),
    "betmgm":        ("soft", 0.25),
}

# Never let these into the benchmark (circular -- we're trading against them).
EXCLUDED_BOOKS = {"kalshi", "polymarket"}

# Any book not in BOOK_WEIGHTS is treated as soft.
UNKNOWN_BOOK = ("soft", 0.25)

# Data-quality filters. Exchange prices on US sports can be thin or stale, so
# a bad quote is dropped rather than allowed to move the benchmark.
MAX_QUOTE_AGE_HOURS = 3.0   # ignore a book's line if it hasn't updated recently
MAX_OVERROUND = 0.10        # >10% hold = stale/wide quote, drop it
MIN_OVERROUND = -0.02       # sides summing well under 100% = crossed/stale, drop it


def book_tier(book_key: str) -> Tuple[str, float]:
    return BOOK_WEIGHTS.get(book_key, UNKNOWN_BOOK)


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _inv_logit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class Consensus:
    fair_home: float                 # sharp-weighted fair probability the home team wins
    avg_overround: float             # weight-averaged hold across books used
    books_used: List[str]            # bookmaker keys that made it through the filters
    sharp_share: float               # share of total weight from exchanges + sharp books (0-1)
    per_book: Dict[str, float] = field(default_factory=dict)       # book -> its own de-vigged home prob
    dropped: Dict[str, str] = field(default_factory=dict)          # book -> reason it was excluded

    @property
    def n_books(self) -> int:
        return len(self.books_used)

    @property
    def n_sharp(self) -> int:
        return sum(1 for b in self.books_used if book_tier(b)[0] != "soft")


def sharp_weighted_consensus(
    bookmakers: list,
    home_team: str,
    away_team: str,
    now: Optional[datetime] = None,
    method: str = "shin",
    require_sharp: bool = True,
) -> Optional[Consensus]:
    """bookmakers: the 'bookmakers' list for one game from The Odds API
    (each with 'key', 'last_update', and a 'markets' list containing 'h2h').

    Returns None if no usable book survives the filters, or -- when
    require_sharp=True (the default) -- if only soft books are available.
    A soft-only benchmark is exactly what this project is trying to avoid,
    so those games are skipped rather than scored."""
    now = now or datetime.now(timezone.utc)
    devig_fn = shin_devig if method == "shin" else multiplicative_devig

    weighted_logit = 0.0
    weighted_overround = 0.0
    total_weight = 0.0
    sharp_weight = 0.0
    used: List[str] = []
    per_book: Dict[str, float] = {}
    dropped: Dict[str, str] = {}

    for book in bookmakers:
        key = book.get("key", "")
        if key in EXCLUDED_BOOKS:
            dropped[key] = "prediction market (excluded)"
            continue

        updated = _parse_ts(book.get("last_update"))
        if updated is not None and (now - updated).total_seconds() > MAX_QUOTE_AGE_HOURS * 3600:
            dropped[key] = f"stale (>{MAX_QUOTE_AGE_HOURS:g}h old)"
            continue

        h2h = next((m for m in book.get("markets", []) if m.get("key") == "h2h"), None)
        if not h2h:
            dropped[key] = "no h2h market"
            continue
        outcomes = h2h.get("outcomes", [])
        o_home = next((o for o in outcomes if o.get("name") == home_team), None)
        o_away = next((o for o in outcomes if o.get("name") == away_team), None)
        if not o_home or not o_away or len(outcomes) != 2:
            dropped[key] = "missing a side"
            continue

        try:
            p_home = american_to_implied_prob(float(o_home["price"]))
            p_away = american_to_implied_prob(float(o_away["price"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            dropped[key] = "bad price"
            continue

        hold = overround(p_home, p_away)
        if hold > MAX_OVERROUND:
            dropped[key] = f"hold {hold:.1%} too wide"
            continue
        if hold < MIN_OVERROUND:
            dropped[key] = f"hold {hold:.1%} (crossed/stale)"
            continue

        fair_home, _ = devig_fn(p_home, p_away)
        tier, weight = book_tier(key)

        weighted_logit += weight * _logit(fair_home)
        weighted_overround += weight * hold
        total_weight += weight
        if tier != "soft":
            sharp_weight += weight
        used.append(key)
        per_book[key] = fair_home

    if total_weight == 0:
        return None
    if require_sharp and sharp_weight == 0:
        return None

    return Consensus(
        fair_home=_inv_logit(weighted_logit / total_weight),
        avg_overround=weighted_overround / total_weight,
        books_used=used,
        sharp_share=sharp_weight / total_weight,
        per_book=per_book,
        dropped=dropped,
    )
