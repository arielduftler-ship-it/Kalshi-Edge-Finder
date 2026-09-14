"""
paper_trade.py

Simulates executing every signal in data/scan_log.csv as a real Kalshi trade,
using no real money and no live Kalshi order-placement calls. This exists to
validate the strategy's actual P&L (not just theoretical net_edge) before
ever wiring up live execution.

How a trade is simulated:
  - Fill price = the logged `entry_price` (the ask you'd have paid at scan
    time for buy_yes, or 1 - bid for buy_no). This assumes you could always
    get filled at the price seen when the signal was logged -- real slippage
    between scan time and order time isn't modeled, so live results will run
    somewhat worse than this. Treat this as a best-case simulation, not a
    guarantee.
  - Position size = STAKE_PER_TRADE dollars, converted to a whole number of
    contracts at that entry price (Kalshi contracts settle at $1, cost
    entry_price to buy).
  - Only rows with a backfilled `outcome` (run backfill_outcomes.py first)
    are settled; everything else is still pending and skipped.
  - Every signal currently in scan_log.csv is side == "buy_yes" (see
    is_underpriced_favorite in edge_engine.py -- the "buy_no" mirror case
    isn't traded yet), but this handles both sides in case that changes.

Recomputes the full report from scratch every run (deterministic given
scan_log.csv), so there's no separate state file to get out of sync --
matches how backfill_outcomes.py and run_daily_scan.py already work.

Run after backfill_outcomes.py:
    python backfill_outcomes.py
    python paper_trade.py
"""

import csv
import math
from pathlib import Path

LOG_PATH = Path(__file__).parent / "data" / "scan_log.csv"
RESULTS_PATH = Path(__file__).parent / "data" / "paper_trade_results.csv"

# Dollar amount "risked" per signal. Purely a simulation knob -- change this
# to see how P&L would have scaled at a different position size.
STAKE_PER_TRADE = 100.0

RESULT_FIELDS = [
    "game_time", "sport", "game_label", "team", "side", "entry_price",
    "net_edge", "contracts", "buy_in", "outcome", "won", "profit", "cumulative_profit",
]


def simulate():
    if not LOG_PATH.exists():
        print(f"No log file at {LOG_PATH} yet -- run run_daily_scan.py first.")
        return

    with open(LOG_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    settled = [r for r in rows if r.get("outcome")]
    pending = len(rows) - len(settled)

    results = []
    cumulative_pnl = 0.0
    total_cost = 0.0
    wins = 0

    for row in settled:
        entry_price = float(row["entry_price"])
        if entry_price <= 0:
            continue  # can't size a position off a zero/invalid price

        contracts = math.floor(STAKE_PER_TRADE / entry_price)
        if contracts < 1:
            continue  # stake too small to buy even one contract at this price

        cost = contracts * entry_price
        side_wins = (
            (row["side"] == "buy_yes" and row["outcome"] == "yes")
            or (row["side"] == "buy_no" and row["outcome"] == "no")
        )
        pnl = contracts * (1 - entry_price) if side_wins else -cost

        cumulative_pnl += pnl
        total_cost += cost
        wins += 1 if side_wins else 0

        results.append({
            "game_time": row.get("game_time", ""),
            "sport": row["sport"],
            "game_label": row["game_label"],
            "team": row["team"],
            "side": row["side"],
            "entry_price": round(entry_price, 4),
            "net_edge": row.get("net_edge", ""),
            "contracts": contracts,
            "buy_in": round(cost, 2),
            "outcome": row["outcome"],
            "won": side_wins,
            "profit": round(pnl, 2),
            "cumulative_profit": round(cumulative_pnl, 2),
        })

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)
        if results:
            # A footer TOTAL row so the bottom line is visible at a glance
            # without opening the sheet and scrolling to the last row's
            # cumulative_profit -- both should always agree.
            writer.writerow({
                "game_time": "", "sport": "", "game_label": "TOTAL", "team": "",
                "side": "", "entry_price": "", "net_edge": "", "contracts": "",
                "buy_in": round(total_cost, 2), "outcome": "", "won": "",
                "profit": round(cumulative_pnl, 2), "cumulative_profit": round(cumulative_pnl, 2),
            })

    n = len(results)
    if n == 0:
        print(f"No settled trades yet ({pending} signal(s) still pending an outcome). "
              f"Run backfill_outcomes.py once those games finish.")
        return

    win_rate = wins / n
    roi = cumulative_pnl / total_cost if total_cost else 0.0

    print(f"Paper trade results ({n} settled, {pending} still pending):")
    print(f"  Win rate:      {win_rate:.1%} ({wins}/{n})")
    print(f"  Total buy-in:  ${total_cost:,.2f}")
    print(f"  Total profit:  ${cumulative_pnl:,.2f}")
    print(f"  ROI on stake:  {roi:+.1%}")
    print(f"  Full ledger (with a TOTAL row) written to {RESULTS_PATH}")


if __name__ == "__main__":
    simulate()
