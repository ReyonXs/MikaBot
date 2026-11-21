from nonebot import on_command, on_message
from nonebot.adapters.milky import Message, MessageEvent
from nonebot.params import CommandArg

from src.mika_games.common import ModelError, complete, lock, read, room, write


async def incoming(event: MessageEvent) -> bool:
    return event.data.sender_id != event.self_id and event.data.message_scene in ("friend", "group")


async def addressed(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    return (await incoming(event) and bool(text) and not text.startswith("/")
            and (event.data.message_scene == "friend" or event.is_tome()))


chat = on_command("聊天", aliases={"chat", "c", "lt"}, rule=incoming, priority=10, block=True, force_whitespace=True)
reset = on_command("清空聊天", aliases={"reset", "clear", "rc"}, rule=incoming, priority=10, block=True, force_whitespace=True)
natural = on_message(rule=addressed, priority=90, block=True)


def session(event):
    return f"chat/{room(event)}/{event.data.sender_id}"


async def reply(event, text):
    if not text or len(text) > 4000:
        return "请发送 1 至 4000 字的文字，例如 /聊天 介绍一下月球。"
    key = session(event)
    async with lock(key):
        history = read(key) or []
        turn = {"role": "user", "content": text}
        try:
            answer = await complete([{"role": "system", "content": "你是 QQ 聊天助手。使用对方的语言，准确、自然地回答。"}, *history, turn])
        except ModelError as exc:
            return str(exc)
        if len(answer) > 3500:
            answer = answer[:3490] + "…（可要求继续）"
        write(key, [*history, turn, {"role": "assistant", "content": answer}][-16:])
        return answer


@chat.handle()
async def explicit(event: MessageEvent, arg: Message = CommandArg()):
    await chat.finish(await reply(event, arg.extract_plain_text().strip()))


@natural.handle()
async def automatic(event: MessageEvent):
    await natural.finish(await reply(event, event.get_plaintext().strip()))


@reset.handle()
async def clear(event: MessageEvent):
    key = session(event)
    async with lock(key):
        write(key, None)
    await reset.finish("已清空你在这里的聊天记录。")
