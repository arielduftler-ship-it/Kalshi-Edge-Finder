# In-game Kalshi price paths: dip and snap-back research

Generated 2026-11-04 19:38 UTC. Sports: nba. Up to 30 games per sport, lookback 450 days, seed 42.

## Sample

| Sport | Games | Median in-game minutes | Median opening spread |
|---|---|---|---|
| nba | 30 | 139 | 1.0¢ |
| all | 30 | 139 | 1.0¢ |

## 1. How far do prices move below the opening price?

"Never below open" allows a 1¢ wobble. "Winners" columns only count teams that went on to win, since a losing team always ends near 0.

| Sport | Side | Games | Never below open | Dip ≥3 | Dip ≥5 | Dip ≥10 | Dip ≥15 | Winners: never below | Winners: dip ≥5 | Winners: dip ≥10 |
|---|---|---|---|---|---|---|---|---|---|---|
| nba | favorite | 30 | 13.3% | 80.0% | 73.3% | 73.3% | 66.7% | 23.5% | 52.9% | 52.9% |
| nba | underdog | 30 | 6.7% | 86.7% | 80.0% | 63.3% | 53.3% | 15.4% | 61.5% | 38.5% |
| all | favorite | 30 | 13.3% | 80.0% | 73.3% | 73.3% | 66.7% | 23.5% | 52.9% | 52.9% |
| all | underdog | 30 | 6.7% | 86.7% | 80.0% | 63.3% | 53.3% | 15.4% | 61.5% | 38.5% |

### By opening price (all sports, one market per game per side)

| Opening price | Games | Win rate | Never below open | Dip ≥5 | Dip ≥10 | Winners: dip ≥5 |
|---|---|---|---|---|---|---|
| 0–20¢ | 6 | 16.7% | 0.0% | 83.3% | 33.3% | 100.0% |
| 20–30¢ | 6 | 16.7% | 0.0% | 83.3% | 83.3% | 0.0% |
| 30–40¢ | 7 | 57.1% | 14.3% | 85.7% | 85.7% | 75.0% |
| 40–50¢ | 11 | 63.6% | 9.1% | 72.7% | 54.5% | 57.1% |
| 50–60¢ | 11 | 36.4% | 18.2% | 81.8% | 81.8% | 50.0% |
| 60–70¢ | 6 | 50.0% | 0.0% | 100.0% | 100.0% | 100.0% |
| 70–80¢ | 6 | 66.7% | 0.0% | 83.3% | 83.3% | 75.0% |
| 80–100¢ | 7 | 85.7% | 28.6% | 28.6% | 28.6% | 16.7% |

## 2. Do prices dip more often than a fair market would?

Fair bound = average of (1 − p0) / (1 − (p0 − dip)). Real rates clearly ABOVE the bound mean overreaction. Rates below it are expected even in a fair market, because prices jump and minute closes miss some lows.

| Sport | Side | Dip | Games | Actual dip rate (95% CI) | Fair bound | Actual − bound |
|---|---|---|---|---|---|---|
| nba | favorite | 3¢ | 30 | 80.0% (62.7%–90.5%) | 89.1% | -9.1 pts |
| nba | favorite | 5¢ | 30 | 73.3% (55.6%–85.8%) | 83.4% | -10.1 pts |
| nba | favorite | 10¢ | 30 | 73.3% (55.6%–85.8%) | 72.5% | +0.9 pts |
| nba | favorite | 15¢ | 30 | 66.7% (48.8%–80.8%) | 64.4% | +2.3 pts |
| nba | favorite | 20¢ | 30 | 56.7% (39.2%–72.6%) | 58.0% | -1.3 pts |
| nba | underdog | 3¢ | 30 | 86.7% (70.3%–94.7%) | 95.7% | -9.0 pts |
| nba | underdog | 5¢ | 30 | 80.0% (62.7%–90.5%) | 93.0% | -13.0 pts |
| nba | underdog | 10¢ | 30 | 63.3% (45.5%–78.1%) | 80.9% | -17.6 pts |
| nba | underdog | 15¢ | 30 | 53.3% (36.1%–69.8%) | 70.2% | -16.8 pts |
| nba | underdog | 20¢ | 30 | 40.0% (24.6%–57.7%) | 60.6% | -20.6 pts |
| all | favorite | 3¢ | 30 | 80.0% (62.7%–90.5%) | 89.1% | -9.1 pts |
| all | favorite | 5¢ | 30 | 73.3% (55.6%–85.8%) | 83.4% | -10.1 pts |
| all | favorite | 10¢ | 30 | 73.3% (55.6%–85.8%) | 72.5% | +0.9 pts |
| all | favorite | 15¢ | 30 | 66.7% (48.8%–80.8%) | 64.4% | +2.3 pts |
| all | favorite | 20¢ | 30 | 56.7% (39.2%–72.6%) | 58.0% | -1.3 pts |
| all | underdog | 3¢ | 30 | 86.7% (70.3%–94.7%) | 95.7% | -9.0 pts |
| all | underdog | 5¢ | 30 | 80.0% (62.7%–90.5%) | 93.0% | -13.0 pts |
| all | underdog | 10¢ | 30 | 63.3% (45.5%–78.1%) | 80.9% | -17.6 pts |
| all | underdog | 15¢ | 30 | 53.3% (36.1%–69.8%) | 70.2% | -16.8 pts |
| all | underdog | 20¢ | 30 | 40.0% (24.6%–57.7%) | 60.6% | -20.6 pts |

