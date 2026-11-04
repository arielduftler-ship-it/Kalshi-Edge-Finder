# In-game Kalshi price paths: dip and snap-back research

Generated 2026-11-04 19:33 UTC. Sports: nba. Up to 30 games per sport, lookback 450 days, seed 42.

## Sample

| Sport | Games | Median in-game minutes | Median opening spread |
|---|---|---|---|
| nba | 30 | 146 | 0.0¢ |
| all | 30 | 146 | 0.0¢ |

## 1. How far do prices move below the opening price?

"Never below open" allows a 1¢ wobble. "Winners" columns only count teams that went on to win, since a losing team always ends near 0.

| Sport | Side | Games | Never below open | Dip ≥3 | Dip ≥5 | Dip ≥10 | Dip ≥15 | Winners: never below | Winners: dip ≥5 | Winners: dip ≥10 |
|---|---|---|---|---|---|---|---|---|---|---|
| nba | favorite | 30 | 86.7% | 13.3% | 13.3% | 13.3% | 10.0% | 88.2% | 11.8% | 11.8% |
| nba | underdog | 30 | 90.0% | 6.7% | 6.7% | 6.7% | 6.7% | 92.3% | 0.0% | 0.0% |
| all | favorite | 30 | 86.7% | 13.3% | 13.3% | 13.3% | 10.0% | 88.2% | 11.8% | 11.8% |
| all | underdog | 30 | 90.0% | 6.7% | 6.7% | 6.7% | 6.7% | 92.3% | 0.0% | 0.0% |

### By opening price (all sports, one market per game per side)

| Opening price | Games | Win rate | Never below open | Dip ≥5 | Dip ≥10 | Winners: dip ≥5 |
|---|---|---|---|---|---|---|
| 0–20¢ | 52 | 50.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| 30–40¢ | 2 | 50.0% | 50.0% | 50.0% | 50.0% | 0.0% |
| 40–50¢ | 2 | 50.0% | 0.0% | 50.0% | 50.0% | 0.0% |
| 50–60¢ | 2 | 50.0% | 0.0% | 100.0% | 100.0% | 100.0% |
| 60–70¢ | 2 | 50.0% | 0.0% | 100.0% | 100.0% | 100.0% |

## 2. Do prices dip more often than a fair market would?

Fair bound = average of (1 − p0) / (1 − (p0 − dip)). Real rates clearly ABOVE the bound mean overreaction. Rates below it are expected even in a fair market, because prices jump and minute closes miss some lows.

| Sport | Side | Dip | Games | Actual dip rate (95% CI) | Fair bound | Actual − bound |
|---|---|---|---|---|---|---|
| nba | favorite | 3¢ | 30 | 13.3% (5.3%–29.7%) | 12.4% | +1.0 pts |
| nba | favorite | 5¢ | 30 | 13.3% (5.3%–29.7%) | 11.8% | +1.5 pts |
| nba | favorite | 10¢ | 30 | 13.3% (5.3%–29.7%) | 10.6% | +2.7 pts |
| nba | favorite | 15¢ | 30 | 10.0% (3.5%–25.6%) | 9.6% | +0.4 pts |
| nba | favorite | 20¢ | 30 | 6.7% (1.8%–21.3%) | 8.8% | -2.2 pts |
| nba | underdog | 3¢ | 30 | 6.7% (1.8%–21.3%) | 12.7% | -6.0 pts |
| nba | underdog | 5¢ | 30 | 6.7% (1.8%–21.3%) | 12.3% | -5.6 pts |
| nba | underdog | 10¢ | 30 | 6.7% (1.8%–21.3%) | 11.4% | -4.7 pts |
| nba | underdog | 15¢ | 30 | 6.7% (1.8%–21.3%) | 10.6% | -3.9 pts |
| nba | underdog | 20¢ | 30 | 6.7% (1.8%–21.3%) | 9.9% | -3.3 pts |
| all | favorite | 3¢ | 30 | 13.3% (5.3%–29.7%) | 12.4% | +1.0 pts |
| all | favorite | 5¢ | 30 | 13.3% (5.3%–29.7%) | 11.8% | +1.5 pts |
| all | favorite | 10¢ | 30 | 13.3% (5.3%–29.7%) | 10.6% | +2.7 pts |
| all | favorite | 15¢ | 30 | 10.0% (3.5%–25.6%) | 9.6% | +0.4 pts |
| all | favorite | 20¢ | 30 | 6.7% (1.8%–21.3%) | 8.8% | -2.2 pts |
| all | underdog | 3¢ | 30 | 6.7% (1.8%–21.3%) | 12.7% | -6.0 pts |
| all | underdog | 5¢ | 30 | 6.7% (1.8%–21.3%) | 12.3% | -5.6 pts |
| all | underdog | 10¢ | 30 | 6.7% (1.8%–21.3%) | 11.4% | -4.7 pts |
| all | underdog | 15¢ | 30 | 6.7% (1.8%–21.3%) | 10.6% | -3.9 pts |
| all | underdog | 20¢ | 30 | 6.7% (1.8%–21.3%) | 9.9% | -3.3 pts |

