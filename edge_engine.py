"""
edge_engine.py

Ties kalshi_client + odds_client + devig together into a signal:

    1. Pull the sportsbook's fair (de-vigged) win probability for a team.
    2. Pull Kalshi's current market price for the matching "Team wins" contract.
    3. Compute the raw edge = fair_prob - kalshi_prob.
    4. Net out Kalshi's taker fee and half the bid-ask spread (a rough
       execution-cost estimate) to get a tradeable edge.
    5. Flag it if the tradeable edge clears your minimum threshold.

This module works on plain dicts/dataclasses so it's easy to unit test and
backtest without hitting either API.
"""

from dataclasses import dataclass
from typing import List, Optional

from devig import multiplicative_devig, shin_devig, overround
from odds_client import OddsClient


@dataclass
class Signal:
    game_label: str          # e.g. "Chiefs @ Bills"
    team: str                # the side this signal is about
    book_fair_prob: float    # de-vigged sportsbook probability
    book_overround: float    # how much vig the book was carrying
    kalshi_price: float      # Kalshi's YES price, as a probability (0-1)
    kalshi_ticker: str
    contracts_assumed: int
    raw_edge: float          # book_fair_prob - kalshi_price
    fee_cost: float          # Kalshi taker fee, in probability-equivalent terms
    spread_cost: float       # half the bid-ask spread, same units
    net_edge: float          # raw_edge - fee_cost - spread_cost
    side: str                # "buy_yes" or "buy_no"


def compute_signal(
    game_label: str,
    team: str,
    book_odds_a: int,
    book_odds_b: int,
    kalshi_yes_bid: int,
    kalshi_yes_ask: int,
    kalshi_ticker: str,
    contracts: int = 100,
    devig_method: str = "shin",
) -> Signal:
    """book_odds_a/b: American odds for [team, opponent] from the sportsbook.
    kalshi_yes_bid/ask: Kalshi's current YES side quotes, in cents (1-99)."""

    prob_a = OddsClient.american_to_implied_prob(book_odds_a)
    prob_b = OddsClient.american_to_implied_prob(book_odds_b)
    devig_fn = shin_devig if devig_method == "shin" else multiplicative_devig
    fair_a, _ = devig_fn(prob_a, prob_b)

    mid_price = ((kalshi_yes_bid + kalshi_yes_ask) / 2) / 100
    spread = (kalshi_yes_ask - kalshi_yes_bid) / 100

    raw_edge = fair_a - mid_price
    side = "buy_yes" if raw_edge > 0 else "buy_no"

    from kalshi_client import KalshiClient
    trade_price_cents = kalshi_yes_ask if side == "buy_yes" else (100 - kalshi_yes_bid)
    fee_dollars = KalshiClient.taker_fee(trade_price_cents, contracts)
    fee_prob_equiv = fee_dollars / contracts  # fee cost per $1 of notional, in probability units

    spread_cost = spread / 2
    net_edge = abs(raw_edge) - fee_prob_equiv - spread_cost

    return Signal(
        game_label=game_label,
        team=team,
        book_fair_prob=fair_a,
        book_overround=overround(prob_a, prob_b),
        kalshi_price=mid_price,
        kalshi_ticker=kalshi_ticker,
        contracts_assumed=contracts,
        raw_edge=raw_edge,
        fee_cost=fee_prob_equiv,
        spread_cost=spread_cost,
        net_edge=net_edge,
        side=side,
    )


def screen_signals(signals: List[Signal], min_net_edge: float = 0.03) -> List[Signal]:
    """Filter to signals that clear a minimum net edge threshold (in probability
    points, e.g. 0.03 = 3 percentage points), sorted best-first."""
    hits = [s for s in signals if s.net_edge >= min_net_edge]
    return sorted(hits, key=lambda s: s.net_edge, reverse=True)