⬆ = the whole confidence interval sits above the fair bound.

## 3. Snap-back test: after a dip, does the team win more often than its price said?

For games whose price touched each dip level: win rate vs. the average price at first touch. In a fair market these match. "Buy-the-dip P&L" = buy YES at the ask at first touch and hold to settlement, per contract, before fees.

| Sport | Side | Dip | Touches | Win rate after touch | Avg touch price | Win rate − price | Buy-the-dip P&L (±1.96 SE) |
|---|---|---|---|---|---|---|---|
| nba | favorite | 3¢ | 24 | 45.8% | 62.2% | -16.4 pts | -17.0¢ (±19.5¢) |
| nba | favorite | 5¢ | 22 | 40.9% | 59.1% | -18.2 pts | -18.8¢ (±20.4¢) |
| nba | favorite | 10¢ | 22 | 40.9% | 53.6% | -12.7 pts | -13.4¢ (±20.7¢) |
| nba | favorite | 15¢ | 20 | 35.0% | 46.1% | -11.1 pts | -11.7¢ (±20.8¢) |
| nba | underdog | 3¢ | 26 | 34.6% | 26.8% | +7.8 pts | +7.2¢ (±17.9¢) |
| nba | underdog | 5¢ | 24 | 33.3% | 24.9% | +8.5 pts | +7.9¢ (±18.6¢) |
| all | favorite | 3¢ | 24 | 45.8% | 62.2% | -16.4 pts | -17.0¢ (±19.5¢) |
| all | favorite | 5¢ | 22 | 40.9% | 59.1% | -18.2 pts | -18.8¢ (±20.4¢) |
| all | favorite | 10¢ | 22 | 40.9% | 53.6% | -12.7 pts | -13.4¢ (±20.7¢) |
| all | favorite | 15¢ | 20 | 35.0% | 46.1% | -11.1 pts | -11.7¢ (±20.8¢) |
| all | underdog | 3¢ | 26 | 34.6% | 26.8% | +7.8 pts | +7.2¢ (±17.9¢) |
| all | underdog | 5¢ | 24 | 33.3% | 24.9% | +8.5 pts | +7.9¢ (±18.6¢) |

## 4. Is the opening price itself well calibrated?

If Kalshi's pregame price is biased (e.g. favorites too cheap), the in-game tests above inherit that bias.

| Opening price | Games | Avg opening price | Win rate | Win rate − price |
|---|---|---|---|---|
| 0–20¢ | 6 | 12.0% | 16.7% | +4.7 pts |
| 20–30¢ | 6 | 25.0% | 16.7% | -8.3 pts |
| 30–40¢ | 7 | 34.4% | 57.1% | +22.7 pts |
| 40–50¢ | 11 | 44.2% | 63.6% | +19.4 pts |
| 50–60¢ | 11 | 56.2% | 36.4% | -19.9 pts |
| 60–70¢ | 6 | 65.3% | 50.0% | -15.3 pts |
| 70–80¢ | 6 | 73.8% | 66.7% | -7.1 pts |
| 80–100¢ | 7 | 86.9% | 85.7% | -1.1 pts |

## Plain-language read

- Dip-rate test: 0 of 10 all-sport dip levels show dips significantly more often than a fair market allows.
- Snap-back test: of 6 all-sport dip levels, 0 show a buy-the-dip profit clearly above zero, 0 clearly below zero, the rest are inside the noise.
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
