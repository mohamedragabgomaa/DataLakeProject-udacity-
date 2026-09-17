from flask import Flask, request, jsonify

try:
    from app.config import MONITOR_SECRET
    from app.bot import handle_update, run_monitor
    from app.opening_report import send_opening_report
except ModuleNotFoundError:
    from mystockhelper.app.config import MONITOR_SECRET
    from mystockhelper.app.bot import handle_update, run_monitor
    from mystockhelper.app.opening_report import send_opening_report

app = Flask(__name__)


def _authorized_monitor_request():
    supplied = request.args.get("secret") or request.headers.get("X-Monitor-Secret", "")
    return bool(MONITOR_SECRET) and supplied == MONITOR_SECRET


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
    if not _authorized_monitor_request():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    try:
        return jsonify({"ok": True, **run_monitor()})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__}), 500


@app.route("/api/opening-report", methods=["GET", "POST"])
def opening_report():
    if not _authorized_monitor_request():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    try:
        force = str(request.args.get("force", "")).lower() in {"1", "true", "yes"}
        scheduled = str(request.args.get("scheduled", "")).lower() in {"1", "true", "yes"}
        result = send_opening_report(force=force, scheduled=scheduled)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__}), 500
