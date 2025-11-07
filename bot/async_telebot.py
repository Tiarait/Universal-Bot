import asyncio
import signal
import sys
import traceback

import requests
import telebot.async_telebot
from telebot.types import Message

from bot.command_handler import CommandHandler
from .utils.bot_utils import is_owner_chat
from utils import constants

class TelegramBot:
    def __init__(self, token, logger):
        self.logger = logger
        self.bot = telebot.async_telebot.AsyncTeleBot(
            token=token,
            parse_mode='HTML'
        )
        self.tasks = []
        self.stop_flag = False
        self.commands = CommandHandler(self.bot, self.logger)
        self.register_handlers()

    def register_handlers(self):
        bot = self.bot
        c = self.commands

        content_types = [
            "text", "audio", "document", "photo",
            "video", "video_note"
        ]
        #, "sticker", "location", "contact", "voice", "venue", "poll", "dice"

        @bot.message_handler(
            func=lambda m: (m.any_text or "").startswith("/") and
                           (m.any_text or "").lstrip('/').split()[0].split('@')[0].lower() in c.cmd_list,
            content_types=content_types
        )
        async def handle_cmd(message: Message):
            try:
                await c.handle_message(message)
            except Exception:
                self.logger.exception("Exception while handling message")

        @bot.message_handler(
            func=lambda message: any(pattern.match(str(message.any_text).lower()) for pattern, _ in c.cmd_patterns),
            content_types=content_types
        )
        async def handle_patterns(message: Message):
            try:
                await c.handle_message(message)
            except Exception:
                self.logger.exception("Exception while handling patterns")

        @bot.inline_handler(func=lambda query: True)
        async def handle_all_inline(query):
            try:
                await c.handle_inline(query)
            except Exception:
                self.logger.exception("Exception while handling inline")

        @bot.message_handler(
            content_types=[
                "text", "audio", "document", "photo",
                "video", "video_note",
                "sticker", "location", "contact", "voice", "venue", "poll", "dice"
            ]
        )
        async def handle_any_message(message: Message):
            try:
                if is_owner_chat(message) or (message.any_text or "").startswith(f"@{constants.BOT_NAME}"):
                    await c.handle_any_message(message)
            except Exception:
                self.logger.exception("Exception while handling message")

        @bot.callback_query_handler(func=lambda call: True)
        async def handle_all_callback(call):
            try:
                err = await c.handle_callback(call)
            except Exception as e:
                err = f"{e}"
                self.logger.exception("Exception while handling inline")
            if err is not None:
                try:
                    await bot.answer_callback_query(call.id, err or "", show_alert=False, cache_time=0)
                except Exception:
                    pass

    async def start_polling(self) -> None:
        self.logger.info("Starting bot polling...")

        bot_info = await self.bot.get_me()
        if bot_info and bot_info.username:
            import utils.constants as constants
            constants.BOT_NAME = bot_info.username


        while not self.stop_flag:
            try:
                await self.bot.infinity_polling(timeout=40)
            except requests.exceptions.ReadTimeout:
                self.logger.warning("Timeout error, restarting in 10 seconds...")
                await asyncio.sleep(10)
            except Exception as e:
                self.logger.error(f"Bot error: {e}\n{traceback.format_exc()}")
                await asyncio.sleep(5)


    async def stop_polling(self) -> None:
        self.bot._polling = False
        await self.bot.close_session()

    async def stop_tasks(self) -> None:
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await self.stop_polling()

    def graceful_exit(self, signum=None, frame=None) -> None:
        self.logger.info(f"Received signal {signum}, stopping bot gracefully...")
        self.stop_flag = True

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.stop_tasks())
        except RuntimeError:
            asyncio.run(self.stop_tasks())

        sys.exit(0)

    def run(self):
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)
        try:
            asyncio.run(self._run())
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Bot stopped by keyboard interrupt")
            asyncio.run(self.stop_polling())
        except Exception as e:
            self.logger.critical(f"Fatal error: {e}\n{traceback.format_exc()}")
            sys.exit(1)

    async def _run(self):
        await asyncio.gather(
            self.start_polling(),
            return_exceptions=True
        )