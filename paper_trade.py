"""
paper_trade.py

Simulates executing every signal in data/scan_log.csv as a real Kalshi trade,
using no real money and no live Kalshi order-placement calls. This exists to
validate the strategy's actual P&L (not just theoretical net_edge) before
ever wiring up live execution.

Two sizing strategies run side by side on the same signals:

  FLAT   -- STAKE_PER_TRADE dollars on every signal, no compounding. Answers
            "does the edge exist?" without sizing noise.
  KELLY  -- fractional Kelly off a compounding bankroll (see kelly.py).
            Answers "how would the bankroll actually have grown?" Bets on
            games settling the same day are sized together off that day's
            starting bankroll, since you wouldn't know each other's results
            when placing them.

How a trade is simulated:
  - Fill price = the logged `entry_price` (the ask you'd have paid at scan
    time for buy_yes, or 1 - bid for buy_no). Real slippage between scan time
    and order time isn't modeled, so treat this as a best-case simulation.
  - All-in cost per contract = entry_price + fee_cost (the logged per-contract
    taker fee). Contracts are always whole numbers (floored).
  - Winning contracts settle at $1, losing at $0. `profit` is always
    `payout - buy_in`, spelled out as separate columns.
  - Only rows with a backfilled `outcome` (run backfill_outcomes.py first)
    are settled; everything else is still pending and skipped.

Recomputes the full report from scratch every run (deterministic given
scan_log.csv), so there's no separate state file to get out of sync.

Run after backfill_outcomes.py:
    python backfill_outcomes.py
    python paper_trade.py
"""

import csv
import math
from collections import defaultdict
from pathlib import Path

from kelly import size_slate

LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"
RESULTS_PATH = Path(__file__).parent / "data" / "paper_trade_results.csv"

# Flat strategy: dollars risked per signal.
STAKE_PER_TRADE = 100.0
# Kelly strategy: starting bankroll that compounds trade to trade.
STARTING_BANKROLL = 1000.0

RESULT_FIELDS = [
    "game_time", "sport", "game_label", "team", "side", "entry_price", "fee_cost",
    "book_fair_prob", "net_edge", "outcome", "won",
    # flat-stake columns
    "flat_contracts", "flat_buy_in", "flat_payout", "flat_profit", "flat_cumulative_profit",
    # Kelly columns
    "full_kelly", "kelly_fraction", "bankroll_before", "kelly_contracts",
    "kelly_buy_in", "kelly_payout", "kelly_profit", "bankroll_after",
]


def _side_wins(row) -> bool:
    return ((row["side"] == "buy_yes" and row["outcome"] == "yes")
            or (row["side"] == "buy_no" and row["outcome"] == "no"))


def _float(row, key, default=0.0) -> float:
    try:
        return float(row.get(key) or default)
    except ValueError:
        return default


