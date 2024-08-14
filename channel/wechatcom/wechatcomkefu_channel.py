# -*- coding=utf-8 -*-
import io
import os
import time

import requests
import web
from wechatpy import events
from wechatpy.enterprise import create_reply, parse_message
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.enterprise.events import register_event
from wechatpy.enterprise.exceptions import InvalidCorpIdException
from wechatpy.exceptions import InvalidSignatureException, WeChatClientException
from wechatpy.fields import StringField
from wechatpy.messages import UnknownMessage

from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from channel.wechatcom.CursorDB import CursorDB
from channel.wechatcom.wechatcomkefu_client import WechatComKeFuClient
from channel.wechatcom.wechatcomkefu_message import WechatComKeFuMessage
from common import memory
from common.log import logger
from common.singleton import singleton
from common.utils import compress_imgfile, fsize, split_string_by_utf8_length
from config import conf, subscribe_msg
from plugins import PluginManager, EventContext, Event
from voice.audio_convert import any_to_amr, split_audio, any_to_wav

MAX_UTF8_LEN = 2048


@register_event('kf_msg_or_event')
class KfMsgOrEvent(events.BaseEvent):
    event = 'kf_msg_or_event'
    token = StringField('Token', '')
    openKfId = StringField('OpenKfId', '')


@singleton
class WechatComKeFuChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.corp_id = conf().get("wechatcom_corp_id")
        self.secret = conf().get("wechatcomapp_secret")
        self.agent_id = conf().get("wechatcomapp_agent_id")
        self.token = conf().get("wechatcomapp_token")
        self.aes_key = conf().get("wechatcomapp_aes_key")
        print(self.corp_id, self.secret, self.agent_id, self.token, self.aes_key)
        logger.info(
            "[wechatcom] init: corp_id: {}, secret: {}, agent_id: {}, token: {}, aes_key: {}".format(self.corp_id,
                                                                                                     self.secret,
                                                                                                     self.agent_id,
                                                                                                     self.token,
                                                                                                     self.aes_key))
        self.crypto = WeChatCrypto(self.token, self.aes_key, self.corp_id)
        self.client = WechatComKeFuClient(self.corp_id, self.secret)
        self.access_token = self.get_access_token()
        self.accounts = []
        self.cursor_db = CursorDB()

    def startup(self):
        # start message listener
        urls = ("/wxcomapp", "channel.wechatcom.wechatcomkefu_channel.Query")
        app = web.application(urls, globals(), autoreload=False)
        port = conf().get("wechatcomapp_port", 9898)
        web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))

    def get_access_token(self):
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.secret}"
        try:
            response = requests.get(url)
            response_data = response.json()
            if response.status_code == 200 and response_data.get("errcode") == 0:
                return response_data['access_token']
            else:
                logger.error(f"获取 access_token 失败: {response_data}")
                return None
        except requests.RequestException as e:
            logger.error(f"请求 access_token 接口失败: {e}")
            return None

    def sync_messages(self, open_kfid, token):
        url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg?access_token={self.access_token}"
        next_cursor = self.cursor_db.get_next_cursor(open_kfid)
        payload = {
            "cursor": next_cursor,
            "token": token,
            "open_kfid": open_kfid
        }
        print("payload: ")
        print(payload)
        try:
            response = requests.post(url, json=payload)
            response_data = response.json()
            print(response_data)
            if response.status_code == 200 and response_data.get("errcode") == 0:
                messages = response_data.get("msg_list", [])
                next_cursor = response_data.get("next_cursor", next_cursor)
                self.cursor_db.save_next_cursor(open_kfid, next_cursor)
                self.handle_messages(messages)
            else:
                logger.error(f"同步消息失败: {response_data}")
        except requests.RequestException as e:
            logger.error(f"请求同步消息接口失败: {e}")

    def handle_messages(self, messages):
        for msg in messages:
            wechatcom_msg = WechatComKeFuMessage(msg, self.client)
            context = self._compose_context(
                wechatcom_msg.ctype,
                wechatcom_msg.content,
                isgroup=False,
                msg=wechatcom_msg,
            )
            if context:
                self.produce(context)

    def send_message(self, touser, open_kfid, msgtype, content, msgid=None):
        url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg?access_token={self.access_token}"
        payload = {
            "touser": touser,
            "open_kfid": open_kfid,
            "msgtype": msgtype,
        }

        if msgtype == "text":
            payload["text"] = {"content": content}
        elif msgtype == "image":
            payload["image"] = {"media_id": content}
        elif msgtype == "voice":
            payload["voice"] = {"media_id": content}

        if msgid:
            payload["msgid"] = msgid

        try:
            response = requests.post(url, json=payload)
            response_data = response.json()
            if response.status_code == 200 and response_data.get("errcode") == 0:
                logger.info(f"消息发送成功: {response_data}")
            else:
                logger.error(f"消息发送失败: {response_data}")
        except requests.RequestException as e:
            logger.error(f"请求发送消息接口失败: {e}")

    def _generate_reply(self, context: Context, reply: Reply = Reply()) -> Reply:
        e_context = PluginManager().emit_event(
            EventContext(
                Event.ON_HANDLE_CONTEXT,
                {"channel": self, "context": context, "reply": reply},
            )
        )
        reply = e_context["reply"]
        if not e_context.is_pass():
            logger.debug("[wechatcom] ready to handle context: type={}, content={}".format(context.type, context.content))
            if context.type == ContextType.TEXT or context.type == ContextType.IMAGE_CREATE:  # 文字和图片消息
                context["channel"] = e_context["channel"]
                reply = super().build_reply_content(context.content, context)
            elif context.type == ContextType.VOICE:  # 语音消息
                cmsg = context["msg"]
                cmsg.prepare()
                file_path = context.content
                wav_path = os.path.splitext(file_path)[0] + ".wav"
                try:
                    any_to_wav(file_path, wav_path)
                except Exception as e:  # 转换失败，直接使用mp3，对于某些api，mp3也可以识别
                    logger.warning("[wechatcom]any to wav error, use raw path. " + str(e))
                    wav_path = file_path
                # 语音识别
                reply = super().build_voice_to_text(wav_path)
                # 删除临时文件
                try:
                    os.remove(file_path)
                    if wav_path != file_path:
                        os.remove(wav_path)
                except Exception as e:
                    pass
                    # logger.warning("[WX]delete temp file error: " + str(e))

                if reply.type == ReplyType.TEXT:
                    new_context = self._compose_context(ContextType.TEXT, reply.content, **context.kwargs)
                    if new_context:
                        reply = self._generate_reply(new_context)
                    else:
                        return
            elif context.type == ContextType.IMAGE:  # 图片消息，当前仅做下载保存到本地的逻辑
                memory.USER_IMAGE_CACHE[context["session_id"]] = {
                    "path": context.content,
                    "msg": context.get("msg")
                }
            elif context.type == ContextType.SHARING:  # 分享信息，当前无默认逻辑
                pass
            elif context.type == ContextType.FUNCTION:  # 函数调用等，当前无默认逻辑
                pass
            elif context.type == ContextType.LOCATION:  # 位置信息，当前无默认逻辑
                pass
            elif context.type == ContextType.LINK:  # 链接信息，当前无默认逻辑
                pass
            elif context.type == ContextType.VIDEO:  # 视频消息，当前无默认逻辑
                pass
            elif context.type == ContextType.FILE:  # 文件消息，当前无默认逻辑
                context["channel"] = e_context["channel"]
                reply = super().build_reply_content(context.content, context)
            else:
                logger.warning("[wechatcom] unknown context type: {}".format(context.type))
                return
        return reply

    def send(self, reply: Reply, context: Context):
        print("[wechatcom]: ")
        print(reply)
        print("[wechatcom]: ")
        print(context)
        receiver = context["receiver"]
        open_kfid = context.kwargs['msg'].to_user_id
        if reply.type in [ReplyType.TEXT, ReplyType.ERROR, ReplyType.INFO]:
            reply_text = reply.content
            texts = split_string_by_utf8_length(reply_text, MAX_UTF8_LEN)
            if len(texts) > 1:
                logger.info("[wechatcom] text too long, split into {} parts".format(len(texts)))
            for i, text in enumerate(texts):
                self.send_message(receiver, open_kfid, "text", text)
                if i != len(texts) - 1:
                    time.sleep(0.5)  # 休眠0.5秒，防止发送过快乱序
            logger.info("[wechatcom] Do send text to {}: {}".format(receiver, reply_text))
        # elif reply.type == ReplyType.VOICE:
        #     try:
        #         media_ids = []
        #         file_path = reply.content
        #         amr_file = os.path.splitext(file_path)[0] + ".amr"
        #         any_to_amr(file_path, amr_file)
        #         duration, files = split_audio(amr_file, 60 * 1000)
        #         if len(files) > 1:
        #             logger.info("[wechatcom] voice too long {}s > 60s , split into {} parts".format(duration / 1000.0,
        #                                                                                             len(files)))
        #         for path in files:
        #             response = self.client.media.upload("voice", open(path, "rb"))
        #             logger.debug("[wechatcom] upload voice response: {}".format(response))
        #             media_ids.append(response["media_id"])
        #     except WeChatClientException as e:
        #         logger.error("[wechatcom] upload voice failed: {}".format(e))
        #         return
        #     try:
        #         os.remove(file_path)
        #         if amr_file != file_path:
        #             os.remove(amr_file)
        #     except Exception:
        #         pass
        #     for media_id in media_ids:
        #         self.client.message.send_voice(self.agent_id, receiver, media_id)
        #         time.sleep(1)
        #     logger.info("[wechatcom] sendVoice={}, receiver={}".format(reply.content, receiver))
        # elif reply.type == ReplyType.IMAGE_URL:  # 从网络下载图片
        #     img_url = reply.content
        #     pic_res = requests.get(img_url, stream=True)
        #     image_storage = io.BytesIO()
        #     for block in pic_res.iter_content(1024):
        #         image_storage.write(block)
        #     sz = fsize(image_storage)
        #     if sz >= 10 * 1024 * 1024:
        #         logger.info("[wechatcom] image too large, ready to compress, sz={}".format(sz))
        #         image_storage = compress_imgfile(image_storage, 10 * 1024 * 1024 - 1)
        #         logger.info("[wechatcom] image compressed, sz={}".format(fsize(image_storage)))
        #     image_storage.seek(0)
        #     try:
        #         response = self.client.media.upload("image", image_storage)
        #         logger.debug("[wechatcom] upload image response: {}".format(response))
        #     except WeChatClientException as e:
        #         logger.error("[wechatcom] upload image failed: {}".format(e))
        #         return
        #
        #     self.client.message.send_image(self.agent_id, receiver, response["media_id"])
        #     logger.info("[wechatcom] sendImage url={}, receiver={}".format(img_url, receiver))
        # elif reply.type == ReplyType.IMAGE:  # 从文件读取图片
        #     image_storage = reply.content
        #     sz = fsize(image_storage)
        #     if sz >= 10 * 1024 * 1024:
        #         logger.info("[wechatcom] image too large, ready to compress, sz={}".format(sz))
        #         image_storage = compress_imgfile(image_storage, 10 * 1024 * 1024 - 1)
        #         logger.info("[wechatcom] image compressed, sz={}".format(fsize(image_storage)))
        #     image_storage.seek(0)
        #     try:
        #         response = self.client.media.upload("image", image_storage)
        #         logger.debug("[wechatcom] upload image response: {}".format(response))
        #     except WeChatClientException as e:
        #         logger.error("[wechatcom] upload image failed: {}".format(e))
        #         return
        #     self.client.message.send_image(self.agent_id, receiver, response["media_id"])
        #     logger.info("[wechatcom] sendImage, receiver={}".format(receiver))

