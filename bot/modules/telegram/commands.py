import json
import os
import re
import tempfile
from html import escape

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InputFile, InlineKeyboardMarkup

from bot.command_handler import CommandHandler
from bot.utils import bot_utils
from utils import constants
from ..base_commands import BaseCommands
from .utils import video_to_clip_bytes, audio_as_voice, get_country
from .strings import *


class Commands(BaseCommands):
    def __init__(self, bot: AsyncTeleBot, handler: CommandHandler = None):
        cmd_func = {
            "vn": self._send_tovideonote,
            "circle": self._send_tovideonote,
            "voice": self._send_tovoice,
            "parse": self._send_parse,
            "inspect": self._send_parse,
            "id": self._send_id,
            "help_circle": self._send_h,
            "help_voice": self._send_h,
            "help_parse": self._send_h,
            "help_id": self._send_h,
        }
        cmd_func_pattern = {
            re.compile(r"^/(vn|circle)(?:@\w+)?", re.IGNORECASE): self._send_tovideonote,
            re.compile(r"^/voice(?:@\w+)?", re.IGNORECASE): self._send_tovoice,
            re.compile(r"^/(parse|inspect)(?:@\w+)?", re.IGNORECASE): self._send_parse,
            re.compile(r"^/id(?:@\w+)?", re.IGNORECASE): self._send_id,
            re.compile(r"^/help_(id|vn|circle|parse|voice)(?:@\w+)?", re.IGNORECASE): self._send_h,
        }
        super().__init__(
            bot, cmd_func, cmd_func_pattern, NAME
        )
        self.command_handler = handler

    @staticmethod
    def _extract_file(m: Message):
        if not m: return None
        if m.audio:
            return m.audio
        if m.video:
            return m.video
        if m.document and (m.document.mime_type.startswith("audio/") or m.document.mime_type.startswith("video/")):
            return m.document
        return None

    async def _send_tovideonote(self, message: Message):
        video_file = None
        if message.video or message.document and message.document.mime_type.startswith("video/"):
            video_file = message.video or message.document
        elif message.reply_to_message:
            rep = message.reply_to_message
            if rep.video or rep.document and rep.document.mime_type.startswith("video/"):
                video_file = rep.video or rep.document

        if not video_file:
            raise ValueError("video not founded")

        st_loading = await bot_utils.try_sticker(self.bot, constants.STICKER_LOADING, message=message,
                                       reply_to_message_id=message.message_id)

        try:
            file_info = await self.bot.get_file(video_file.file_id)
            video_bytes = await self.bot.download_file(file_info.file_path)

            _bio = await video_to_clip_bytes(video_bytes, name=video_file.file_name)
            r = await bot_utils.try_video_note(
                self.bot,
                chat_id=message.chat.id,
                video_bio=_bio,
                reply_to_message_id=message.message_id
            )
            if isinstance(r, Exception):
                raise ValueError(str(r))
        except Exception as e:
            raise ValueError(str(e))
        finally:
            await bot_utils.try_delete(self.bot, message=st_loading)


    async def _send_tovoice(self, message: Message):
        _file = self._extract_file(message) or self._extract_file(message.reply_to_message)
        if not _file:
            raise ValueError("audio not founded")
        st_loading = await bot_utils.try_sticker(self.bot, constants.STICKER_LOADING, message=message,
                                                 reply_to_message_id=message.message_id)
        try:
            file_info = await self.bot.get_file(_file.file_id)
            _bytes = await self.bot.download_file(file_info.file_path)

            _bio = await audio_as_voice(_bytes, name=_file.file_name)
            r = await bot_utils.try_voice(
                self.bot,
                chat_id=message.chat.id,
                audio_bio=_bio,
                reply_to_message_id=message.message_id
            )
            if isinstance(r, Exception):
                raise ValueError(str(r))
        except Exception as e:
            raise ValueError(str(e))
        finally:
            await bot_utils.try_delete(self.bot, message=st_loading)

    async def _send_id(self, message: Message):
        def format_phone(p: str) -> str:
            return f"<code>{p}</code>  <a href='https://wa.me/{p}'>WA</a> <a href='https://botapi.co/viber/{p}?=&_bk=cloudflare'>Viber</a>"
        target = message.reply_to_message or message
        if message.reply_to_message:
            if message.reply_to_message.contact:
                user = message.reply_to_message.contact
                uid = user.user_id
                n = ""
                is_bot = False
                tel = user.phone_number
                if tel and not tel.startswith("+"): tel = "+"+tel
                _link = f"https://t.me/{tel}" if tel else ""
            else:
                user = message.reply_to_message.from_user
                uid = user.id
                n = f"@{escape(user.username)}"
                is_bot = user.is_bot
                tel = ""
                _link = f"https://t.me/{user.username}" if user.username else ""

            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            markup = InlineKeyboardMarkup().add(bot_utils.cb("Copy ID", uid))
            text = (
                f"<b>{'🤖 Bot' if is_bot else '👤 User'}:</b> {n}\n" +
                f"🆔 <b>ID:</b> <code>{uid}</code>\n" +
                f"💬 <b>Name:</b> {escape(full_name or '—') or '—'}\n" +
                (f"🔗 <b>Link:</b> {_link}\n" if _link else "") +
                (f"📲 <b>Phone:</b> {format_phone(tel)}\n" if tel else "") +
                (f"<i>({get_country(tel)})</i>" if tel else "")
            )
        else:
            if message.contact:
                user = message.contact
                uid = user.user_id
                n = ""
                is_bot = False
                tel = user.phone_number
                if tel and not tel.startswith("+"): tel = "+" + tel
                _link = f"https://t.me/{tel}" if tel else ""

                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                markup = InlineKeyboardMarkup().add(bot_utils.cb("Copy ID", uid))
                text = (
                        f"<b>{'🤖 Bot' if is_bot else '👤 User'}:</b> {n}\n" +
                        f"🆔 <b>ID:</b> <code>{uid}</code>\n" +
                        f"💬 <b>Name:</b> {escape(full_name or '—') or '—'}\n" +
                        (f"🔗 <b>Link:</b> {_link}\n" if _link else "") +
                        (f"📲 <b>Phone:</b> {format_phone(tel)}\n" if tel else "") +
                        (f"<i>({get_country(tel)})</i>" if tel else "")
                )
            else:
                chat = message.chat
                c_id = message.chat.id
                full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip()
                markup = InlineKeyboardMarkup().add(bot_utils.cb("Copy ID", c_id))
                _link = f"t.me/c/{str(chat.id).replace('-100', '')}/{message.message_id}" if str(chat.id).startswith("-100") else ""
                n = f"@{chat.username}" if chat.username else ""
                text = (
                    f"<b>🗣 Chat:</b> {escape(n or chat.title)}\n" +
                    f"🆔 <b>ID:</b> <code>{c_id}</code>\n" +
                    (f"💬 <b>Title:</b> {escape(chat.title or '—')}\n" if chat.title and chat.username else "") +
                    (f"💬 <b>Name:</b> {escape(full_name or '—')}\n" if full_name else "") +
                    f"🔊 <b>Type:</b> {chat.type}\n" +
                    (f"🔗 <b>Link:</b> {chat.invite_link or _link or '—'}\n" if chat.invite_link or _link else "")
                )
        if target.forward_from or target.forward_from_chat:
            fuser = target.forward_from
            fchat = target.forward_from_chat
            if fuser:
                uid = fuser.id
                n = f"@{escape(fuser.username)}" if fuser.username else ""
                is_bot = fuser.is_bot
                full_name = f"{fuser.first_name or ''} {fuser.last_name or ''}".strip()
                text += "\n\n"
                text += (
                    f"<b>{'🤖 Forwarded Bot' if is_bot else '👤 Forwarded User'}:</b> {n}\n"
                    f"🆔 <b>ID:</b> <code>{uid}</code>\n"
                    f"💬 <b>Name:</b> {escape(full_name or '—')}\n"
                )

            elif fchat:
                cid = fchat.id
                uname = f"@{escape(fchat.username)}" if fchat.username else ""
                text += "\n\n"
                text += (
                    f"<b>📢 Forwarded Chat:</b> {escape(fchat.title or uname or '—')}\n"
                    f"🆔 <b>ID:</b> <code>{cid}</code>\n"
                    f"💬 <b>Type:</b> {fchat.type}\n"
                )

        await bot_utils.try_send(
            self.bot, chat_id=message.chat.id, text=text, markup=markup,
            reply_to_message_id=message.message_id, disable_web_page_preview=True)

    async def _send_parse(self, message: Message):
        m = message.reply_to_message or message

        json_str = json.dumps(m.json, ensure_ascii=False, indent=2)

        MAX_LEN = 3996  # 4096 max. Telegram limit for <pre><code>
        text = f"<blockquote expandable><pre><code class='json'>{escape(json_str[:MAX_LEN])}"
        if len(json_str) > MAX_LEN:
            text += "..."
        text += "</code></pre></blockquote>"

        if len(json_str) > MAX_LEN:
            text += f"\n\n🚧 {self.strings.get('TOO_LONG', message.chat.id)} ⏬"

        r = await bot_utils.try_send(
            self.bot, chat_id=message.chat.id, text=text,
            reply_to_message_id=message.message_id
        )
        reply_to_message_id = message.message_id
        if isinstance(r, Message):
            reply_to_message_id = r.message_id

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as temp_file:
            temp_file.write(json_str)
            temp_file_path = temp_file.name

        try:
            with open(temp_file_path, "rb") as file:
                await self.bot.send_document(
                    message.chat.id,
                    document=InputFile(file, file_name=f"{message.chat.id}_{message.message_id}.json"),
                    reply_to_message_id=reply_to_message_id
                )
        finally:
            os.remove(temp_file_path)


    async def handle_any_message(self, message: Message) -> bool:
        if message.contact:
            try:
                await self._send_id(message)
                return True
            except Exception:
                return False
        try:
            await self._send_tovideonote(message)
            if message.contact or message.reply_to_message or message.forward_from or message.forward_from_chat:
                await self._send_id(message)
            return True
        except Exception:
            return False