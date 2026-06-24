from typing import TYPE_CHECKING

from httpx import HTTPError
from nonebot import logger
from nonebot.adapters.milky import Message, MessageEvent

from src.plugins.lib import web_utils

from .config import HEADERS

if TYPE_CHECKING:
    from furl import furl


async def get_image(url: 'furl') -> bytes | None:
    client = web_utils.get_client()
    try:
        response = await client.get(url.url, headers=HEADERS)
        response.raise_for_status()

    except HTTPError as exc:
        logger.error(f'图片请求失败: {exc}')
    else:
        return response.content


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
