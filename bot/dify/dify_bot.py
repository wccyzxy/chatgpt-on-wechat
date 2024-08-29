# encoding:utf-8
import json

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
class DIFYBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        self.dify_url = conf().get("dify_url")
        self.dify_token = conf().get("dify_token")
        self.args = {
            "inputs": {},
            "response_mode": "blocking",
            "conversation_id": "",
            "user": f"{uuid.uuid4()}",
            "files": [
            ]
        }

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[DIFYBOT] query={}".format(query))

            new_args = self.args.copy()
            new_args["query"] = query
            reply_content = self.reply_text(args=new_args)
            logger.debug(
                "[DIFYBOT] new_query={}, reply_content={} ".format(
                    query,
                    reply_content["content"],
                )
            )
            if reply_content["code"] == 0:
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[DIFYBOT] error reply {}".format(reply_content))
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
                "Authorization": "Bearer " + self.dify_token,
                "Content-Type": "application/json",
            }
            response = requests.post(f"{self.dify_url if self.dify_url.endswith('/') else self.dify_url + '/'}chat-messages", headers=headers, json=args, timeout=30)
            data = response.json()
            logger.debug("[DIFYBOT] response data={}".format(data))
            message = json.loads(data['answer'])['text']
            return {
                "conversation_id": data["conversation_id"],
                "code": 0,
                "content": message,
            }
        except Exception as e:
            logger.error("[DIFYBOT] error {}".format(e))
            need_retry = retry_count < 2
            result = {"conversation_id": 0, "code": 404, "content": "我现在有点累了，等会再来吧"}

            if need_retry:
                logger.warn("[DIFYBOT] 第{}次重试".format(retry_count + 1))
                return self.reply_text(args, retry_count + 1)
            else:
                return result

