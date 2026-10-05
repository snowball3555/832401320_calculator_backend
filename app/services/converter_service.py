"""单位换算服务（扩展功能）。

设计要点：**每个类别只定义"相对基准单位的系数"**，任意两个单位之间的换算都由
``value * from_factor / to_factor`` 推导出来。这样新增单位只需要在表里加一行，
不需要为 N 个单位写 N² 个换算式。

温度是个例外：摄氏/华氏/开尔文之间是**仿射变换**（有偏移量）而不是纯比例，
因此单独用一对 ``to_celsius`` / ``from_celsius`` 函数处理。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.calculator_service import normalize_number
from app.utils.errors import ConversionError


@dataclass(frozen=True, slots=True)
class UnitDef:
    """一个单位的定义。"""

    code: str
    name: str
    factor: float = 1.0  # 相对基准单位的系数


@dataclass(frozen=True, slots=True)
class UnitCategory:
    """一类单位。"""

    key: str
    name: str
    base_unit: str
    units: dict[str, UnitDef]
    to_base: Callable[[float], float] | None = None
    from_base: Callable[[float], float] | None = None

    def unit(self, code: str) -> UnitDef:
        unit = self.units.get(code)
        if unit is None:
            available = "、".join(self.units)
            raise ConversionError(f"「{self.name}」不支持单位 “{code}”，可选：{available}")
        return unit


def _u(code: str, name: str, factor: float = 1.0) -> UnitDef:
    return UnitDef(code, name, factor)


CATEGORIES: dict[str, UnitCategory] = {
    "length": UnitCategory(
        "length", "长度", "m",
        {
            "mm": _u("mm", "毫米", 0.001),
            "cm": _u("cm", "厘米", 0.01),
            "dm": _u("dm", "分米", 0.1),
            "m": _u("m", "米", 1.0),
            "km": _u("km", "千米", 1000.0),
            "in": _u("in", "英寸", 0.0254),
            "ft": _u("ft", "英尺", 0.3048),
            "yd": _u("yd", "码", 0.9144),
            "mi": _u("mi", "英里", 1609.344),
            "nmi": _u("nmi", "海里", 1852.0),
        },
    ),
    "mass": UnitCategory(
        "mass", "质量", "kg",
        {
            "mg": _u("mg", "毫克", 1e-6),
            "g": _u("g", "克", 0.001),
            "kg": _u("kg", "千克", 1.0),
            "t": _u("t", "吨", 1000.0),
            "oz": _u("oz", "盎司", 0.028349523125),
            "lb": _u("lb", "磅", 0.45359237),
            "jin": _u("jin", "斤", 0.5),
        },
    ),
    "area": UnitCategory(
        "area", "面积", "m2",
        {
            "cm2": _u("cm2", "平方厘米", 0.0001),
            "m2": _u("m2", "平方米", 1.0),
            "km2": _u("km2", "平方千米", 1e6),
            "ha": _u("ha", "公顷", 10000.0),
            "mu": _u("mu", "亩", 666.6666666666666),
            "ft2": _u("ft2", "平方英尺", 0.09290304),
            "acre": _u("acre", "英亩", 4046.8564224),
        },
    ),
    "volume": UnitCategory(
        "volume", "体积", "L",
        {
            "ml": _u("ml", "毫升", 0.001),
            "L": _u("L", "升", 1.0),
            "m3": _u("m3", "立方米", 1000.0),
            "gal": _u("gal", "美制加仑", 3.785411784),
            "qt": _u("qt", "美制夸脱", 0.946352946),
            "floz": _u("floz", "美制液体盎司", 0.0295735295625),
        },
    ),
    "time": UnitCategory(
        "time", "时间", "s",
        {
            "ms": _u("ms", "毫秒", 0.001),
            "s": _u("s", "秒", 1.0),
            "min": _u("min", "分钟", 60.0),
            "h": _u("h", "小时", 3600.0),
            "day": _u("day", "天", 86400.0),
            "week": _u("week", "周", 604800.0),
        },
    ),
    "speed": UnitCategory(
        "speed", "速度", "m/s",
        {
            "m/s": _u("m/s", "米每秒", 1.0),
            "km/h": _u("km/h", "千米每小时", 1 / 3.6),
            "mph": _u("mph", "英里每小时", 0.44704),
            "knot": _u("knot", "节", 0.5144444444444445),
        },
    ),
    "data": UnitCategory(
        "data", "数据存储", "B",
        {
            "bit": _u("bit", "比特", 0.125),
            "B": _u("B", "字节", 1.0),
            "KB": _u("KB", "千字节", 1024.0),
            "MB": _u("MB", "兆字节", 1024.0**2),
            "GB": _u("GB", "吉字节", 1024.0**3),
            "TB": _u("TB", "太字节", 1024.0**4),
        },
    ),
    "temperature": UnitCategory(
        "temperature", "温度", "degC",
        {
            "degC": _u("degC", "摄氏度"),
            "degF": _u("degF", "华氏度"),
            "K": _u("K", "开尔文"),
        },
        to_base=lambda value: value,  # 占位，实际逻辑在 _to_celsius / _from_celsius
        from_base=lambda value: value,
    ),
}


# ---------------------------------------------------------------------------
# 温度换算
# ---------------------------------------------------------------------------
def _temperature_to_celsius(value: float, unit: str) -> float:
    if unit == "degC":
        return value
    if unit == "degF":
        return (value - 32.0) * 5.0 / 9.0
    if unit == "K":
        if value < 0:
            raise ConversionError("开尔文温度不能小于 0")
        return value - 273.15
    raise ConversionError(f"不支持的温度单位 “{unit}”")


def _celsius_to_temperature(value: float, unit: str) -> float:
    if unit == "degC":
        return value
    if unit == "degF":
        return value * 9.0 / 5.0 + 32.0
    if unit == "K":
        if value < -273.15:
            raise ConversionError("换算结果低于绝对零度")
        return value + 273.15
    raise ConversionError(f"不支持的温度单位 “{unit}”")


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------
def convert_unit(value: float, category: str, from_unit: str, to_unit: str) -> dict:
    """单位换算。"""
    spec = CATEGORIES.get(category)
    if spec is None:
        available = "、".join(f"{key}({item.name})" for key, item in CATEGORIES.items())
        raise ConversionError(f"不支持的单位类别 “{category}”，可选：{available}")

    source = spec.unit(from_unit)
    target = spec.unit(to_unit)

    if category == "temperature":
        celsius = _temperature_to_celsius(value, from_unit)
        result = _celsius_to_temperature(celsius, to_unit)
        formula = (
            f"{value:g} {source.name} → {celsius:.12g} 摄氏度 → {result:.12g} {target.name}"
            "（温度换算含偏移量，不能按比例直接相乘）"
        )
    else:
        base_value = value * source.factor
        result = base_value / target.factor
        formula = (
            f"{value:g} {source.name} × {source.factor:g} = {base_value:g} {spec.base_unit}"
            f"；÷ {target.factor:g} = {result:.12g} {target.name}"
        )

    normalized, display = normalize_number(result)

    return {
        "value": value,
        "category": category,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "from_name": source.name,
        "to_name": target.name,
        "result": normalized,
        "result_display": display,
        "formula": formula,
    }


def describe_categories() -> list[dict]:
    """给 ``/api/meta/functions`` 用的单位类别清单。"""
    return [
        {
            "key": spec.key,
            "name": spec.name,
            "base_unit": spec.base_unit,
            "units": [
                {"code": unit.code, "name": unit.name} for unit in spec.units.values()
            ],
        }
        for spec in CATEGORIES.values()
    ]
