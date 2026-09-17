from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import ALLOWED_CHAT_ID, WATCHLIST, MIN_OPPORTUNITY_SCORE
from .market import get_snapshot
from .analysis import score_opportunity
from .market_context import get_market_context
from .telegram_api import send_message

NEW_YORK = ZoneInfo("America/New_York")
RIYADH = ZoneInfo("Asia/Riyadh")

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


def _compact_money(value):
    if value is None:
        return "غير متاح"
    value = float(value)
    if abs(value) >= 1_000_000_000:
        return f"${value/1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    return f"${value:,.0f}"


def _is_report_window(now_ny: datetime) -> bool:
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


def _candidate_action(snapshot, opportunity, context):
    daily = snapshot.daily_change_pct or 0
    move15 = snapshot.move_15m_pct or 0
    vol = snapshot.volume_spike
    catalyst = context.get("catalyst", "غير مؤكد") if context else "غير مؤكد"

    if daily >= 5.0:
        return f"انتظر Pullback ولا تطارد السعر. Catalyst: {catalyst}."
    if opportunity.score >= 70 and move15 > 0 and vol is not None and vol >= 1.2:
        return f"فرصة مراقبة قوية بعد تأكيد Breakout وثبات Volume. Catalyst: {catalyst}."
    if opportunity.score >= MIN_OPPORTUNITY_SCORE:
        return f"قائمة مراقبة قوية؛ انتظر تأكيد Momentum/Volume. Catalyst: {catalyst}."
    return "لا توجد إشارة كافية حاليًا."


def _report_title(now_ny: datetime, force: bool, scheduled: bool):
    if scheduled and not _is_report_window(now_ny):
        return "⚠️ تقرير السوق - تشغيل تلقائي متأخر"
    if force and not scheduled:
        return "🧪 تقرير سوق - اختبار يدوي"
    return "📈 تقرير أول 30 دقيقة من السوق الأمريكي"


def build_opening_report(force: bool = False, scheduled: bool = False):
    now_ny = datetime.now(NEW_YORK)
    now_riyadh = datetime.now(RIYADH)

    if scheduled and now_ny.weekday() >= 5:
        return None, "weekend"

    if not force and not scheduled and not _is_report_window(now_ny):
        return None, "outside_opening_window"

    market = _fetch_many(MARKET_ETFS)
    spy = market.get("SPY")

    # Scheduled runs may arrive late, but only send while the U.S. market is still regular.
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

    contexts = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(get_market_context, s.ticker): s.ticker for _, s, _ in candidates}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                contexts[ticker] = future.result()
            except Exception:
                contexts[ticker] = None

    late_note = []
    if scheduled and not _is_report_window(now_ny):
        late_note = [
            "⚠️ تنبيه: GitHub Actions شغّل المهمة بعد نافذة أول 30 دقيقة، لذلك هذه قراءة السوق وقت التشغيل وليست Opening Snapshot.",
            "",
        ]

    rows = [
        _report_title(now_ny, force, scheduled),
        f"🕙 نيويورك: {now_ny:%Y-%m-%d %H:%M}",
        f"🕔 الرياض: {now_riyadh:%Y-%m-%d %H:%M}",
        "",
        *late_note,
        "🧭 حالة السوق",
    ]

    for ticker in MARKET_ETFS:
        s = market.get(ticker)
        if s is None:
            rows.append(f"{ticker}: بيانات غير متاحة")
        else:
            rows.append(f"{ticker}: {_fmt(s.daily_change_pct, '%')} | 15m {_fmt(s.move_15m_pct, '%')}")

    rows += ["", "🔥 الأكثر صعودًا من قائمة الفحص"]
    for idx, s in enumerate(gainers, start=1):
        owned = " | ضمن محفظتك" if s.ticker in WATCHLIST else ""
        rows.append(
            f"{idx}) {s.ticker}: اليوم {_fmt(s.daily_change_pct, '%')} | "
            f"15m {_fmt(s.move_15m_pct, '%')} | Vol {_fmt(s.volume_spike, 'x')}{owned}"
        )

    section_title = "🎯 أفضل فرص المراقبة بعد أول 30 دقيقة" if _is_report_window(now_ny) else "🎯 أفضل فرص المراقبة وقت التشغيل"
    rows += ["", section_title]
    if not candidates:
        rows.append("لا توجد فرصة تجاوزت فلتر التأكيد حاليًا؛ الانتظار أفضل من مطاردة السوق.")
    else:
        for rank, (_, s, o) in enumerate(candidates, start=1):
            context = contexts.get(s.ticker) or {}
            fundamentals = context.get("fundamentals") or {}
            rows += [
                f"{rank}) {s.ticker} | Opportunity Score {o.score}/100",
                f"السعر: {_fmt(s.price)} | اليوم: {_fmt(s.daily_change_pct, '%')} | 15m: {_fmt(s.move_15m_pct, '%')}",
                f"Volume: {_fmt(s.volume_spike, 'x')} | Risk {o.risk}/10 | Confidence {o.confidence}/100",
                f"Market Cap: {_compact_money(fundamentals.get('market_cap'))} | Earnings: {context.get('earnings', 'غير متاح')}",
                f"Catalyst: {context.get('catalyst', 'غير مؤكد')}",
                f"لماذا؟ {o.rationale}",
                f"خطة المراقبة: {_candidate_action(s, o, context)}",
                "",
            ]

    rows += [
        "⚠️ قاعدة Never Chase",
        "السهم الأكثر صعودًا ليس بالضرورة الأفضل. لا يمكن معرفة القمة مسبقًا بشكل موثوق؛ راقب استمرار Momentum وVolume بدل مطاردة السعر.",
        "",
        "📌 Data Quality",
        "البيانات والسياق Best-Effort وليست Exchange-Grade Real-Time، وقد تكون Catalyst/News/Fundamentals ناقصة أو متأخرة.",
        "ملاحظة: قائمة الفحص مركزة على أسهم أمريكية سائلة ونشطة وليست كامل السوق الأمريكي.",
    ]

    status = "ready_late" if scheduled and not _is_report_window(now_ny) else "ready"
    return "\n".join(rows), status


def send_opening_report(force: bool = False, scheduled: bool = False):
    if not ALLOWED_CHAT_ID:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_ID is not configured.")

    report, status = build_opening_report(force=force, scheduled=scheduled)
    if not report:
        return {"sent": False, "status": status}

    send_message(ALLOWED_CHAT_ID, report)
    return {"sent": True, "status": status}
