import asyncio

from nonebot import require
from sqlalchemy import inspect, select

require('nonebot_plugin_orm')
from nonebot_plugin_orm import get_session

from .metadata import CODES


class EmojiCodeCache:
    def __init__(self) -> None:
        self.values: frozenset[str] | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> frozenset[str]:
        if self.values is None:
            async with self._lock:
                if self.values is None:
                    async with get_session() as session:
                        conn = await session.connection()
                        exists = await conn.run_sync(
                            lambda c: inspect(c).has_table(CODES.name)
                        )
                        rows = (
                            await session.scalars(select(CODES.c.emoji))
                            if exists
                            else ()
                        )
                        emojis = frozenset(rows)
                    if self.values is None:
                        self.values = emojis
        return self.values


emoji_codes = EmojiCodeCache()
