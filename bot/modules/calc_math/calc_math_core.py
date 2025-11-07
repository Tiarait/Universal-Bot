import re

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from html import escape

from utils import setup_logger, setup_fake

ERROR_TEXT = "⚠️ Incorrect expression"

class CalcMath:
    def __init__(self, text: str, log_on: bool = None):
        self.logger = setup_logger('CalcMath', 'calculator_math.log') if log_on else setup_fake()
        self.error = ""
        self.text_full = ""
        self.pre_symb = "+"
        self.results = []
        self.lambdas = {}
        if not text:
            self.error = ERROR_TEXT
            return
        self.launch(text)

    def launch(self, text: str):
        self.error = ""
        # normalize text
        self.text_full = re.sub(r"\s+", " ", text).replace("—", "--").replace("–", "--").replace("÷", "/").strip()
        self.text_full = re.sub(r'(\d),(\d{3})\.(\d+)', r'\1\2.\3', self.text_full)  # 2,006.56 -> 2006.56

        if self.text_full[0] in "-—–" and self.text_full[1] == " ":
            prefix, rest = self.text_full[:2], self.text_full[2:]
            self.text_full = rest.strip()
            self.pre_symb = prefix.strip()
        elif self.text_full[0] in "+*/":
            prefix, rest = self.text_full[:1], self.text_full[1:]
            self.text_full = rest.strip()
            self.pre_symb = prefix.strip()

        # if not self.is_math_expression(self.text_full):
        #     self.error = "🚨 " + self.text_full
        #     return

        parts = [p.strip() for p in self.text_full.split(";") if p.strip()]
        self.results = []

        # parse lambda
        for part in parts:
            match = re.match(r"([a-zA-Z_]\w*)\s*\((.*?)\)\s*:=\s*(.+)", part)
            if match:
                name, args, body = match.groups()
                args = [a.strip() for a in args.split(",")]
                body = body.replace("^", "**")
                self.lambdas[name] = (args, body)
                self.results.append(None)
            else:
                calc_result = self.calculate(part)
                self.results.append(calc_result)
                if self.error:
                    break

        ends_results = [r for r in self.results if r is not None]
        if not ends_results and not self.error:
            self.error = ERROR_TEXT


    def calculate(self, expr_text: str = None):
        if not expr_text: expr_text = self.text_full
        # sympy functions
        local_dict = {
            'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan,
            'log': sp.log, 'ln': sp.log, 'sqrt': sp.sqrt,
            'abs': sp.Abs, 'pi': sp.pi, 'e': sp.E,
            'diff': sp.diff, 'integrate': sp.integrate, 'limit': sp.limit,
            'Sum': sp.summation, 'solve': sp.solve
        }

        # 1. empty lambdas
        for name, (args, body) in self.lambdas.items():
            local_dict[name] = lambda *vals: 0

        # 2. real lambdas
        for name, (args, body) in self.lambdas.items():
            symbols_list = sp.symbols(args)
            expr = parse_expr(body, local_dict={**local_dict, **dict(zip(args, symbols_list))})
            local_dict[name] = lambda *vals, ex=expr, syms=symbols_list: ex.subs(dict(zip(syms, vals))).evalf()

        # convert binary/hex
        expr_text = re.sub(r"0b[01]+", lambda m: str(int(m.group(0), 2)), expr_text)
        expr_text = re.sub(r"0x[0-9a-fA-F]+", lambda m: str(int(m.group(0), 16)), expr_text)

        # sizes
        size_map = {
            "B": 1, "b": 1,
            "KB": 1024, "Kb": 1024, "kb": 1024,
            "MB": 1024 ** 2, "Mb": 1024 ** 2, "mb": 1024 ** 2,
            "GB": 1024 ** 3, "Gb": 1024 ** 3, "gb": 1024 ** 3,
            "TB": 1024 ** 4, "Tb": 1024 ** 4, "tb": 1024 ** 4
        }
        expr_text = re.sub(r"\b(\d+(\.\d+)?)(B|KB|MB|GB|TB|Kb|Mb|Gb|Tb|b|kb|mb|gb|tb)\b",
                           lambda m: str(sp.Float(float(m.group(1)) * size_map.get(m.group(3).upper(), 1))),
                           expr_text)

        # unit prefixes
        unit_map = {
            'P': 1e15, 'T': 1e12, 'G': 1e9,
            'М': 1e6, 'M': 1e6, 'м': 1e6,
            # 'к': 1e3, 'К': 1e3, 'k': 1e3,
            'т': 1e3,
            'm': 1e-3,
            'u': 1e-6, 'n': 1e-9, 'p': 1e-12}
        expr_text = re.sub(
            r"\b(\d+(\.\d+)?)([PTGМMтмmunp])\b",
            lambda m: str(sp.Float(float(m.group(1)) * unit_map.get(m.group(3), 1))),
            expr_text)

        while re.search(r"\d+\.?\d*\s*[кk]", expr_text, re.IGNORECASE):
            expr_text = re.sub(
                r"(\d+\.?\d*)\s*[кk]",
                lambda match: str(Decimal(match.group(1)) * 1000),
                expr_text,
                flags=re.IGNORECASE
            )

        # replaced pct(a,b) on value in %
        expr_text = re.sub(
            r"pct\(([^,]+),([^()]+)\)",
            lambda m: str(float(m.group(1)) / float(m.group(2)) * 100),
            expr_text
        )

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
                full_start = expression0.rfind(left_expr, 0, end)

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

                    if expression0[:full_start].strip() or expression0[match.end():].strip():
                        expression0 = (
                                expression0[:full_start] +
                                f"({left_expr} {op} {percent_expr})" +
                                expression0[match.end():]
                        )
                    else:
                        expression0 = f"{left_expr} {op} {percent_expr}"
            return expression0

        if "%" in expr_text:
            expr_text = process_percent(expr_text)
            if expr_text.endswith("%"):
                expr_text = expr_text[:-1]
        try:
            expr = parse_expr(expr_text, local_dict=local_dict, evaluate=True)
            if isinstance(expr, sp.Expr):
                val = expr.evalf()
                if isinstance(val, (sp.Float, sp.Integer)):
                    val = float(val)
                return int(val) if val == int(val) else float(val)
            return expr
        except Exception as e:
            self.error = f"⚠️ {str(e)}"
            return None

    def calc_results(self) -> list[str]:
        if not self.results: return []
        return [str(r) for r in self.results if r]

    def last_result(self, _to: int = None) -> str:
        if not self.results: return ""
        return self.calc_result(r=self.results[-1], _to=_to)

    def calc_result(self, r, _to: int = None) -> str:
        if not r: r = "0"
        if str(r).startswith("0") and not "." in str(r): return r
        try:
            v = float(r)
            s = f"{v:.20f}"
            match = re.match(r"0\.0*(\d+)", s)
            if match:
                zeros = len(s.split(".")[1]) - len(s.split(".")[1].lstrip("0"))
                if zeros >= _to or 10:
                    digits = match.group(1)[:3]
                    new_val = f"0.{('0' * zeros)}{digits}"
                    d = Decimal(new_val).quantize(Decimal(f"1e-{zeros + 3}"), rounding=ROUND_HALF_UP)
                    return str(d.normalize())
        except Exception:
            pass
        if isinstance(r, tuple):
            r = list(r)
        if isinstance(r, list):
            n_list = []
            for v in r:
                try:
                    n_list.append(self.round_to(float(v), _to or 10))
                except Exception:
                    n_list.append(str(v))
            return f"[{', '.join(n_list)}]"
        try:
            return self.round_to(float(r), _to or 10)
        except Exception:
            return r

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


    def result_text(self, round_to: int = None) -> str:
        result = ""
        if self.error:
            result = self.text_full
            result += f"<blockquote>{escape(self.error)}</blockquote>"
            return result

        parts = [p.strip() for p in self.text_full.split(";") if p.strip()]
        from utils.constants import DEL_LINE
        for ind, part in enumerate(parts):
            result += f"\n<code>{part}</code>"
            if self.results[ind] is not None:
                rr = str(self.calc_result(r=self.results[ind], _to=round_to)).strip() or "0"
                if part != rr and self.text_full != rr + ".0":
                    result += f" = <code>{rr}</code>"
                # result += DEL_LINE
        return result.strip(DEL_LINE).strip()