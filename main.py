"""
Stock Price API
Live stock data. Alpha Vantage free tier or Yahoo fallback.
"""
import subprocess, json as _json, time, threading
from typing import Optional
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Stock Price API", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Cache
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 300  # 5 min for stock data

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
    cmd = ["curl", "-s", "--connect-timeout", "5", "--max-time", "8", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return _json.loads(r.stdout) if r.returncode == 0 and r.stdout else {}
    except:
        return {}

def get_quote(symbol: str) -> StockResult:
    # Try Yahoo first
    data = curl_get(f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}")
    if data:
        result = data.get("chart", {}).get("result", [])
        if result:
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

    # Fallback: Alpha Vantage free endpoint
    data2 = curl_get(
        f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=demo"
    )
    if data2 and "Global Quote" in data2:
        q = data2["Global Quote"]
        try:
            return StockResult(
                symbol=symbol,
                price=float(q.get("05. price", 0)),
                change=float(q.get("09. change", 0)),
                change_percent=float(q.get("10. change percent", "0%").replace("%", "")),
            )
        except:
            pass

    return StockResult(symbol=symbol, error="Symbol not found or data source unavailable")

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "cache_size": len(_cache)}

@app.get("/")
async def root():
    return {"service": "Stock Price API", "version": "1.1.0"}

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
