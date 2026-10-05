"""表达式词法分析器（Tokenizer）。

安全声明
--------
本项目**没有任何** ``eval`` / ``exec`` / ``compile`` / ``pickle`` / ``subprocess`` 调用，
用户输入只会被当作"数学表达式"逐字符扫描成 Token，再由手写的递归下降解析器构造成
抽象语法树（AST），最后按白名单函数表求值。即使输入是 ``__import__('os').system('rm -rf /')``，
也只会得到一条"非法字符"的语法错误，绝不会被当作代码执行。

Token 类型
----------
``number``  数值字面量，支持小数与科学计数法（``3.14``、``.5``、``1.5e-3``）
``name``    标识符：函数名（``sin``）或常量名（``pi``、``e``）
``op``      运算符：``+ - * / % ^ !``
``lparen`` ``rparen`` ``comma``  括号与函数参数分隔符
``eof``     结束标记，便于解析器统一向前看
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.errors import ExpressionSyntaxError, ExpressionTooComplexError

# ---------------------------------------------------------------------------
# 防御性限制：把"恶意/异常输入"挡在解析之前，避免 CPU 与内存被拖垮
# ---------------------------------------------------------------------------
MAX_EXPRESSION_LENGTH = 500
MAX_TOKEN_COUNT = 300
MAX_NESTING_DEPTH = 32
MAX_NODE_COUNT = 200

# 中英文全角符号、显示符号 → ASCII 规范形式
_NORMALIZE_MAP = {
    "×": "*",
    "✕": "*",
    "⋅": "*",
    "·": "*",
    "＊": "*",
    "÷": "/",
    "／": "/",
    "−": "-",
    "–": "-",
    "—": "-",
    "－": "-",
    "＋": "+",
    "＾": "^",
    "！": "!",
    "％": "%",
    "（": "(",
    "）": ")",
    "，": ",",
    "。": ".",
    "　": " ",
    "π": "pi",
}

_OP_CHARS = set("+-*/%^!")


@dataclass(slots=True)
class Token:
    """一个词法单元。"""

    kind: str
    value: str
    pos: int

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Token({self.kind!r}, {self.value!r}, pos={self.pos})"


def normalize_expression(text: str) -> str:
    """把用户输入规范化为解析器可识别的形式（仅做字符替换，不做任何求值）。"""
    for src, dst in _NORMALIZE_MAP.items():
        text = text.replace(src, dst)
    return text


def _read_number(src: str, start: int) -> tuple[str, int]:
    """从 ``start`` 开始读取一个数值字面量，返回 (文本, 下一个位置)。"""
    length = len(src)
    index = start
    seen_dot = False
    while index < length and (src[index].isdigit() or (src[index] == "." and not seen_dot)):
        if src[index] == ".":
            seen_dot = True
        index += 1

    # 科学计数法：仅当 e/E 后面确实跟着数字时才吞掉，避免与常量 e 冲突
    if index < length and src[index] in "eE":
        probe = index + 1
        if probe < length and src[probe] in "+-":
            probe += 1
        if probe < length and src[probe].isdigit():
            while probe < length and src[probe].isdigit():
                probe += 1
            index = probe
    return src[start:index], index


def tokenize(expression: str) -> list[Token]:
    """把表达式字符串切分成 Token 列表。"""
    src = normalize_expression(expression)

    if not src.strip():
        raise ExpressionSyntaxError("表达式为空，请输入算式")
    if len(src) > MAX_EXPRESSION_LENGTH:
        raise ExpressionTooComplexError(
            f"表达式长度不能超过 {MAX_EXPRESSION_LENGTH} 个字符（当前 {len(src)}）"
        )

    tokens: list[Token] = []
    index = 0
    length = len(src)

    while index < length:
        char = src[index]

        if char.isspace():
            index += 1
            continue

        # 数值：数字开头，或 ".5" 这种省略整数部分的写法
        if char.isdigit() or (char == "." and index + 1 < length and src[index + 1].isdigit()):
            start = index
            text, index = _read_number(src, index)
            tokens.append(Token("number", text, start))
            continue

        # 标识符：函数名或常量名
        if char.isalpha() or char == "_":
            start = index
            while index < length and (src[index].isalnum() or src[index] == "_"):
                index += 1
            tokens.append(Token("name", src[start:index], start))
            continue

        if char in _OP_CHARS:
            tokens.append(Token("op", char, index))
            index += 1
            continue

        if char == "(":
            tokens.append(Token("lparen", char, index))
            index += 1
            continue

        if char == ")":
            tokens.append(Token("rparen", char, index))
            index += 1
            continue

        if char == ",":
            tokens.append(Token("comma", char, index))
            index += 1
            continue

        raise ExpressionSyntaxError(f"表达式中存在非法字符 “{char}”（第 {index + 1} 个字符）")

    if len(tokens) > MAX_TOKEN_COUNT:
        raise ExpressionTooComplexError(f"表达式元素过多（超过 {MAX_TOKEN_COUNT} 个）")

    tokens.append(Token("eof", "", length))
    return tokens
