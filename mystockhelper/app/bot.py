from __future__ import annotations
from .config import WATCHLIST, OPPORTUNITY_UNIVERSE, ALLOWED_CHAT_ID, MIN_OPPORTUNITY_SCORE, PORTFOLIO, CASH_SAR, CASH_USD
from .market import get_snapshot
from .analysis import assess, status_line, score_opportunity
from .portfolio_metrics import portfolio_totals, position_metrics
from .portfolio_advice import break_even_gap_pct, portfolio_aware_view, top_actions
from .chat_router import classify_message
from .telegram_api import send_message

HELP = """MyStockHelper

يمكنك استخدام الأوامر أو التحدث معي بالعربية بشكل طبيعي.

الأوامر:
/status - تقرير المحفظة بالعربية
/stock NVDA - تحليل سهم محدد
/watchlist - عرض الأسهم الحالية
/opportunities - فحص فرص شراء جديدة
/chatid - عرض Telegram Chat ID
/help - المساعدة

أمثلة محادثة:
كيف وضع محفظتي اليوم؟
حلل لي NVDA
ما رأيك في ORCL؟
كم السيولة عندي؟
ما أخطر مركز في المحفظة؟
هل توجد فرص شراء الآن؟

ملاحظة Market Data:
المصدر المجاني Best-Effort وليس Exchange-Grade Real-Time."""


def _authorized(chat_id):
    return bool(ALLOWED_CHAT_ID) and str(chat_id) == str(ALLOWED_CHAT_ID)


def _money(x):
    return "غير متاح" if x is None else f"${x:,.2f}"


def _sar(x):
    return "غير متاح" if x is None else f"{x:,.0f} SAR"


def _pct(x):
    return "غير متاح" if x is None else f"{x:+.2f}%"


def _pct_plain(x):
    return "غير متاح" if x is None else f"{x:.2f}%"


def _portfolio_report():
    snapshots = {}
    assessments = {}
    prices = {}

    for ticker in WATCHLIST:
        try:
            s = get_snapshot(ticker)
            a = assess(s, include_sec=False)
            snapshots[ticker] = s
            assessments[ticker] = a
            prices[ticker] = s.price
        except Exception:
            snapshots[ticker] = None
            assessments[ticker] = None
            prices[ticker] = None

    totals = portfolio_totals(prices)
    position_views = []

    for ticker in WATCHLIST:
        s = snapshots.get(ticker)
        a = assessments.get(ticker)
        pos = PORTFOLIO.get(ticker)
        if not pos or s is None or s.price is None or a is None:
            continue
        m = position_metrics(ticker, s.price, totals['portfolio_value'])
        view = portfolio_aware_view(ticker, s, a, m)
        position_views.append({
            "ticker": ticker,
            "pnl_pct": m['pnl_pct'],
            "weight_pct": m['weight_pct'],
            "risk": a.risk,
            "view": view,
        })

    rows = [
        "📊 تقرير المحفظة الاستثمارية",
        "",
        "🧭 الملخص التنفيذي",
        f"إجمالي تكلفة شراء الأسهم: {_money(totals['total_cost'])}",
        f"القيمة الحالية للأسهم: {_money(totals['total_value'])}",
        f"السيولة المتاحة: {_sar(CASH_SAR)} ≈ {_money(CASH_USD)}",
        f"إجمالي قيمة المحفظة: {_money(totals['portfolio_value'])}",
        f"الربح/الخسارة غير المحققة للأسهم: {_money(totals['pnl'])} ({_pct(totals['pnl_pct'])})",
        f"نسبة الاستثمار: {_pct_plain(totals['invested_pct'])} | Cash Allocation: {_pct_plain(totals['cash_pct'])}",
        f"Buying Power التقريبي: {_money(totals['cash_usd'])}",
        "",
        "🎯 أهم إجراءات اليوم",
    ]

    for action in top_actions(position_views, totals.get('cash_pct')):
        rows.append(action)

    rows += ["", "📌 تفاصيل المراكز"]

    for ticker in WATCHLIST:
        s = snapshots.get(ticker)
        a = assessments.get(ticker)
        pos = PORTFOLIO.get(ticker)

        if not pos:
            rows += [f"⚪ {ticker}", "بيانات المركز غير موجودة في PORTFOLIO_JSON", ""]
            continue

        if s is None or s.price is None or a is None:
            rows += [
                f"⚪ {ticker}",
                f"الكمية: {pos['shares']:g} | متوسط الشراء: {_money(pos['avg_cost'])}",
                "بيانات السوق غير متاحة حاليًا.",
                "",
            ]
            continue

        m = position_metrics(ticker, s.price, totals['portfolio_value'])
        view = portfolio_aware_view(ticker, s, a, m)
        gap = break_even_gap_pct(s.price, m['avg_cost'])
        if gap is None:
            break_even_text = "غير متاحة"
        elif gap <= 0:
            break_even_text = f"فوق Break-even بنسبة {abs(gap):.2f}%"
        else:
            break_even_text = f"يحتاج ارتفاع {gap:.2f}% للوصول إلى Break-even"

        rows += [
            f"{view['level']} {ticker} — {view['label']}",
            f"الكمية: {m['shares']:g} سهم | متوسط الشراء: {_money(m['avg_cost'])}",
            f"السعر الحالي: {_money(s.price)} | قيمة المركز: {_money(m['value'])}",
            f"P/L: {_money(m['pnl'])} ({_pct(m['pnl_pct'])}) | الوزن من إجمالي المحفظة: {_pct_plain(m['weight_pct'])}",
            f"Break-even: {break_even_text}",
            f"اليوم: {_pct(s.daily_change_pct)} | 15m: {_pct(s.move_15m_pct)} | Trend: {a.trend}",
            f"Risk: {a.risk}/10 | Confidence: {a.confidence}/100",
            f"التقييم الفني: {a.recommendation}",
            f"التوصية Portfolio-Aware: {view['recommendation']}",
            "",
        ]

    concentrations = []
    for ticker in WATCHLIST:
        s = snapshots.get(ticker)
        if s is None or s.price is None:
            continue
        m = position_metrics(ticker, s.price, totals['portfolio_value'])
        if m and m['weight_pct'] is not None and m['weight_pct'] >= 35:
            concentrations.append(f"{ticker} {m['weight_pct']:.1f}%")

    rows += ["🛡️ Concentration Risk"]
    if concentrations:
        rows.append("تركيز مرتفع في: " + "، ".join(concentrations))
    else:
        rows.append("لا يوجد مركز منفرد يتجاوز 35% من إجمالي قيمة المحفظة شامل السيولة.")

    rows += [
        "",
        "📌 ملاحظة:",
        "الأسعار Best-Effort وليست Exchange-Grade Real-Time. الأرقام المعروضة تقديرية وتعتمد على بيانات السوق المتاحة.",
        "",
        "استخدم /opportunities لفحص فرص شراء جديدة.",
    ]
    return "\n".join(rows)


