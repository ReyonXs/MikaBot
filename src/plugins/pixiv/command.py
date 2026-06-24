from arclet.alconna import Alconna, Args, CommandMeta, Option, Subcommand
from nonebot.adapters.milky import Message, MessageEvent  # noqa: TC002
from nonebot_plugin_alconna import AlconnaQuery, Match, Query, on_alconna

from .command_args import QualityArg, build_lolicon_config, resolve_quality
from .lolicon import get_random_picture_message
from .messages import build_pixiv_message
from .pixiv_api import get_pixiv_data
from .utils import parse_tags, with_reply

command = on_alconna(
    Alconna(
        ['/'],
        'pix',
        Subcommand('config'),
        Args['pid?', int],
        Option('-t|--tag', Args['tag', str]),
        Option('-r|--r18'),
        Option('-n|--num', Args['num', int]),
        Option('-q|--quality', Args['quality', QualityArg]),
        Option('-e|--exclude_ai'),
        meta=CommandMeta(description='Pixiv 助手'),
    )
)


async def _finish(event: MessageEvent, message: str | Message) -> None:
    await command.finish(with_reply(event, message))


@command.assign('config')
async def handle_config(event: MessageEvent) -> None:
    await _finish(event, 'pix config')


@command.handle()
async def handle_main(  # noqa: PLR0913
    event: MessageEvent,
    pid: Match[int],
    tag: Match[str],
    num: Match[int],
    quality: Match[QualityArg],
    r18: Query[object] = AlconnaQuery('r18'),
    exclude_ai: Query[object] = AlconnaQuery('exclude_ai'),
) -> None:
    if pid.available:
        data = await get_pixiv_data(pid.result)
        message = await build_pixiv_message(data)
        if message is None:
            await _finish(event, '图片获取失败')
            return
        await _finish(event, message)
        return

    tags = parse_tags(tag.result if tag.available else None)
    image_quality = resolve_quality(quality.result if quality.available else None)
    config = build_lolicon_config(
        tags=tags,
        r18=r18.available,
        num=num.result if num.available else None,
        quality=image_quality,
        exclude_ai=exclude_ai.available,
    )
    message = await get_random_picture_message(config)
    if message is None:
        await _finish(event, '图片获取失败')
        return
    await _finish(event, message)
