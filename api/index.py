"""
Единая serverless-функция для Vercel.

Маршруты (обрабатываются одной функцией, т.к. Vercel направляет /api/* сюда):
  • POST  /api/index            — приём апдейтов от Telegram (webhook).
  • GET   /api/setup            — разовая установка webhook со стороны Vercel.
  • GET   /api/index            — статус ("webhook endpoint is live").

GET /api/setup сам определяет публичный адрес и вызывает setWebhook
(запрос идёт из среды Vercel, где api.telegram.org доступен).
Использует BOT_TOKEN и (если задан) WEBHOOK_SECRET из переменных окружения.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

# Корень репозитория в путь импорта, чтобы видеть config.py / core.py / routes_data.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.types import Update  # noqa: E402

from config import load_config  # noqa: E402
from core import build_dispatcher, logger  # noqa: E402

_config = load_config()
_secret = os.getenv("WEBHOOK_SECRET", "").strip()


def _set_webhook(host: str) -> dict:
    token = _config.token
    webhook_url = f"https://{host}/api/index"
    params = {"url": webhook_url, "drop_pending_updates": "true"}
    if _secret:
        params["secret_token"] = _secret
    api = f"https://api.telegram.org/bot{token}/setWebhook"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(api, data=data, timeout=20) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "webhook_url": webhook_url}
    result["webhook_url"] = webhook_url
    return result


async def _process(payload: dict) -> None:
    bot = Bot(token=_config.token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = build_dispatcher(_config)
    try:
        update = Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        # /api/setup (или любой путь с "setup") -> установка webhook
        if "setup" in self.path.lower():
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
            result = _set_webhook(host)
            self._send(
                200 if result.get("ok") else 500,
                json.dumps(result, ensure_ascii=False, indent=2),
                "application/json; charset=utf-8",
            )
            return
        self._send(200, "Resender TG Bot: webhook endpoint is live.")

    def do_POST(self) -> None:  # noqa: N802
        if _secret:
            got = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if got != _secret:
                self._send(401, "unauthorized")
                return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8"))
            asyncio.run(_process(payload))
        except Exception as e:  # noqa: BLE001
            logger.error("Ошибка обработки апдейта: %s", e)
        self._send(200, "ok")
