"""
Stock Price API
Live stock data via Yahoo Finance (free, no API key).
"""

import subprocess, json as _json
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Stock Price API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}



class StockResult(BaseModel):
    symbol: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    previous_close: Optional[float] = None
    market_cap: Optional[str] = None
    currency: str = "USD"
    error: Optional[str] = None


def curl_get(url: str) -> dict:
    cmd = ["curl", "-s", "--connect-timeout", "8", "--max-time", "12", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return _json.loads(r.stdout) if r.returncode == 0 and r.stdout else {}


def get_quote(symbol: str) -> StockResult:
    data = curl_get(f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}")
    if not data:
        return StockResult(symbol=symbol, error="Could not fetch data")

    result = data.get("chart", {}).get("result", [])
    if not result:
        return StockResult(symbol=symbol, error="Symbol not found")

    meta = result[0].get("meta", {})
    return StockResult(
        symbol=symbol,
        price=meta.get("regularMarketPrice"),
        change=meta.get("regularMarketChange"),
        change_percent=meta.get("regularMarketChangePercent"),
        open=meta.get("regularMarketOpen"),
        high=meta.get("regularMarketDayHigh"),
        low=meta.get("regularMarketDayLow"),
        volume=meta.get("regularMarketVolume"),
        previous_close=meta.get("previousClose"),
        market_cap=meta.get("marketCap"),
        currency=meta.get("currency", "USD"),
    )


@app.api_route("/health", methods=["GET", "HEAD"])
async def health(): return {"status": "ok", "source": "Yahoo Finance"}


@app.get("/")
async def root(): return {"service": "Stock Price API", "version": "1.0.0"}


@app.get("/quote", response_model=StockResult)
async def quote(symbol: str = Query(..., description="Stock symbol, e.g. AAPL, TSLA, GOOGL")):
    return get_quote(symbol.upper())
