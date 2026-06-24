from furl import furl
from nonebot.adapters.milky import Message, MessageSegment

from .utils import get_image


async def _build_image_message(image_url: str, text: str) -> Message | None:
    image = await get_image(furl(image_url))
    if image is None:
        return None

    return Message(
        [
            MessageSegment.image(raw=image),
            MessageSegment.text(text),
        ]
    )


async def build_pixiv_message(data: dict) -> Message | None:
    urls = data.get('urls') or {}
    image_url = urls.get('original') or next(iter(urls.values()), None)
    if image_url is None:
        return None

    return await _build_image_message(
        image_url,
        f'标题: {data["title"]}\n作者: {data["userName"]}',
    )


async def build_lolicon_message(data: dict) -> Message | None:
    image_url = data.get('urls')
    if not image_url:
        return None

    return await _build_image_message(
        image_url,
        f'标题: {data["title"]}\n作者: {data["author"]}\nPID: {data["pid"]}',
    )
