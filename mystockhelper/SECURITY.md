# Security

Never commit Telegram tokens or API keys. Store TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID, and MONITOR_SECRET only as deployment/repository secrets. Restrict bot commands to the configured Chat ID and protect /api/monitor with a long random secret.
