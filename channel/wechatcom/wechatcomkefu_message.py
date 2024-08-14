import json
import re

from wechatpy.enterprise import WeChatClient

from bridge.context import ContextType
from channel.chat_message import ChatMessage
from common.log import logger
from common.tmp_dir import TmpDir


class WechatComKeFuMessage(ChatMessage):
    def __init__(self, msg, client: WeChatClient, is_group=False):
        super().__init__(msg)
        self.msg_id = msg.get("msgid")
        self.create_time = msg.get("send_time")
        self.is_group = is_group

        if msg.get("msgtype") == "text":
            self.ctype = ContextType.TEXT
            self.content = msg.get("text", {}).get("content", "")
        elif msg.get("msgtype") == "image":
            self.ctype = ContextType.IMAGE
            self.content = TmpDir().path() + msg.get("image").get("media_id") + ".png"  # content直接存临时目录路径

            def download_image():
                # 如果响应状态码是200，则将响应内容写入本地文件
                response = client.media.download(msg.get("image").get("media_id"))
                if response.status_code == 200:
                    content_disposition = response.headers.get('Content-disposition')
                    filename = re.findall('filename="(.+)"', content_disposition)[0]
                    self.content = self.content + f""".{filename.split(".")[-1]}"""
                    with open(self.content, "wb") as f:
                        f.write(response.content)
                else:
                    logger.info(f"[wechatcom] Failed to download image file, {response.content}")

            self._prepare_fn = download_image
        elif msg.get("msgtype") == "voice":
            self.ctype = ContextType.VOICE
            self.content = TmpDir().path() + msg.get("voice").get("media_id") + ".mp3"  # content直接存临时目录路径

            def download_voice():
                # 如果响应状态码是200，则将响应内容写入本地文件
                response = client.media.download(msg.media_id)
                if response.status_code == 200:
                    content_disposition = response.headers.get('Content-disposition')
                    filename = re.findall('filename="(.+)"', content_disposition)[0]
                    self.content = self.content + f""".{filename.split(".")[-1]}"""
                    with open(self.content, "wb") as f:
                        f.write(response.content)
                else:
                    logger.info(f"[wechatcom] Failed to download voice file, {response.content}")

            self._prepare_fn = download_voice
        elif msg.get("msgtype") == "video":
            self.ctype = ContextType.VIDEO
            self.content = TmpDir().path() + msg.get("video").get("media_id") + ".mp4"  # content直接存临时目录路径

            def download_video():
                # 如果响应状态码是200，则将响应内容写入本地文件
                response = client.media.download(msg.get("video").get("media_id"))
                if response.status_code == 200:
                    content_disposition = response.headers.get('Content-disposition')
                    filename = re.findall('filename="(.+)"', content_disposition)[0]
                    self.content = self.content + f""".{filename.split(".")[-1]}"""
                    with open(self.content, "wb") as f:
                        f.write(response.content)
                else:
                    logger.info(f"[wechatcom] Failed to download voice file, {response.content}")

            self._prepare_fn = download_video()
        elif msg.get("msgtype") == "file":
            self.ctype = ContextType.FILE
            self.content = TmpDir().path() + msg.get("file").get("media_id")  # content直接存临时目录路径

            def download_file():
                # 如果响应状态码是200，则将响应内容写入本地文件
                response = client.media.download(msg.get("file").get("media_id"))
                print(response.headers)
                if response.status_code == 200:
                    content_disposition = response.headers.get('Content-disposition')
                    filename = re.findall('filename="(.+)"', content_disposition)[0]
                    self.content = self.content + f""".{filename.split(".")[-1]}"""
                    with open(self.content, "wb") as f:
                        f.write(response.content)
                else:
                    logger.info(f"[wechatcom] Failed to download voice file, {response.content}")

            self._prepare_fn = download_file()
        elif msg.get("msgtype") == "location":
            self.ctype = ContextType.LOCATION
            self.content = json.dumps(msg.get("location", {}))
        elif msg.get("msgtype") == "link":
            self.ctype = ContextType.LINK
            self.content = json.dumps(msg.get("link", {}))
        else:
            raise NotImplementedError("Unsupported message type: Type:{} ".format(msg.get("msgtype")))

        self.from_user_id = msg.get("external_userid")
        self.to_user_id = msg.get("open_kfid")
        self.other_user_id = msg.get("external_userid")
