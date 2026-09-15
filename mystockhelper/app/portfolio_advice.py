from __future__ import annotations


def break_even_gap_pct(current_price, avg_cost):
    if current_price in (None, 0) or avg_cost in (None, 0):
        return None
    return (avg_cost / current_price - 1.0) * 100.0


def portfolio_aware_view(ticker, snapshot, assessment, metrics):
    if not metrics or snapshot is None or assessment is None:
        return {
            "level": "⚪",
            "label": "بيانات غير كافية",
            "recommendation": "انتظر اكتمال البيانات قبل تغيير حجم المركز.",
            "priority": 20,
        }

    pnl_pct = metrics.get("pnl_pct")
    weight = metrics.get("weight_pct")
    risk = assessment.risk
    trend = assessment.trend
    daily = snapshot.daily_change_pct or 0.0

    if weight is not None and weight >= 40:
        return {
            "level": "🟠",
            "label": "مخاطر تركّز مرتفعة",
            "recommendation": "احتفاظ/مراقبة، لكن لا تعزز المركز حاليًا قبل انخفاض Concentration Risk أو وجود مبرر استثماري قوي ومؤكد.",
            "priority": 100 + weight,
        }

    if pnl_pct is not None and pnl_pct <= -35:
        impact = "تأثيره على إجمالي المحفظة محدود بسبب صغر الوزن." if (weight or 0) < 2 else "تأثير المركز على المحفظة يحتاج متابعة مباشرة."
        return {
            "level": "🔴",
            "label": "مراجعة استراتيجية للمركز",
            "recommendation": f"الخسارة النسبية كبيرة. تجنب Average Down تلقائيًا وراجع فرضية الاحتفاظ. {impact}",
            "priority": 90 + min(abs(pnl_pct), 50),
        }

    if pnl_pct is not None and pnl_pct <= -10 and risk >= 7:
        return {
            "level": "🟠",
            "label": "أولوية إدارة مخاطر",
            "recommendation": "لا تعزز أثناء ارتفاع Risk. راقب استقرار Trend وVolume قبل أي زيادة في التعرض.",
            "priority": 80 + abs(pnl_pct),
        }

    if trend in {"هابط", "هابط قوي"} or daily <= -2.0:
        return {
            "level": "🟡",
            "label": "احتفاظ حذر",
            "recommendation": "لا تعزز الآن. انتظر تحسن Trend وعودة Volume داعم قبل زيادة حجم المركز.",
            "priority": 65 + risk,
        }

    if pnl_pct is not None and pnl_pct >= 5:
        return {
            "level": "🟢",
            "label": "مركز رابح",
            "recommendation": "احتفاظ مع حماية المكاسب ومراقبة ضعف Momentum أو كسر مستويات الدعم قصيرة الأجل.",
            "priority": 45 + min(pnl_pct, 20),
        }

    if trend in {"صاعد", "صاعد قوي"}:
        return {
            "level": "🟢",
            "label": "وضع فني إيجابي",
            "recommendation": "احتفاظ ومراقبة استمرار Momentum؛ أي تعزيز يبقى مشروطًا بتأكيد Volume وعدم رفع تركّز المحفظة بشكل مفرط.",
            "priority": 40 + risk,
        }

    return {
        "level": "🟡",
        "label": "مراقبة",
        "recommendation": "احتفاظ ومراقبة. لا توجد حاليًا إشارة كافية لتغيير حجم المركز.",
        "priority": 30 + risk,
    }


def top_actions(position_views, cash_pct):
    actions = []

    concentrated = [x for x in position_views if (x.get("weight_pct") or 0) >= 35]
    if concentrated:
        x = max(concentrated, key=lambda item: item.get("weight_pct") or 0)
        actions.append(
            f"🟠 {x['ticker']}: يمثل {x['weight_pct']:.1f}% من إجمالي المحفظة؛ الأولوية عدم زيادة التركّز ومراجعة حجم المركز قبل أي تعزيز."
        )

    stressed = [x for x in position_views if (x.get("pnl_pct") or 0) <= -20]
    if stressed:
        x = min(stressed, key=lambda item: item.get("pnl_pct") or 0)
        actions.append(
            f"🔴 {x['ticker']}: الخسارة {x['pnl_pct']:.1f}%؛ يحتاج مراجعة فرضية الاحتفاظ بدل Average Down تلقائيًا."
        )

    risk_positions = [x for x in position_views if (x.get("risk") or 0) >= 7 and x not in stressed]
    if risk_positions:
        x = max(risk_positions, key=lambda item: item.get("risk") or 0)
        actions.append(
            f"🟠 {x['ticker']}: Risk {x['risk']}/10؛ راقب Trend وVolume ولا ترفع التعرض أثناء ارتفاع المخاطر."
        )

    if cash_pct is not None and cash_pct < 10:
        actions.append(
            f"💰 السيولة {cash_pct:.1f}% فقط من المحفظة؛ استخدم Buying Power بشكل انتقائي واحتفظ بهامش سيولة للطوارئ والفرص الأعلى جودة."
        )

    if not actions:
        actions.append("🟢 لا توجد أولوية مخاطر استثنائية حاليًا؛ استمر في المراقبة والانضباط في حجم المراكز.")

    return actions[:3]
