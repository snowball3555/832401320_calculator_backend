"""表达式语法分析器（递归下降）与抽象语法树。

文法（EBNF，优先级由低到高）::

    expression  := term (("+" | "-") term)*
    term        := unary (("*" | "/" | "%") unary | implicit unary)*
    implicit    := unary              -- 隐式乘法：2pi、3(4+5)、(1+2)(3+4)
    unary       := ("+" | "-") unary | power
    power       := postfix ("^" unary)?          -- 右结合，且允许 2^-1
    postfix     := primary ("!")*                 -- 后缀阶乘，可叠加 3!!
    primary     := NUMBER | IDENT | IDENT "(" args ")" | "(" expression ")"
    args        := expression ("," expression)*

为什么不用 ``eval`` / 现成表达式库？
------------------------------------
作业明确禁止把用户输入当作程序代码执行。这里采取"自己实现词法+语法分析"的方案：

1. **安全性**：没有 ``eval``/``exec``/``compile``，输入只可能被解释成数学表达式，
   函数调用受 :data:`app.services.math_functions.FUNCTIONS` 白名单约束；
2. **可控的错误提示**：可以为"括号不匹配""除数为 0""末尾缺少操作数"等场景
   返回精确且可展示给用户的中文提示，而不是一句干巴巴的 SyntaxError；
3. **可展示的中间产物**：解析结果是一棵 AST，``/api/parse`` 接口能把它序列化成 JSON，
   便于讲清楚"优先级"和"括号"到底是怎么被处理的。

运算符优先级与结合性
--------------------
=====================  ==========  ==========================================
运算符                 优先级      结合性
=====================  ==========  ==========================================
``+`` ``-`` (二元)     1           左结合
``*`` ``/`` ``%``      2           左结合
隐式乘法               2           左结合（与 ``*`` 同级）
``+`` ``-`` (一元)     3           右结合（前缀）
``^``                  4           右结合（``2^3^2 = 2^9``）
``!`` (后缀)           5           后缀
=====================  ==========  ==========================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.expression_lexer import (
    MAX_NESTING_DEPTH,
    MAX_NODE_COUNT,
    Token,
    tokenize,
)
from app.services.math_functions import CONSTANTS, FUNCTIONS
from app.utils.errors import ExpressionSyntaxError, ExpressionTooComplexError

# ---------------------------------------------------------------------------
# 抽象语法树节点
# ---------------------------------------------------------------------------


class Node:
    """AST 节点基类。"""

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    def to_infix(self) -> str:  # pragma: no cover - 由子类实现
        raise NotImplementedError


@dataclass(slots=True)
class NumberNode(Node):
    """数值字面量节点。"""

    value: float

    def to_dict(self) -> dict[str, Any]:
        return {"type": "number", "value": self.value}

    def to_infix(self) -> str:
        return _format_number(self.value)


@dataclass(slots=True)
class UnaryNode(Node):
    """一元正负号节点。"""

    op: str
    operand: Node

    def to_dict(self) -> dict[str, Any]:
        return {"type": "unary", "op": self.op, "operand": self.operand.to_dict()}

    def to_infix(self) -> str:
        return f"({self.op}{self.operand.to_infix()})"


@dataclass(slots=True)
class BinaryNode(Node):
    """二元运算节点。"""

    op: str
    left: Node
    right: Node

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "binary",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }

    def to_infix(self) -> str:
        return f"({self.left.to_infix()} {self.op} {self.right.to_infix()})"


@dataclass(slots=True)
class FunctionNode(Node):
    """函数调用节点。"""

    name: str
    args: list[Node]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "args": [arg.to_dict() for arg in self.args],
        }

    def to_infix(self) -> str:
        rendered = ", ".join(arg.to_infix() for arg in self.args)
        return f"{self.name}({rendered})"


@dataclass(slots=True)
class FactorialNode(Node):
    """后缀阶乘节点。"""

    operand: Node

    def to_dict(self) -> dict[str, Any]:
        return {"type": "factorial", "operand": self.operand.to_dict()}

    def to_infix(self) -> str:
        return f"({self.operand.to_infix()}!)"


def _format_number(value: float) -> str:
    """把 AST 中的数值格式化回简短文本，供 ``to_infix`` 展示。"""
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return f"{value:.12g}"


# ---------------------------------------------------------------------------
# 递归下降解析器
# ---------------------------------------------------------------------------


class ExpressionParser:
    """把 Token 序列解析成 AST。

    解析器自身不计算任何结果，只负责"结构是否正确"；
    求值交给 :mod:`app.services.calculator_service`，职责分离，便于分别测试。
    """

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._index = 0
        self._depth = 0
        self._node_count = 0

    # -- 基础设施 ---------------------------------------------------------
    def _peek(self, offset: int = 0) -> Token:
        position = self._index + offset
        if position >= len(self._tokens):
            position = len(self._tokens) - 1
        return self._tokens[position]

    def _advance(self) -> Token:
        token = self._peek()
        if token.kind != "eof":
            self._index += 1
        return token

    def _match_op(self, *values: str) -> Token | None:
        token = self._peek()
        if token.kind == "op" and token.value in values:
            return self._advance()
        return None

    def _make(self, node: Node) -> Node:
        self._node_count += 1
        if self._node_count > MAX_NODE_COUNT:
            raise ExpressionTooComplexError(
                f"表达式包含的运算过多（超过 {MAX_NODE_COUNT} 个节点）"
            )
        return node

    def _enter(self) -> None:
        self._depth += 1
        if self._depth > MAX_NESTING_DEPTH:
            raise ExpressionTooComplexError(
                f"括号或函数的嵌套层数不能超过 {MAX_NESTING_DEPTH} 层"
            )

    def _leave(self) -> None:
        self._depth -= 1

    def _expect_rparen(self) -> None:
        token = self._peek()
        if token.kind != "rparen":
            raise ExpressionSyntaxError("括号不匹配：缺少一个右括号 “)”")
        self._advance()

    # -- 文法产生式 -------------------------------------------------------
    def parse(self) -> Node:
        """解析入口：消耗全部 Token，任何一个多余字符都会被报错。"""
        if self._peek().kind == "eof":
            raise ExpressionSyntaxError("表达式为空，请输入算式")

        node = self._parse_expression()

        token = self._peek()
        if token.kind == "rparen":
            raise ExpressionSyntaxError("括号不匹配：多了一个右括号 “)”")
        if token.kind == "comma":
            raise ExpressionSyntaxError("逗号只能用于分隔函数参数，例如 round(3.14, 2)")
        if token.kind != "eof":
            raise ExpressionSyntaxError(
                f"表达式存在无法解析的部分：“{token.value}”（第 {token.pos + 1} 个字符附近）"
            )
        return node

    def _parse_expression(self) -> Node:
        """加减法层：左结合。"""
        node = self._parse_term()
        while True:
            token = self._match_op("+", "-")
            if token is None:
                return node
            right = self._parse_term_after_operator(token)
            node = self._make(BinaryNode(token.value, node, right))

    def _parse_term(self) -> Node:
        """乘除法/取模/隐式乘法层：左结合。"""
        node = self._parse_unary()
        while True:
            token = self._match_op("*", "/", "%")
            if token is not None:
                right = self._parse_unary_after_operator(token)
                node = self._make(BinaryNode(token.value, node, right))
                continue

            # 隐式乘法：2pi、3(4+5)、(1+2)(3+4)、2sin(1)
            # 刻意**不允许** "2 3" 这种两个裸数字相邻的写法，保持与主流计算器一致，
            # 避免用户输入 "12 8" 时被静默算成 96。
            following = self._peek()
            if following.kind in {"name", "lparen"}:
                right = self._parse_unary()
                node = self._make(BinaryNode("*", node, right))
                continue

            return node

    def _parse_unary(self) -> Node:
        """一元正负号层：前缀、右结合，因此 --5 合法且等于 5。"""
        token = self._match_op("+", "-")
        if token is None:
            return self._parse_power()
        operand = self._parse_unary()
        return self._make(UnaryNode(token.value, operand))

    def _parse_power(self) -> Node:
        """幂运算层：右结合，指数侧允许一元负号，故 2^-1 合法。"""
        base = self._parse_postfix()
        token = self._match_op("^")
        if token is None:
            return base
        exponent = self._parse_unary_after_operator(token)
        return self._make(BinaryNode("^", base, exponent))

    def _parse_postfix(self) -> Node:
        """后缀层：阶乘，可叠加（3! = 6，3!! = 720）。"""
        node = self._parse_primary()
        while self._match_op("!") is not None:
            node = self._make(FactorialNode(node))
        return node

    def _parse_primary(self) -> Node:
        """原子层：数值、常量、函数调用、括号表达式。"""
        token = self._advance()

        if token.kind == "number":
            try:
                return self._make(NumberNode(float(token.value)))
            except ValueError as exc:  # pragma: no cover - 词法层已保证格式
                raise ExpressionSyntaxError(f"无法识别的数字 “{token.value}”") from exc

        if token.kind == "name":
            return self._parse_name(token)

        if token.kind == "lparen":
            self._enter()
            if self._peek().kind == "rparen":
                raise ExpressionSyntaxError("括号内不能为空，例如 (1+2)")
            node = self._parse_expression()
            self._expect_rparen()
            self._leave()
            return node

        if token.kind == "eof":
            raise ExpressionSyntaxError("表达式不完整：末尾缺少操作数")

        if token.kind == "rparen":
            raise ExpressionSyntaxError("括号不匹配：多了一个右括号 “)”")

        raise ExpressionSyntaxError(
            f"运算符 “{token.value}” 的位置不正确（第 {token.pos + 1} 个字符附近）"
        )

    def _parse_name(self, token: Token) -> Node:
        """处理标识符：函数调用或常量。"""
        name = token.value.lower()

        # 函数调用：名字后面紧跟左括号
        if name in FUNCTIONS and self._peek().kind == "lparen":
            self._advance()  # 吃掉 "("
            self._enter()
            args: list[Node] = []
            if self._peek().kind != "rparen":
                args.append(self._parse_expression())
                while self._peek().kind == "comma":
                    self._advance()
                    args.append(self._parse_expression())
            self._expect_rparen()
            self._leave()

            spec = FUNCTIONS[name]
            if not spec.min_args <= len(args) <= spec.max_args:
                raise ExpressionSyntaxError(
                    f"函数 {name} 需要 {spec.arity_text}，实际传入了 {len(args)} 个"
                )
            return self._make(FunctionNode(name, args))

        if name in FUNCTIONS:
            raise ExpressionSyntaxError(
                f"函数 {name} 必须带括号调用，例如 {FUNCTIONS[name].example}"
            )

        if name in CONSTANTS:
            return self._make(NumberNode(CONSTANTS[name]))

        raise ExpressionSyntaxError(f"未知的名称 “{token.value}”，它不是内置常量或函数")

    # -- 带上下文的错误提示 ------------------------------------------------
    def _parse_term_after_operator(self, operator: Token) -> Node:
        if self._peek().kind == "eof":
            raise ExpressionSyntaxError(f"表达式不完整：运算符 “{operator.value}” 后面缺少操作数")
        return self._parse_term()

    def _parse_unary_after_operator(self, operator: Token) -> Node:
        if self._peek().kind == "eof":
            raise ExpressionSyntaxError(f"表达式不完整：运算符 “{operator.value}” 后面缺少操作数")
        return self._parse_unary()


def parse_expression(expression: str) -> Node:
    """对外入口：字符串 → AST。"""
    tokens = tokenize(expression)
    return ExpressionParser(tokens).parse()


def describe_ast(node: Node) -> dict[str, Any]:
    """把 AST 转成可 JSON 序列化的结构，同时统计节点数与深度。"""
    return {
        "tree": node.to_dict(),
        "infix": strip_outer_parentheses(node.to_infix()),
        "node_count": count_nodes(node),
        "max_depth": measure_depth(node),
    }


def strip_outer_parentheses(text: str) -> str:
    """去掉最外层多余括号，让 ``to_infix`` 的输出更易读。"""
    if text.startswith("(") and text.endswith(")"):
        depth = 0
        for index, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(text) - 1:
                    return text
        return text[1:-1]
    return text


def count_nodes(node: Node) -> int:
    """统计 AST 的节点总数。"""
    if isinstance(node, NumberNode):
        return 1
    if isinstance(node, UnaryNode):
        return 1 + count_nodes(node.operand)
    if isinstance(node, FactorialNode):
        return 1 + count_nodes(node.operand)
    if isinstance(node, BinaryNode):
        return 1 + count_nodes(node.left) + count_nodes(node.right)
    if isinstance(node, FunctionNode):
        return 1 + sum(count_nodes(arg) for arg in node.args)
    return 0  # pragma: no cover - 不可能到达


def measure_depth(node: Node) -> int:
    """统计 AST 的最大深度，用于展示"括号嵌套"的层次。"""
    if isinstance(node, NumberNode):
        return 1
    if isinstance(node, UnaryNode):
        return 1 + measure_depth(node.operand)
    if isinstance(node, FactorialNode):
        return 1 + measure_depth(node.operand)
    if isinstance(node, BinaryNode):
        return 1 + max(measure_depth(node.left), measure_depth(node.right))
    if isinstance(node, FunctionNode):
        return 1 + max((measure_depth(arg) for arg in node.args), default=0)
    return 0  # pragma: no cover - 不可能到达
