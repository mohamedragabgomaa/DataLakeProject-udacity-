import os,sys,requests
token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
if not token: raise SystemExit("Set TELEGRAM_BOT_TOKEN in your shell first.")
if len(sys.argv)!=2: raise SystemExit("Usage: python scripts/set_webhook.py https://YOUR-PROJECT.vercel.app")
base=sys.argv[1].rstrip("/"); webhook=base+"/api/telegram"
r=requests.post(f"https://api.telegram.org/bot{token}/setWebhook",json={"url":webhook,"allowed_updates":["message","edited_message"]},timeout=15)
r.raise_for_status(); print(r.json())
