# Kalshi Edge Finder

Compares Kalshi's peer-to-peer sports-contract prices against de-vigged
sportsbook lines to flag cases where the two disagree by more than
execution costs (Kalshi's taker fee + bid-ask spread) can explain.

**Thesis:** sportsbooks actively shade their lines to balance liability,
which pulls their prices toward fair value. Kalshi's price is pure
crowd order flow, so retail/fan sentiment (public bias toward popular
teams, home favorites, primetime games) can sit in the price for longer,
especially in thinner markets. The model doesn't assume Kalshi is "wrong"
— it flags divergence and lets you decide whether it's mispricing or
information the book hasn't caught up to yet.

## Project layout

| File | Purpose |
|---|---|
| `kalshi_client.py` | Pulls Kalshi market/orderbook data (public, no auth needed); RSA-PSS request signing included for portfolio endpoints if you extend this to actually trade |
| `odds_client.py` | Pulls sportsbook moneylines from The Odds API |
| `devig.py` | Multiplicative and Shin's-method de-vigging |
| `edge_engine.py` | Matches a game across both sources, computes fee/spread-adjusted net edge |
| `notebook.ipynb` | Walkthrough + charts — the main deliverable |

## Setup

1. `pip install -r requirements.txt`
2. Kalshi: you already have an account. Public market data (`get_events`,
   `get_markets`, `get_orderbook`) needs no auth. If you later want
   portfolio/order endpoints, generate an API key pair under
   Settings → API in the Kalshi dashboard and pass a `KalshiCredentials`
   into `KalshiClient`.
3. Odds data: sign up free at https://the-odds-api.com (500 req/month
   free tier is enough for daily polling of NFL/NBA/MLB moneylines).
   `export ODDS_API_KEY=...`

## Honest limitations (worth saying out loud in an interview)

- **This is a known strategy**, not a proprietary discovery — the value
  of the project is in the implementation and the backtest discipline,
  not the idea itself.
- **De-vigged sportsbook price is not "true" probability** — it's the
  book's own risk-managed price, so this measures book-vs-market
  divergence, not divergence from ground truth.
- **Thin liquidity cuts both ways** — Kalshi's biggest divergences show
  up on markets with the widest spreads, which is exactly where your
  own order moves the price against you.
- **Needs a real backtest before any live money**, using historical
  Kalshi order-book snapshots (not just closing prices) or you'll
  overstate the edge. The `notebook.ipynb` backtest section uses
  synthetic data to demonstrate the framework — swap in logged history
  once you're collecting it.