⬆ = the whole confidence interval sits above the fair bound.

## 3. Snap-back test: after a dip, does the team win more often than its price said?

For games whose price touched each dip level: win rate vs. the average price at first touch. In a fair market these match. "Buy-the-dip P&L" = buy YES at the ask at first touch and hold to settlement, per contract, before fees.

| Sport | Side | Dip | Touches | Win rate after touch | Avg touch price | Win rate − price | Buy-the-dip P&L (±1.96 SE) |
|---|---|---|---|---|---|---|---|

## 4. Is the opening price itself well calibrated?

If Kalshi's pregame price is biased (e.g. favorites too cheap), the in-game tests above inherit that bias.

| Opening price | Games | Avg opening price | Win rate | Win rate − price |
|---|---|---|---|---|
| 0–20¢ | 52 | 0.5% | 50.0% | +49.5 pts |
| 30–40¢ | 2 | 33.5% | 50.0% | +16.5 pts |
| 40–50¢ | 2 | 48.0% | 50.0% | +2.0 pts |
| 50–60¢ | 2 | 52.5% | 50.0% | -2.5 pts |
| 60–70¢ | 2 | 67.0% | 50.0% | -17.0 pts |

## Plain-language read

- Dip-rate test: 0 of 10 all-sport dip levels show dips significantly more often than a fair market allows.
- Snap-back test: of 0 all-sport dip levels, 0 show a buy-the-dip profit clearly above zero, 0 clearly below zero, the rest are inside the noise.
- If both tests come back near zero, in-game swings are ordinary game volatility. A convergence exit would then mostly sell winners early, and holding the pregame edge to settlement is the better rule.
- If snap-back is clearly positive, Kalshi overreacts in-game, and buying dips (or exiting at the sharp number) has its own edge worth testing against fees and depth.
- Fees are not included. Kalshi's taker fee is largest near 50¢, so any edge under ~2¢ per contract is unlikely to survive taking liquidity.

## 5. Your logged signals: did Kalshi ever reach the book's fair price?

Entry = logged entry price. Target = logged book fair probability. Touch uses the bid/ask midpoint, so a real sell would land slightly lower. Before fees.

| Ticker | Entry | Target | Touched target? | Won? | Sell-at-target P&L | Hold P&L |
|---|---|---|---|---|---|---|
| KXMLBGAME-26SEP091915TBATL-ATL | 0.43 | 0.53 | no | no | -43.0¢ | -43.0¢ |
| KXMLBGAME-26SEP091840HOUPHI-PHI | 0.31 | 0.65 | yes | yes | +34.2¢ | +69.0¢ |
| KXNBAGAME-26OCT20BOSDET-DET | 0.50 | 0.53 | no | yes | +50.0¢ | +50.0¢ |
| **Average (3)** | | | | | **+13.7¢** | **+25.3¢** |

Too few rows to conclude anything yet; this table grows as the scanner logs more signals.

## Charts

![dip rates](dip_rate_vs_fair.png)

![snap-back](snapback.png)

![calibration](opening_calibration.png)

![examples](example_paths.png)
