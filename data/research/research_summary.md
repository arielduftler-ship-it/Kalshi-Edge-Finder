# In-game Kalshi price paths: dip and snap-back research

Generated 2026-11-04 20:16 UTC. Sports: nba, nhl, nfl. Up to 500 games per sport, lookback 450 days, seed 42.

## Sample

| Sport | Games | Median in-game minutes | Median opening spread |
|---|---|---|---|
| nba | 499 | 139 | 1.0¢ |
| nfl | 475 | 175 | 1.0¢ |
| nhl | 492 | 154 | 1.0¢ |
| all | 1466 | 153 | 1.0¢ |

## 1. How far do prices move below the opening price?

"Never below open" allows a 1¢ wobble. "Winners" columns only count teams that went on to win, since a losing team always ends near 0.

| Sport | Side | Games | Never below open | Dip ≥3 | Dip ≥5 | Dip ≥10 | Dip ≥15 | Winners: never below | Winners: dip ≥5 | Winners: dip ≥10 |
|---|---|---|---|---|---|---|---|---|---|---|
| nba | favorite | 499 | 12.8% | 82.0% | 76.4% | 65.9% | 58.9% | 18.8% | 65.6% | 50.3% |
| nba | underdog | 499 | 3.8% | 93.8% | 91.0% | 77.6% | 66.9% | 11.9% | 75.5% | 52.8% |
| nfl | favorite | 475 | 8.2% | 86.9% | 81.3% | 73.3% | 64.8% | 13.0% | 70.3% | 57.7% |
| nfl | underdog | 475 | 4.0% | 94.5% | 90.3% | 80.8% | 69.7% | 10.3% | 74.9% | 55.4% |
| nhl | favorite | 492 | 13.2% | 81.9% | 76.2% | 68.5% | 65.4% | 22.6% | 59.7% | 47.6% |
| nhl | underdog | 492 | 11.2% | 81.9% | 76.6% | 74.8% | 71.5% | 24.0% | 49.5% | 45.6% |
| all | favorite | 1466 | 11.5% | 83.6% | 77.9% | 69.2% | 63.0% | 18.1% | 65.3% | 51.8% |
| all | underdog | 1466 | 6.3% | 90.0% | 85.9% | 77.7% | 69.4% | 16.0% | 65.4% | 50.9% |

### By opening price (all sports, one market per game per side)

| Opening price | Games | Win rate | Never below open | Dip ≥5 | Dip ≥10 | Winners: dip ≥5 |
|---|---|---|---|---|---|---|
| 0–20¢ | 150 | 16.7% | 2.0% | 89.3% | 55.3% | 64.0% |
| 20–30¢ | 241 | 27.4% | 2.5% | 92.5% | 83.8% | 74.2% |
| 30–40¢ | 418 | 36.6% | 8.1% | 87.1% | 83.3% | 67.3% |
| 40–50¢ | 650 | 44.8% | 7.7% | 82.0% | 77.1% | 62.5% |
| 50–60¢ | 653 | 54.7% | 10.6% | 80.2% | 73.2% | 64.1% |
| 60–70¢ | 420 | 63.6% | 10.0% | 81.0% | 70.5% | 70.4% |
| 70–80¢ | 244 | 72.5% | 10.2% | 78.3% | 67.6% | 70.1% |
| 80–100¢ | 156 | 83.3% | 20.5% | 59.6% | 51.3% | 51.5% |

## 2. Do prices dip more often than a fair market would?

Fair bound = average of (1 − Po) / (1 − (Po − dip)). Real rates clearly ABOVE the bound mean overreaction. Rates below it are expected even in a fair market, because prices jump and minute closes miss some lows. A losing team counts as reaching every level, because it settles at $0 even when the last quote was higher.

