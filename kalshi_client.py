"""
kalshi_client.py

Thin wrapper around the Kalshi v2 REST API.

Public market-data endpoints (GET /markets, /events, /markets/{ticker}/orderbook)
do not require authentication. Portfolio/order endpoints do, using Kalshi's
RSA-PSS request-signing scheme:

    message   = f"{timestamp_ms}{METHOD}{path}"
    signature = RSA-PSS-SHA256(private_key, message)

headers:
    KALSHI-ACCESS-KEY:       <api_key_id>
    KALSHI-ACCESS-TIMESTAMP: <timestamp_ms>
    KALSHI-ACCESS-SIGNATURE: <base64 signature>

Docs: https://trading-api.readme.kalshi.com/
"""

import base64
import time
from dataclasses import dataclass
from typing import Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PROD_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"


@dataclass
class KalshiCredentials:
    """Only needed for authenticated (portfolio/order) endpoints."""
    api_key_id: str
    private_key_path: str  # path to the PEM file Kalshi gives you once


class KalshiClient:
    def __init__(self, base_url: str = PROD_BASE_URL, credentials: Optional[KalshiCredentials] = None):
        self.base_url = base_url
        self.credentials = credentials
        self._private_key = None
        if credentials:
            with open(credentials.private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(f.read(), password=None)
        self.session = requests.Session()

    # ---------- auth ----------

    def _signed_headers(self, method: str, path: str) -> dict:
        if not self.credentials or not self._private_key:
            raise RuntimeError("No credentials configured — this call needs an authenticated client.")
        timestamp_ms = str(int(time.time() * 1000))
        message = f"{timestamp_ms}{method.upper()}{path}".encode("utf-8")
        signature = self._private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.credentials.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        }

    def _get(self, path: str, params: Optional[dict] = None, authenticated: bool = False, max_retries: int = 4) -> dict:
        url = f"{self.base_url}{path}"
        headers = self._signed_headers("GET", f"/trade-api/v2{path}") if authenticated else {}
        for attempt in range(max_retries + 1):
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429 and attempt < max_retries:
                # Respect Retry-After if Kalshi sends one; otherwise back off
                # exponentially. Confirmed in practice: running this workflow
                # many times a day (get_markets is called once per open event,
                # so ~15-40 calls per run) trips Kalshi's rate limit.
                wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()  # exhausted retries -- raise the last error
        return resp.json()

    # ---------- public market data ----------

    def get_events(self, series_ticker: Optional[str] = None, status: str = "open") -> list:
        """List events (e.g. one event per game/week). series_ticker filters to a sport,
        e.g. 'KXNFLGAME', 'KXNBAGAME', 'KXMLBGAME' (verify exact prefixes in the Kalshi UI —
        Kalshi periodically renames series tickers)."""
        params = {"status": status}
        if series_ticker:
            params["series_ticker"] = series_ticker
        data = self._get("/events", params=params)
        return data.get("events", [])

    def get_markets(self, event_ticker: Optional[str] = None, status: str = "open") -> list:
        params = {"status": status}
        if event_ticker:
            params["event_ticker"] = event_ticker
        data = self._get("/markets", params=params)
        return data.get("markets", [])

    def get_market(self, ticker: str) -> dict:
        return self._get(f"/markets/{ticker}")["market"]

    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        return self._get(f"/markets/{ticker}/orderbook", params={"depth": depth})["orderbook"]

    # ---------- fees ----------

    @staticmethod
    def taker_fee(price_cents: int, contracts: int) -> float:
        """Kalshi's published taker fee formula: fee = round_up(0.07 * C * P * (1-P))
        where P is price in dollars (0-1) and C is number of contracts.
        Verify the current multiplier (it has changed across market categories) at
        kalshi.com/fees before trusting this in a live signal calc."""
        p = price_cents / 100
        import math
        fee = 0.07 * contracts * p * (1 - p)
        return math.ceil(fee * 100) / 100  # round up to the cent
