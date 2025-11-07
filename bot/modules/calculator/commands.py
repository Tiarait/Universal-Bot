import re

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineQuery, Message, InlineQueryResultArticle, InputTextMessageContent

from ..base_commands import BaseCommands
from .calculator_core import Calculator
from bot.utils import bot_utils
import utils.constants as constants


class Commands(BaseCommands):
    def __init__(self, bot: AsyncTeleBot):
        cmd_func = {
            "calc": self._send_calc,
            "help_calc": self._send_h,
        }
        cmd_func_pattern = {
            re.compile(r"^/calc(?:@\w+)?", re.IGNORECASE): self._send_calc,
            re.compile(r"^/help_calc(?:@\w+)?", re.IGNORECASE): self._send_h,
        }
        super().__init__(
            bot, cmd_func, cmd_func_pattern, "calculator"
        )


    # async def handle_any_message(self, message: Message) -> bool:
    #     text = message.any_text or ""
    #     if text.startswith(f"@{constants.BOT_NAME}"):
    #         text = text.split(f"@{constants.BOT_NAME}", 1)[1]
    #     if not text: return False
    #     expression, text_comm = Calculator.split_expression_and_text(text)
    #     if not expression: return False
    #
    #     result_text = self._send_calc_text(text, "")
    #     if not result_text: return False
    #
    #     result = await bot_utils.try_send(
    #         self.bot, message.chat.id, result_text,
    #         reply_to_message_id=message.message_id)
    #     if isinstance(result, Exception):
    #         self.logger.error(f"Cant send calc result to chat [{message.chat.id}] from handle_any_message: {result}")
    #         return False
    #     return True
    #
    # async def handle_inline(self, query: InlineQuery) -> bool:
    #     text = query.query.strip()
    #     expression, text_comm = Calculator.split_expression_and_text(text)
    #     if not expression: return False
    #
    #     thumb = constants.THUMB_DEF
    #     try:
    #         result = self._send_calc_text(expression, "")
    #     except Exception:
    #         result = f"❌ {self.strings.get('error_calc_cant', query.from_user.id)}"
    #
    #     if "❌" in result or "⚠️" in result:
    #         thumb = constants.THUMB_ERR
    #
    #     title = re.sub(r'<[^>]*>', '', result) if result else \
    #         f"🔎 {self.strings.get('enter_what_need', query.from_user.id)}"
    #     if not result:
    #         thumb = constants.THUMB_SEARCH
    #
    #     if constants.DEL_LINE in title:
    #         title = title.split(constants.DEL_LINE)[-1]
    #
    #     title = (title
    #              .replace("\n", "")
    #              .replace("quot;", "")
    #              .replace("\"", "")
    #              .replace("&", ""))
    #     desc = self.strings.get('click_to_send', query.from_user.id) if result else \
    #         f"⚠️ {self.strings.get('enter_what_need', query.from_user.id)}"
    #
    #     if not result: result = "/calc 1+1"
    #     if "⚠️" in title: result = f"/calc {query.query.strip()}"
    #     r_list = [InlineQueryResultArticle(
    #         id=1,
    #         title=title,
    #         description=desc,
    #         thumbnail_url=thumb,
    #         input_message_content=InputTextMessageContent(
    #             message_text=result,
    #             parse_mode="HTML",
    #             disable_web_page_preview=True
    #         )
    #     )]
    #
    #     try:
    #         await self.bot.answer_inline_query(query.id, r_list, cache_time=1)
    #     except Exception:
    #         self.logger.error(f"Cant inline result to [{query.from_user.id}]: {result}")
    #     return True

    @staticmethod
    def _parse_reply_text(message: Message) -> tuple[str, str]:
        reply_c_text, reply_text = "", ""
        if not message.reply_to_message:
            return reply_c_text, reply_text
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        if "= <code>" in reply_text:
            reply_c_text = reply_text.split("= <code>")[1].split("</code>")[0].strip()
        elif "=" in reply_text:
            reply_c_text = reply_text.split("=")[1].strip()
            if " " in reply_c_text: reply_c_text = reply_c_text.split(" ")[0].strip()
            if "\n" in reply_c_text: reply_c_text = reply_c_text.split("\n")[0].strip()
        return reply_c_text, reply_text

    async def _send_calc(self, message: Message):
        c_text = self._parse_text(message)
        reply_c_text, reply_text = self._parse_reply_text(message)

        if not c_text and not reply_c_text and reply_text:
            c_text = reply_text
        if not c_text:
            raise ValueError(self.strings.get("error_calc_empty", message.chat.id))

        result_text = self._send_calc_text(c_text, reply_c_text)

        result = await bot_utils.try_send(
            self.bot, message.chat.id, result_text,
            reply_to_message_id=message.message_id)
        if isinstance(result, Exception):
            self.logger.error(f"Cant send calc result to chat [{message.chat.id}]: {result}")

    @staticmethod
    def _send_calc_text(c_text: str, reply_c_text: str) -> str:
        lines = [p.strip() for l in c_text.splitlines() for p in l.split(";") if p.strip()]

        calculators = []
        if c_text[0] in "-+*/—–" and reply_c_text and len(lines) == 1:
            calculators.append(Calculator(reply_c_text + lines[0]))
        else:
            if reply_c_text:
                calculators.append(Calculator(reply_c_text))
            for line in lines:
                if line[0] in "-+*/—–" and line[1] == " ":
                    last_calc = calculators[-1].calc_result()
                    calculators.append(Calculator(last_calc + line))
                else:
                    calculators.append(Calculator(line))

        result_text = ""
        for c in calculators:
            if result_text: result_text += constants.DEL_LINE
            result_text += "\n" + c.result_text()
        if len(calculators) > 1:
            results_calc = []
            for c in calculators:
                if c.error or not c.calc_result(): continue
                r = c.calc_result()
                if results_calc:
                    if float(r) < 0:
                        results_calc.append(f"{c.pre_symb}({r})")
                    else:
                        results_calc.append(f"{c.pre_symb}{r}")
                else:
                    results_calc.append(r)
            result_calc = Calculator("".join(results_calc))
            result_text += f"{constants.DEL_LINE_END}<blockquote>{result_calc.result_text()}</blockquote>"
        return result_text


