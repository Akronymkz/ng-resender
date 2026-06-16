"""
Разовая установка webhook со стороны Vercel.

После деплоя откройте в браузере:
    https://<project>.vercel.app/api/setup

Эндпоинт сам определит свой публичный адрес и зарегистрирует webhook
в Telegram (запрос идёт из среды Vercel, где api.telegram.org доступен).
Использует BOT_TOKEN и (если задан) WEBHOOK_SECRET из переменных окружения.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler


def _set_webhook(host: str) -> dict:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        return {"ok": False, "error": "BOT_TOKEN не задан в переменных окружения Vercel"}

    webhook_url = f"https://{host}/api/index"
    params = {"url": webhook_url, "drop_pending_updates": "true"}
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if secret:
        params["secret_token"] = secret

    api = f"https://api.telegram.org/bot{token}/setWebhook"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(api, data=data, timeout=20) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "webhook_url": webhook_url}
    result["webhook_url"] = webhook_url
    return result


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        result = _set_webhook(host)
        body = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200 if result.get("ok") else 500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
