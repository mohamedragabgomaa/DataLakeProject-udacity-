from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import ALLOWED_CHAT_ID, WATCHLIST, MIN_OPPORTUNITY_SCORE
from .market import get_snapshot
from .analysis import score_opportunity
from .telegram_api import send_message

NEW_YORK = ZoneInfo("America/New_York")
RIYADH = ZoneInfo("Asia/Riyadh")

# Liquid / actively traded U.S. names for the zero-cost opening scan.
# This is a curated scan universe, not the entire U.S. market.
OPENING_SCAN_UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "AVGO", "AMD",
    "TSLA", "PLTR", "NFLX", "CRM", "ORCL", "ADBE", "NOW", "MU",
    "ARM", "SMCI", "PANW", "CRWD", "SHOP", "UBER", "COIN", "HOOD",
    "SOFI", "RDDT", "RKLB", "IONQ", "ESTC", "PCLA", "XOS"
]

MARKET_ETFS = ["SPY", "QQQ", "IWM", "DIA"]


def _fmt(value, suffix="", digits=2):
    if value is None:
        return "غير متاح"
    return f"{value:.{digits}f}{suffix}"


def _is_report_window(now_ny: datetime) -> bool:
    # Scheduled twice in UTC to absorb U.S. daylight-saving changes.
    # Only the run that lands in the 10:00 New York hour is accepted.
    return now_ny.weekday() < 5 and now_ny.hour == 10


def _fetch_many(tickers):
    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(get_snapshot, ticker): ticker for ticker in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = None
    return results


def _candidate_action(snapshot, opportunity):
    daily = snapshot.daily_change_pct or 0
    move15 = snapshot.move_15m_pct or 0
    vol = snapshot.volume_spike

    if daily >= 5.0:
        return "انتظار Pullback - لا تطارد السهم بعد امتداد قوي."
    if opportunity.score >= 70 and move15 > 0 and vol is not None and vol >= 1.2:
        return "مرشح شراء مشروط بعد تأكيد Breakout/ثبات السعر؛ تجنب Market Order المتسرع."
    if opportunity.score >= MIN_OPPORTUNITY_SCORE:
        return "قائمة مراقبة قوية؛ انتظر تأكيد Momentum وVolume قبل الدخول."
    return "لا توجد إشارة شراء كافية حاليًا."


def build_opening_report(force: bool = False):
    now_ny = datetime.now(NEW_YORK)
    now_riyadh = datetime.now(RIYADH)

    if not force and not _is_report_window(now_ny):
        return None, "outside_opening_window"

    market = _fetch_many(MARKET_ETFS)
    spy = market.get("SPY")

    if not force and (spy is None or str(spy.market_state).upper() != "REGULAR"):
        return None, "market_not_regular"

    snapshots = _fetch_many(OPENING_SCAN_UNIVERSE)
    valid = [s for s in snapshots.values() if s is not None and s.daily_change_pct is not None]

    if not valid:
        return None, "market_data_unavailable"

    gainers = sorted(valid, key=lambda s: s.daily_change_pct, reverse=True)[:7]

    candidates = []
    for s in valid:
        if (s.daily_change_pct or 0) <= 0:
            continue
        o = score_opportunity(s)
        if o.score >= MIN_OPPORTUNITY_SCORE:
            candidates.append((o.score, s, o))

    candidates.sort(key=lambda item: item[0], reverse=True)
    candidates = candidates[:3]

    rows = [
        "📈 تقرير أول 30 دقيقة من السوق الأمريكي",
        f"🕙 نيويورك: {now_ny:%Y-%m-%d %H:%M}",
        f"🕔 الرياض: {now_riyadh:%Y-%m-%d %H:%M}",
        "",
        "🧭 حالة السوق",
    ]

    for ticker in MARKET_ETFS:
        s = market.get(ticker)
        if s is None:
            rows.append(f"{ticker}: بيانات غير متاحة")
        else:
            rows.append(
                f"{ticker}: {_fmt(s.daily_change_pct, '%')} | 15m {_fmt(s.move_15m_pct, '%')}"
            )

    rows += ["", "🔥 الأكثر صعودًا من قائمة الفحص"]
    for idx, s in enumerate(gainers, start=1):
        owned = " | ضمن محفظتك" if s.ticker in WATCHLIST else ""
        rows.append(
            f"{idx}) {s.ticker}: اليوم {_fmt(s.daily_change_pct, '%')} | "
            f"15m {_fmt(s.move_15m_pct, '%')} | Vol {_fmt(s.volume_spike, 'x')}{owned}"
        )

    rows += ["", "🎯 أفضل مرشحي الشراء المشروط"]
    if not candidates:
        rows.append("لا توجد فرصة تجاوزت فلتر التأكيد حاليًا؛ الانتظار أفضل من مطاردة السوق.")
    else:
        for rank, (_, s, o) in enumerate(candidates, start=1):
            rows += [
                f"{rank}) {s.ticker} | Opportunity Score {o.score}/100",
                f"السعر: {_fmt(s.price)} | اليوم: {_fmt(s.daily_change_pct, '%')} | 15m: {_fmt(s.move_15m_pct, '%')}",
                f"Volume: {_fmt(s.volume_spike, 'x')} | Risk {o.risk}/10 | Confidence {o.confidence}/100",
                f"لماذا؟ {o.rationale}",
                f"خطة التصرف: {_candidate_action(s, o)}",
                "",
            ]

    rows += [
        "⚠️ قاعدة Never Chase",
        "السهم الأكثر صعودًا ليس بالضرورة الأفضل للشراء. الامتداد السعري بدون Pullback/Volume/Catalyst مناسب قد يرفع المخاطر.",
        "",
        "📌 Data Quality",
        "البيانات Best-Effort وليست Exchange-Grade Real-Time. التقرير أداة Screening وليس أمر تنفيذ صفقة.",
        "",
        "ملاحظة: قائمة الفحص مركزة على أسهم أمريكية سائلة ونشطة وليست كامل السوق الأمريكي.",
    ]

    return "\n".join(rows), "ready"


def send_opening_report(force: bool = False):
    if not ALLOWED_CHAT_ID:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_ID is not configured.")

    report, status = build_opening_report(force=force)
    if not report:
        return {"sent": False, "status": status}

    send_message(ALLOWED_CHAT_ID, report)
    return {"sent": True, "status": status}