def simulate():
    if not LOG_PATH.exists():
        print(f"No log file at {LOG_PATH} yet -- run run_daily_scan.py first.")
        return

    with open(LOG_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    settled = [r for r in rows if r.get("outcome") and _float(r, "entry_price") > 0]
    pending = len(rows) - len([r for r in rows if r.get("outcome")])

    # Group by settlement date (game_time is either YYYY-MM-DD or full ISO;
    # the first 10 chars are the date either way), oldest first.
    slates = defaultdict(list)
    for r in settled:
        slates[r.get("game_time", "")[:10]].append(r)

    results = []
    flat_cum = 0.0
    flat_cost_total = 0.0
    kelly_cost_total = 0.0
    bankroll = STARTING_BANKROLL
    wins = 0

    for day in sorted(slates):
        slate = slates[day]
        bets = [{
            # For buy_no, the probability that matters is the NO side winning.
            "p": _float(r, "book_fair_prob") if r["side"] == "buy_yes" else 1 - _float(r, "book_fair_prob"),
            "price": _float(r, "entry_price"),
            "fee": _float(r, "fee_cost"),
        } for r in slate]
        sizes = size_slate(bets, bankroll)

        bankroll_start = bankroll
        day_pnl = 0.0

        for row, bet, size in zip(slate, bets, sizes):
            won = _side_wins(row)
            wins += 1 if won else 0
            cost_per = bet["price"] + bet["fee"]

            # --- flat ---
            flat_contracts = math.floor(STAKE_PER_TRADE / cost_per)
            flat_buy_in = flat_contracts * cost_per
            flat_payout = flat_contracts * 1.0 if won else 0.0
            flat_profit = flat_payout - flat_buy_in
            flat_cum += flat_profit
            flat_cost_total += flat_buy_in

            # --- Kelly ---
            kelly_payout = size.contracts * 1.0 if won else 0.0
            kelly_profit = kelly_payout - size.stake
            day_pnl += kelly_profit
            kelly_cost_total += size.stake

            results.append({
                "game_time": row.get("game_time", ""),
                "sport": row["sport"],
                "game_label": row["game_label"],
                "team": row["team"],
                "side": row["side"],
                "entry_price": round(bet["price"], 4),
                "fee_cost": round(bet["fee"], 4),
                "book_fair_prob": row.get("book_fair_prob", ""),
                "net_edge": row.get("net_edge", ""),
                "outcome": row["outcome"],
                "won": won,
                "flat_contracts": flat_contracts,
                "flat_buy_in": round(flat_buy_in, 2),
                "flat_payout": round(flat_payout, 2),
                "flat_profit": round(flat_profit, 2),
                "flat_cumulative_profit": round(flat_cum, 2),
                "full_kelly": round(size.full_kelly, 4),
                "kelly_fraction": round(size.fraction, 4),
                "bankroll_before": round(bankroll_start, 2),
                "kelly_contracts": size.contracts,
                "kelly_buy_in": round(size.stake, 2),
                "kelly_payout": round(kelly_payout, 2),
                "kelly_profit": round(kelly_profit, 2),
                "bankroll_after": "",  # filled in once the whole slate settles
            })

        bankroll = bankroll_start + day_pnl
        for r in results[-len(slate):]:
            r["bankroll_after"] = round(bankroll, 2)

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)
        if results:
            total = {k: "" for k in RESULT_FIELDS}
            total.update({
                "game_label": "TOTAL",
                "flat_buy_in": round(flat_cost_total, 2),
                "flat_payout": round(sum(r["flat_payout"] for r in results), 2),
                "flat_profit": round(flat_cum, 2),
                "flat_cumulative_profit": round(flat_cum, 2),
                "bankroll_before": round(STARTING_BANKROLL, 2),
                "kelly_buy_in": round(kelly_cost_total, 2),
                "kelly_payout": round(sum(r["kelly_payout"] for r in results), 2),
                "kelly_profit": round(bankroll - STARTING_BANKROLL, 2),
                "bankroll_after": round(bankroll, 2),
            })
            writer.writerow(total)

    n = len(results)
    if n == 0:
        print(f"No settled trades yet ({pending} signal(s) still pending an outcome). "
              f"Run backfill_outcomes.py once those games finish.")
        return

    print(f"Paper trade results ({n} settled, {pending} still pending):")
    print(f"  Win rate:        {wins / n:.1%} ({wins}/{n})")
    print(f"  FLAT  (${STAKE_PER_TRADE:,.0f}/trade):  profit ${flat_cum:,.2f}  "
          f"ROI on stake {flat_cum / flat_cost_total:+.1%}" if flat_cost_total else "")
    print(f"  KELLY (start ${STARTING_BANKROLL:,.0f}):  ending bankroll ${bankroll:,.2f}  "
          f"({bankroll / STARTING_BANKROLL - 1:+.1%})")
    print(f"  Full ledger (with a TOTAL row) written to {RESULTS_PATH}")


if __name__ == "__main__":
    simulate()
