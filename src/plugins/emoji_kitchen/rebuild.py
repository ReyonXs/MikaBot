from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from nonebot import require

require('nonebot_plugin_orm')
from nonebot_plugin_orm import get_session

from .config import METADATA_FILENAME
from .emoji_codes import emoji_codes
from .metadata import import_metadata
from .utils import get_metadata_json


async def rebuild(entry: dict | None = None) -> None:
    with TemporaryDirectory() as directory:
        metadata_path = Path(directory) / METADATA_FILENAME
        sha = await get_metadata_json(metadata_path, entry)
        async with get_session() as session, session.begin():
            emojis = await import_metadata(session, metadata_path, sha)
        emoji_codes.values = emojis
