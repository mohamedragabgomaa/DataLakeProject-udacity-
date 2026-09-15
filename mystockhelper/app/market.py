from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, stdev, median
import math
import requests

UA = "Mozilla/5.0 MyStockHelper2090/1.0"
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

@dataclass
class MarketSnapshot:
    ticker: str
    price: float | None
    previous_close: float | None
    daily_change_pct: float | None
    timestamp: datetime
    currency: str | None
    market_state: str | None
    freshness: str
    source: str
    move_15m_pct: float | None = None
    move_60m_pct: float | None = None
    zscore_15m: float | None = None
    latest_bar_volume: float | None = None
    median_bar_volume: float | None = None
    volume_spike: float | None = None
    session_high: float | None = None
    session_low: float | None = None
    recent_split: bool = False
    recent_dividend: bool = False

def _safe_float(x):
    try:
        if x is None: return None
        x = float(x)
        if math.isnan(x): return None
        return x
    except Exception:
        return None

def _get_chart(ticker: str, interval="5m", range_="5d", include_prepost=True):
    r = requests.get(BASE.format(ticker=ticker), params={"interval":interval,"range":range_,"includePrePost":str(include_prepost).lower(),"events":"div,splits"}, headers={"User-Agent": UA}, timeout=12)
    r.raise_for_status()
    payload = r.json()
    error = payload.get("chart", {}).get("error")
    if error: raise RuntimeError(f"Market source error for {ticker}: {error}")
    result = payload.get("chart", {}).get("result") or []
    if not result: raise RuntimeError(f"No market data returned for {ticker}.")
    return result[0]

def _pct(new, old):
    if new is None or old in (None,0): return None
    return (new / old - 1.0) * 100.0

def _lag_return(closes, bars):
    vals = [c for c in closes if c is not None]
    if len(vals) <= bars: return None
    return _pct(vals[-1], vals[-1-bars])

def _rolling_returns(closes, bars):
    vals = [c for c in closes if c is not None]
    return [r for i in range(bars,len(vals)) if (r := _pct(vals[i], vals[i-bars])) is not None]

def _zscore(value, history):
    if value is None or len(history) < 20: return None
    hist = history[:-1] if len(history) > 1 else history
    if len(hist) < 2: return None
    sd = stdev(hist)
    return 0.0 if sd == 0 else (value - mean(hist)) / sd

def get_snapshot(ticker: str) -> MarketSnapshot:
    ticker = ticker.upper().strip()
    result = _get_chart(ticker)
    meta = result.get("meta", {})
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [_safe_float(x) for x in (quote.get("close") or [])]
    highs = [_safe_float(x) for x in (quote.get("high") or [])]
    lows = [_safe_float(x) for x in (quote.get("low") or [])]
    volumes = [_safe_float(x) for x in (quote.get("volume") or [])]
    price = _safe_float(meta.get("regularMarketPrice"))
    if price is None:
        valid = [x for x in closes if x is not None]
        price = valid[-1] if valid else None
    previous_close = _safe_float(meta.get("previousClose")) or _safe_float(meta.get("chartPreviousClose"))
    latest_ts = meta.get("regularMarketTime")
    ts = datetime.fromtimestamp(int(latest_ts), tz=timezone.utc) if latest_ts else (datetime.fromtimestamp(int(timestamps[-1]), tz=timezone.utc) if timestamps else datetime.now(timezone.utc))
    move_15 = _lag_return(closes, 3)
    move_60 = _lag_return(closes, 12)
    z15 = _zscore(move_15, _rolling_returns(closes, 3))
    valid_vols = [v for v in volumes if v is not None and v > 0]
    latest_vol = valid_vols[-1] if valid_vols else None
    med_vol = median(valid_vols[:-1]) if len(valid_vols) > 5 else None
    vol_spike = latest_vol / med_vol if latest_vol is not None and med_vol not in (None,0) else None
    valid_highs = [x for x in highs[-78:] if x is not None]
    valid_lows = [x for x in lows[-78:] if x is not None]
    events = result.get("events") or {}
    return MarketSnapshot(ticker=ticker, price=price, previous_close=previous_close, daily_change_pct=_pct(price,previous_close), timestamp=ts, currency=meta.get("currency"), market_state=meta.get("marketState"), freshness="BEST_EFFORT / NOT EXCHANGE-GRADE REAL-TIME", source="Yahoo Finance chart endpoint (unofficial/best-effort)", move_15m_pct=move_15, move_60m_pct=move_60, zscore_15m=z15, latest_bar_volume=latest_vol, median_bar_volume=med_vol, volume_spike=vol_spike, session_high=max(valid_highs) if valid_highs else None, session_low=min(valid_lows) if valid_lows else None, recent_split=bool(events.get("splits")), recent_dividend=bool(events.get("dividends")))
