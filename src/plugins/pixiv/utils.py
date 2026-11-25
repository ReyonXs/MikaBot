import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

from httpx import HTTPError
from nonebot import logger
from nonebot.adapters.milky import Message, MessageEvent
from PIL import Image

from src.plugins.lib import web_utils

from .config import DOWNLOAD_LIMIT, HEADERS
from .errors import PixivError

if TYPE_CHECKING:
    from furl import furl


async def get_image(url: 'furl') -> bytes:
    async with DOWNLOAD_LIMIT:
        return await _get_image(url)


async def _get_image(url: 'furl') -> bytes:
    client = web_utils.get_client()
    try:
        response = await client.get(url.url, headers=HEADERS)
        response.raise_for_status()

    except HTTPError as exc:
        logger.error(f'图片请求失败: {exc!r}')
        raise PixivError(f'图片请求失败: {exc!r}') from exc  # noqa: TRY003
    else:
        if result := response.content:
            return result
        raise PixivError('图片获取失败')


def with_reply(event: MessageEvent, message: str | Message) -> Message:
    content = Message(message)
    if event.is_private:
        return content

    reply_message = Message([event.reply_to])
    reply_message.extend(content)
    return reply_message


def parse_tags(raw_tag: str | None) -> list[str]:
    if not raw_tag:
        return []
    return [tag.strip() for tag in raw_tag.replace('，', ',').split(',') if tag.strip()]


def _to_pil(raw: bytes) -> Image.Image:
    image = Image.open(BytesIO(raw))
    image.load()
    return image


async def to_pil(raw: bytes) -> Image.Image:
    return await asyncio.to_thread(_to_pil, raw)


def _to_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format='WEBP', lossless=True, method=2)
    return buffer.getvalue()


async def to_bytes(image: Image.Image) -> bytes:
    return await asyncio.to_thread(_to_bytes, image)
