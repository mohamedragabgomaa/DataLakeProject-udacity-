from __future__ import annotations
from .config import WATCHLIST,ALLOWED_CHAT_ID
from .market import get_snapshot
from .analysis import assess,status_line
from .telegram_api import send_message

HELP="""MyStockHelper\n\nCommands:\n/status - Portfolio status\n/stock NVDA - Analyze one ticker\n/watchlist - Show Tier 1 watchlist\n/chatid - Show your Telegram Chat ID\n/help - Commands\n\nPriority portfolio:\nPCLA, NVDA, ORCL, ESTC, XOS\n\nMarket-data note:\nThe free default source is best-effort and is not treated as exchange-grade real-time data."""

def _authorized(chat_id): return bool(ALLOWED_CHAT_ID) and str(chat_id)==str(ALLOWED_CHAT_ID)

def handle_update(update:dict):
    msg=update.get("message") or update.get("edited_message")
    if not msg: return {"handled":False}
    chat_id=(msg.get("chat") or {}).get("id"); text=(msg.get("text") or "").strip()
    if not chat_id: return {"handled":False}
    command=text.split()[0].split("@")[0].lower() if text else ""
    if command=="/chatid": send_message(chat_id,f"Your Chat ID is: {chat_id}"); return {"handled":True}
    if command=="/start": send_message(chat_id, HELP if not ALLOWED_CHAT_ID or _authorized(chat_id) else "This bot is private. Use /chatid and configure the allowed Chat ID."); return {"handled":True}
    if not _authorized(chat_id): send_message(chat_id,"Unauthorized chat. This bot is configured for a private investor account."); return {"handled":True,"authorized":False}
    if command=="/help": send_message(chat_id,HELP); return {"handled":True}
    if command=="/watchlist": send_message(chat_id,"Portfolio Priority Tier 1:\n"+"\n".join(f"- {x}" for x in WATCHLIST)); return {"handled":True}
    if command=="/stock":
        parts=text.split()
        if len(parts)<2: send_message(chat_id,"Usage: /stock NVDA"); return {"handled":True}
        ticker=parts[1].upper()
        try: s=get_snapshot(ticker); a=assess(s); send_message(chat_id,a.text)
        except Exception as e: send_message(chat_id,f"{ticker}: DATA UNAVAILABLE / UNABLE TO VERIFY.\nReason: {type(e).__name__}")
        return {"handled":True}
    if command=="/status":
        rows=["PORTFOLIO STATUS",""]
        for ticker in WATCHLIST:
            try: s=get_snapshot(ticker); rows.append(status_line(s,assess(s,include_sec=False)))
            except Exception: rows.append(f"{ticker}: DATA UNAVAILABLE / UNABLE TO VERIFY")
        rows += ["","Data is best-effort and not exchange-grade real-time."]
        send_message(chat_id,"\n".join(rows)); return {"handled":True}
    if text.startswith("/"): send_message(chat_id,"Unknown command. Use /help."); return {"handled":True}
    return {"handled":False}

def run_monitor():
    if not ALLOWED_CHAT_ID: raise RuntimeError("TELEGRAM_ALLOWED_CHAT_ID is not configured.")
    sent=[]; checked=[]
    for ticker in WATCHLIST:
        checked.append(ticker)
        try:
            s=get_snapshot(ticker); a=assess(s)
            if a.alert: send_message(ALLOWED_CHAT_ID,a.text); sent.append(ticker)
        except Exception: continue
    return {"checked":checked,"alerts_sent":sent}
