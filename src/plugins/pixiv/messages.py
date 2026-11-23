from furl import furl
from nonebot import logger
from nonebot.adapters.milky import Message, MessageSegment
from PIL import Image

from src.plugins.lib.mirage_colored import generate

from .utils import get_image, to_bytes, to_pil


async def _build_image_message(
    image_url: str, text: str, *, is_r18: bool
) -> Message | None:
    image = await get_image(furl(image_url))
    if image is None:
        return None

    if is_r18:
        try:
            decoded = await to_pil(image)
        except (OSError, Image.DecompressionBombError) as exc:
            logger.warning(f'图片解码失败: {exc!r}')
            return None
        image = await to_bytes(await generate(decoded))

    return Message(
        [
            MessageSegment.image(raw=image),
            MessageSegment.text(text),
        ]
    )


async def build_pixiv_message(data: dict, *, is_private: bool) -> Message | None:
    urls = data.get('urls') or {}
    image_url = urls.get('original') or next(iter(urls.values()), None)
    if image_url is None:
        return None

    is_r18 = False if is_private else bool(data.get('xRestrict'))

    return await _build_image_message(
        image_url,
        f'标题: {data["title"]}\n作者: {data["userName"]}',
        is_r18=is_r18,
    )


async def build_lolicon_message(data: dict, *, is_private: bool) -> Message | None:
    image_url = data.get('urls')
    if not image_url:
        return None

    is_r18 = False if is_private else data.get('r18', False)
    logger.debug(f'data: {data}')
    logger.debug(f'is_r18: {is_r18}')

    return await _build_image_message(
        image_url,
        f'标题: {data["title"]}\n作者: {data["author"]}\nPID: {data["pid"]}',
        is_r18=is_r18,
    )
