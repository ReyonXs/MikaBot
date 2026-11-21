import asyncio
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from weakref import WeakValueDictionary

import httpx
from nonebot.adapters.milky import MessageEvent

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
DB = Path(__file__).resolve().parents[2] / "data" / "qqbot.sqlite3"
_locks = WeakValueDictionary()


def lock(key):
    return _locks.setdefault(key, asyncio.Lock())


def room(event: MessageEvent):
    return f"{event.self_id}/{event.data.message_scene}/{event.data.peer_id}"


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return db


def read(key):
    with closing(connection()) as db:
        row = db.execute("SELECT value FROM sessions WHERE id=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def write(key, value):
    with closing(connection()) as db, db:
        if value is None:
            db.execute("DELETE FROM sessions WHERE id=?", (key,))
        else:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))


class ModelError(Exception):
    pass


async def complete(messages, *, judge=False):
    base = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    token = os.getenv("LLM_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {"model": os.getenv("LLM_MODEL", "deepseek-v4-flash"), "messages": messages}
    if judge:
        body["temperature"] = 0
    try:
        async with httpx.AsyncClient(timeout=85) as client:
            response = await asyncio.wait_for(client.post(f"{base}/chat/completions", json=body, headers=headers), 90)
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    except httpx.HTTPStatusError as exc:
        raise ModelError(f"模型服务返回 HTTP {exc.response.status_code}。请检查模型、密钥或账户额度。") from None
    except (asyncio.TimeoutError, httpx.RequestError):
        raise ModelError("模型服务连接失败或超时，请稍后重试。") from None
    except (KeyError, ValueError, IndexError, TypeError):
        pass
    raise ModelError("模型服务返回了无法读取的回答，请重试。")
