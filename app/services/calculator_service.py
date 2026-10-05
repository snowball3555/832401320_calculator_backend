"""计算服务：AST 求值 + 结果规范化。

职责边界
--------
* :mod:`app.services.expression_lexer` —— 只做词法切分
* :mod:`app.services.expression_parser` —— 只做语法分析（字符串 → AST）
* 本模块 —— 只做求值与数值规范化（AST → 结果）

三者拆开的最大好处是**可测试**：语法错误和数值错误可以分别用单元测试覆盖，
而不是在一大坨函数里靠 if/else 混着判断。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from app.services.expression_parser import (
    BinaryNode,
    FactorialNode,
    FunctionNode,
    Node,
    NumberNode,
    UnaryNode,
    count_nodes,
    describe_ast,
    measure_depth,
    parse_expression,
)
from app.services.math_functions import FUNCTIONS
from app.utils.errors import (
    CalculatorError,
    DivisionByZeroError,
    ExpressionSyntaxError,
    MathDomainError,
    NumericOverflowError,
)

# 双精度浮点的十进制指数上限（约 1e308）
_MAX_DECIMAL_EXPONENT = 308.0


@dataclass(slots=True)
class CalculationResult:
    """一次成功计算的完整结果。"""

    raw_expression: str
    """用户原样输入的表达式。"""

    expression: str
    """规范化后的表达式（× → *、全角符号 → 半角），历史记录中保存这一份。"""

    result: int | float
    """数值结果；能整除时返回整数，避免出现 ``20.0`` 这种多余的小数点。"""

    result_display: str
    """给人看的字符串形式。"""

    node_count: int
    max_depth: int
    elapsed_ms: float

    def to_dict(self) -> dict:
        return {
            "expression": self.expression,
            "raw_expression": self.raw_expression,
            "result": self.result,
            "result_display": self.result_display,
            "node_count": self.node_count,
            "max_depth": self.max_depth,
            "elapsed_ms": self.elapsed_ms,
        }


# ---------------------------------------------------------------------------
# 结果规范化
# ---------------------------------------------------------------------------
def normalize_number(value: float) -> tuple[int | float, str]:
    """把浮点结果整理成"人看起来舒服"的形式。

    浮点误差是绕不开的：``0.1 + 0.2`` 在 IEEE-754 下等于 ``0.30000000000000004``。
    计算器不能把这个值直接丢给用户，所以这里统一按 **12 位有效数字**收敛后再输出，
    同时如果结果在误差范围内是整数，就返回 ``int``，让前端显示 ``20`` 而不是 ``20.0``。
    """
    if isinstance(value, bool):  # pragma: no cover - 防御性
        value = float(value)
    value = float(value)

    if not math.isfinite(value):
        raise NumericOverflowError("计算结果不是有限数值（可能溢出或未定义）")

    if value == 0:
        return 0, "0"

    rounded = float(f"{value:.12g}")

    if abs(rounded) < 1e16 and abs(rounded - round(rounded)) < 1e-9:
        integer = int(round(rounded))
        return integer, str(integer)

    return rounded, f"{rounded:.12g}"


# ---------------------------------------------------------------------------
# 求值
# ---------------------------------------------------------------------------
def _power(base: float, exponent: float) -> float:
    """幂运算，带完整的安全护栏。

    需要挡住的几类输入：

    * ``0^-1`` —— 等价于除以 0；
    * ``(-8)^0.5`` —— 实数范围内无意义；
    * ``9^9^9`` —— 数值爆炸，若不预判会把 CPU 卡死（这里先做对数估算再决定是否计算）。
    """
    if base == 0 and exponent < 0:
        raise DivisionByZeroError("0 不能作为负指数幂的底数（等价于除以 0）")

    if base < 0 and not float(exponent).is_integer():
        raise MathDomainError("负数在实数范围内不能开非整数次方")

    if exponent != 0 and abs(base) not in (0.0, 1.0):
        estimated_exponent = abs(exponent) * math.log10(abs(base))
        if estimated_exponent > _MAX_DECIMAL_EXPONENT:
            raise NumericOverflowError(
                "幂运算结果超出可表示范围"
                f"（{base} 的 {exponent} 次方约等于 10 的 {estimated_exponent:.0f} 次方）"
            )

    try:
        return math.pow(base, exponent)
    except OverflowError as exc:
        raise NumericOverflowError("幂运算结果超出可表示范围") from exc
    except ValueError as exc:
        raise MathDomainError("幂运算在实数范围内无意义") from exc


def _apply_binary(operator: str, left: float, right: float) -> float:
    """执行一个二元运算。"""
    if operator == "+":
        result = left + right
    elif operator == "-":
        result = left - right
    elif operator == "*":
        result = left * right
    elif operator == "/":
        if right == 0:
            raise DivisionByZeroError("除数不能为 0")
        result = left / right
    elif operator == "%":
        if right == 0:
            raise DivisionByZeroError("取模运算的除数不能为 0")
        result = math.fmod(left, right)
    elif operator == "^":
        return _power(left, right)
    else:  # pragma: no cover - 解析器不会产出未知运算符
        raise ExpressionSyntaxError(f"不支持的运算符 “{operator}”")

    if not math.isfinite(result):
        raise NumericOverflowError("计算结果超出可表示范围")
    return result


def _call_function(name: str, args: list[float]) -> float:
    """按白名单调用函数，并把标准库异常翻译成本项目的业务异常。"""
    spec = FUNCTIONS.get(name)
    if spec is None:  # pragma: no cover - 解析阶段已校验
        raise ExpressionSyntaxError(f"未知的函数 “{name}”")

    if not spec.min_args <= len(args) <= spec.max_args:
        raise ExpressionSyntaxError(
            f"函数 {name} 需要 {spec.arity_text}，实际传入了 {len(args)} 个"
        )

    try:
        value = spec.func(*args)
    except ZeroDivisionError as exc:
        raise DivisionByZeroError(str(exc) or f"{name} 运算中出现除以 0") from exc
    except OverflowError as exc:
        raise NumericOverflowError(f"{name} 的结果超出可表示范围") from exc
    except ValueError as exc:
        # 标准库只会给出 "math domain error" 这类英文提示，对用户没有意义；
        # 只有在函数自己给出了中文说明（例如阶乘越界）时才沿用原话。
        text = str(exc).strip()
        if not text or text.lower() in {"math domain error", "math range error"}:
            text = f"函数 {name} 的参数超出定义域（{spec.description}）"
        raise MathDomainError(text) from exc
    except TypeError as exc:  # pragma: no cover - 防御性
        raise ExpressionSyntaxError(f"{name} 的参数类型不正确：{exc}") from exc

    return float(value)


def evaluate(node: Node) -> float:
    """递归求值 AST。"""
    if isinstance(node, NumberNode):
        return node.value

    if isinstance(node, UnaryNode):
        value = evaluate(node.operand)
        return value if node.op == "+" else -value

    if isinstance(node, FactorialNode):
        return _call_function("factorial", [evaluate(node.operand)])

    if isinstance(node, BinaryNode):
        left = evaluate(node.left)
        right = evaluate(node.right)
        return _apply_binary(node.op, left, right)

    if isinstance(node, FunctionNode):
        args = [evaluate(arg) for arg in node.args]
        # pow / mod 与 ^ / % 语义一致，统一走二元运算以复用除零与溢出保护
        if node.name == "pow":
            return _apply_binary("^", args[0], args[1])
        if node.name == "mod":
            return _apply_binary("%", args[0], args[1])
        return _call_function(node.name, args)

    raise CalculatorError("无法识别的表达式结构")  # pragma: no cover - 防御性


# ---------------------------------------------------------------------------
# 对外 API
# ---------------------------------------------------------------------------
def calculate(expression: str) -> CalculationResult:
    """计算表达式并返回结构化结果（失败时抛出 :class:`CalculatorError` 子类）。"""
    if expression is None or not str(expression).strip():
        raise ExpressionSyntaxError("表达式为空，请输入算式")

    raw = str(expression)
    started = time.perf_counter()

    ast = parse_expression(raw)
    value = evaluate(ast)
    result, display = normalize_number(value)

    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    from app.services.expression_lexer import normalize_expression  # 局部导入避免循环依赖

    return CalculationResult(
        raw_expression=raw,
        expression=normalize_expression(raw).strip(),
        result=result,
        result_display=display,
        node_count=count_nodes(ast),
        max_depth=measure_depth(ast),
        elapsed_ms=elapsed_ms,
    )


def inspect(expression: str) -> dict:
    """只做语法分析、不计算：给 ``POST /api/parse`` 用来展示 AST 与词法结果。"""
    from app.services.expression_lexer import normalize_expression, tokenize

    if expression is None or not str(expression).strip():
        raise ExpressionSyntaxError("表达式为空，请输入算式")

    raw = str(expression)
    tokens = tokenize(raw)
    ast = parse_expression(raw)

    payload = describe_ast(ast)
    payload["raw_expression"] = raw
    payload["expression"] = normalize_expression(raw).strip()
    payload["tokens"] = [
        {"kind": token.kind, "value": token.value, "pos": token.pos}
        for token in tokens
        if token.kind != "eof"
    ]
    return payload
