import re
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from html import escape

from utils import setup_logger, setup_fake

ERROR_TEXT = "⚠️ Incorrect expression"

class Calculator:
    def __init__(self, text: str, log_on: bool = None):
        self.logger = setup_logger('Calculator', 'calculator.log') if log_on else setup_fake()
        self.error = ""
        self.text_full = ""
        self.text_comm = ""
        self.pre_symb = "+"
        self.expressions = []
        self.result = None
        if not text:
            self.error = ERROR_TEXT
            return
        self.launch(text)

    def launch(self, text):
        self.error = ""
        self.text_full = (
            re.sub(r"\s+", " ", str(text))
            .replace("—", "--")
            .replace("–", "--")
            .replace("–", "--")
            .replace("÷", "/")
        )
        self.text_comm = ""
        self.expressions = []
        self.result = ""
        if self.text_full[0] in "-—–" and self.text_full[1] == " ":
            prefix, rest = self.text_full[:2], self.text_full[2:]
            self.text_full = rest.strip()
            self.pre_symb = prefix.strip()
        elif self.text_full[0] in "+*/":
            prefix, rest = self.text_full[:1], self.text_full[1:]
            self.text_full = rest.strip()
            self.pre_symb = prefix.strip()
        exp, self.text_comm = self.split_expression_and_text(self.text_full)
        if not exp:
            self.error = ERROR_TEXT
            return
        exp = exp.replace(" ", "")
        parts = re.split(r"(?<=[кk])(?=\d)", exp, flags=re.IGNORECASE)
        if len(parts) > 1:
            exp = parts[0]
            self.text_comm = parts[1] + " " + self.text_comm
        self.text_comm = self.text_comm.strip()
        self.expressions.append(exp)
        self.result = self.calculate()

    @staticmethod
    def split_expression_and_text(text: str) -> tuple[str, str]:
        expression = str(text).strip()
        text_part = ""
        math_part = ""
        match2 = re.match(r"([^\s+\-*/=()]+)\s*(\(([^)]+)\))", expression, re.IGNORECASE)
        if match2:
            math_part = match2.group(1).replace(",", ".")
            text_part = match2.group(2)

        match = re.match(
            # r"([0-9+\-*/().,\sкk%]*\d[кk%]*)(?=\s*\D|$)(.*)",
            r"([0-9+\-*/().,\sкk%PTGMмМКB]*\d[кk%PTGMмМКB]*)(?=\s*\D|$)(.*)",
            math_part or expression or text_part,
            re.IGNORECASE)
        if match:
            math_part = match.group(1).replace(",", ".")
            if match.group(2).strip() != text_part:
                text_part = match.group(2) + " " + text_part

        if not math_part:
            return "", expression

        if " " in math_part:
            parts = math_part.split(" ")
            for i, ep in enumerate(parts):
                check_s = ep.replace(",", ".").strip()
                if check_s.replace(".", "").isdigit() and check_s.count('.') > 1:
                    math_part = " ".join(parts[:i])
                    text_part = " ".join(parts[i:]) + " " + text_part
                    break

        if math_part.count("(") != math_part.count(")"):
            while text_part and text_part[0] == ")":
                math_part += text_part[0]
                text_part = text_part[1:]

        text_comm = text_part.strip()
        return math_part.strip(), text_comm

    def calculate(self) -> float | int | None:
        try:
            expression = self.normalize_number(self.expressions[-1].replace(" ", ""))
            self.expressions.append(expression)
            if "-+" in expression:
                raise ValueError(f'{ERROR_TEXT}: "-+"')
            if "+-" in expression:
                raise ValueError(f'{ERROR_TEXT}: "+-"')

            size_map = {
                "B": 1, "b": 1,
                "KB": 1024, "Kb": 1024, "kb": 1024,
                "MB": 1024 ** 2, "Mb": 1024 ** 2, "mb": 1024 ** 2,
                "GB": 1024 ** 3, "Gb": 1024 ** 3, "gb": 1024 ** 3,
                "TB": 1024 ** 4, "Tb": 1024 ** 4, "tb": 1024 ** 4
            }
            unit_map = {
                'P': 1e15, 'T': 1e12, 'G': 1e9,
                'М': 1e6, 'M': 1e6, 'м': 1e6,
                # 'к': 1e3, 'К': 1e3, 'k': 1e3,
                'т': 1e3,
                'm': 1e-3,
                'u': 1e-6, 'n': 1e-9, 'p': 1e-12}

            def repl_units(m):
                val = Decimal(m.group(1))
                unit = m.group(3).upper()
                if unit in size_map:
                    return str(val * size_map[unit])
                if m.group(3) in unit_map:
                    return str(val * Decimal(unit_map[m.group(3)]))
                return m.group(0)

            expression = re.sub(r"\b(\d+(\.\d+)?)([PTGМMтмmunp]|B|b|KB|Kb|kb|MB|Mb|mb|GB|Gb|gb|TB|Tb|tb)\b", repl_units, expression)

            while re.search(r"\d+\.?\d*\s*[кk]", expression, re.IGNORECASE):
                expression = self.normalize_number(re.sub(
                    r"(\d+\.?\d*)\s*[кk]",
                    lambda match: str(Decimal(match.group(1)) * 1000),
                    expression,
                    flags=re.IGNORECASE
                ))
            self.expressions.append(expression)

            def percent_inverse(match):
                full_expr, op, percent = match.groups()
                act = "/"
                if op in ["--", "++"]: act = "*"
                if op == "--": op = "-"
                if op == "++": op = "+"
                percent_value = eval(f"1 + ({op}{percent} / 100)", {"__builtins__": {}}, {})

                def need_brackets() -> bool:
                    for ch in ["*", "/", "+", "-", "–", "—"]:
                        if ch in full_expr: return True
                    return False

                if (full_expr.startswith("(") and full_expr.endswith(")")) or not need_brackets():
                    self.expressions.append(f"{full_expr}{op}{percent}%%")
                    return f"{full_expr}{act}{percent_value}"
                else:
                    self.expressions.append(f"({full_expr}){op}{percent}%%")
                    return f"{eval(full_expr)}{act}{percent_value}"

            expression = re.sub(r"(\(?.*?\)?)\s*([+\-]{1,2})\s*(\d+\.?\d*)\s*%%", percent_inverse, expression)
            self.expressions.append(expression)
            expression = expression.replace("--", "-").replace("++", "+")

            def replace_percent(match):
                num = Decimal(match.group(1)) / 100
                return str(num)

            expression = re.sub(r"(\d+\.?\d*)%%", replace_percent, expression)
            self.expressions.append(expression)

            def process_percent(expression0):
                expression0 = re.sub(r"\((\d+(\.\d+)?)%\)", r"\1%", expression0)
                pattern = re.compile(r"([+\-])\s*(\d+\.?\d*)\s*%")

                def find_left(expr, start_index):
                    i = start_index - 1
                    balance = 0
                    while i >= 0:
                        if expr[i] == ")":
                            balance += 1
                        elif expr[i] == "(":
                            balance -= 1
                        if balance < 0: break
                        i -= 1
                    return expr[i + 1:start_index].strip()

                while True:
                    match = pattern.search(expression0)
                    if not match: break
                    op, percent = match.groups()
                    end = match.start()
                    left_expr = find_left(expression0, end)
                    full_start = end - len(left_expr)

                    if left_expr.endswith("%"):
                        left_val = float(left_expr[:-1])
                        percent_val = float(percent)
                        result = left_val + percent_val if op == "+" else left_val - percent_val
                        result = int(result) if result == int(result) else float(result)
                        pre_percent_val = expression0[:full_start].strip()
                        after_percent_val = expression0[match.end():].strip()
                        expression0 = pre_percent_val + f"{result}%" + after_percent_val
                        expression0 = expression0.replace(f"({result}%)", f"{result}%")
                    else:
                        try:
                            eval_left = eval(left_expr, {"__builtins__": {}}, {})
                        except:
                            eval_left = left_expr
                        percent_expr = f"({eval_left} * {percent} / 100)" \
                            if isinstance(eval_left, (int, float)) \
                            else f"({left_expr} * {percent} / 100)"
                        expression0 = (
                                expression0[:full_start] +
                                f"({left_expr} {op} {percent_expr})" + expression0[match.end():]
                        )
                return expression0

            expression = process_percent(expression)
            self.expressions.append(expression)

            if "%" in expression:
                expression = re.sub(r"(\d+\.?\d*)%", r"(\1/100)", expression)
                # return self.calculate(try_calc + 1)
            result = eval(expression, {"__builtins__": {}}, {})
            self.logger.info(f"Result: {self.expressions[0]} = {result}")

            d = Decimal(str(result)).quantize(Decimal('1.0000000000000'), rounding=ROUND_HALF_UP)
            if d == d.to_integral():
                result = int(d)
            else:
                result = float(d)
            return result
        except Exception as e:
            self.logger.error(f"ERROR calculate [{self.expressions[0]}]: {e}")
            self.error = str(e)
            return None

    @staticmethod
    def normalize_number(expression: str) -> str:
        def fix_number(num: str) -> str:
            num = num.replace(",", "")
            symb_start = ""
            symb_end = ""
            if len(num) > 1 and not num[0].isdigit() and num[0] != ".":
                symb_start = num[0]
                num = num[1:]
            if len(num) > 1 and not num[-1].isdigit() and num[-1] != ".":
                symb_end = num[-1]
                num = num[:-1]
            if num.startswith("."):
                num = f"0{num}"
            if num.count(".") > 1:
                num = num.replace(".", "", 1)  # Del only first dot
            if len(num) > 1 and num.startswith("0") and "." not in num and "," not in num:
                num = f"0.{num[1:]}"
            if num.endswith(".0"):
                num = num[:-2]
            return symb_start + num + symb_end

        return re.sub(r"(\b|\.|,)\d+([,.]\d+)?([kк]?)*\b", lambda m: fix_number(m.group()), expression)

    def calc_result(self, _to: int = None) -> str:
        if not self.result:
            self.result = "0"
        try:
            v = Decimal(str(self.result))
            if _to is None:
                _to = 20
            # round properly
            d = v.quantize(Decimal(f'1e-{_to}'), rounding=ROUND_HALF_UP)
            d_str = format(d, 'f')
            # remove trailing zeros
            return d_str.rstrip("0").rstrip(".") if "." in d_str else d_str
        except Exception:
            # fallback if something went wrong
            return str(self.result)

    @staticmethod
    def round_to(v: float, _to: int = None) -> str:
        if not v: return ""
        if _to is None: _to = 20
        try:
            v = round(v, _to)
            d = Decimal(str(v)).quantize(Decimal(f'1e-{_to}'), rounding=ROUND_DOWN)
            while d == 0 and _to < 9:
                _to += 1
                d = Decimal(str(v)).quantize(Decimal(f'1e-{_to}'), rounding=ROUND_DOWN)

            d_str = format(d, 'f')
            return d_str.rstrip("0").rstrip(".") if "." in d_str else d_str
        except Exception:
            v_str = format(v, 'f')
            return v_str.rstrip("0").rstrip(".") if "." in v_str else v_str

    def expression(self, lvl: int) -> str:
        if not self.expressions: return ""
        if lvl <= len(self.expressions):
            r = self.expressions[lvl]
        else:
            r = self.expressions[-1]
        return r

    def result_text(self, round_to: int = None) -> str:
        if self.error:
            result = self.text_full
            if self.error == ERROR_TEXT and self.text_comm:
                result += f"<blockquote>{escape(self.text_comm)}</blockquote>"
            else:
                result += f"<blockquote>{escape(self.error)}</blockquote>"
                if self.text_comm:
                    if not self.text_comm.startswith("(") and not self.text_comm.endswith(")"):
                        result += f"\n(<i>{escape(self.text_comm)}</i>)"
                    else:
                        result += f"\n<i>{escape(self.text_comm)}</i>"
            return result

        # last_expr = self.expression(-1)
        # if "//" in last_expr and last_expr.count("//") == 1:
        #     return command_calcrest(last_expr + " " + self.text_comm)

        result = f"<code>{self.expression(0)}</code>"
        if self.expression(2) != self.expression(0):
            result += f" = <code>{self.expression(2)}</code>"
        nex_exp = 4
        nex_exp += (self.expression(0).count("%%") - 1)
        if self.expression(nex_exp) != self.expression(0) and self.expression(nex_exp) != self.expression(2):
            result += f" = <code>{self.expression(nex_exp)}</code>"
        rr = self.calc_result(_to=round_to).strip() or "0"
        if self.expression(nex_exp) != rr and self.expression(nex_exp) != rr + ".0":
            result += f" = <code>{rr}</code>"
        if "=" not in result: result += f" = <code>{rr}</code>"

        if self.text_comm:
            if not self.text_comm.startswith("(") and not self.text_comm.endswith(")"):
                result += f"\n(<i>{escape(self.text_comm)}</i>)"
            else:
                result += f"\n<i>{escape(self.text_comm)}</i>"
        return result.strip()