def _opportunities_report():
    candidates = []
    errors = []

    for ticker in OPPORTUNITY_UNIVERSE:
        if ticker in WATCHLIST:
            continue
        try:
            s = get_snapshot(ticker)
            o = score_opportunity(s)
            if o.score >= MIN_OPPORTUNITY_SCORE:
                candidates.append((o.score, s, o))
        except Exception:
            errors.append(ticker)

    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:5]

    rows = ["🔎 فرص شراء جديدة", ""]

    if not candidates:
        rows += [
            "لا توجد حاليًا فرصة جديدة تجاوزت فلتر التأكيد.",
            "القرار الصحيح هنا هو الانتظار بدل إجبار السوق على إعطاء فرصة.",
        ]
    else:
        for _, s, o in candidates:
            rows += [
                f"{o.ticker} | Score {o.score}/100",
                f"التصنيف: {o.label}",
                f"السعر: {s.price if s.price is not None else 'غير متاح'}",
                f"التغير اليومي: {s.daily_change_pct:.2f}%" if s.daily_change_pct is not None else "التغير اليومي: غير متاح",
                f"15m Move: {s.move_15m_pct:.2f}%" if s.move_15m_pct is not None else "15m Move: غير متاح",
                f"Volume Spike: {s.volume_spike:.2f}x" if s.volume_spike is not None else "Volume Spike: غير متاح",
                f"Risk: {o.risk}/10 | Confidence: {o.confidence}/100",
                f"الأسباب: {o.rationale}",
                "التوصية: لا تدخل Market Order مباشرة؛ راقب Pullback/Breakout confirmation وCatalyst موثوق قبل الشراء.",
                "",
            ]

    rows += [
        "⚠️ تنبيه:",
        "فرص الشراء هنا هي Screening وليست ضمانًا أو توصية مالية ملزمة. المصدر المجاني ليس Exchange-Grade Real-Time.",
    ]

    return "\n".join(rows)


def _stock_report(ticker):
    try:
        s = get_snapshot(ticker)
        a = assess(s)
        return a.text
    except Exception as e:
        return f"{ticker}: البيانات غير متاحة / Unable to Verify.\nالسبب: {type(e).__name__}"


def _cash_report():
    return (
        "💰 السيولة الحالية\n"
        f"السيولة: {_sar(CASH_SAR)} ≈ {_money(CASH_USD)}\n"
        f"Buying Power التقريبي: {_money(CASH_USD)}\n"
        "هذه القيمة لا تشمل أي تحويلات أو التزامات مستقبلية غير مسجلة في البوت."
    )


