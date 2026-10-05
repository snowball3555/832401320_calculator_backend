"""进制转换服务（扩展功能）。

实现方式：**手工按位权展开 / 短除法**，不借助 ``int(text, base)`` 之外的任何"魔法"，
也不使用 ``eval``。

* 十进制方向：按位权累加 ``value = value * from_base + digit``；
* 输出方向：整数部分用短除法取余，小数部分用"乘基取整"逐位生成。

小数部分是进制转换的经典坑：``0.1`` 在二进制下是无限循环小数，
所以这里限制最多输出 16 位小数，并明确告知用户"已按精度截断"。
"""

from __future__ import annotations

from app.utils.errors import ConversionError

DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
SUPPORTED_BASES = list(range(2, 37))
MAX_FRACTION_DIGITS = 16


def _digit_value(char: str) -> int:
    value = DIGITS.find(char.lower())
    if value < 0:
        raise ConversionError(f"无法识别的数字字符 “{char}”")
    return value


def _render_integer(value: int, base: int) -> str:
    if value == 0:
        return "0"
    digits: list[str] = []
    while value > 0:
        value, remainder = divmod(value, base)
        digits.append(DIGITS[remainder])
    return "".join(reversed(digits))


def _render_fraction(fraction: float, base: int, max_digits: int = MAX_FRACTION_DIGITS) -> tuple[str, bool]:
    """把小数部分转换成目标进制，返回 (文本, 是否被截断)。"""
    if fraction == 0:
        return "", False

    digits: list[str] = []
    truncated = False
    for _ in range(max_digits):
        fraction *= base
        digit = int(fraction)
        # 浮点误差兜底：例如 0.9999999999 应进位为 1
        if digit >= base:
            digit = base - 1
        digits.append(DIGITS[digit])
        fraction -= digit
        # 阈值取 1e-12 而不是 1e-15：残余量若 ≤1e-12，则下一轮的 digit = int(base × 残余)
        # 对任何 base ≤ 36 都必然为 0，也就是说这些位本来就无意义（尾随 0 也会被裁掉）。
        # 只有把阈值放宽到 1e-12，才能把上游浮点噪声（约 1e-16 相对误差）挡在输出之外。
        if fraction <= 1e-12:
            fraction = 0.0
            break
    else:
        truncated = fraction > 0

    while digits and digits[-1] == "0":
        digits.pop()
    return "".join(digits), truncated


def convert_base(value: str, from_base: int, to_base: int) -> dict:
    """把 ``value`` 从 ``from_base`` 进制转换到 ``to_base`` 进制。"""
    if not 2 <= from_base <= 36:
        raise ConversionError(f"源进制必须在 2~36 之间，当前为 {from_base}")
    if not 2 <= to_base <= 36:
        raise ConversionError(f"目标进制必须在 2~36 之间，当前为 {to_base}")

    text = str(value).strip().lower().replace(" ", "").replace("_", "")
    if not text:
        raise ConversionError("待转换的数值不能为空")

    sign = ""
    if text[0] in "+-":
        sign = "-" if text[0] == "-" else ""
        text = text[1:]

    if text.count(".") > 1:
        raise ConversionError("数值中最多只能有一个小数点")

    integer_text, _, fraction_text = text.partition(".")
    if not integer_text and not fraction_text:
        raise ConversionError("待转换的数值不合法")

    # 按位权展开成十进制（整数部分用整数运算，避免精度损失）
    integer_value = 0
    for char in integer_text:
        digit = _digit_value(char)
        if digit >= from_base:
            raise ConversionError(f"数字 “{char}” 不属于 {from_base} 进制")
        integer_value = integer_value * from_base + digit

    # 小数部分：先把各位拼成一个整数（精确），最后只做**一次**除法。
    # 早期写法是逐位 `fraction += digit * scale; scale /= base`，会把每一步的浮点误差累积起来
    # —— 实测 `0.75` 会变成 0.7500000000000001，转成 16 进制后多出一串垃圾数字
    # （`0.c0000000000008`）。改成"整数分子 ÷ 基的幂"后，0.75 能得到精确的 0.75。
    fraction_numerator = 0
    for char in fraction_text:
        digit = _digit_value(char)
        if digit >= from_base:
            raise ConversionError(f"数字 “{char}” 不属于 {from_base} 进制")
        fraction_numerator = fraction_numerator * from_base + digit
    fraction_value = fraction_numerator / (from_base ** len(fraction_text)) if fraction_text else 0.0

    # 输出到目标进制
    rendered_integer = _render_integer(integer_value, to_base)
    rendered_fraction, truncated = _render_fraction(fraction_value, to_base)

    result = f"{sign}{rendered_integer}"
    if rendered_fraction:
        result += f".{rendered_fraction}"

    decimal_value = sign + str(integer_value)
    if fraction_value:
        decimal_value += f"{fraction_value:.12g}"[1:]

    return {
        "value": value,
        "from_base": from_base,
        "to_base": to_base,
        "result": result,
        "decimal_value": decimal_value,
        "fraction_truncated": truncated,
        "note": (
            f"小数部分最多保留 {MAX_FRACTION_DIGITS} 位，已按精度截断"
            if truncated
            else "转换结果精确"
        ),
    }