| Sport | Side | Dip | Games | Actual dip rate (95% CI) | Fair bound | Actual − bound |
|---|---|---|---|---|---|---|
| nba | favorite | 3¢ | 499 | 82.0% (78.4%–85.1%) | 89.4% | -7.4 pts |
| nba | favorite | 5¢ | 499 | 76.6% (72.6%–80.1%) | 83.8% | -7.3 pts |
| nba | favorite | 10¢ | 499 | 66.1% (61.9%–70.1%) | 72.9% | -6.7 pts |
| nba | favorite | 15¢ | 499 | 59.1% (54.8%–63.3%) | 64.7% | -5.6 pts |
| nba | favorite | 20¢ | 499 | 52.1% (47.7%–56.5%) | 58.3% | -6.2 pts |
| nba | underdog | 3¢ | 499 | 94.0% (91.5%–95.8%) | 95.3% | -1.3 pts |
| nba | underdog | 5¢ | 499 | 91.6% (88.8%–93.7%) | 92.5% | -0.9 pts |
| nba | underdog | 10¢ | 499 | 80.6% (76.9%–83.8%) | 83.0% | -2.5 pts |
| nba | underdog | 15¢ | 499 | 68.9% (64.7%–72.8%) | 71.9% | -3.0 pts |
| nba | underdog | 20¢ | 499 | 58.3% (53.9%–62.6%) | 60.6% | -2.3 pts |
| nfl | favorite | 3¢ | 475 | 86.9% (83.6%–89.7%) | 91.1% | -4.1 pts |
| nfl | favorite | 5¢ | 475 | 81.3% (77.5%–84.5%) | 86.1% | -4.8 pts |
| nfl | favorite | 10¢ | 475 | 73.3% (69.1%–77.0%) | 75.9% | -2.6 pts |
| nfl | favorite | 15¢ | 475 | 64.8% (60.4%–69.0%) | 68.0% | -3.1 pts |
| nfl | favorite | 20¢ | 475 | 59.8% (55.3%–64.1%) | 61.6% | -1.9 pts |
| nfl | underdog | 3¢ | 475 | 94.9% (92.6%–96.6%) | 95.5% | -0.6 pts |
| nfl | underdog | 5¢ | 475 | 90.7% (87.8%–93.0%) | 92.8% | -2.0 pts |
| nfl | underdog | 10¢ | 475 | 83.2% (79.5%–86.3%) | 86.1% | -3.0 pts |
| nfl | underdog | 15¢ | 475 | 72.4% (68.2%–76.2%) | 76.0% | -3.6 pts |
| nfl | underdog | 20¢ | 475 | 63.6% (59.2%–67.8%) | 67.6% | -4.0 pts |
| nhl | favorite | 3¢ | 492 | 82.1% (78.5%–85.2%) | 93.1% | -11.0 pts |
| nhl | favorite | 5¢ | 492 | 76.4% (72.5%–80.0%) | 89.1% | -12.7 pts |
| nhl | favorite | 10¢ | 492 | 69.3% (65.1%–73.2%) | 80.4% | -11.1 pts |
| nhl | favorite | 15¢ | 492 | 67.1% (62.8%–71.1%) | 73.2% | -6.2 pts |
| nhl | favorite | 20¢ | 492 | 60.2% (55.8%–64.4%) | 67.3% | -7.1 pts |
| nhl | underdog | 3¢ | 492 | 83.5% (80.0%–86.6%) | 95.0% | -11.5 pts |
| nhl | underdog | 5¢ | 492 | 79.1% (75.3%–82.4%) | 92.0% | -12.9 pts |
| nhl | underdog | 10¢ | 492 | 77.4% (73.5%–80.9%) | 85.2% | -7.8 pts |
| nhl | underdog | 15¢ | 492 | 75.2% (71.2%–78.8%) | 79.4% | -4.2 pts |
| nhl | underdog | 20¢ | 492 | 68.3% (64.1%–72.2%) | 74.3% | -6.0 pts |
| all | favorite | 3¢ | 1466 | 83.6% (81.6%–85.4%) | 91.2% | -7.6 pts |
| all | favorite | 5¢ | 1466 | 78.0% (75.8%–80.1%) | 86.3% | -8.3 pts |
| all | favorite | 10¢ | 1466 | 69.5% (67.1%–71.8%) | 76.4% | -6.9 pts |
| all | favorite | 15¢ | 1466 | 63.6% (61.1%–66.1%) | 68.6% | -5.0 pts |
| all | favorite | 20¢ | 1466 | 57.3% (54.8%–59.8%) | 62.4% | -5.1 pts |
| all | underdog | 3¢ | 1466 | 90.8% (89.2%–92.2%) | 95.3% | -4.5 pts |
| all | underdog | 5¢ | 1466 | 87.1% (85.3%–88.7%) | 92.4% | -5.3 pts |
| all | underdog | 10¢ | 1466 | 80.4% (78.2%–82.3%) | 84.8% | -4.4 pts |
| all | underdog | 15¢ | 1466 | 72.2% (69.8%–74.4%) | 75.8% | -3.6 pts |
| all | underdog | 20¢ | 1466 | 63.4% (60.9%–65.8%) | 67.5% | -4.1 pts |

