"""
Webhook-эндпоинт для Vercel (serverless).

Telegram присылает апдейты POST-запросом на /api/index.
Каждый запрос обрабатывается отдельно (serverless без состояния).

GET-запрос на этот же адрес возвращает короткий статус — удобно
проверить, что функция задеплоена.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Добавляем корень репозитория в путь импорта, чтобы видеть config.py / core.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.types import Update  # noqa: E402

from config import load_config  # noqa: E402
from core import build_dispatcher, logger  # noqa: E402

# Конфиг читается один раз на «холодный старт» инстанса.
_config = load_config()

# Необязательный секрет: задаётся в Vercel env как WEBHOOK_SECRET и при setWebhook.
_secret = os.getenv("WEBHOOK_SECRET", "").strip()


async def _process(payload: dict) -> None:
    bot = Bot(
        token=_config.token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = build_dispatcher(_config)
    try:
        update = Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str = "ok") -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        self._send(200, "Resender TG Bot: webhook endpoint is live.")

    def do_POST(self) -> None:  # noqa: N802
        # Проверка секретного токена от Telegram (если настроен).
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
            # Возвращаем 200, чтобы Telegram не повторял проблемный апдейт бесконечно.
        self._send(200, "ok")
