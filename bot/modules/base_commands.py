from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup

import bot.utils.bot_utils as bot_utils
from utils.logging_utils import setup_logger
from utils.strings_manager import StringsManager
from utils import constants


class BaseCommands:
    def __init__(self, bot: AsyncTeleBot, cmd_func: dict, cmd_func_pattern: dict, module_name: str):
        self.bot = bot
        self.logger = setup_logger('Commands', 'commands.log')
        self._cmd_func = cmd_func
        self.cmd_list = self._cmd_func.keys()
        self._cmd_func_pattern = cmd_func_pattern
        self.cmd_patterns = self._cmd_func_pattern.keys()
        self.module_name = module_name
        self.strings = StringsManager()
        self.settings = self.strings.redis
        self.order = 0


    async def make_command(self, message: Message, command: str = None):
        text = message.any_text.strip()
        if not command:
            command = text.split(" ")[0] if " " in text else text
            if "\n" in command: command = command.split("\n")[0]
            if "@" in command:
                command = command.split("@")[0]
        command = command.strip("/")

        if command in self._cmd_func:
            await self.handle_command(self._cmd_func[command], message=message)
            return

        for pattern, func in self._cmd_func_pattern.items():
            if pattern.match(f"/{command}"):
                await self.handle_command(func, message=message)
                return

    async def handle_command(self, command_func, *args, **kwargs):
        f_name = command_func.__name__
        u_message: Message = kwargs.get('message')
        text = u_message.any_text or ""
        try:
            self.logger.info(f"User {u_message.from_user.id} make command - {text}")
            await command_func(*args, **kwargs)
        except Exception as e:
            # num = random.randint(10000, 99999)
            self.logger.exception(f"Execute command error #{u_message.message_id}: '{f_name}'")
            if str(e).startswith("⚠️") or "<blockquote>" in str(e):
                err_str = str(e)
            else:
                err_str = self.strings.get("error_command", u_message.chat.id)
                err_str += f" <blockquote>{e}</blockquote>"

            if text.startswith("/"):
                cmd = text.split(" ")[0] if " " in text else text
                if "@" in cmd: cmd = cmd.split("@")[0]
                n_h = self.strings.get("need_help", u_message.chat.id)
                err_str += f"\n🧐 {n_h} /help_{cmd.strip('/')}"

            st_loading = await bot_utils.try_sticker(self.bot, constants.STICKER_ERROR, message=u_message, reply_to_message_id=u_message.message_id)
            result = await bot_utils.try_send(
                self.bot, u_message.chat.id, err_str,
                reply_to_message_id=u_message.message_id)
            if isinstance(result, Exception):
                self.logger.exception(f"Cant answer to [{u_message.chat.id}] on error: {result}")
            await bot_utils.try_delete(self.bot, message=st_loading, timeout=3000)

    @staticmethod
    def _parse_text(message: Message) -> str:
        _text = (message.text or message.caption or "").strip()
        cmd, calc_text = _text, ""
        if not _text: return ""
        if " " in _text: cmd = _text.split(" ")[0]
        if "\n" in cmd: cmd = _text.split("\n")[0]
        return _text.split(cmd, 1)[1] if len(_text) > len(cmd) else ""

    def _h_text(self, cmd: str, user_id: int = None, module_name: str = None) -> str:
        text = ""
        short_desc = self.strings.get(f"{module_name}_desc_{cmd}", user_id)
        if not short_desc: return text
        full_help = self.strings.get(f"{module_name}_help_{cmd}", user_id)
        # if full_help:
        #     text += f"<blockquote>{short_desc}</blockquote>"
        text += f"\n{full_help or short_desc}"
        _cmd = cmd.replace('_help', '').replace('help_', '')
        examples = self.strings.get(f"{module_name}_examples_{cmd}", user_id)
        if examples:
            text += "\n⠀\n<b>📘 Examples</b>\n"
            text += f"<pre><code>{examples}</code></pre>"
        return text

    async def _send_h(self, message: Message):
        text = message.any_text
        cmd = text.split(" ")[0] if " " in text else text
        if "\n" in cmd: cmd = cmd.split("\n")[0]
        if "@" in cmd: cmd = cmd.split("@")[0]
        if not cmd.startswith("/help_"): return

        cmd = cmd.split("/help_")[1]
        text = self._h_text(cmd, message.chat.id, self.module_name)
        if not text: return

        result = await bot_utils.try_send(
            self.bot, message.chat.id, text,
            markup=InlineKeyboardMarkup().add(
                *[
                    bot_utils.b(f"⬅️ /help", f"base_h"),
                    bot_utils.b(f"❌️ {self.strings.get('close_msg', message.chat.id)}", f"delete")
                ], row_width=1
            ),
            reply_to_message_id=message.message_id)
        if isinstance(result, Exception):
            self.logger.exception(f"Cant send help_{cmd} to [{message.chat.id}] on error: {result}")