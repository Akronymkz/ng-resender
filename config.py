"""Загрузка конфигурации бота: токен (из env) и правила маршрутизации.

Правила берутся из routes_data.py (обычный Python-модуль — он автоматически
попадает в бандл серверлесс-функции Vercel, т.к. импортируется).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

import routes_data

load_dotenv()


@dataclass
class Route:
    """Одно правило пересылки: откуда -> куда."""

    name: str
    source_chat_id: int
    source_thread_id: int | None
    dest_chat_id: int
    dest_thread_id: int | None
    match_hashtags: set[str] = field(default_factory=set)

    def matches(self, chat_id: int, thread_id: int | None, hashtags: set[str]) -> bool:
        """Проверяет, подходит ли сообщение под это правило."""
        if chat_id != self.source_chat_id:
            return False
        if thread_id != self.source_thread_id:
            return False
        if self.match_hashtags and not (self.match_hashtags & hashtags):
            return False
        return True


@dataclass
class Config:
    token: str
    routes: list[Route]


def _norm_tags(raw) -> set[str]:
    """Нормализует список хэштегов: нижний регистр, ведущий '#'."""
    tags: set[str] = set()
    for t in raw or []:
        t = str(t).strip().lower()
        if not t:
            continue
        if not t.startswith("#"):
            t = "#" + t
        tags.add(t)
    return tags


def _thread(value) -> int | None:
    return int(value) if value is not None else None


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Локально — впишите в .env; на Vercel — в Environment Variables."
        )

    default_source = getattr(routes_data, "SOURCE_CHAT_ID", None)
    default_dest = getattr(routes_data, "DEST_CHAT_ID", None)

    routes: list[Route] = []
    for i, item in enumerate(routes_data.ROUTES, start=1):
        source_chat_id = item.get("source_chat_id", default_source)
        dest_chat_id = item.get("dest_chat_id", default_dest)
        if source_chat_id is None or dest_chat_id is None:
            raise RuntimeError(
                f"Маршрут #{i} ({item.get('name', '?')}): не задан source_chat_id или dest_chat_id."
            )
        routes.append(
            Route(
                name=item.get("name", f"route-{i}"),
                source_chat_id=int(source_chat_id),
                source_thread_id=_thread(item.get("source_thread_id")),
                dest_chat_id=int(dest_chat_id),
                dest_thread_id=_thread(item.get("dest_thread_id")),
                match_hashtags=_norm_tags(item.get("match_hashtags")),
            )
        )

    if not routes:
        raise RuntimeError("В routes_data.py нет ни одного правила (ROUTES).")

    return Config(token=token, routes=routes)
