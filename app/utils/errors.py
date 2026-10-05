"""统一异常体系。

设计思路
--------
1. 所有业务异常都继承 :class:`CalculatorError`，并携带 ``http_status`` 与 ``error_code``，
   这样接口层只需要一个异常处理器就能把它们翻译成规范的 JSON 错误响应，
   控制器里不需要写重复的 try/except（见 ``app/main.py`` 的 ``calculator_error_handler``）。
2. 错误码是稳定的机器可读标识，前端可据此做差异化 UI 提示；
   ``message`` 是面向用户的中文提示，可以直接展示。
3. 表达式解析器与求值器只抛出本模块的异常，绝不向上抛出裸 ``ValueError``，
   避免把 Python 内部错误细节泄漏给客户端。
"""

from __future__ import annotations


class CalculatorError(Exception):
    """所有计算相关异常的基类。"""

    http_status = 400
    error_code = "CALCULATOR_ERROR"
    default_message = "计算失败"

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self) -> dict:
        payload = {"success": False, "error_code": self.error_code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class ExpressionSyntaxError(CalculatorError):
    """表达式语法错误：非法字符、括号不匹配、运算符缺失操作数等。"""

    error_code = "INVALID_EXPRESSION"
    default_message = "表达式非法，请检查后重试"


class ExpressionTooComplexError(CalculatorError):
    """表达式过于复杂（超长、嵌套过深、节点过多），属于防御性限制。"""

    error_code = "EXPRESSION_TOO_COMPLEX"
    default_message = "表达式过于复杂，请简化后重试"


class DivisionByZeroError(CalculatorError):
    """除数为 0（含取模、0 的负数次幂）。"""

    error_code = "DIVISION_BY_ZERO"
    default_message = "除数不能为 0"


class MathDomainError(CalculatorError):
    """数学定义域错误：负数开平方、非正数取对数、tan(π/2) 等。"""

    error_code = "MATH_DOMAIN_ERROR"
    default_message = "该运算在实数范围内无意义"


class NumericOverflowError(CalculatorError):
    """结果溢出（超出双精度浮点可表示范围）。"""

    error_code = "NUMERIC_OVERFLOW"
    default_message = "计算结果超出可表示范围"


class ResourceNotFoundError(CalculatorError):
    """请求的资源不存在。"""

    http_status = 404
    error_code = "NOT_FOUND"
    default_message = "资源不存在"


class ConversionError(CalculatorError):
    """进制 / 单位换算参数错误。"""

    error_code = "CONVERSION_ERROR"
    default_message = "换算参数错误"
