from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .config import (
    MIN_ABS_15M_MOVE_PCT,
    MIN_15M_ZSCORE,
    MIN_ABS_DAILY_MOVE_PCT,
    HIGH_DAILY_MOVE_PCT,
    VOLUME_SPIKE_MULTIPLIER,
    MIN_OPPORTUNITY_SCORE,
    HIGH_OPPORTUNITY_SCORE,
)
from .sec import latest_material_filing

RIYADH = ZoneInfo("Asia/Riyadh")
NEW_YORK = ZoneInfo("America/New_York")


@dataclass
class Assessment:
    ticker: str
    alert: bool
    priority: str
    recommendation: str
    confidence: int
    risk: int
    trigger: str
    catalyst: str
    text: str
    trend: str = "محايد"
    volume_state: str = "غير متاح"
    rationale: str = ""
    action_plan: str = ""


@dataclass
class Opportunity:
    ticker: str
    score: int
    label: str
    rationale: str
    risk: int
    confidence: int


def _fmt(x, suffix="", digits=2):
    return "غير متاح" if x is None else f"{x:.{digits}f}{suffix}"


def trend_label(s):
    signals = [s.daily_change_pct, s.move_15m_pct, s.move_60m_pct]
    pos = sum(1 for x in signals if x is not None and x > 0.15)
    neg = sum(1 for x in signals if x is not None and x < -0.15)

    if pos >= 3:
        return "صاعد قوي"
    if pos >= 2 and neg == 0:
        return "صاعد"
    if neg >= 3:
        return "هابط قوي"
    if neg >= 2 and pos == 0:
        return "هابط"
    if pos >= 1 and neg >= 1:
        return "متذبذب / Mixed"
    return "محايد"


def volume_label(s):
    v = s.volume_spike
    if v is None:
        return "غير متاح"
    if v >= 4.0:
        return "مرتفع جدًا"
    if v >= 2.0:
        return "مرتفع"
    if v >= 1.2:
        return "فوق المعتاد"
    if v >= 0.7:
        return "طبيعي"
    return "ضعيف"


def _risk_score(s):
    if s.price is None:
        return 8

    risk = 5
    if s.daily_change_pct is not None and abs(s.daily_change_pct) >= 2.0:
        risk += 1
    if s.move_15m_pct is not None and abs(s.move_15m_pct) >= 1.0:
        risk += 1
    if s.move_60m_pct is not None and abs(s.move_60m_pct) >= 2.0:
        risk += 1
    if s.zscore_15m is not None and abs(s.zscore_15m) >= 3.0:
        risk += 1
    if s.recent_split:
        risk += 1

    calm = (
        s.daily_change_pct is not None and abs(s.daily_change_pct) < 1.0
        and s.move_15m_pct is not None and abs(s.move_15m_pct) < 0.5
        and (s.volume_spike is None or s.volume_spike < 1.5)
    )
    if calm:
        risk -= 1

    return max(1, min(risk, 10))


def _confidence_score(s, abnormal, volume_confirmed):
    if s.price is None:
        return 20

    fields = [
        s.daily_change_pct,
        s.move_15m_pct,
        s.move_60m_pct,
        s.zscore_15m,
        s.volume_spike,
        s.session_high,
        s.session_low,
    ]
    available = sum(1 for x in fields if x is not None)
    score = 34 + min(available * 4, 24)

    tr = trend_label(s)
    if tr in {"صاعد قوي", "هابط قوي", "صاعد", "هابط"}:
        score += 5
    if abnormal:
        score += 5
    if volume_confirmed:
        score += 5

    # سقف محافظ لأن البيانات Best-Effort ولا يوجد Catalyst validation كامل في /status.
    return max(20, min(score, 72))


def _recommendation(s, abnormal, volume_confirmed):
    if s.price is None:
        return "أدلة غير كافية"

    d = s.daily_change_pct or 0
    m15 = s.move_15m_pct or 0
    m60 = s.move_60m_pct or 0
    z = s.zscore_15m
    vol = s.volume_spike

    if s.recent_split:
        return "مراجعة فقط - Corporate Action"

    if d <= -HIGH_DAILY_MOVE_PCT:
        return "خفّض المخاطر / راجع المركز"

    if m15 <= -2.0 and z is not None and z <= -3.0 and vol is not None and vol >= 1.5:
        return "خفّض المخاطر / راجع المركز"

    if d <= -2.0 and (m15 < 0 or m60 < 0):
        return "احتفاظ حذر / لا تعزز الآن"

    if m15 <= -2.0:
        return "احتفاظ حذر / راقب Support"

    if d >= HIGH_DAILY_MOVE_PCT:
        return "انتظر Pullback ولا تطارد السعر"

    aligned_up = d > 0 and m15 > 0 and m60 > 0
    healthy_vol = vol is not None and 1.2 <= vol <= 4.0
    non_extreme_z = z is None or z < 3.5

    if aligned_up and healthy_vol and non_extreme_z:
        return "احتفاظ + تعزيز مشروط عند تأكيد Breakout"

    if d >= 0.5 and m60 > 0:
        return "احتفاظ إيجابي / راقب استمرار Momentum"

    return "احتفاظ / مراقبة"


