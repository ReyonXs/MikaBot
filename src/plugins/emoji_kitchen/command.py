from arclet.alconna import Alconna
from httpx import HTTPError
from nonebot import logger
from nonebot.adapters.milky import (
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.typing import T_State  # noqa: TC002
from nonebot_plugin_alconna import on_alconna

from src.plugins.lib import with_reply

from .emoji_codes import emoji_codes
from .utils import (
    PAIR_PATTERN,
    get_combination_image,
    get_combination_url,
    parse_emoji_pair,
)


async def is_emoji_pair(event: MessageEvent, state: T_State) -> bool:
    pair = parse_emoji_pair(event.original_message)
    if pair is None:
        return False

    left, right = pair
    emojis = await emoji_codes.get()
    if left not in emojis or right not in emojis:
        return False
    state['emoji_kitchen_pair'] = pair
    return True


emoji_pair = on_alconna(
    Alconna('emoji_kitchen'),
    rule=is_emoji_pair,
    use_origin=True,
    use_cmd_start=False,
    block=False,
)
emoji_pair.shortcut(PAIR_PATTERN, command='emoji_kitchen', fuzzy=False)


async def _finish(event: MessageEvent, message: str | Message) -> None:
    await emoji_pair.finish(with_reply(event, message))


@emoji_pair.handle()
async def _(event: MessageEvent, state: T_State) -> None:
    left, right = state['emoji_kitchen_pair']
    url = await get_combination_url(left, right)
    if url is None:
        await _finish(event, '没有这个表情组合')
        return
    try:
        image = await get_combination_image(url)
    except HTTPError as exc:
        logger.warning(f'组合图片下载失败 ({exc!r})')
        await _finish(event, '组合图片下载失败, 请稍后再试')
        return

    if image is None:
        await _finish(event, '组合图片格式无效')
        return
    await emoji_pair.finish(MessageSegment.image(raw=image))
