"""
edge_engine.py

Ties kalshi_client + odds_client + devig together into a signal:

    1. Get a fair win probability for a team. In production this is the
       sharp-weighted consensus from devig.sharp_weighted_consensus (exchanges
       and sharp-leaning books dominate; soft books carry a token weight).
    2. Pull Kalshi's current market price for the matching "Team wins" contract.
    3. Compute the raw edge = fair_prob - kalshi_prob.
    4. Net out Kalshi's taker fee and half the bid-ask spread (a rough
       execution-cost estimate) to get a tradeable edge.
    5. Flag it if the tradeable edge clears your minimum threshold.

This module works on plain dicts/dataclasses so it's easy to unit test and
backtest without hitting either API.
"""

from dataclasses import dataclass
from typing import List

from devig import multiplicative_devig, shin_devig, overround, american_to_implied_prob, Consensus


@dataclass
class Signal:
    game_label: str          # e.g. "Chiefs @ Bills"
    team: str                # the side this signal is about
    book_fair_prob: float    # fair probability (sharp-weighted consensus in production)
    book_overround: float    # average vig across the books used
    kalshi_price: float      # Kalshi's YES midpoint, as a probability (0-1)
    kalshi_ticker: str
    contracts_assumed: int
    raw_edge: float          # book_fair_prob - kalshi_price
    fee_cost: float          # Kalshi taker fee, in probability-equivalent terms
    spread_cost: float       # half the bid-ask spread, same units
    net_edge: float          # |raw_edge| - fee_cost - spread_cost
    side: str                # "buy_yes" or "buy_no"
    entry_price: float       # actual price you'd pay (ask if buy_yes, 1-bid if buy_no)
    n_books: int = 1         # how many books fed the fair probability
    n_sharp: int = 0         # how many of those were exchanges / sharp books
    sharp_share: float = 0.0 # share of the benchmark's weight from sharp sources (0-1)
    books_used: str = ""     # e.g. "betfair_ex_eu|novig|lowvig"


def compute_signal_from_fair(
    game_label: str,
    team: str,
    fair_prob: float,
    benchmark_overround: float,
    kalshi_yes_bid: int,
    kalshi_yes_ask: int,
    kalshi_ticker: str,
    contracts: int = 100,
) -> Signal:
    """Core edge math, given a fair probability from any source.
    kalshi_yes_bid/ask: Kalshi's current YES side quotes, in cents (1-99)."""
    from kalshi_client import KalshiClient

    mid_price = ((kalshi_yes_bid + kalshi_yes_ask) / 2) / 100
    spread = (kalshi_yes_ask - kalshi_yes_bid) / 100

    raw_edge = fair_prob - mid_price
    side = "buy_yes" if raw_edge > 0 else "buy_no"

    trade_price_cents = kalshi_yes_ask if side == "buy_yes" else (100 - kalshi_yes_bid)
    fee_dollars = KalshiClient.taker_fee(trade_price_cents, contracts)
    fee_prob_equiv = fee_dollars / contracts  # fee cost per $1 of notional, in probability units

    spread_cost = spread / 2
    net_edge = abs(raw_edge) - fee_prob_equiv - spread_cost

    return Signal(
        game_label=game_label,
        team=team,
        book_fair_prob=fair_prob,
        book_overround=benchmark_overround,
        kalshi_price=mid_price,
        kalshi_ticker=kalshi_ticker,
        contracts_assumed=contracts,
        raw_edge=raw_edge,
        fee_cost=fee_prob_equiv,
        spread_cost=spread_cost,
        net_edge=net_edge,
        side=side,
        entry_price=trade_price_cents / 100,
    )


def compute_signal_from_consensus(
    game_label: str,
    team: str,
    consensus: Consensus,
    kalshi_yes_bid: int,
    kalshi_yes_ask: int,
    kalshi_ticker: str,
    contracts: int = 100,
) -> Signal:
    """Production path: `team` must be the home team, since Consensus.fair_home
    is the home side's probability (the Kalshi market we match is the
    home-team-wins contract)."""
    sig = compute_signal_from_fair(
        game_label, team, consensus.fair_home, consensus.avg_overround,
        kalshi_yes_bid, kalshi_yes_ask, kalshi_ticker, contracts,
    )
    sig.n_books = consensus.n_books
    sig.n_sharp = consensus.n_sharp
    sig.sharp_share = consensus.sharp_share
    sig.books_used = "|".join(consensus.books_used)
    return sig


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
    """Single-book version, kept for the notebook and quick experiments.
    book_odds_a/b: American odds for [team, opponent] from ONE sportsbook."""
    prob_a = american_to_implied_prob(book_odds_a)
    prob_b = american_to_implied_prob(book_odds_b)
    devig_fn = shin_devig if devig_method == "shin" else multiplicative_devig
    fair_a, _ = devig_fn(prob_a, prob_b)
    return compute_signal_from_fair(
        game_label, team, fair_a, overround(prob_a, prob_b),
        kalshi_yes_bid, kalshi_yes_ask, kalshi_ticker, contracts,
    )


def is_underpriced_favorite(sig: Signal) -> bool:
    """True if the benchmark considers this team a favorite (fair prob > 50%)
    but Kalshi's market is pricing it as an underdog (price < 50%). This is
    the specific mispricing pattern we're trading right now. It always implies
    side == "buy_yes", since fair > mid in this case by definition.

    We're intentionally NOT trading the mirror case (an underdog overpriced
    by Kalshi, side == "buy_no") yet -- narrower scope while validating the
    core thesis."""
    return sig.book_fair_prob > 0.5 and sig.kalshi_price < 0.5


def screen_signals(signals: List[Signal], min_net_edge: float = 0.03, favorites_only: bool = True) -> List[Signal]:
    """Filter to signals that clear a minimum net edge threshold (in probability
    points, e.g. 0.03 = 3 percentage points), sorted best-first. By default
    also restricts to underpriced favorites -- pass favorites_only=False to
    see every edge, favorite or underdog."""
    hits = [s for s in signals if s.net_edge >= min_net_edge]
    if favorites_only:
        hits = [s for s in hits if is_underpriced_favorite(s)]
    return sorted(hits, key=lambda s: s.net_edge, reverse=True)
