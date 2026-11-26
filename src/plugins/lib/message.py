from nonebot.adapters.milky import Message, MessageEvent


def with_reply(event: MessageEvent, message: str | Message) -> Message:
    content = Message(message)
    if event.is_private:
        return content

    reply_message = Message([event.reply_to])
    reply_message.extend(content)
    return reply_message
