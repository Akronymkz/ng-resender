"""
Общая логика бота: маршрутизация и пересылка сообщений.

Используется и в режиме polling (локально, bot.py),
и в режиме webhook (на Vercel, api/index.py).
"""
from __future__ import annotations

import logging
import re

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from config import Config, Route

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("resender")

# Хэштеги: '#' + буквы/цифры/подчёркивание (включая кириллицу).
HASHTAG_RE = re.compile(r"#[^\s#@]+", re.UNICODE)


def extract_hashtags(*texts: str | None) -> set[str]:
    """Достаёт хэштеги из переданных строк, в нижнем регистре."""
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        for m in HASHTAG_RE.findall(text):
            found.add(m.lower())
    return found


def matching_routes(
    routes: list[Route], chat_id: int, thread_id: int | None, hashtags: set[str]
) -> list[Route]:
    """Возвращает все маршруты, подходящие под сообщение (без дублей назначения)."""
    result: list[Route] = []
    seen: set[tuple[int, int | None]] = set()
    for r in routes:
        if r.matches(chat_id, thread_id, hashtags):
            key = (r.dest_chat_id, r.dest_thread_id)
            if key not in seen:
                seen.add(key)
                result.append(r)
    return result


def build_dispatcher(config: Config) -> Dispatcher:
    """Создаёт Dispatcher с зарегистрированными обработчиками."""
    dp = Dispatcher()

    @dp.message(Command("id"))
    async def cmd_id(message: Message) -> None:
        """Показывает chat_id и thread_id — для заполнения config/routes.yaml."""
        thread = message.message_thread_id
        text = (
            "<b>Данные для config/routes.yaml</b>\n"
            f"chat_id: <code>{message.chat.id}</code>\n"
            f"thread_id (топик): <code>{thread if thread is not None else 'нет (General)'}</code>\n"
            f"Название чата: {message.chat.title or '—'}"
        )
        await message.reply(text, message_thread_id=thread)

    @dp.message()
    async def on_message(message: Message, bot: Bot) -> None:
        thread_id = message.message_thread_id
        hashtags = extract_hashtags(message.text, message.caption)

        routes = matching_routes(config.routes, message.chat.id, thread_id, hashtags)
        if not routes:
            return

        for route in routes:
            try:
                await bot.forward_message(
                    chat_id=route.dest_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    message_thread_id=route.dest_thread_id,
                )
                logger.info(
                    "Переслано %s -> chat %s / топик %s [%s]",
                    message.message_id, route.dest_chat_id, route.dest_thread_id, route.name,
                )
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "Ошибка пересылки %s [%s]: %s", message.message_id, route.name, e
                )

    return dp