def _rationale(s, recommendation):
    reasons = []
    tr = trend_label(s)
    reasons.append(f"Trend قصير الأجل: {tr}")

    if s.daily_change_pct is not None:
        if s.daily_change_pct <= -2:
            reasons.append("ضغط يومي واضح على السعر")
        elif s.daily_change_pct >= 2:
            reasons.append("Momentum يومي إيجابي ملحوظ")

    if s.move_15m_pct is not None and abs(s.move_15m_pct) >= 1:
        direction = "صعود" if s.move_15m_pct > 0 else "هبوط"
        reasons.append(f"حركة {direction} قوية خلال 15m")

    if s.volume_spike is not None:
        if s.volume_spike >= 2:
            reasons.append("Volume أعلى من المعتاد ويدعم أهمية الحركة")
        elif s.volume_spike < 0.7:
            reasons.append("Volume ضعيف؛ تأكيد الحركة محدود")

    if "تعزيز" in recommendation:
        reasons.append("التعزيز يبقى مشروطًا بتأكيد Breakout وليس شراء Market مباشر")
    elif "خفّض" in recommendation:
        reasons.append("الأولوية الحالية لحماية رأس المال وليس متوسط التكلفة")

    return "؛ ".join(reasons[:4])


def _action_plan(s, recommendation):
    low = _fmt(s.session_low)
    high = _fmt(s.session_high)

    if "خفّض" in recommendation:
        return (
            f"الأولوية حماية رأس المال. راقب Session Low قرب {low}. "
            "كسر القاع مع Volume متزايد يرفع خطر استمرار الهبوط."
        )
    if "حذر" in recommendation:
        return (
            f"لا تضف للمركز الآن. راقب ثبات السعر فوق Session Low {low} "
            "وتحسن 15m/60m وVolume قبل أي تعزيز."
        )
    if "Pullback" in recommendation:
        return (
            f"لا تطارد السعر. انتظر Pullback منظم ثم عودة الطلب؛ "
            f"Session High الحالي {high} مرجع Resistance قصير الأجل."
        )
    if "تعزيز" in recommendation:
        return (
            f"احتفاظ بالمركز؛ التعزيز فقط إذا تأكد Breakout فوق منطقة Session High {high} "
            "مع Volume داعم وبدون امتداد سعري مفرط."
        )
    if "إيجابي" in recommendation:
        return (
            f"احتفاظ مع مراقبة Momentum. راقب Session High {high}؛ "
            "لا تغيّر حجم المركز لمجرد حركة قصيرة دون Volume مؤكد."
        )
    return (
        f"احتفاظ ومراقبة. Session Low {low} وSession High {high} هما مرجعان قصيرا الأجل؛ "
        "لا يوجد سبب كافٍ حاليًا لزيادة المخاطرة."
    )


def assess(s, include_sec=True):
    abnormal = (
        s.move_15m_pct is not None
        and abs(s.move_15m_pct) >= MIN_ABS_15M_MOVE_PCT
        and s.zscore_15m is not None
        and abs(s.zscore_15m) >= MIN_15M_ZSCORE
    )
    volume_confirmed = (
        s.volume_spike is not None
        and s.volume_spike >= VOLUME_SPIKE_MULTIPLIER
    )
    material_daily = (
        s.daily_change_pct is not None
        and abs(s.daily_change_pct) >= MIN_ABS_DAILY_MOVE_PCT
    )

    alert = abnormal and (volume_confirmed or material_daily) and not s.recent_split

    if alert and (s.move_15m_pct or 0) > 0:
        priority = "مرتفع"
        trigger = "حركة صعود غير اعتيادية متعددة العوامل خلال 15 دقيقة"
    elif alert:
        priority = "حرج" if (s.daily_change_pct or 0) <= -HIGH_DAILY_MOVE_PCT else "مرتفع"
        trigger = "حركة هبوط غير اعتيادية متعددة العوامل خلال 15 دقيقة"
    else:
        priority = "معلوماتي"
        trigger = "لا توجد إشارة Alert متعددة العوامل حالياً"

    filing = None
    if include_sec and alert:
        try:
            filing = latest_material_filing(s.ticker)
        except Exception:
            filing = None

    if filing:
        catalyst = f"تم رصد إفصاح SEC: {filing.get('form')} بتاريخ {filing.get('date')}"
    elif s.recent_split or s.recent_dividend:
        catalyst = "تم رصد Corporate Action؛ يجب تفسير حركة السعر بحذر."
    else:
        catalyst = "لا يوجد Catalyst مؤكد حتى الآن"

    recommendation = _recommendation(s, abnormal, volume_confirmed)
    confidence = _confidence_score(s, abnormal, volume_confirmed)
    risk = _risk_score(s)
    trend = trend_label(s)
    vol_state = volume_label(s)
    rationale = _rationale(s, recommendation)
    action_plan = _action_plan(s, recommendation)

    rt = s.timestamp.astimezone(RIYADH)
    nt = s.timestamp.astimezone(NEW_YORK)

    text = f"""🚨 تنبيه المحفظة - {s.ticker}

الأولوية: {priority}
وقت الرياض: {rt:%Y-%m-%d %H:%M:%S}
وقت نيويورك: {nt:%Y-%m-%d %H:%M:%S}
السعر الحالي: {_fmt(s.price)}
التغير اليومي: {_fmt(s.daily_change_pct, '%')}
حركة 15m: {_fmt(s.move_15m_pct, '%')}
حركة 60m: {_fmt(s.move_60m_pct, '%')}
Trend: {trend}
15m Z-Score: {_fmt(s.zscore_15m)}
Volume Spike (5m): {_fmt(s.volume_spike, 'x')} - {vol_state}

سبب التنبيه:
{trigger}

Catalyst:
{catalyst}

التوصية:
{recommendation}

لماذا؟
{rationale}

خطة التصرف:
{action_plan}

Confidence Score: {confidence}/100
Risk Score: {risk}/10

Market Data Status:
{s.freshness}

المصدر:
{s.source}

تنبيه مهم:
مصدر البيانات المجاني Best-Effort وليس Exchange-Grade Real-Time، لذلك لا تعتمد على هذا التنبيه وحده لتنفيذ صفقة فورية."""

    return Assessment(
        ticker=s.ticker,
        alert=alert,
        priority=priority,
        recommendation=recommendation,
        confidence=confidence,
        risk=risk,
        trigger=trigger,
        catalyst=catalyst,
        text=text,
        trend=trend,
        volume_state=vol_state,
        rationale=rationale,
        action_plan=action_plan,
    )


