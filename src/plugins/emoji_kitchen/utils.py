from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from furl import furl
from nonebot import logger, require
from sqlalchemy import Text, column, select, table

from src.plugins.lib import verify_blob, web_utils

require('nonebot_plugin_orm')
from nonebot_plugin_orm import get_session

from .config import (
    COMBINATIONS_VIEW_NAME,
    METADATA_DIRECTORY_URL,
    METADATA_FILENAME,
)

if TYPE_CHECKING:
    from pathlib import Path

    from nonebot.adapters.milky import Message


PAIR_PATTERN = re.compile(r'([^\s+]+)[ ]*\+[ ]*([^\s+]+)')
COMBINATIONS = table(
    COMBINATIONS_VIEW_NAME,
    column('emoji1', Text),
    column('emoji2', Text),
    column('url', Text),
)


def parse_emoji_pair(message: Message) -> tuple[str, str] | None:
    if any(not segment.is_text() for segment in message):
        return None
    match = PAIR_PATTERN.fullmatch(message.extract_plain_text())
    return (match[1], match[2]) if match else None


async def get_combination_url(left: str, right: str) -> furl | None:
    async with get_session() as session:
        url = await session.scalar(
            select(COMBINATIONS.c.url).where(
                COMBINATIONS.c.emoji1 == left, COMBINATIONS.c.emoji2 == right
            )
        )
    return furl(url) if url is not None else None


async def get_combination_image(url: furl) -> bytes | None:
    response = await web_utils.get_client().get(url.url, follow_redirects=True)
    response.raise_for_status()
    image = response.content
    return image if image.startswith(b'\x89PNG\r\n\x1a\n') else None


async def get_metadata_entry() -> dict:
    client = web_utils.get_client()
    response = await client.get(METADATA_DIRECTORY_URL.url)
    response.raise_for_status()

    for entry in response.json():
        if entry['name'] == METADATA_FILENAME and entry['type'] == 'file':
            entry['git_url'] = furl(entry['git_url'])
            return entry

    msg = f'GitHub 目录中缺少 {METADATA_FILENAME}'
    raise FileNotFoundError(msg)


async def get_metadata_sha() -> str:
    entry = await get_metadata_entry()
    return entry['sha']


async def get_metadata_json(target: Path, entry: dict | None = None) -> str:
    if entry is None:
        entry = await get_metadata_entry()
    sha = entry['sha']
    logger.info(f'正在下载 {METADATA_FILENAME}')
    await web_utils.download_file(
        entry['git_url'], target, headers={'Accept': 'application/vnd.github.raw+json'}
    )
    await asyncio.to_thread(verify_blob, target, entry['size'], sha)
    return sha
