import asyncio

from furl import furl
from nonebot import logger
from nonebot.adapters.milky import Message, MessageSegment
from PIL import Image

from src.plugins.lib.mirage_colored import generate

from .errors import PixivError
from .utils import get_image, to_bytes, to_pil


async def _build_image_message(
    image_urls: list, text: str, *, is_r18: bool
) -> Message:
    images = await asyncio.gather(
        *(get_image(furl(image_url)) for image_url in image_urls)
    )

    if is_r18:
        try:
            for index, image in enumerate(images):
                decoded_image = await to_pil(image)
                images[index] = await to_bytes(await generate(decoded_image))

        except (OSError, Image.DecompressionBombError) as exc:
            logger.warning(f'图片解码失败: {exc!r}')
            raise PixivError('图片解码失败') from exc

    image_segments = (MessageSegment.image(raw=image) for image in images)

    return Message(
        [
            *image_segments,
            MessageSegment.text(text),
        ]
    )


async def build_pixiv_message(data: dict, *, is_private: bool) -> Message:
    page_urls = data.get('urls', [])
    image_urls = []
    for item in page_urls:
        url = item.get('original') or next(iter(item.values()), None)
        if url is None:
            raise PixivError('图片 URL 获取失败')  # noqa: TRY003
        image_urls.append(url)

    is_r18 = False if is_private else bool(data.get('xRestrict'))

    return await _build_image_message(
        image_urls,
        f'标题: {data["title"]}\n作者: {data["userName"]}',
        is_r18=is_r18,
    )


async def build_lolicon_message(data: dict, *, is_private: bool) -> Message:
    image_url = data.get('urls')
    if not image_url:
        raise PixivError('图片 URL 获取失败')  # noqa: TRY003

    is_r18 = False if is_private else data.get('r18', False)
    logger.debug(f'data: {data}')
    logger.debug(f'is_r18: {is_r18}')

    return await _build_image_message(
        [image_url],
        f'标题: {data["title"]}\n作者: {data["author"]}\nPID: {data["pid"]}',
        is_r18=is_r18,
    )
