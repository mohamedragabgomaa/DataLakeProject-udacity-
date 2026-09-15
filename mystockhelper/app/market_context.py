from __future__ import annotations

from datetime import datetime, timezone
import requests

from .sec import latest_material_filing

UA = "Mozilla/5.0 MyStockHelper/1.0"
QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"


def _age_hours(ts):
    try:
        now = datetime.now(timezone.utc).timestamp()
        return max(0.0, (now - float(ts)) / 3600.0)
    except Exception:
        return None


def _quote_context(ticker):
    try:
        r = requests.get(
            QUOTE_URL,
            params={"symbols": ticker},
            headers={"User-Agent": UA},
            timeout=8,
        )
        r.raise_for_status()
        result = (((r.json() or {}).get("quoteResponse") or {}).get("result") or [])
        q = result[0] if result else {}
        return {
            "market_cap": q.get("marketCap"),
            "trailing_pe": q.get("trailingPE"),
            "forward_pe": q.get("forwardPE"),
            "avg_volume_3m": q.get("averageDailyVolume3Month"),
            "earnings_ts": q.get("earningsTimestamp") or q.get("earningsTimestampStart"),
        }
    except Exception:
        return {}


def _news_context(ticker):
    try:
        r = requests.get(
            SEARCH_URL,
            params={
                "q": ticker,
                "quotesCount": 1,
                "newsCount": 5,
                "enableFuzzyQuery": "false",
            },
            headers={"User-Agent": UA},
            timeout=8,
        )
        r.raise_for_status()
        items = (r.json() or {}).get("news") or []
        news = []
        for item in items[:5]:
            ts = item.get("providerPublishTime")
            news.append({
                "title": item.get("title"),
                "publisher": item.get("publisher"),
                "age_hours": _age_hours(ts),
            })
        return news
    except Exception:
        return []


def get_market_context(ticker):
    ticker = ticker.upper().strip()
    quote = _quote_context(ticker)
    news = _news_context(ticker)

    filing = None
    try:
        filing = latest_material_filing(ticker)
    except Exception:
        filing = None

    recent_news = [n for n in news if n.get("age_hours") is not None and n["age_hours"] <= 24]
    catalyst = "غير مؤكد"
    catalyst_score = 0

    if filing:
        catalyst = f"SEC {filing.get('form')} بتاريخ {filing.get('date')}"
        catalyst_score += 10
    if recent_news:
        first = recent_news[0]
        catalyst = f"خبر حديث: {first.get('title') or 'عنوان غير متاح'}"
        catalyst_score += 10

    earnings_text = "غير متاح"
    earnings_ts = quote.get("earnings_ts")
    if earnings_ts:
        try:
            dt = datetime.fromtimestamp(float(earnings_ts), tz=timezone.utc)
            earnings_text = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    fundamentals = {
        "market_cap": quote.get("market_cap"),
        "trailing_pe": quote.get("trailing_pe"),
        "forward_pe": quote.get("forward_pe"),
        "avg_volume_3m": quote.get("avg_volume_3m"),
    }

    return {
        "ticker": ticker,
        "fundamentals": fundamentals,
        "earnings": earnings_text,
        "news": news,
        "sec": filing,
        "catalyst": catalyst,
        "catalyst_score": min(catalyst_score, 20),
        "source_note": "Best-Effort Yahoo/SEC context; may be incomplete or delayed.",
    }
