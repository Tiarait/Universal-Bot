import re

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message

from bot.command_handler import CommandHandler
from bot.utils import bot_utils
from utils import constants
from utils.request_limiter import RequestLimiter
from ..base_commands import BaseCommands
from .utils import *
from .strings import *


class Commands(BaseCommands):
    def __init__(self, bot: AsyncTeleBot, handler: CommandHandler = None):
        cmd_func = {
            "ai": self._send_ai,
            "help_ai": self._send_h,
        }
        cmd_func_pattern = {
            re.compile(r"^/ai(?:@\w+)?", re.IGNORECASE): self._send_ai,
            re.compile(r"^/help_(ai)(?:@\w+)?", re.IGNORECASE): self._send_h,
        }
        super().__init__(
            bot, cmd_func, cmd_func_pattern, NAME
        )
        self.order = 99999
        self.command_handler = handler

    async def _send_ai(self, message: Message, is_help: bool = False):
        text = message.any_text or ""
        msgs = []
        if text.startswith("/"): text = text.split(" ", 1)[1] if " " in text else ""

        m_reply = message.reply_to_message
        reply_text = (m_reply.any_text or "") if m_reply else ""

        if reply_text: msgs.append(reply_text)
        if text: msgs.append(text)

        if text and reply_text: text = "↑ " + text
        text = (reply_text + "\n" + text).strip()

        if not text:
            raise ValueError("empty query")

        sticker = constants.STICKER_THINKS
        st_loading = await bot_utils.try_sticker(self.bot, sticker, message=message, reply_to_message_id=message.message_id)

        wait_msg: Message | None = None
        async def handle_response(result):
            await bot_utils.try_delete(self.bot, message=st_loading)
            if not isinstance(result, dict):
                text_result = f"⚠️ ERROR: {result}"
            else:
                text_result = result.get("error", "") or result.get("message", "") or "⚠️ UNKNOWN ERROR..."

            if wait_msg and isinstance(wait_msg, Message):
                await bot_utils.try_edit(
                    self.bot, message=wait_msg,
                    text=text_result,
                    disable_web_page_preview=True,
                    # parse_mode="Markdown",
                )
            else:
                await bot_utils.try_send(
                    self.bot, chat_id=message.chat.id,
                    text=text_result,
                    reply_to_message_id=message.message_id,
                    disable_web_page_preview=True,
                    # parse_mode="Markdown",
                )

        limiter = RequestLimiter()

        # queue_name = "apifreellm.com"
        # limiter.set_rate_limit(queue_name, 5)
        # f = apifreellm_com(text)

        queue_name = "cerebras_ai"
        limiter.set_rate_limit(queue_name, 2)
        lang_str = self.strings.get("lang_name", message.chat.id).replace("🤡", "")
        f = cerebras_ai(msgs, message.chat.id, lang=lang_str, is_help=is_help)
        api_keys = load_keys("CEREBRAS_TOKENS")
        if not api_keys:
            raise ValueError("Invalid API key")

        task_id = await limiter.run(
            name=queue_name,
            proxy="",
            user_id=message.chat.id,
            coro=f,
            callback=handle_response
        )

        queue_pos, queue_len = limiter.get_task_position(task_id)
        if queue_pos > 1 and queue_len:
            wait_str = f"Wait {queue_pos}/{queue_len}"
        else:
            wait_str = f"..."
        wait_msg = await bot_utils.try_send(
            self.bot, message.chat.id, wait_str,
            reply_to_message_id=message.message_id
        )

    async def handle_any_message(self, message: Message) -> bool:
        if (message.any_text or "").startswith(("/", "@")): return False
        try:
            await self._send_ai(message, is_help=True)
            return True
        except Exception:
            return False