import re

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineQuery, Message, InlineQueryResultArticle, InputTextMessageContent

from ..base_commands import BaseCommands
from .calc_math_core import CalcMath
from bot.utils import bot_utils
import utils.constants as constants


class Commands(BaseCommands):
    def __init__(self, bot: AsyncTeleBot):
        cmd_func = {
            "math": self._send_math,
            "help_math": self._send_h,
            "solve": self._send_solve,
            "help_solve": self._send_h,
        }
        cmd_func_pattern = {
            re.compile(r"^/math(?:@\w+)?", re.IGNORECASE): self._send_math,
            re.compile(r"^/solve(?:@\w+)?", re.IGNORECASE): self._send_solve,
            re.compile(r"^/help_(math|solve)(?:@\w+)?", re.IGNORECASE): self._send_h,
        }
        super().__init__(
            bot, cmd_func, cmd_func_pattern, "calc_math"
        )

    async def handle_any_message(self, message: Message) -> bool:
        text = message.any_text or ""
        if text.startswith(f"@{constants.BOT_NAME}"):
            text = text.split(f"@{constants.BOT_NAME}", 1)[1]
        if not text: return False
        if not re.search(r"[0-9+\-*/^()]", text):
            return False
        if not re.search(r"\d", text):
            return False
        # is_expression = CalcMath.is_math_expression(text)
        test_calc = CalcMath(text)
        if not test_calc.calc_results() or test_calc.error: return False

        result_text = self._send_calc_text(text, "")
        if not result_text: return False

        result = await bot_utils.try_send(
            self.bot, message.chat.id, result_text,
            reply_to_message_id=message.message_id)
        if isinstance(result, Exception):
            self.logger.error(f"Cant send calc result to chat [{message.chat.id}] from handle_any_message: {result}")
            return False
        return True

    async def handle_inline(self, query: InlineQuery) -> list:
        text = query.query.strip()
        if not re.search(r"[0-9+\-*/^()]", text):
            return []
        if not re.search(r"\d", text):
            return []
        # is_expression = CalcMath.is_math_expression(text)
        test_calc = CalcMath(text)
        if not test_calc.calc_results() or test_calc.error: return []

        thumb = constants.THUMB_DEF
        try:
            result = self._send_calc_text(text, "")
        except Exception:
            result = f"❌ {self.strings.get('math_error_calc_cant', query.from_user.id)}"

        if "❌" in result or "⚠️" in result:
            thumb = constants.THUMB_ERR

        title = re.sub(r'<[^>]*>', '', result) if result else \
            f"🔎 {self.strings.get('enter_what_need', query.from_user.id)}"
        if not result:
            thumb = constants.THUMB_SEARCH

        if constants.DEL_LINE in title:
            title = title.split(constants.DEL_LINE)[-1]

        title = (title
                 .replace("\n", "")
                 .replace("quot;", "")
                 .replace("\"", "")
                 .replace("&", ""))
        desc = self.strings.get('click_to_send', query.from_user.id) if result else \
            f"⚠️ {self.strings.get('enter_what_need', query.from_user.id)}"

        if not result: result = "/calc 1+1"
        if "⚠️" in title: result = f"/calc {query.query.strip()}"
        return [InlineQueryResultArticle(
            id=1,
            title=title,
            description=desc,
            thumbnail_url=thumb,
            input_message_content=InputTextMessageContent(
                message_text=result,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        )]

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

    async def _send_math(self, message: Message):
        c_text = self._parse_text(message)
        reply_c_text, reply_text = self._parse_reply_text(message)

        if not c_text and not reply_c_text and reply_text:
            c_text = reply_text
        if not c_text:
            raise ValueError(self.strings.get("math_error_calc_empty", message.chat.id))

        result_text = self._send_calc_text(c_text, reply_c_text)

        result = await bot_utils.try_send(
            self.bot, message.chat.id, result_text,
            reply_to_message_id=message.message_id)
        if isinstance(result, Exception):
            self.logger.error(f"Cant send calc result to chat [{message.chat.id}]: {result}")


    def _send_calc_text(self, c_text: str, reply_c_text: str) -> str:
        lines = [l.strip() for l in c_text.splitlines() if l.strip()]
        calculators = []
        if c_text[0] in "-+*/—–" and reply_c_text and len(lines) == 1:
            calculators.append(CalcMath(reply_c_text + lines[0]))
        else:
            if reply_c_text:
                calculators.append(CalcMath(reply_c_text))
            for line in lines:
                c = CalcMath(line)
                if c.error and calculators and not ":=" in line:
                    c_with_prev = CalcMath(f"{calculators[-1].text_full}; {line}")
                    if not c_with_prev.error:
                        calculators[-1] = c_with_prev
                    else:
                        calculators.append(c)
                else:
                    calculators.append(c)
            if not any(not c.error and c.calc_results() for c in calculators):
                calculators = []
                if reply_c_text:
                    calculators.append(CalcMath(reply_c_text))
                calculators.append(CalcMath(";".join(lines)))

        result_text = (constants.DEL_LINE + "\n").join(c.result_text() for c in calculators)

        if len(calculators) > 1:
            result_text += self._result_calculate(calculators)
        return result_text

    async def _send_solve(self, message: Message):
        c_text = self._parse_text(message)
        reply_c_text, reply_text = self._parse_reply_text(message)

        if not c_text and not reply_c_text and reply_text:
            c_text = reply_text
        if not c_text:
            raise ValueError(self.strings.get("math_error_solve_empty", message.chat.id))

        result_text = self._send_solve_text(c_text)

        result = await bot_utils.try_send(
            self.bot, message.chat.id, result_text,
            reply_to_message_id=message.message_id)
        if isinstance(result, Exception):
            self.logger.error(f"Cant send calc result to chat [{message.chat.id}]: {result}")


    def _send_solve_text(self, c_text: str) -> str:
        from sympy import symbols, parse_expr

        lines = [p.strip() for l in c_text.splitlines() for p in l.split(";") if p.strip()]
        calculators = []
        for line in lines:
            # determine variable automatically
            if "," in line:
                expr_text, var_text = line.split(",", 1)
                var = symbols(var_text.strip())
            else:
                expr_text = line
                expr = parse_expr(expr_text)
                vars_in_expr = list(expr.free_symbols)
                var = vars_in_expr[0] if vars_in_expr else symbols("x")
            calculators.append(CalcMath(f"solve({expr_text}, {var})"))

        result_text = constants.DEL_LINE.join(c.result_text() for c in calculators)

        if len(calculators) > 1:
            result_text += self._result_calculate(calculators)
        return result_text

    @staticmethod
    def _result_calculate(calculators):
        result_text = ""
        results = []
        for c in calculators:
            if not c.results: continue
            results.extend([str(r) for r in c.results if r])
        if not results: return result_text
        has_error = any(c.error or not r or str(r).startswith("[") for c, r in zip(calculators, results))

        if has_error:
            if len(results) > 1:
                joined = "; ".join(map(str, results))
                result_text += f"{constants.DEL_LINE_END}<blockquote>RESULTS: <code>{joined}</code>"
                results_str_calc = [f"({r})" for r in results]
                r_calc = CalcMath("+".join(results_str_calc))
                if not r_calc.error:
                    result_text += f"\nSUM = <code>{r_calc.last_result()}</code>"
                result_text += "</blockquote>"
        else:
            parts = []
            for c, r in zip(calculators, results):
                if not (c.error or not r or str(r).startswith("[")):
                    prefix = c.pre_symb if parts else ""
                    parts.append(f"{prefix}({r})" if parts and float(r) < 0 else f"{prefix}{r}")

            if len(parts) > 1:
                result_calc = CalcMath("".join(parts))
                result_text += f"{constants.DEL_LINE_END}<blockquote>{result_calc.result_text()}</blockquote>"
        return result_text
