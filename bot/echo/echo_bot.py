from bot.bot import Bot
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType


class ECHOBot(Bot):
    def reply(self, query, context):
        if context.type == ContextType.TEXT:
            return Reply(ReplyType.TEXT, query)
        elif context.type == ContextType.IMAGE:
            return Reply(ReplyType.TEXT, "收到图片")
        elif context.type == ContextType.VOICE:
            return Reply(ReplyType.TEXT, "收到语音")
        elif context.type == ContextType.VIDEO:
            return Reply(ReplyType.TEXT, "收到视频")
        elif context.type == ContextType.FILE:
            return Reply(ReplyType.TEXT, "收到文件")
        elif context.type == ContextType.LOCATION:
            return Reply(ReplyType.TEXT, query)
        elif context.type == ContextType.SHARING:
            return Reply(ReplyType.TEXT, "收到分享")
        elif context.type == ContextType.LINK:
            return Reply(ReplyType.TEXT, "收到链接")
        else:
            return Reply(ReplyType.TEXT, "不支持消息类型")