import os
import random
import re
import zipfile
from html import escape

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup, CallbackQuery, InlineKeyboardButton, CopyTextButton

from bot.command_handler import CommandHandler
from bot.utils import bot_utils
from ..base_commands import BaseCommands
from .strings import *
from utils.utils import video_to_audio_bytes
from utils import constants, logging_utils, load_keys


class Commands(BaseCommands):
    def __init__(self, bot: AsyncTeleBot, handler: CommandHandler = None):
        cmd_func = {
            "help": self._send_help,
            "start": self._send_start,
            "contacts": self._send_contacts,
            "mp3": self._send_tomp3,
            "audio": self._send_tomp3,
            "help_mp3": self._send_tomp3,
            "logs": self._send_logs,
        }
        cmd_func_pattern = {
            re.compile(r"^/help(?:@\w+)?", re.IGNORECASE): self._send_help,
            re.compile(r"^/(audio|mp3)(?:@\w+)?", re.IGNORECASE): self._send_tomp3,
            re.compile(r"^/help_(audio|mp3)(?:@\w+)?", re.IGNORECASE): self._send_h,
        }
        super().__init__(
            bot, cmd_func, cmd_func_pattern, NAME
        )
        self.command_handler = handler

    async def _send_start(self, message: Message, is_edit: bool = False):
        args = message.text.split()
        if len(args) > 1 and args[1].lower() == "contacts":
            return await self._send_contacts(message)

        is_person = message.chat.id == message.from_user.id
        lang = (message.from_user.language_code if is_person else None) or ""
        def_lang = self.settings.get_user_lang(message.chat.id)
        smb = "🇺🇦" if str(lang).lower() in ["ru", "uk"] or str(def_lang).lower() in ["ru", "uk"] else ""
        if not def_lang:
            self.settings.set_user_lang(message.chat.id, (lang or "en").lower())
            pre_w = WELCOME_PERSON if is_person else WELCOME_CHAT
            full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
            name = full_name if is_person else message.chat.title
            text = smb + self.strings.get(pre_w, message.chat.id, escape(name or message.from_user.username or "_"))
            text += "\n\n"
            text += self.strings.get(WELCOME, message.chat.id)
            if is_person:
                text += f"\n\n<blockquote>💡 {self.strings.get(HINT, message.chat.id)}</blockquote>"
                text += self.strings.get(WELCOME_PERSON_OPT, message.chat.id)
            # if not lang or str(lang).lower() != str(def_lang):
            #     text += "\n" + self.strings.get(CHANGE_LANG, message.chat.id)
            change_lang_str = self.strings.get(CHANGE_LANG, message.chat.id)
            if not is_edit:
                await bot_utils.try_sticker(self.bot, constants.STICKER_START, message = message)
        else:
            full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
            name = escape(full_name) if is_person else ""
            text = smb + self.strings.get(WELCOME_BACK, message.chat.id, name).replace("  ", " ").replace(",,", ",")

            change_lang_str = self.strings.get(CHANGE_LANG, message.chat.id)
            if not is_edit:
                await bot_utils.try_sticker(self.bot, random.choice([constants.STICKER_START, constants.STICKER_GOOD]), message=message)

        markup = InlineKeyboardMarkup().add(
            bot_utils.b(change_lang_str, "change_lang"),
        )
        if is_edit:
            result = await bot_utils.try_edit(
                self.bot, text, message=message,
                markup=markup,
            )
        else:
            result = await bot_utils.try_send(self.bot, message.chat.id, text, markup)
        if isinstance(result, Exception):
            self.logger.error(f"Cant _send_start to chat [{message.chat.id}]: {result}")

    async def _send_contacts(self, message: Message):
        mail = "ai.poi.bot@gmail.com"
        mail_url = "https://is.gd/6xzvYw"
        text = self.strings.get(CONTACTS, message.chat.id)
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton(text="ai.poi.bot@gmail.com", url=mail_url),
            InlineKeyboardButton(text=self.strings.get(COPY, message.chat.id), copy_text=CopyTextButton(text=mail)),
        )
        await bot_utils.try_send(self.bot, message.chat.id, text, markup)


    async def _send_help(self, message: Message, is_edit: bool = False):
        lines, cmds = [], []
        for cmd in self.command_handler.cmd_list.keys():
            if not "help_" in cmd and not "_help" in cmd:
                continue
            module = self.command_handler.cmd_list_module.get(cmd, '')
            _desc = self.strings.get(f"{module}_desc_{cmd}", message.chat.id)
            if _desc:
                c = cmd.replace("help_", "").replace("_help", "")
                _c_desc = self.strings.get(f"{module}_desc_{c}", message.chat.id)
                if _c_desc:
                    lines.append(f"<b><code>/{c}</code></b> — {_c_desc}")
                lines.append(f"/{cmd} — {_desc}")
                lines.append(f"")
                cmds.append(cmd)

        result_text = self.strings.get(HELP, message.chat.id)
        result_text += "\n" + self.strings.get(CHANGE_LANG, message.chat.id)
        result_text += "\n\n" + "\n".join(lines)

        buttons = [bot_utils.b(f"ℹ️ /{c}", f"base_h_{c}") for c in cmds]
        if len(buttons) % 3 != 0: buttons.append(bot_utils.b(f"...", f"."))
        markup = InlineKeyboardMarkup().add(*buttons, row_width=3)
        markup.add(bot_utils.b(f"❌️ {self.strings.get(CLOSE, message.chat.id)}", f"delete"))
        if is_edit:
            result = await bot_utils.try_edit(
                self.bot, result_text, message=message,
                markup=markup,
            )
        else:
            result = await bot_utils.try_send(
                self.bot, message.chat.id, result_text,
                markup=markup,
                reply_to_message_id=message.message_id)
        if isinstance(result, Exception):
            self.logger.error(f"Cant send help to chat [{message.chat.id}]: {result}")

    async def handle_callback(self, call: CallbackQuery) -> str | bool:
        key = call.data.strip()
        if key == "base_h":
            await self._send_help(
                call.message, True
            )
        elif key.startswith("setlang_"):
            lang = key.split("_")[1].strip().lower()
            self.settings.set_user_lang(call.message.chat.id, (lang or "en").lower())
            await self._send_start(call.message, True)
            return True
        elif key == "change_lang":
            access = call.message.chat.id == call.from_user.id
            if not access:
                access = await bot_utils.is_admin(self.bot, call.message.chat.id, call.from_user.id)
            if not access:
                return self.strings.get(ACCESS_ADMIN, call.message.chat.id)

            await bot_utils.try_edit(
                self.bot,
                self.strings.get(TEXT_LANG, call.message.chat.id),
                message=call.message,
                markup=InlineKeyboardMarkup().add(
                    *[
                        bot_utils.b(self.strings.get_with_lang(key="lang_name", lang=k), f"setlang_{k}") for k in self.strings.strings_by_lang.keys()
                    ], row_width=2
                ),
            )
            return True
        elif key.startswith("base_h_help_"):
            cmd = key.split("base_h_help_")[1]
            module = self.command_handler.cmd_list_module.get(cmd, '')
            text = self._h_text(cmd, call.message.chat.id, module)
            if not text: return False
            await bot_utils.try_edit(
                self.bot, text, message=call.message,
                markup=InlineKeyboardMarkup().add(
                    *[
                        bot_utils.b(f"⬅️ /help", f"base_h"),
                        bot_utils.b(f"❌️ {self.strings.get(CLOSE, call.message.chat.id)}", f"delete")
                    ], row_width=1
                ),
            )
            return True
        return False

    async def _send_tomp3(self, message: Message):
        def _extract_video(m: Message):
            if not m: return None
            if m.video:
                return m.video
            if m.document and m.document.mime_type.startswith("video/"):
                return m.document
            return None

        video_file = _extract_video(message) or _extract_video(message.reply_to_message)
        if not video_file:
            raise ValueError("video not founded")
        st_loading = await bot_utils.try_sticker(self.bot, constants.STICKER_MUSIC, message=message,
                                                 reply_to_message_id=message.message_id)
        try:
            file_info = await self.bot.get_file(video_file.file_id)
            _bytes = await self.bot.download_file(file_info.file_path)
            audio_bytes = await video_to_audio_bytes(_bytes, name=video_file.file_name)

            await self.bot.send_audio(
                chat_id=message.chat.id,
                audio=audio_bytes,
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            raise ValueError(str(e))
        finally:
            await bot_utils.try_delete(self.bot, message=st_loading)

    async def _send_logs(self, message: Message):
        if not str(message.chat.id) in load_keys("OWNER_IDS"): return
        st_loading = await bot_utils.try_sticker(
            self.bot, constants.STICKER_LOADING, message=message,
            reply_to_message_id=message.message_id)
        output_file = os.path.join(logging_utils.DIR_LOGS, "logs.zip")
        try:
            log_files = [os.path.join(logging_utils.DIR_LOGS, f) for f in os.listdir(logging_utils.DIR_LOGS) if f.endswith('.log')]
            if not log_files: return

            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_STORED) as zip_f:
                for file in log_files:
                    zip_f.write(file, os.path.relpath(file, logging_utils.DIR_LOGS))
            with open(output_file, "rb") as _file:
                await self.bot.send_document(message.chat.id, _file)
        except Exception as e:
            await self.bot.send_message(message.chat.id, str(e))
        finally:
            os.remove(output_file)
            await bot_utils.try_delete(self.bot, message=st_loading)