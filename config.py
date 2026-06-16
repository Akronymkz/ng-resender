"""Загрузка конфигурации бота: токен и правила маршрутизации."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

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


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Скопируйте .env.example в .env и впишите токен бота."
        )

    routes_file = os.getenv("ROUTES_FILE", "config/routes.yaml")
    path = Path(routes_file)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    if not path.exists():
        raise RuntimeError(f"Не найден файл маршрутов: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    default_source = data.get("source_chat_id")
    default_dest = data.get("dest_chat_id")

    routes: list[Route] = []
    for i, item in enumerate(data.get("routes", []), start=1):
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
                source_thread_id=(
                    int(item["source_thread_id"])
                    if item.get("source_thread_id") is not None
                    else None
                ),
                dest_chat_id=int(dest_chat_id),
                dest_thread_id=(
                    int(item["dest_thread_id"])
                    if item.get("dest_thread_id") is not None
                    else None
                ),
                match_hashtags=_norm_tags(item.get("match_hashtags")),
            )
        )

    if not routes:
        raise RuntimeError("В файле маршрутов нет ни одного правила (routes).")

    return Config(token=token, routes=routes)
