from bot.bot import Bot
from bot.chatgpt.chat_gpt_bot import ChatGPTBot
from bot.rag.rag import RAG
from bridge.reply import ReplyType, Reply


class RAGBot(Bot):
    def __init__(self):
        self.rag = RAG()

    def reply(self, query, context):
        if len(self.rag.query(query)) > 0 :
            return Reply(ReplyType.TEXT, self.rag.queryAnswer(query))
        return ChatGPTBot().reply(query, context)