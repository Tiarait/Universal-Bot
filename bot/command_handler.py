import pkgutil
import importlib
import time
import traceback
from logging import Logger

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineQuery, Message, InlineQueryResultArticle, InputTextMessageContent, CallbackQuery, \
    InlineQueryResultsButton

from utils.strings_manager import StringsManager

from utils import constants
from .utils import bot_utils


class CommandHandler:
    def __init__(self, bot: AsyncTeleBot, logger: Logger):
        self.bot = bot
        self.bot_logger = logger
        self.cmd_list_module = {}  # { "module_name": cmd }
        self.cmd_list = {}  # { "command_name": module_instance }
        self.cmd_patterns = []  # [(pattern, module_instance)]
        self.inline_handlers = []  # [module_instance]
        self.any_message_handlers = []  # [module_instance]
        self.callback_handlers = []  # [module_instance]
        self.strings = StringsManager()
        self.load_modules()

    def load_modules(self):
        import bot.modules as modules_pkg
        for loader, name, is_pkg in pkgutil.iter_modules(modules_pkg.__path__):
            module = importlib.import_module(f"bot.modules.{name}")
            if hasattr(module, "Commands"):
                if name == "base":
                    instance = module.Commands(self.bot, handler=self)
                else:
                    instance = module.Commands(self.bot)
                for cmd in getattr(instance, "cmd_list", {}):
                    self.cmd_list[cmd] = instance
                    self.cmd_list_module[cmd] = name
                for pat in getattr(instance, "cmd_patterns", []):
                    self.cmd_patterns.append((pat, instance))
                if hasattr(instance, "handle_inline") and callable(instance.handle_inline):
                    self.inline_handlers.append(instance)
                if hasattr(instance, "handle_any_message") and callable(instance.handle_any_message):
                    self.any_message_handlers.append(instance)
                if hasattr(instance, "handle_callback") and callable(instance.handle_callback):
                    self.callback_handlers.append(instance)

    async def handle_message(self, message: Message):
        text = message.any_text.lower()
        cmd = text.split(" ")[0] if " " in text else text
        if "\n" in cmd: cmd = cmd.split("\n")[0]
        if "@" in cmd:
            b_name = cmd.split("@")[1]
            cmd = cmd.split("@")[0]
            if b_name.lower() != constants.BOT_NAME:
                return
        cmd = cmd.strip("/")
        if cmd in self.cmd_list:
            await self.cmd_list[cmd].make_command(message, command=cmd)
            return

        for pattern, instance in self.cmd_patterns:
            if pattern.match(text):
                await instance.make_command(message, command=cmd)

    async def handle_any_message(self, message: Message):
        handlers = sorted(
            self.any_message_handlers,
            key=lambda h: getattr(h, "order", 0),
            reverse=False
        )
        for instance in handlers:
            handled = await instance.handle_any_message(message)
            if handled: return
        await bot_utils.try_reaction(bot=self.bot, message=message, reaction="😡")

    async def handle_inline(self, query: InlineQuery):
        text = query.query.strip()
        r_list = []
        if not text.startswith("/"):
            for instance in self.inline_handlers:
                handled_list = await instance.handle_inline(query)
                if handled_list and isinstance(handled_list, list):
                    r_list = handled_list
                    break

        if text and not r_list:
            thumb_cmd = constants.THUMB_DEF
            for cmd in self.cmd_list.keys():
                check_title = text != "/" and (cmd.startswith(text) or f"/{cmd}".startswith(text))

                module = self.cmd_list_module.get(cmd, '')

                _desc = self.strings.get(f"{module}_desc_{cmd}", query.from_user.id)
                if not _desc: continue
                check_desc = len(text) > 3 and f" {text}" in f" {_desc}"

                _tags = self.strings.get(f"{module}_tags_{cmd}", query.from_user.id)
                _tags += ", " + self.strings.get_with_lang(f"{module}_tags_{cmd}", query.from_user.id, "en")
                check_tags = len(text) > 3 and f", {text}" in f", {_tags} "

                if check_title or check_desc or check_tags:
                    title = f"/help_{cmd}"
                    r_list.append(
                        InlineQueryResultArticle(
                            id=len(r_list) + 1,
                            title=title,
                            description=_desc,
                            thumbnail_url=thumb_cmd,
                            input_message_content=InputTextMessageContent(
                                message_text=f"/help_{cmd}@{constants.BOT_NAME}",
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
                        )
                    )
        if not text or not r_list:
            thumb = constants.THUMB_SEARCH
            r_list.append(
                InlineQueryResultArticle(
                    id=len(r_list) + 1,
                    title=f"🔎 {self.strings.get('enter_command', query.from_user.id)}",
                    description="/help",
                    thumbnail_url=thumb,
                    input_message_content=InputTextMessageContent(
                        message_text=f"/help@{constants.BOT_NAME}",
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )
        # if text:
            # thumb = "https://i.postimg.cc/k4J65jPX/free-icon-advertisement-5225340.png"
            # mail = "ai.poi.bot@gmail.com"
            # mail_url = "https://is.gd/6xzvYw"
            # r_list.insert(
            #     0, InlineQueryResultArticle(
            #         id="ads",
            #         title=self.strings.get('ads_title', query.from_user.id),
            #         description=self.strings.get('ads_desc', query.from_user.id),
            #         reply_markup=InlineKeyboardMarkup().add(
            #             InlineKeyboardButton(text="ai.poi.bot@gmail.com", url=mail_url),
            #             InlineKeyboardButton(text="Copy", copy_text=CopyTextButton(text=mail)),
            #         ),
            #         thumbnail_url=thumb,
            #         input_message_content=InputTextMessageContent(
            #             message_text=self.strings.get('contact', query.from_user.id),
            #             parse_mode="HTML",
            #         )
            #     )
            # )
        try:
            await self.bot.answer_inline_query(
                query.id, r_list, cache_time=1,
                button=InlineQueryResultsButton(
                    text=self.strings.get('ads', query.from_user.id),
                    # web_app=WebAppInfo(
                    #     url=f"https://is.gd/6xzvYw",
                    # )
                    start_parameter="contacts"
                )
            )
        except Exception:
            traceback.print_exc()
        return True

    async def handle_callback(self, call: CallbackQuery) -> str | None:
        user_id = call.message.chat.id
        hist = bot_utils.hist_user_timecall.setdefault(user_id, {})
        cur_time = int(time.time() * 1000)
        if t_block := bot_utils.check_flood(user_id):
            return self.strings.get("wait_sec", call.message.chat.id, t_block)
        if (cur_time - hist.get(call.data, 0)) < 500:
            bot_utils.block_flood(user_id, 1000)
            return self.strings.get("wait_sec", call.message.chat.id, bot_utils.check_flood(user_id))
        hist[call.data] = cur_time
        if call.data == "delete":
            await bot_utils.try_delete(self.bot, message=call.message)
            return None
        for instance in self.callback_handlers:
            handled = await instance.handle_callback(call)
            if handled:
                break
        return None