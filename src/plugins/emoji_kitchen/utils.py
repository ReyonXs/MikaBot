from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from furl import furl
from nonebot import logger

from src.plugins.lib import verify_blob, web_utils

from .config import METADATA_DIRECTORY_URL, METADATA_FILENAME

if TYPE_CHECKING:
    from pathlib import Path


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
