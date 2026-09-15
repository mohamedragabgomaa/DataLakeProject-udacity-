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


def _arabic_recommendation(s, abnormal, volume_confirmed):
    if s.price is None:
        return "أدلة غير كافية", 20, 8

    confidence = 45 + (10 if abnormal else 0) + (8 if volume_confirmed else 0)
    risk = 6

    if s.recent_split:
        confidence -= 10
        risk += 1
    if s.daily_change_pct is not None and abs(s.daily_change_pct) >= HIGH_DAILY_MOVE_PCT:
        risk += 1

    if s.daily_change_pct is not None and s.daily_change_pct <= -HIGH_DAILY_MOVE_PCT:
        rec = "خفّض المخاطر / راجع المركز"
    elif s.daily_change_pct is not None and s.daily_change_pct >= HIGH_DAILY_MOVE_PCT:
        rec = "انتظر Pullback ولا تطارد السعر"
    elif abnormal and volume_confirmed and (s.move_15m_pct or 0) > 0:
        rec = "احتفاظ مع مراقبة تعزيز مشروط"
    elif abnormal and (s.move_15m_pct or 0) < 0:
        rec = "احتفاظ حذر / راقب Support"
    else:
        rec = "احتفاظ / مراقبة"

    return rec, max(0, min(confidence, 70)), max(1, min(risk, 10))


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
        trigger = "حركة صعود غير اعتيادية خلال 15 دقيقة"
    elif alert:
        priority = "حرج" if (s.daily_change_pct or 0) <= -HIGH_DAILY_MOVE_PCT else "مرتفع"
        trigger = "حركة هبوط غير اعتيادية خلال 15 دقيقة"
    else:
        priority = "معلوماتي"
        trigger = "لا توجد إشارة جوهرية متعددة العوامل حالياً"

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

    recommendation, confidence, risk = _arabic_recommendation(s, abnormal, volume_confirmed)

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
15m Z-Score: {_fmt(s.zscore_15m)}
Volume Spike (5m): {_fmt(s.volume_spike, 'x')}

سبب التنبيه:
{trigger}

Catalyst:
{catalyst}

التوصية:
{recommendation}

Confidence Score: {confidence}/100
Risk Score: {risk}/10

Market Data Status:
{s.freshness}

المصدر:
{s.source}

تنبيه مهم:
مصدر البيانات المجاني Best-Effort وليس Exchange-Grade Real-Time، لذلك لا تعتمد على هذا التنبيه وحده لتنفيذ صفقة فورية."""

    return Assessment(
        s.ticker,
        alert,
        priority,
        recommendation,
        confidence,
        risk,
        trigger,
        catalyst,
        text,
    )


def status_line(s, a):
    return (
        f"{s.ticker} | السعر {_fmt(s.price)} | اليوم {_fmt(s.daily_change_pct, '%')} | "
        f"15m {_fmt(s.move_15m_pct, '%')} | Vol {_fmt(s.volume_spike, 'x')} | "
        f"التوصية: {a.recommendation} | Risk {a.risk}/10 | Confidence {a.confidence}/100"
    )


def score_opportunity(s):
    if s.price is None:
        return Opportunity(s.ticker, 0, "غير مؤهل", "البيانات غير كافية", 8, 20)

    score = 0
    reasons = []
    risk = 6

    if s.daily_change_pct is not None:
        if 0.5 <= s.daily_change_pct <= 4.0:
            score += 20
            reasons.append("زخم يومي إيجابي بدون امتداد مفرط")
        elif s.daily_change_pct > HIGH_DAILY_MOVE_PCT:
            score -= 10
            risk += 1
            reasons.append("السعر ممتد؛ خطر Chase مرتفع")

    if s.move_15m_pct is not None and 0.3 <= s.move_15m_pct <= 2.0:
        score += 20
        reasons.append("Momentum قصير الأجل إيجابي")

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

    rationale = "، ".join(reasons) if reasons else "لا توجد عوامل تأكيد كافية"
    return Opportunity(s.ticker, score, label, rationale, min(risk, 10), confidence)
