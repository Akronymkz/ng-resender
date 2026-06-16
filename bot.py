"""
Локальный запуск бота в режиме long polling.

Используйте этот режим для отладки и чтобы узнать ID чатов/топиков
командой /id. На Vercel работает другой режим — webhook (api/index.py).

Запуск:  python bot.py
"""
from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from config import load_config
from core import build_dispatcher, logger


async def main() -> None:
    config = load_config()
    bot = Bot(
        token=config.token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = build_dispatcher(config)

    logger.info("Бот запущен (polling). Маршрутов: %d", len(config.routes))
    for r in config.routes:
        logger.info(
            "  %s: chat %s / топик %s  ->  chat %s / топик %s  (хэштеги: %s)",
            r.name, r.source_chat_id, r.source_thread_id,
            r.dest_chat_id, r.dest_thread_id,
            ", ".join(sorted(r.match_hashtags)) or "любые",
        )

    # Снимаем webhook (если был) и пропускаем накопившиеся апдейты.
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
