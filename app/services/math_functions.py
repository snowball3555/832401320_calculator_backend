"""数学常量与函数白名单。

为什么不直接用 ``eval``？
------------------------
``eval("__import__('os').system('...')")`` 会真的执行系统命令，是典型的远程代码执行漏洞。
本模块把所有允许的运算收敛成一张**显式白名单表**：只有表里出现过的名字才会被求值，
其余名字一律在解析阶段报"未知的名称"。这样即使表达式里塞进 Python 代码，也只会得到语法错误。

每个函数都带有元数据（参数个数、说明、示例），一方面供解析器做参数校验，
另一方面通过 ``GET /api/meta/functions`` 暴露给前端，让前端可以动态渲染科学计算面板，
避免前后端各写一份函数列表导致不一致。
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 常量白名单
# ---------------------------------------------------------------------------
CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "phi": (1 + math.sqrt(5)) / 2,  # 黄金分割比
}

# 常量别名：sin(pi) 与 sin(π) 等价（词法阶段已把 π 归一化为 pi，这里再兜一层）
CONSTANTS["π"] = math.pi


# ---------------------------------------------------------------------------
# 需要额外做定义域判断的函数（直接调用标准库会抛出难以理解的英文报错）
# ---------------------------------------------------------------------------
_TAN_GUARD_EPSILON = 1e-12
_FACTORIAL_MAX = 170  # 170! 已接近双精度浮点上限（约 7.26e306）


def _tan(x: float) -> float:
    """正切函数；cos(x)≈0 时按"该点无定义"处理，而不是返回 1.6e16 这种误导性数值。"""
    if abs(math.cos(x)) < _TAN_GUARD_EPSILON:
        raise ValueError("tan 在该角度处无定义（cos 为 0）")
    return math.tan(x)


def _factorial(x: float) -> float:
    """阶乘：仅接受 0~170 的整数。"""
    if x != int(x):
        raise ValueError("阶乘只能作用于整数")
    n = int(x)
    if n < 0:
        raise ValueError("负数没有阶乘")
    if n > _FACTORIAL_MAX:
        raise ValueError(f"阶乘参数不能大于 {_FACTORIAL_MAX}")
    return float(math.factorial(n))


def _cbrt(x: float) -> float:
    """立方根：负数也有实立方根，需要保留符号。"""
    return math.copysign(abs(x) ** (1 / 3), x)


def _log(x: float, base: float | None = None) -> float:
    """对数：单参数按计算器惯例表示常用对数（以 10 为底），双参数可指定底数。"""
    if x <= 0:
        raise ValueError("对数的真数必须大于 0")
    if base is None:
        return math.log10(x)
    if base <= 0:
        raise ValueError("对数的底数必须大于 0")
    if base == 1:
        raise ValueError("对数的底数不能为 1")
    return math.log(x, base)


def _mod(left: float, right: float) -> float:
    """取模：采用 C 语言语义（结果符号跟随被除数），与 math.fmod 一致。"""
    if right == 0:
        raise ZeroDivisionError("取模运算的除数不能为 0")
    return math.fmod(left, right)


def _sign(x: float) -> float:
    return 0.0 if x == 0 else math.copysign(1.0, x)


def _round(x: float, digits: float | None = None) -> float:
    """四舍五入；位数参数由表达式传入的是浮点，需要转成整数再交给内置 round。"""
    if digits is None:
        return float(round(x))
    if digits != int(digits):
        raise ValueError("四舍五入的位数必须是整数")
    return float(round(x, int(digits)))


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    """一个白名单函数的元数据。"""

    name: str
    func: Callable[..., float]
    min_args: int
    max_args: int
    description: str
    example: str
    category: str = "scientific"

    @property
    def arity_text(self) -> str:
        if self.min_args == self.max_args:
            return f"{self.min_args} 个参数"
        if self.max_args >= 99:
            return f"至少 {self.min_args} 个参数"
        return f"{self.min_args}~{self.max_args} 个参数"


def _spec(name, func, lo, hi, description, example, category="scientific") -> FunctionSpec:
    return FunctionSpec(name, func, lo, hi, description, example, category)


FUNCTIONS: dict[str, FunctionSpec] = {
    spec.name: spec
    for spec in (
        # 三角函数
        _spec("sin", math.sin, 1, 1, "正弦（弧度）", "sin(pi/2)=1"),
        _spec("cos", math.cos, 1, 1, "余弦（弧度）", "cos(0)=1"),
        _spec("tan", _tan, 1, 1, "正切（弧度）", "tan(pi/4)=1"),
        _spec("asin", math.asin, 1, 1, "反正弦，参数需在 [-1,1]", "asin(1)=pi/2"),
        _spec("acos", math.acos, 1, 1, "反余弦，参数需在 [-1,1]", "acos(1)=0"),
        _spec("atan", math.atan, 1, 1, "反正切", "atan(1)=pi/4"),
        _spec("sinh", math.sinh, 1, 1, "双曲正弦", "sinh(1)≈1.1752"),
        _spec("cosh", math.cosh, 1, 1, "双曲余弦", "cosh(1)≈1.5431"),
        _spec("tanh", math.tanh, 1, 1, "双曲正切", "tanh(1)≈0.7616"),
        _spec("deg", math.degrees, 1, 1, "弧度转角度", "deg(pi)=180"),
        _spec("rad", math.radians, 1, 1, "角度转弧度", "rad(180)=pi"),
        # 幂与根
        _spec("sqrt", math.sqrt, 1, 1, "平方根，参数需 ≥0", "sqrt(16)=4"),
        _spec("cbrt", _cbrt, 1, 1, "立方根，支持负数", "cbrt(-8)=-2"),
        _spec("exp", math.exp, 1, 1, "自然指数 e^x", "exp(1)=e"),
        _spec("pow", math.pow, 2, 2, "幂运算，等价于 ^", "pow(2,10)=1024"),
        _spec("hypot", math.hypot, 2, 99, "欧几里得范数", "hypot(3,4)=5"),
        # 对数
        _spec("ln", math.log, 1, 1, "自然对数", "ln(e)=1"),
        _spec("log", _log, 1, 2, "常用对数；双参数可指定底数", "log(100)=2、log(8,2)=3"),
        _spec("log10", math.log10, 1, 1, "以 10 为底的对数", "log10(1000)=3"),
        _spec("log2", math.log2, 1, 1, "以 2 为底的对数", "log2(8)=3"),
        # 取整与符号
        _spec("abs", abs, 1, 1, "绝对值", "abs(-3)=3"),
        _spec("floor", math.floor, 1, 1, "向下取整", "floor(2.9)=2"),
        _spec("ceil", math.ceil, 1, 1, "向上取整", "ceil(2.1)=3"),
        _spec("round", _round, 1, 2, "四舍五入，可指定小数位", "round(3.14159,2)=3.14"),
        _spec("sign", _sign, 1, 1, "符号函数", "sign(-5)=-1"),
        _spec("factorial", _factorial, 1, 1, "阶乘，参数为 0~170 的整数", "factorial(5)=120"),
        # 统计
        _spec("max", max, 1, 99, "最大值", "max(1,9,4)=9"),
        _spec("min", min, 1, 99, "最小值", "min(1,9,4)=1"),
        _spec("mod", _mod, 2, 2, "取模，等价于 %", "mod(10,3)=1"),
    )
}


def describe_functions() -> list[dict]:
    """供 ``/api/meta/functions`` 使用的函数清单。"""
    return [
        {
            "name": spec.name,
            "arity": spec.arity_text,
            "min_args": spec.min_args,
            "max_args": spec.max_args,
            "description": spec.description,
            "example": spec.example,
            "category": spec.category,
        }
        for spec in sorted(FUNCTIONS.values(), key=lambda item: item.name)
    ]


def describe_constants() -> list[dict]:
    """供 ``/api/meta/functions`` 使用的常量清单。"""
    return [
        {"name": "pi", "value": math.pi, "description": "圆周率 π"},
        {"name": "e", "value": math.e, "description": "自然常数 e"},
        {"name": "tau", "value": math.tau, "description": "2π"},
        {"name": "phi", "value": CONSTANTS["phi"], "description": "黄金分割比"},
    ]
