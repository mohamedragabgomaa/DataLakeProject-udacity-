import os

# الأسهم الحالية / Portfolio Priority Tier 1
WATCHLIST = ["PCLA", "NVDA", "ORCL", "ESTC", "XOS"]

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