class Query:
    def GET(self):
        channel = WechatComKeFuChannel()
        params = web.input()
        logger.info("[wechatcom] get receive params: {}".format(params))
        try:
            signature = params.msg_signature
            timestamp = params.timestamp
            nonce = params.nonce
            echostr = params.echostr
            echostr = channel.crypto.check_signature(signature, timestamp, nonce, echostr)
        except InvalidSignatureException:
            raise web.Forbidden()
        return echostr

    def POST(self):
        channel = WechatComKeFuChannel()
        params = web.input()
        logger.info("[wechatcom] post receive params: {}".format(params))
        try:
            signature = params.msg_signature
            timestamp = params.timestamp
            nonce = params.nonce
            message = channel.crypto.decrypt_message(web.data(), signature, timestamp, nonce)
        except (InvalidSignatureException, InvalidCorpIdException):
            raise web.Forbidden()
        msg = parse_message(message)
        logger.info("[wechatcom] receive message: {}, msg= {}".format(message, msg))
        if msg.type == "event":
            if msg.event == "kf_msg_or_event":
                channel.sync_messages(msg.openKfId, msg.token)
        # else:
        #     try:
        #         wechatcom_msg = WechatComAppMessage(msg, client=channel.client)
        #     except NotImplementedError as e:
        #         logger.debug("[wechatcom] " + str(e))
        #         return "success"
        #     context = channel._compose_context(
        #         wechatcom_msg.ctype,
        #         wechatcom_msg.content,
        #         isgroup=False,
        #         msg=wechatcom_msg,
        #     )
        #     if context:
        #         channel.produce(context)
        return "success"
