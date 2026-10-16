"""
kelly.py

Kelly criterion position sizing for Kalshi binary contracts.

The math
--------
A Kalshi YES contract costs `price` and pays $1 if the event happens. Add the
per-contract taker fee and your all-in cost per contract is

    cost = price + fee

If you win, you profit (1 - cost) per contract; if you lose, you lose `cost`.
So the net odds are b = (1 - cost) / cost, and plugging into the standard
Kelly formula f* = (p*b - q) / b simplifies to:

    f* = (p - cost) / (1 - cost)

i.e. your edge over the all-in price, divided by what you stand to win per
contract. Note that `p - cost` is exactly the scanner's `net_edge`
(book_fair_prob - ask - fee), so f* = net_edge / (1 - cost).

Why we don't bet full Kelly
---------------------------
Full Kelly is only optimal if `p` is the TRUE probability. Ours is a
de-vigged sportsbook estimate, which has error -- and overbetting a
mis-estimated edge is far worse than underbetting it (growth falls off a
cliff past 2x Kelly). So sizing goes through three guardrails:

  1. KELLY_MULTIPLIER  -- bet a fraction of Kelly (quarter Kelly by default).
  2. MAX_BET_FRACTION  -- hard cap on any single bet as a share of bankroll.
                          Huge edges are more often bad data (stale quote,
                          mismatched ticker) than real, so they should NOT
                          get huge bets.
  3. MAX_DAILY_EXPOSURE -- cap on total bankroll committed to games settling
                          on the same day. Kelly fractions computed one bet
                          at a time assume you place them sequentially; when
                          several are live at once, naively summing them
                          over-commits the bankroll.
"""

import math
from dataclasses import dataclass
from typing import List

KELLY_MULTIPLIER = 0.25      # quarter Kelly
MAX_BET_FRACTION = 0.05      # never more than 5% of bankroll on one game
MAX_DAILY_EXPOSURE = 0.25    # never more than 25% of bankroll on one day's slate


def kelly_fraction(p: float, price: float, fee_per_contract: float = 0.0) -> float:
    """Full-Kelly fraction of bankroll for buying a YES contract.

    p:                 your estimated win probability (book_fair_prob)
    price:             the price you pay per contract, in dollars (the ask)
    fee_per_contract:  Kalshi taker fee per contract, in dollars

    Returns 0 when there's no positive edge (Kelly says don't bet)."""
    cost = price + fee_per_contract
    if not (0 < cost < 1) or not (0 < p < 1):
        return 0.0
    return max(0.0, (p - cost) / (1 - cost))


def sized_fraction(
    p: float,
    price: float,
    fee_per_contract: float = 0.0,
    multiplier: float = KELLY_MULTIPLIER,
    max_bet: float = MAX_BET_FRACTION,
) -> float:
    """Fractional Kelly with the single-bet cap applied."""
    return min(kelly_fraction(p, price, fee_per_contract) * multiplier, max_bet)


@dataclass
class BetSize:
    full_kelly: float     # raw Kelly fraction, for reference / logging
    fraction: float       # final share of bankroll after all guardrails
    stake: float          # dollars actually spent (contracts * all-in cost)
    contracts: int


def size_slate(
    bets: List[dict],
    bankroll: float,
    multiplier: float = KELLY_MULTIPLIER,
    max_bet: float = MAX_BET_FRACTION,
    max_exposure: float = MAX_DAILY_EXPOSURE,
) -> List[BetSize]:
    """Size a group of bets that are all open at the same time (e.g. one day's
    games). Each bet dict needs keys: p, price, fee.

    Every bet is sized off the SAME starting bankroll (you don't know the
    other results yet), then all fractions are scaled down proportionally
    if their total would exceed max_exposure. Contracts are floored to whole
    numbers, so the realized stake is always <= the target."""
    fulls = [kelly_fraction(b["p"], b["price"], b["fee"]) for b in bets]
    fracs = [min(f * multiplier, max_bet) for f in fulls]

    total = sum(fracs)
    if total > max_exposure:
        scale = max_exposure / total
        fracs = [f * scale for f in fracs]

    out = []
    for b, full, frac in zip(bets, fulls, fracs):
        cost = b["price"] + b["fee"]
        contracts = math.floor(bankroll * frac / cost) if cost > 0 else 0
        out.append(BetSize(
            full_kelly=full,
            fraction=frac,
            stake=contracts * cost,
            contracts=contracts,
        ))
    return out


if __name__ == "__main__":
    # Sanity check on two real logged signals.
    # Braves: p=0.525, ask=0.43, fee=0.0172 -> modest edge, modest bet
    # Phillies: p=0.6522, ask=0.31, fee=0.015 -> full Kelly says ~48% of
    #   bankroll, which is the cap's whole reason for existing.
    for name, p, price, fee in [("Braves", 0.525, 0.43, 0.0172),
                                ("Phillies", 0.6522, 0.31, 0.015)]:
        fk = kelly_fraction(p, price, fee)
        print(f"{name:9s} full Kelly={fk:6.1%}  quarter={fk * 0.25:6.1%}  "
              f"after cap={sized_fraction(p, price, fee):6.1%}")
