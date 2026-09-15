import requests
from .config import BOT_TOKEN

BASE = "https://api.telegram.org/bot{token}/{method}"

def _require_token():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

def call(method: str, payload: dict | None = None, timeout: int = 15):
    _require_token()
    url = BASE.format(token=BOT_TOKEN, method=method)
    r = requests.post(url, json=payload or {}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data.get("result")

def split_message(text: str, limit: int = 3900):
    text = str(text)
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks

def send_message(chat_id: str | int, text: str):
    results = []
    for chunk in split_message(text):
        results.append(call("sendMessage", {
            "chat_id": str(chat_id),
            "text": chunk,
            "disable_web_page_preview": True
        }))
    return results
