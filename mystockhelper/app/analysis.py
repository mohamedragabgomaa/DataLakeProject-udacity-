from __future__ import annotations
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from .config import MIN_ABS_15M_MOVE_PCT,MIN_15M_ZSCORE,MIN_ABS_DAILY_MOVE_PCT,HIGH_DAILY_MOVE_PCT,VOLUME_SPIKE_MULTIPLIER
from .sec import latest_material_filing

RIYADH=ZoneInfo("Asia/Riyadh"); NEW_YORK=ZoneInfo("America/New_York")

@dataclass
class Assessment:
    ticker:str; alert:bool; priority:str; recommendation:str; confidence:int; risk:int; trigger:str; catalyst:str; text:str

def _fmt(x,suffix="",digits=2):
    return "DATA UNAVAILABLE" if x is None else f"{x:.{digits}f}{suffix}"

def assess(s, include_sec=True):
    abnormal=s.move_15m_pct is not None and abs(s.move_15m_pct)>=MIN_ABS_15M_MOVE_PCT and s.zscore_15m is not None and abs(s.zscore_15m)>=MIN_15M_ZSCORE
    volume_confirmed=s.volume_spike is not None and s.volume_spike>=VOLUME_SPIKE_MULTIPLIER
    material_daily=s.daily_change_pct is not None and abs(s.daily_change_pct)>=MIN_ABS_DAILY_MOVE_PCT
    alert=abnormal and (volume_confirmed or material_daily) and not s.recent_split
    if alert and (s.move_15m_pct or 0)>0: priority="HIGH"; trigger="Abnormal upward 15-minute move"
    elif alert: priority="CRITICAL" if (s.daily_change_pct or 0)<=-HIGH_DAILY_MOVE_PCT else "HIGH"; trigger="Abnormal downward 15-minute move"
    else: priority="INFORMATIONAL"; trigger="No material multi-factor alert"
    filing=None
    if include_sec and alert:
        try: filing=latest_material_filing(s.ticker)
        except Exception: filing=None
    if filing: catalyst=f"SEC filing detected: {filing.get('form')} filed {filing.get('date')}"
    elif s.recent_split or s.recent_dividend: catalyst="Corporate-action signal detected; interpret price movement cautiously."
    else: catalyst="NO CONFIRMED CATALYST IDENTIFIED"
    confidence=45+(10 if abnormal else 0)+(8 if volume_confirmed else 0); risk=6+(1 if s.recent_split else 0)+(1 if s.daily_change_pct is not None and abs(s.daily_change_pct)>=HIGH_DAILY_MOVE_PCT else 0)
    if s.price is None: recommendation="INSUFFICIENT EVIDENCE"; confidence=20; risk=8
    elif s.daily_change_pct is not None and s.daily_change_pct<=-HIGH_DAILY_MOVE_PCT: recommendation="REDUCE RISK / REVIEW"
    elif s.daily_change_pct is not None and s.daily_change_pct>=HIGH_DAILY_MOVE_PCT: recommendation="WATCH / WAIT FOR PULLBACK"
    else: recommendation="WATCH"
    rt=s.timestamp.astimezone(RIYADH); nt=s.timestamp.astimezone(NEW_YORK)
    text=f"""🚨 PORTFOLIO ALERT - {s.ticker}\n\nAlert Priority: {priority}\nTime - Riyadh: {rt:%Y-%m-%d %H:%M:%S}\nTime - New York: {nt:%Y-%m-%d %H:%M:%S}\nCurrent Price: {_fmt(s.price)}\nDaily Change: {_fmt(s.daily_change_pct,'%')}\n15m Move: {_fmt(s.move_15m_pct,'%')}\n60m Move: {_fmt(s.move_60m_pct,'%')}\n15m Z-Score: {_fmt(s.zscore_15m)}\n5m Volume Spike: {_fmt(s.volume_spike,'x')}\n\nTrigger:\n{trigger}\n\nCatalyst:\n{catalyst}\n\nAI Assessment:\nRecommendation: {recommendation}\nConfidence Score: {min(confidence,70)}/100\nRisk Score: {min(risk,10)}/10\n\nMarket Data Status:\n{s.freshness}\n\nSource:\n{s.source}\n\nIMPORTANT:\nThis free data source is not treated as exchange-grade real-time data.\nDo not use this alert alone for immediate trade execution."""
    return Assessment(s.ticker,alert,priority,recommendation,min(confidence,70),min(risk,10),trigger,catalyst,text)

def status_line(s,a):
    return f"{s.ticker}: Price {_fmt(s.price)} | Day {_fmt(s.daily_change_pct,'%')} | 15m {_fmt(s.move_15m_pct,'%')} | Z {_fmt(s.zscore_15m)} | Vol {_fmt(s.volume_spike,'x')} | {a.recommendation}"