⬆ = the whole confidence interval sits above the fair bound.

## 3. Snap-back test: after a dip, does the team win more often than its price said?

For games whose price touched each dip level: win rate vs. the average price at first touch. In a fair market these match. "Buy-the-dip P&L" = buy YES at the ask at first touch and hold to settlement, per contract, before fees.

| Sport | Side | Dip | Touches | Win rate after touch | Avg touch price | Win rate − price | Buy-the-dip P&L (±1.96 SE) |
|---|---|---|---|---|---|---|---|
| nba | favorite | 3¢ | 409 | 61.1% | 62.8% | -1.7 pts | -2.3¢ (±4.6¢) |
| nba | favorite | 5¢ | 381 | 58.5% | 60.2% | -1.7 pts | -2.3¢ (±4.8¢) |
| nba | favorite | 10¢ | 329 | 52.0% | 55.1% | -3.1 pts | -3.7¢ (±5.3¢) |
| nba | favorite | 15¢ | 294 | 46.3% | 48.9% | -2.6 pts | -3.3¢ (±5.6¢) |
| nba | favorite | 20¢ | 259 | 39.0% | 42.8% | -3.8 pts | -4.6¢ (±5.9¢) |
| nba | underdog | 3¢ | 468 | 28.0% | 26.7% | +1.3 pts | +0.7¢ (±4.0¢) |
| nba | underdog | 5¢ | 454 | 26.4% | 24.8% | +1.6 pts | +1.0¢ (±4.0¢) |
| nba | underdog | 10¢ | 387 | 21.7% | 20.9% | +0.8 pts | +0.1¢ (±4.1¢) |
| nba | underdog | 15¢ | 334 | 16.8% | 17.3% | -0.5 pts | -1.2¢ (±3.9¢) |
| nba | underdog | 20¢ | 269 | 12.3% | 14.0% | -1.8 pts | -2.4¢ (±3.8¢) |
| nfl | favorite | 3¢ | 413 | 57.6% | 60.1% | -2.5 pts | -3.2¢ (±4.7¢) |
| nfl | favorite | 5¢ | 386 | 54.7% | 57.6% | -3.0 pts | -3.7¢ (±4.9¢) |
| nfl | favorite | 10¢ | 348 | 49.7% | 52.1% | -2.4 pts | -3.2¢ (±5.2¢) |
| nfl | favorite | 15¢ | 308 | 43.2% | 46.0% | -2.8 pts | -3.6¢ (±5.5¢) |
| nfl | favorite | 20¢ | 284 | 38.4% | 40.7% | -2.4 pts | -3.1¢ (±5.6¢) |
| nfl | underdog | 3¢ | 449 | 33.6% | 29.5% | +4.1 pts | +3.4¢ (±4.3¢) |
| nfl | underdog | 5¢ | 429 | 30.5% | 27.5% | +3.0 pts | +2.3¢ (±4.2¢) |
| nfl | underdog | 10¢ | 384 | 25.3% | 23.1% | +2.2 pts | +1.4¢ (±4.2¢) |
| nfl | underdog | 15¢ | 331 | 21.1% | 19.2% | +1.9 pts | +1.2¢ (±4.3¢) |
| nfl | underdog | 20¢ | 281 | 16.4% | 15.2% | +1.2 pts | +0.4¢ (±4.3¢) |
| nhl | favorite | 3¢ | 403 | 49.6% | 49.7% | -0.0 pts | -1.3¢ (±4.8¢) |
| nhl | favorite | 5¢ | 375 | 45.9% | 45.7% | +0.2 pts | -1.2¢ (±5.0¢) |
| nhl | favorite | 10¢ | 337 | 40.7% | 41.5% | -0.9 pts | -2.3¢ (±5.2¢) |
| nhl | favorite | 15¢ | 322 | 39.1% | 39.4% | -0.3 pts | -1.5¢ (±5.3¢) |
| nhl | favorite | 20¢ | 284 | 32.4% | 32.7% | -0.4 pts | -1.6¢ (±5.3¢) |
| nhl | underdog | 3¢ | 403 | 30.5% | 31.9% | -1.3 pts | -2.8¢ (±4.4¢) |
| nhl | underdog | 5¢ | 377 | 26.8% | 29.4% | -2.6 pts | -4.1¢ (±4.4¢) |
| nhl | underdog | 10¢ | 368 | 25.3% | 27.0% | -1.7 pts | -3.0¢ (±4.4¢) |
| nhl | underdog | 15¢ | 352 | 23.3% | 23.5% | -0.2 pts | -1.2¢ (±4.3¢) |
| nhl | underdog | 20¢ | 308 | 15.6% | 17.2% | -1.6 pts | -2.8¢ (±4.0¢) |
| all | favorite | 3¢ | 1225 | 56.2% | 57.6% | -1.4 pts | -2.3¢ (±2.7¢) |
| all | favorite | 5¢ | 1142 | 53.1% | 54.6% | -1.5 pts | -2.4¢ (±2.8¢) |
| all | favorite | 10¢ | 1014 | 47.4% | 49.6% | -2.1 pts | -3.1¢ (±3.0¢) |
| all | favorite | 15¢ | 924 | 42.7% | 44.6% | -1.9 pts | -2.8¢ (±3.1¢) |
| all | favorite | 20¢ | 827 | 36.5% | 38.7% | -2.1 pts | -3.0¢ (±3.2¢) |
| all | underdog | 3¢ | 1320 | 30.7% | 29.2% | +1.5 pts | +0.5¢ (±2.4¢) |
| all | underdog | 5¢ | 1260 | 27.9% | 27.1% | +0.8 pts | -0.1¢ (±2.4¢) |
| all | underdog | 10¢ | 1139 | 24.1% | 23.6% | +0.4 pts | -0.4¢ (±2.4¢) |
| all | underdog | 15¢ | 1017 | 20.5% | 20.1% | +0.4 pts | -0.4¢ (±2.4¢) |
| all | underdog | 20¢ | 858 | 14.8% | 15.6% | -0.8 pts | -1.6¢ (±2.3¢) |

## 4. Is the opening price itself well calibrated?

If Kalshi's pregame price is biased (e.g. favorites too cheap), the in-game tests above inherit that bias.

| Opening price | Games | Avg opening price | Win rate | Win rate − price |
|---|---|---|---|---|
| 0–20¢ | 150 | 14.1% | 16.7% | +2.6 pts |
| 20–30¢ | 241 | 25.3% | 27.4% | +2.1 pts |
| 30–40¢ | 418 | 35.6% | 36.6% | +1.0 pts |
| 40–50¢ | 650 | 44.9% | 44.8% | -0.1 pts |
| 50–60¢ | 653 | 55.1% | 54.7% | -0.5 pts |
| 60–70¢ | 420 | 64.3% | 63.6% | -0.7 pts |
| 70–80¢ | 244 | 74.6% | 72.5% | -2.0 pts |
| 80–100¢ | 156 | 85.8% | 83.3% | -2.5 pts |

## Plain-language read

- Dip-rate test: 0 of 10 all-sport dip levels show dips significantly more often than a fair market allows.
- Snap-back test: of 10 all-sport dip levels, 0 show a buy-the-dip profit clearly above zero, 1 clearly below zero, the rest are inside the noise.
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
