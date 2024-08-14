import json
import uuid

import pymongo
import requests

from bot.bot import Bot
from bot.chatgpt.chat_gpt_bot import ChatGPTBot
from bridge.reply import ReplyType, Reply
from bot.summarize.mongo import MongoDB


class SUMMARIZEBot(Bot):
    def __init__(self):
        self.mongo = MongoDB()
        self.api_key = 'app-mgXpJvAKJrWNGfFJfBFs8pUZ'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def send_message(self, query, user):
        data = {
            "inputs": {},
            "query": query,
            "response_mode": "blocking",
            "conversation_id": "",
            "user": user,
            "files": []
        }
        response = requests.post(
            'http://122.51.128.152:5001/v1/chat-messages',
            headers=self.headers,
            data=json.dumps(data)
        )
        return response.json()['answer']

    def reply(self, query, context):
        group_id = context.kwargs['msg'].other_user_nickname
        if query.startswith("总结") and len(query.split(" ")) == 2:
            try:
                n = int(query.split(" ")[1])
            except ValueError:
                # 返回错误信息
                return Reply(ReplyType.TEXT, "总结命令格式不正确，请参考：总结 [n]")
            records = self.mongo.find_many(group_id, {}).sort("_id", pymongo.DESCENDING).limit(1000)
            msg = []
            for record in records:
                if record['content'].startswith("@bot 总结"):
                    continue
                msg.append(f"{record['user']}: {record['content']}")
                if len(msg) == n:
                    break
            msg = list(reversed(msg))
            msg_txt = "\n".join(msg)
            replay_text = f"{msg_txt}\n\n总结：{self.send_message(msg_txt, str(uuid.uuid4()))}"
            return Reply(ReplyType.TEXT, replay_text)
        if query.startswith("总结") and len(query.split(" ")) == 3:
            try:
                n = int(query.split(" ")[1])
            except ValueError:
                # 返回错误信息
                return Reply(ReplyType.TEXT, "总结命令格式不正确，请参考：总结 [n] [user]")
            user = query.split(" ")[1]
            records = self.mongo.find_many(group_id, {"user": user}).sort("_id", pymongo.DESCENDING).limit(1000)
            msg = []
            for record in records:
                if record['content'].startswith("@bot 总结"):
                    continue
                msg.append(f"{record['user']}: {record['content']}")
                if len(msg) == n:
                    break
            msg = list(reversed(msg))
            msg_txt = "\n".join(msg)
            replay_text = f"{msg_txt}\n\n总结：{self.send_message(msg_txt, str(uuid.uuid4()))}"
            return Reply(ReplyType.TEXT, replay_text)
        return ChatGPTBot().reply(query, context)