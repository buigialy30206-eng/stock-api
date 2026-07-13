"""
Stock Price API
Real-time stock quotes via Twelve Data. Free API key required.
"""
import subprocess, json as _json, time, threading
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Get free key at https://twelvedata.com/apikey
API_KEY = "demo"  # Replace with your free key at https://twelvedata.com/apikey

app = FastAPI(title="Stock Price API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "source": "Twelve Data"}

_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 300


class StockResult(BaseModel):
    symbol: str
    name: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    previous_close: Optional[float] = None
    exchange: Optional[str] = None
    currency: str = "USD"
    error: Optional[str] = None


def curl_get(url: str) -> dict:
    cmd = ["curl", "-s", "--connect-timeout", "5", "--max-time", "8", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return _json.loads(r.stdout) if r.returncode == 0 and r.stdout else {}
    except:
        return {}


def get_quote(symbol: str) -> StockResult:
    data = curl_get(f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={API_KEY}")
    if not data or "symbol" not in data:
        return StockResult(symbol=symbol, error=data.get("message", "Data source unavailable"))

    return StockResult(
        symbol=symbol,
        name=data.get("name"),
        price=float(data["close"]) if data.get("close") else None,
        change=float(data.get("change", 0)) if data.get("change") else None,
        change_percent=float(data.get("percent_change", 0)) if data.get("percent_change") else None,
        open=float(data["open"]) if data.get("open") else None,
        high=float(data["high"]) if data.get("high") else None,
        low=float(data["low"]) if data.get("low") else None,
        volume=int(data.get("volume", 0)) if data.get("volume") else None,
        previous_close=float(data.get("previous_close", 0)) if data.get("previous_close") else None,
        exchange=data.get("exchange"),
        currency=data.get("currency", "USD"),
    )


@app.get("/")
async def root():
    return {"service": "Stock Price API", "version": "2.0.0", "related": ["Currency Converter API", "Company Info API"]}


@app.get("/quote", response_model=StockResult)
async def quote(symbol: str = Query(..., description="Stock symbol, e.g. AAPL, TSLA")):
    sym = symbol.upper()
    with _cache_lock:
        entry = _cache.get(sym)
        if entry and time.time() - entry["ts"] < CACHE_TTL:
            return StockResult(**entry["data"])

    result = get_quote(sym)
    if not result.error:
        with _cache_lock:
            _cache[sym] = {"data": result.model_dump(), "ts": time.time()}
            if len(_cache) > 500:
                oldest = min(_cache, key=lambda k: _cache[k]["ts"])
                del _cache[oldest]
    return result