def _portfolio_risk_report():
    prices = {}
    items = []
    for ticker in WATCHLIST:
        try:
            s = get_snapshot(ticker)
            prices[ticker] = s.price
        except Exception:
            prices[ticker] = None

    totals = portfolio_totals(prices)
    for ticker in WATCHLIST:
        price = prices.get(ticker)
        if price is None:
            continue
        m = position_metrics(ticker, price, totals['portfolio_value'])
        if m:
            items.append((m['weight_pct'] or 0, ticker, m))

    if not items:
        return "تعذر حساب مخاطر المحفظة حاليًا بسبب نقص بيانات السوق."

    items.sort(reverse=True)
    weight, ticker, m = items[0]
    return (
        "🛡️ أبرز مخاطر المحفظة حاليًا\n"
        f"أكبر مركز: {ticker}\n"
        f"الوزن من إجمالي المحفظة: {weight:.2f}%\n"
        f"P/L للمركز: {_pct(m['pnl_pct'])}\n"
        "كلما زاد وزن مركز واحد ارتفع Concentration Risk حتى لو كان السهم جيدًا فنيًا."
    )


def _handle_conversation(chat_id, text):
    intent = classify_message(text)
    kind = intent.get("intent")
    ticker = intent.get("ticker")

    if kind == "greeting":
        send_message(chat_id, "أهلًا 👋 أنا MyStockHelper. اسألني عن محفظتك أو السيولة أو الفرص أو أي سهم بالرمز.")
        return True
    if kind == "help":
        send_message(chat_id, HELP)
        return True
    if kind == "cash":
        send_message(chat_id, _cash_report())
        return True
    if kind == "portfolio_risk":
        send_message(chat_id, _portfolio_risk_report())
        return True
    if kind == "portfolio":
        send_message(chat_id, _portfolio_report())
        return True
    if kind == "opportunities":
        send_message(chat_id, _opportunities_report())
        return True
    if kind == "watchlist":
        send_message(chat_id, "📌 الأسهم الحالية:\n" + "\n".join(f"- {x}" for x in WATCHLIST))
        return True
    if kind == "stock" and ticker:
        send_message(chat_id, _stock_report(ticker))
        return True
    if kind == "need_ticker":
        send_message(chat_id, "اذكر رمز السهم أو اسمه، مثال: حلل لي NVDA")
        return True

    send_message(
        chat_id,
        "أستطيع حاليًا الدردشة معك حول المحفظة، السيولة، المخاطر، فرص الشراء وتحليل الأسهم.\n"
        "مثال: كيف وضع محفظتي؟ أو حلل NVDA أو كم السيولة عندي؟"
    )
    return True


def handle_update(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return {"handled": False}

    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id:
        return {"handled": False}

    command = text.split()[0].split("@")[0].lower() if text else ""

    if command == "/chatid":
        send_message(chat_id, f"Your Chat ID is: {chat_id}")
        return {"handled": True}

    if command == "/start":
        if not ALLOWED_CHAT_ID or _authorized(chat_id):
            send_message(chat_id, HELP)
        else:
            send_message(chat_id, "هذا البوت خاص بحساب استثماري واحد.")
        return {"handled": True}

    if not _authorized(chat_id):
        send_message(chat_id, "هذا البوت خاص بحساب استثماري واحد وغير مصرح لهذا الحساب.")
        return {"handled": True, "authorized": False}

    if command == "/help":
        send_message(chat_id, HELP)
        return {"handled": True}

    if command == "/watchlist":
        send_message(chat_id, "📌 الأسهم الحالية:\n" + "\n".join(f"- {x}" for x in WATCHLIST))
        return {"handled": True}

    if command == "/stock":
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "الاستخدام: /stock NVDA")
            return {"handled": True}
        send_message(chat_id, _stock_report(parts[1].upper()))
        return {"handled": True}

    if command == "/status":
        send_message(chat_id, _portfolio_report())
        return {"handled": True}

    if command == "/opportunities":
        send_message(chat_id, _opportunities_report())
        return {"handled": True}

    if text.startswith("/"):
        send_message(chat_id, "أمر غير معروف. استخدم /help")
        return {"handled": True}

    return {"handled": _handle_conversation(chat_id, text)}


def run_monitor():
    if not ALLOWED_CHAT_ID:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_ID is not configured.")

    sent = []
    checked = []
    for ticker in WATCHLIST:
        checked.append(ticker)
        try:
            s = get_snapshot(ticker)
            a = assess(s)
            if a.alert:
                send_message(ALLOWED_CHAT_ID, a.text)
                sent.append(ticker)
        except Exception:
            continue
    return {"checked": checked, "alerts_sent": sent}
