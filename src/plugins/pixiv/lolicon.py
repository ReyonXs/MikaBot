import asyncio
from typing import TYPE_CHECKING

from httpx import HTTPError
from nonebot import logger
from nonebot.adapters.milky import Message, MessageSegment

from src.plugins.lib import web_utils

from .config import DEFAULT_LOLICON_CONFIG, LOLICON_API, LoliconConfig
from .messages import build_lolicon_message

if TYPE_CHECKING:
    from furl import furl

_LOLICON_BUSY_MESSAGE = '已有 Lolicon 请求正在处理中，请稍后再试'
_MESSAGE_SEPARATOR = '\n————\n'
_lolicon_request_lock = asyncio.Lock()


async def get_random_picture_message(
    args: LoliconConfig, *, is_private: bool
) -> Message | None:
    if _lolicon_request_lock.locked():
        return Message(MessageSegment.text(_LOLICON_BUSY_MESSAGE))

    async with _lolicon_request_lock:
        data = await _get_lolicon_api_data(args)
        if not data:
            return None

        return await _build_lolicon_messages(data, is_private=is_private)


async def _build_lolicon_messages(
    data: list[dict], *, is_private: bool
) -> Message | None:
    messages: list[MessageSegment] = []
    for item in data:
        message = await build_lolicon_message(item, is_private=is_private)
        if message is None:
            continue
        if messages:
            messages.append(MessageSegment.text(_MESSAGE_SEPARATOR))
        messages.extend(message)

    if not messages:
        return None

    return Message(messages)


def _build_lolicon_api_url(config: LoliconConfig = DEFAULT_LOLICON_CONFIG) -> 'furl':
    url = LOLICON_API.copy()

    params = {
        'r18': config.r18,
        'num': config.num,
        'tag': config.tag,
        'size': config.size,
        'proxy': config.proxy,
        'excludeAI': config.exclude_ai,
    }

    for key, value in params.items():
        if value == '':
            continue
        url.args.add(key, value)

    logger.debug(f'url: {url}')
    return url


def _parse_lolicon_api_data(raw_json: dict):
    error = raw_json.get('error')
    if error:
        logger.error(f'Lolicon API 调用错误: {error}')
        return []
    pictures = []
    for item in raw_json['data']:
        urls = item.get('urls')
        if not isinstance(urls, dict):
            continue
        image_url = next(
            (url for url in urls.values() if isinstance(url, str) and url.strip()),
            None,
        )
        if image_url is None:
            continue
        pictures.append(
            {
                'pid': item['pid'],
                'title': item['title'],
                'author': item['author'],
                'r18': item['r18'],
                'urls': image_url,
            }
        )
    return pictures


async def _get_lolicon_api_data(args: LoliconConfig) -> list:
    client = web_utils.get_client()
    url = _build_lolicon_api_url(args)
    try:
        response = await client.get(url.url)
        response.raise_for_status()

        return _parse_lolicon_api_data(response.json())
    except HTTPError as exc:
        logger.error(f'LOLICON API 请求失败: {exc!r}')
        return []
