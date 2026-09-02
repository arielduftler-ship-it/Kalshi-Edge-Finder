"""
devig.py

Sportsbook moneyline odds embed a margin (the vig) — the two implied
probabilities sum to more than 1.0. To compare a book's line to Kalshi's
price on equal footing, strip the vig out first.

Two methods:

1. Multiplicative (basic): normalize both implied probabilities so they
   sum to 1. Fast, standard, but assumes the vig is spread proportionally
   across both sides — often not true for lopsided favorites.

2. Shin's method: solves for a single "insider trading" parameter z that
   better handles favorite-longshot bias (books shade vig disproportionately
   onto longshots). More accurate on skewed lines, e.g. big favorites.
   Reference: Shin, H.S. (1993), "Measuring the Incidence of Insider Trading
   in a Market for State-Contingent Claims."
"""

from typing import Tuple
import math


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
