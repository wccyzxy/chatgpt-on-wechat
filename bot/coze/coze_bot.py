# encoding:utf-8

import requests

from bot.bot import Bot
from bot.openai.open_ai_image import OpenAIImage
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
import uuid
import re


# OpenAI对话模型API (可用)
class COZEBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        # set the default api_key
        self.bot_id = conf().get("coze_bot_id")
        self.coze_url = "https://api.coze.cn/open_api/v2/chat"
        self.coze_token = conf().get("coze_token")
        self.args = {
            "conversation_id": f"{uuid.uuid4()}",  # 会话的id,
            "bot_id": self.bot_id,
            "user": f"{uuid.uuid4()}",
            "stream": False,
        }

    def remove_leading_json(self, s):
        logger.debug("[COZEBOT] s={}".format(s))
        pattern = r'^\{((?:[^{}]*|{(?:[^{}]*|{[^{}]*})*})*?)\}'
        result = re.sub(pattern, '', s, count=1)

        return result.strip()
    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[COZEBOT] query={}".format(query))

            new_args = self.args.copy()
            new_args["query"] = query
            reply_content = self.reply_text(args=new_args)
            logger.debug(
                "[COZEBOT] new_query={}, reply_content={} ".format(
                    query,
                    reply_content["content"],
                )
            )
            if reply_content["code"] == 0:
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[COZEBOT] error reply {}".format(reply_content))
            return reply

        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, args=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            if args is None:
                args = self.args
            headers = {
                "Authorization": "Bearer " + self.coze_token,
                "Content-Type": "application/json",
            }
            response = requests.post(self.coze_url, headers=headers, json=args, timeout=30)
            data = response.json()
            logger.debug("[COZEBOT] response data={}".format(data))
            messages = data['messages']
            message = ""
            for m in messages:
                if m["type"] == "answer" and ("card_type" not in m["content"] or "template_url" not in m["content"]):
                    message = message + m["content"]
            return {
                "conversation_id": data["conversation_id"],
                "code": data["code"],
                "content": message,
            }
        except Exception as e:
            logger.error("[COZEBOT] error {}".format(e))
            need_retry = retry_count < 2
            result = {"conversation_id": 0, "code": 404, "content": "我现在有点累了，等会再来吧"}

            if need_retry:
                logger.warn("[COZEBOT] 第{}次重试".format(retry_count + 1))
                return self.reply_text(args, retry_count + 1)
            else:
                return result

