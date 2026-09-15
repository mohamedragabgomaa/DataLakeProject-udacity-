from flask import Flask, request, jsonify

from app.config import MONITOR_SECRET
from app.bot import handle_update, run_monitor

app = Flask(__name__)


@app.get("/")
def root():
    return jsonify({
        "service": "MyStockHelper",
        "status": "ok",
        "cost_target": "$0 paid services",
        "warning": "Default market data is best-effort, not exchange-grade real-time."
    })


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/telegram")
def telegram_webhook():
    try:
        return jsonify({"ok": True, "result": handle_update(request.get_json(silent=True) or {})})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__}), 500


@app.route("/api/monitor", methods=["GET", "POST"])
def monitor():
    supplied = request.args.get("secret") or request.headers.get("X-Monitor-Secret", "")
    if not MONITOR_SECRET or supplied != MONITOR_SECRET:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    try:
        return jsonify({"ok": True, **run_monitor()})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__}), 500