def status_line(s, a):
    return (
        f"{s.ticker} | السعر {_fmt(s.price)} | اليوم {_fmt(s.daily_change_pct, '%')} | "
        f"15m {_fmt(s.move_15m_pct, '%')} | Trend {a.trend} | "
        f"Vol {_fmt(s.volume_spike, 'x')} | {a.recommendation} | "
        f"Risk {a.risk}/10 | Confidence {a.confidence}/100"
    )


def score_opportunity(s):
    if s.price is None:
        return Opportunity(s.ticker, 0, "غير مؤهل", "البيانات غير كافية", 8, 20)

    score = 0
    reasons = []
    risk = _risk_score(s)

    if s.daily_change_pct is not None:
        if 0.5 <= s.daily_change_pct <= 4.0:
            score += 20
            reasons.append("زخم يومي إيجابي بدون امتداد مفرط")
        elif s.daily_change_pct > HIGH_DAILY_MOVE_PCT:
            score -= 10
            risk += 1
            reasons.append("السعر ممتد؛ خطر Chase مرتفع")
        elif s.daily_change_pct <= -2.0:
            score -= 10
            reasons.append("Momentum يومي سلبي")

    if s.move_15m_pct is not None and 0.3 <= s.move_15m_pct <= 2.0:
        score += 20
        reasons.append("Momentum قصير الأجل إيجابي")

    if s.move_60m_pct is not None and s.move_60m_pct > 0.5:
        score += 10
        reasons.append("اتجاه 60m داعم")

    if s.zscore_15m is not None and 1.0 <= s.zscore_15m <= 3.5:
        score += 15
        reasons.append("الحركة أعلى من المعتاد لكن ليست متطرفة")

    if s.volume_spike is not None:
        if 1.5 <= s.volume_spike <= 4.0:
            score += 25
            reasons.append("Volume expansion داعم")
        elif s.volume_spike > 5.0:
            score += 5
            risk += 1
            reasons.append("Volume شديد الارتفاع؛ يحتاج تحقق Catalyst")
        elif s.volume_spike < 0.7:
            score -= 5
            reasons.append("Volume ضعيف")

    if s.session_high is not None and s.price is not None and s.session_high > 0:
        distance_from_high = (s.session_high - s.price) / s.session_high * 100
        if 0 <= distance_from_high <= 1.5:
            score += 10
            reasons.append("السعر قريب من Session High")

    if s.recent_split:
        score -= 25
        risk += 2
        reasons.append("Recent split يقلل موثوقية المقارنة السعرية")

    score = max(0, min(score, 100))
    confidence = min(75, 35 + score // 2)

    if score >= HIGH_OPPORTUNITY_SCORE:
        label = "فرصة شراء مشروطة - High Conviction Watch"
    elif score >= MIN_OPPORTUNITY_SCORE:
        label = "قائمة مراقبة قوية"
    else:
        label = "لا توجد فرصة شراء واضحة"

    rationale = "؛ ".join(reasons) if reasons else "لا توجد عوامل تأكيد كافية"
    return Opportunity(s.ticker, score, label, rationale, min(risk, 10), confidence)
