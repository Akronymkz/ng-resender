"""
Управление webhook'ом Telegram.

  python set_webhook.py set https://<project>.vercel.app/api/index
  python set_webhook.py info
  python set_webhook.py delete

Токен берётся из BOT_TOKEN (.env). Если задан WEBHOOK_SECRET — он
передаётся как secret_token (Telegram будет слать его в заголовке).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

API = "https://api.telegram.org/bot{token}/{method}"


def call(method: str, **params) -> dict:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Не задан BOT_TOKEN (.env).")
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v}).encode()
    with urllib.request.urlopen(url, data=data) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]

    if cmd == "set":
        if len(sys.argv) < 3:
            sys.exit("Укажите URL: python set_webhook.py set https://.../api/index")
        url = sys.argv[2]
        res = call(
            "setWebhook",
            url=url,
            secret_token=os.getenv("WEBHOOK_SECRET", "").strip(),
            drop_pending_updates="true",
        )
    elif cmd == "delete":
        res = call("deleteWebhook", drop_pending_updates="true")
    elif cmd == "info":
        res = call("getWebhookInfo")
    else:
        sys.exit(f"Неизвестная команда: {cmd}")

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
