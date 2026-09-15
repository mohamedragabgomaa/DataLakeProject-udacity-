import json
import os

DEFAULT_WATCHLIST = ["PCLA", "NVDA", "ORCL", "ESTC", "XOS"]


def _load_portfolio():
    raw = os.getenv("PORTFOLIO_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        cleaned = {}
        for ticker, position in payload.items():
            symbol = str(ticker).upper().strip()
            shares = float(position.get("shares", 0))
            avg_cost = float(position.get("avg_cost", 0))
            if symbol and shares > 0 and avg_cost > 0:
                cleaned[symbol] = {"shares": shares, "avg_cost": avg_cost}
        return cleaned
    except Exception:
        return {}


# Portfolio values are stored privately in Vercel Environment Variables,
# never committed to the public GitHub repository.
PORTFOLIO = _load_portfolio()
WATCHLIST = list(PORTFOLIO.keys()) if PORTFOLIO else DEFAULT_WATCHLIST

# Universe أولي لفرص جديدة. نستبعد الأسهم الحالية تلقائياً.
# تم إبقاؤه محدوداً حتى يعمل الفحص ضمن الموارد المجانية وبزمن استجابة معقول.
OPPORTUNITY_UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "AVGO", "AMD", "PLTR"
]

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
MONITOR_SECRET = os.getenv("MONITOR_SECRET", "").strip()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()

RIYADH_TZ = "Asia/Riyadh"
NEW_YORK_TZ = "America/New_York"

MIN_ABS_15M_MOVE_PCT = 1.0
MIN_15M_ZSCORE = 3.0
MIN_ABS_DAILY_MOVE_PCT = 2.0
HIGH_DAILY_MOVE_PCT = 5.0
VOLUME_SPIKE_MULTIPLIER = 2.5

# فلتر فرص الشراء الجديدة
MIN_OPPORTUNITY_SCORE = 55
HIGH_OPPORTUNITY_SCORE = 70
