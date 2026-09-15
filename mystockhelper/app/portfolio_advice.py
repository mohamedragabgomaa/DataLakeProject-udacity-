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
    move15 = snapshot.move_15m_pct or 0.0
    technical_recommendation = str(getattr(assessment, "recommendation", "") or "")

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

    momentum_extended = (
        trend in {"صاعد", "صاعد قوي"}
        and risk >= 7
        and (daily >= 4.0 or move15 >= 3.0 or "Pullback" in technical_recommendation)
    )
    if momentum_extended:
        return {
            "level": "🟠",
            "label": "Momentum قوي / مخاطرة مرتفعة",
            "recommendation": "الزخم قوي لكن المخاطرة مرتفعة والسعر ممتد. لا تطارد الحركة؛ انتظر Pullback أو تماسكًا مع Volume داعم قبل أي تعزيز.",
            "priority": 88 + risk,
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


def _impact_score(item):
    weight = max(0.0, float(item.get("weight_pct") or 0.0))
    pnl = abs(float(item.get("pnl_pct") or 0.0))
    risk = float(item.get("risk") or 0.0)
    view = item.get("view") or {}
    view_priority = float(view.get("priority") or 0.0)
    return (
        (weight * 1.5)
        + (min(pnl, 50.0) * min(weight, 20.0) / 20.0)
        + (risk * min(weight, 20.0) / 10.0)
        + (view_priority * min(weight, 25.0) / 100.0)
    )


def top_actions(position_views, cash_pct):
    ranked = sorted(position_views, key=_impact_score, reverse=True)
    actions = []

    for x in ranked:
        if len(actions) >= 3:
            break
        weight = float(x.get("weight_pct") or 0.0)
        pnl = float(x.get("pnl_pct") or 0.0)
        risk = int(x.get("risk") or 0)
        view = x.get("view") or {}
        label = str(view.get("label") or "")

        if weight >= 35:
            actions.append(
                f"🟠 {x['ticker']}: يمثل {weight:.1f}% من إجمالي المحفظة؛ الأولوية عدم زيادة التركّز ومراجعة حجم المركز قبل أي تعزيز."
            )
        elif label == "Momentum قوي / مخاطرة مرتفعة" and weight >= 5:
            actions.append(
                f"🟠 {x['ticker']}: Momentum قوي مع Risk {risk}/10 ووزن {weight:.1f}%؛ لا تطارد السعر وانتظر Pullback/تماسك قبل أي تعزيز."
            )
        elif label == "احتفاظ حذر" and weight >= 10:
            actions.append(
                f"🟡 {x['ticker']}: اتجاه ضعيف/هابط مع وزن {weight:.1f}%؛ راقبه قبل المراكز الرابحة ولا تعزز حتى يتحسن Trend وVolume."
            )
        elif pnl <= -20 and weight >= 2:
            actions.append(
                f"🔴 {x['ticker']}: الخسارة {pnl:.1f}% مع وزن {weight:.1f}%؛ يحتاج مراجعة فرضية الاحتفاظ وإدارة الأثر على المحفظة."
            )
        elif risk >= 7 and weight >= 5:
            actions.append(
                f"🟠 {x['ticker']}: Risk {risk}/10 ووزن {weight:.1f}%؛ راقب Trend وVolume ولا ترفع التعرض أثناء ارتفاع المخاطر."
            )
        elif pnl >= 5 and weight >= 5:
            actions.append(
                f"🟢 {x['ticker']}: مركز رابح بوزن {weight:.1f}%؛ راقب حماية المكاسب واستمرار Momentum."
            )

    if cash_pct is not None and cash_pct < 10 and len(actions) < 3:
        actions.append(
            f"💰 السيولة {cash_pct:.1f}% فقط من المحفظة؛ احتفظ بهامش سيولة ولا تستخدم Buying Power بالكامل في فرصة واحدة."
        )

    if not actions:
        actions.append("🟢 لا توجد أولوية مخاطر استثنائية حاليًا؛ استمر في المراقبة والانضباط في حجم المراكز.")

    return actions[:3]
