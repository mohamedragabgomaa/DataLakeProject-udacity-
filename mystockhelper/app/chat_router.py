from __future__ import annotations

import re

from .config import WATCHLIST, OPPORTUNITY_UNIVERSE

ARABIC_TICKER_ALIASES = {
    "نفيديا": "NVDA",
    "انفيديا": "NVDA",
    "nvidia": "NVDA",
    "أوراكل": "ORCL",
    "اوراكل": "ORCL",
    "oracle": "ORCL",
    "الاستك": "ESTC",
    "elastic": "ESTC",
    "اكس او اس": "XOS",
    "xos": "XOS",
    "بي سي ال ايه": "PCLA",
    "pcla": "PCLA",
}

KNOWN_TICKERS = set(WATCHLIST) | set(OPPORTUNITY_UNIVERSE) | {
    "SPY", "QQQ", "IWM", "DIA", "TSLA", "CRM", "ADBE", "NOW", "MU",
    "ARM", "SMCI", "PANW", "CRWD", "SHOP", "UBER", "COIN", "HOOD",
    "SOFI", "RDDT", "RKLB", "IONQ", "NFLX"
}


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def extract_ticker(text: str):
    normalized = _norm(text)

    for alias, ticker in ARABIC_TICKER_ALIASES.items():
        if alias in normalized:
            return ticker

    words = re.findall(r"\b[A-Za-z]{1,6}\b", text or "")
    for word in words:
        ticker = word.upper()
        if ticker in KNOWN_TICKERS:
            return ticker
    return None


def classify_message(text: str):
    normalized = _norm(text)
    ticker = extract_ticker(text)

    if not normalized:
        return {"intent": "empty", "ticker": None}

    if any(x in normalized for x in ["السلام", "مرحبا", "اهلا", "أهلا", "صباح الخير", "مساء الخير", "hello", "hi"]):
        return {"intent": "greeting", "ticker": ticker}

    if any(x in normalized for x in ["ساعدني", "مساعدة", "ايش اقدر", "وش تقدر", "ماذا تستطيع", "help"]):
        return {"intent": "help", "ticker": ticker}

    if any(x in normalized for x in ["كم الكاش", "كم السيولة", "السيولة عندي", "الكاش عندي", "buying power", "cash"]):
        return {"intent": "cash", "ticker": ticker}

    if any(x in normalized for x in ["محفظتي", "المحفظة", "وضع المحفظة", "كيف المحفظة", "portfolio"]):
        if any(x in normalized for x in ["خطر", "مخاطر", "اخطر", "أخطر", "risk"]):
            return {"intent": "portfolio_risk", "ticker": ticker}
        return {"intent": "portfolio", "ticker": ticker}

    if any(x in normalized for x in ["فرص", "فرصة", "اشتري", "شراء", "opportunit"]):
        if ticker:
            return {"intent": "stock", "ticker": ticker}
        return {"intent": "opportunities", "ticker": None}

    if any(x in normalized for x in ["الاسهم عندي", "الأسهم عندي", "اسهمي", "أسهمي", "watchlist"]):
        return {"intent": "watchlist", "ticker": ticker}

    if ticker:
        return {"intent": "stock", "ticker": ticker}

    if any(x in normalized for x in ["حلل", "حلل لي", "ما رأيك", "وش رايك", "ايش رايك", "رأيك في"]):
        return {"intent": "need_ticker", "ticker": None}

    return {"intent": "unknown", "ticker": ticker}
