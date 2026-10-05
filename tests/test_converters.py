"""进制转换 / 单位换算 / 函数白名单的单元测试。

补这组测试的原因很直接：用 `pytest --cov` 量过一次，`base_converter.py` 只有 **61%**
（错误分支几乎没走到）、`converter_service.py` 77%、`math_functions.py` 82%。
扩展功能既然在博客里声称"可用"，就必须把边界与异常路径也测到，而不是只测顺路走通的那几条。

覆盖重点：
* 进制：符号、小数（精确 vs 无限循环被截断）、空格/下划线分隔、大小写、各种非法输入
* 单位：温度三种温标互转 + 绝对零度边界、未知类别/未知单位、同单位恒等
* 函数白名单：元数据结构、参数个数描述、以及每个自定义包装函数的异常分支
"""

from __future__ import annotations

import math

import pytest

from app.services.base_converter import convert_base
from app.services.converter_service import CATEGORIES, convert_unit, describe_categories
from app.services.math_functions import (
    CONSTANTS,
    FUNCTIONS,
    _cbrt,
    _factorial,
    _log,
    _mod,
    _round,
    _sign,
    _tan,
    describe_constants,
    describe_functions,
)
from app.utils.errors import ConversionError


class TestBaseConverterIntegers:
    @pytest.mark.parametrize(
        ("value", "from_base", "to_base", "expected"),
        [
            ("255", 10, 16, "ff"),
            ("255", 10, 2, "11111111"),
            ("ff", 16, 10, "255"),
            ("FF", 16, 10, "255"),          # 大写输入也要认
            ("11111111", 2, 16, "ff"),
            ("777", 8, 10, "511"),
            ("zz", 36, 10, "1295"),          # 36 进制的上界
            ("0", 10, 2, "0"),               # 0 的渲染分支
            ("000255", 10, 10, "255"),       # 前导零
            ("1 000", 10, 10, "1000"),       # 空格分隔
            ("1_000", 10, 10, "1000"),       # 下划线分隔
            ("+1010", 2, 10, "10"),          # 显式正号
            ("-1010", 2, 10, "-10"),         # 负号
            ("-ff", 16, 2, "-11111111"),
        ],
    )
    def test_integer_conversions(self, value, from_base, to_base, expected):
        assert convert_base(value, from_base, to_base)["result"] == expected

    def test_decimal_value_is_reported(self):
        payload = convert_base("ff", 16, 2)
        assert payload["decimal_value"] == "255"
        assert payload["note"] == "转换结果精确"
        assert payload["fraction_truncated"] is False

    def test_same_base_returns_input(self):
        assert convert_base("123", 8, 8)["result"] == "123"


class TestBaseConverterFractions:
    @pytest.mark.parametrize(
        ("value", "from_base", "to_base", "expected"),
        [
            ("0.5", 10, 2, "0.1"),           # 0.5 = 0.1₂（精确）
            ("0.25", 10, 2, "0.01"),         # 0.25 = 0.01₂（精确）
            ("1010.101", 2, 10, "10.625"),
            (".5", 10, 2, "0.1"),            # 省略整数部分
            ("10.5", 10, 2, "1010.1"),
            ("0.75", 10, 16, "0.c"),         # 0.75 = 0.c₁₆
        ],
    )
    def test_exact_fractions(self, value, from_base, to_base, expected):
        payload = convert_base(value, from_base, to_base)
        assert payload["result"] == expected
        assert payload["fraction_truncated"] is False

    def test_repeating_fraction_is_truncated_with_hint(self):
        """0.1 在二进制下是无限循环小数，必须截断并明确告知用户。"""
        payload = convert_base("0.1", 10, 2)
        assert payload["result"].startswith("0.0001100110011")
        assert payload["fraction_truncated"] is True
        assert "截断" in payload["note"]

    def test_trailing_zero_digits_are_trimmed(self):
        # 0.50 的二进制是 0.1，不应输出 0.10
        assert convert_base("0.50", 10, 2)["result"] == "0.1"


class TestBaseConverterErrors:
    @pytest.mark.parametrize("from_base", [1, 0, -2, 37, 100])
    def test_source_base_out_of_range(self, from_base):
        with pytest.raises(ConversionError) as excinfo:
            convert_base("10", from_base, 10)
        assert "源进制" in excinfo.value.message

    @pytest.mark.parametrize("to_base", [1, 0, -5, 37])
    def test_target_base_out_of_range(self, to_base):
        with pytest.raises(ConversionError) as excinfo:
            convert_base("10", 10, to_base)
        assert "目标进制" in excinfo.value.message

    @pytest.mark.parametrize("value", ["", "   ", "_", "-", "+", "."])
    def test_empty_or_sign_only_values(self, value):
        with pytest.raises(ConversionError):
            convert_base(value, 10, 2)

    def test_multiple_dots_rejected(self):
        with pytest.raises(ConversionError) as excinfo:
            convert_base("1.2.3", 10, 2)
        assert "小数点" in excinfo.value.message

    @pytest.mark.parametrize("value", ["2", "9", "a"])
    def test_digit_not_in_source_base(self, value):
        with pytest.raises(ConversionError) as excinfo:
            convert_base(value, 2, 10)
        assert "不属于" in excinfo.value.message or "无法识别" in excinfo.value.message

    def test_illegal_character_rejected(self):
        with pytest.raises(ConversionError) as excinfo:
            convert_base("12$", 10, 2)
        assert "无法识别" in excinfo.value.message

    @pytest.mark.parametrize("value", ["z", "!", "中"])
    def test_characters_not_valid_in_the_source_base(self, value):
        # z 在 36 进制里合法，但在 16 进制里越界；! 与中文则根本不是进制字符
        with pytest.raises(ConversionError):
            convert_base(value, 16, 10)


class TestUnitConverter:
    @pytest.mark.parametrize(
        ("category", "from_unit", "to_unit", "value", "expected"),
        [
            ("length", "m", "m", 5, 5),                       # 同单位恒等
            ("length", "mi", "m", 1, 1609.344),
            ("mass", "lb", "kg", 1, 0.45359237),
            ("mass", "jin", "g", 1, 500),
            ("area", "ha", "m2", 1, 10000),
            ("volume", "L", "ml", 1, 1000),
            ("time", "day", "h", 1, 24),
            ("speed", "km/h", "m/s", 36, 10),
            ("speed", "knot", "m/s", 1, 0.5144444444444445),
            ("data", "MB", "KB", 1, 1024),
            ("data", "bit", "B", 8, 1),
        ],
    )
    def test_proportional_conversions(self, category, from_unit, to_unit, value, expected):
        payload = convert_unit(value, category, from_unit, to_unit)
        assert payload["result"] == pytest.approx(expected)
        assert payload["formula"]

    @pytest.mark.parametrize(
        ("from_unit", "to_unit", "value", "expected"),
        [
            ("degC", "degF", 100, 212),
            ("degF", "degC", 32, 0),
            ("degC", "K", 0, 273.15),
            ("K", "degC", 0, -273.15),
            ("degF", "K", 32, 273.15),
            ("K", "degF", 273.15, 32),
            ("degC", "degC", 25, 25),
        ],
    )
    def test_temperature_conversions(self, from_unit, to_unit, value, expected):
        payload = convert_unit(value, "temperature", from_unit, to_unit)
        assert payload["result"] == pytest.approx(expected)
        assert "偏移量" in payload["formula"]

    def test_negative_kelvin_input_rejected(self):
        with pytest.raises(ConversionError) as excinfo:
            convert_unit(-1, "temperature", "K", "degC")
        assert "开尔文" in excinfo.value.message

    def test_result_below_absolute_zero_rejected(self):
        with pytest.raises(ConversionError) as excinfo:
            convert_unit(-300, "temperature", "degC", "K")
        assert "绝对零度" in excinfo.value.message

    def test_unknown_category_lists_available(self):
        with pytest.raises(ConversionError) as excinfo:
            convert_unit(1, "weight", "kg", "g")
        assert "weight" in excinfo.value.message
        assert "length" in excinfo.value.message

    def test_unknown_unit_lists_available(self):
        with pytest.raises(ConversionError) as excinfo:
            convert_unit(1, "length", "lightyear", "m")
        assert "lightyear" in excinfo.value.message
        assert "km" in excinfo.value.message

    def test_unsupported_temperature_unit(self):
        # 绕过 CATEGORIES 的校验，直接测温度换算内部对未知单位的兜底
        from app.services.converter_service import _celsius_to_temperature, _temperature_to_celsius

        with pytest.raises(ConversionError):
            _temperature_to_celsius(1, "degR")
        with pytest.raises(ConversionError):
            _celsius_to_temperature(1, "degR")

    def test_describe_categories_shape(self):
        described = describe_categories()
        keys = {item["key"] for item in described}
        assert {"length", "mass", "area", "volume", "time", "speed", "data", "temperature"} <= keys
        for item in described:
            assert item["name"] and item["base_unit"] and item["units"]
            assert all({"code", "name"} <= set(unit) for unit in item["units"])

    def test_all_categories_have_base_unit(self):
        for key, spec in CATEGORIES.items():
            assert spec.base_unit in spec.units, f"{key} 的基准单位必须在自己声明的单位表里"


class TestMathFunctionRegistry:
    def test_function_count_and_unique_names(self):
        assert len(FUNCTIONS) == 29
        assert len(set(FUNCTIONS)) == len(FUNCTIONS)

    def test_describe_functions_shape(self):
        described = describe_functions()
        assert len(described) == len(FUNCTIONS)
        names = [item["name"] for item in described]
        assert names == sorted(names), "函数清单应按名字排序，便于前端展示"
        for item in described:
            assert item["arity"] and item["description"] and item["example"]

    def test_describe_constants_shape(self):
        described = describe_constants()
        names = {item["name"] for item in described}
        assert names == {"pi", "e", "tau", "phi"}
        assert all(isinstance(item["value"], float) for item in described)

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("sin", "1 个参数"),          # min == max 的分支
            ("log", "1~2 个参数"),        # 区间分支
            ("max", "至少 1 个参数"),     # 上界为 99 的"至少"分支
        ],
    )
    def test_arity_text_branches(self, name, expected):
        assert FUNCTIONS[name].arity_text == expected

    def test_constants_values(self):
        assert CONSTANTS["pi"] == pytest.approx(math.pi)
        assert CONSTANTS["e"] == pytest.approx(math.e)
        assert CONSTANTS["π"] == pytest.approx(math.pi)


class TestMathFunctionWrappers:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(-8, -2.0), (8, 2.0), (0, 0.0), (27, 3.0)],
    )
    def test_cbrt_keeps_sign(self, value, expected):
        assert _cbrt(value) == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(-5, -1.0), (5, 1.0), (0, 0.0)],
    )
    def test_sign(self, value, expected):
        assert _sign(value) == expected

    @pytest.mark.parametrize(("value", "expected"), [(0, 1.0), (1, 1.0), (5, 120.0)])
    def test_factorial_valid(self, value, expected):
        assert _factorial(value) == expected

    @pytest.mark.parametrize("value", [3.5, -1, 171])
    def test_factorial_invalid(self, value):
        with pytest.raises(ValueError):
            _factorial(value)

    @pytest.mark.parametrize(("x", "y"), [(10, 3), (-10, 3), (10, -3)])
    def test_mod_matches_fmod(self, x, y):
        assert _mod(x, y) == pytest.approx(math.fmod(x, y))

    def test_mod_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            _mod(1, 0)

    def test_tan_guard(self):
        assert _tan(0) == pytest.approx(0)
        with pytest.raises(ValueError):
            _tan(math.pi / 2)

    def test_log_single_argument_is_base10(self):
        assert _log(1000) == pytest.approx(3)

    def test_log_with_base(self):
        assert _log(8, 2) == pytest.approx(3)

    @pytest.mark.parametrize(("x", "base"), [(0, None), (-1, None), (8, 0), (8, -2), (8, 1)])
    def test_log_domain_errors(self, x, base):
        with pytest.raises(ValueError):
            _log(x, base)

    def test_round_variants(self):
        assert _round(2.4) == 2.0
        assert _round(3.14159, 2) == pytest.approx(3.14)

    def test_round_rejects_fractional_digits(self):
        with pytest.raises(ValueError):
            _round(1.234, 1.5)


class TestConverterApiEndpoints:
    """接口层：确认异常被翻译成 400 + CONVERSION_ERROR。"""

    def test_base_conversion_errors_return_400(self, client):
        # 数字越界、多个小数点属于业务校验 → 400 CONVERSION_ERROR
        for payload in (
            {"value": "2", "from_base": 2, "to_base": 10},
            {"value": "1.2.3", "from_base": 10, "to_base": 2},
        ):
            response = client.post("/api/convert/base", json=payload)
            assert response.status_code == 400, payload
            assert response.json()["error_code"] == "CONVERSION_ERROR"

    def test_base_out_of_range_is_rejected_by_schema(self, client):
        # 进制超范围由 Pydantic 的 ge/le 约束先拦住 → 422 VALIDATION_ERROR
        # （服务层里还有一道 2~36 的检查，属于纵深防御，接口层到不了那里）
        for payload in (
            {"value": "10", "from_base": 40, "to_base": 10},
            {"value": "10", "from_base": 1, "to_base": 10},
            {"value": "10", "from_base": 10, "to_base": 37},
        ):
            response = client.post("/api/convert/base", json=payload)
            assert response.status_code == 422, payload
            assert response.json()["error_code"] == "VALIDATION_ERROR"

    def test_unit_conversion_errors_return_400(self, client):
        for payload in (
            {"value": 1, "category": "weight", "from_unit": "kg", "to_unit": "g"},
            {"value": 1, "category": "length", "from_unit": "ly", "to_unit": "m"},
            {"value": -300, "category": "temperature", "from_unit": "degC", "to_unit": "K"},
        ):
            response = client.post("/api/convert/unit", json=payload)
            assert response.status_code == 400, payload
            assert response.json()["error_code"] == "CONVERSION_ERROR"

    def test_base_conversion_truncation_flag_over_api(self, client):
        body = client.post(
            "/api/convert/base", json={"value": "0.1", "from_base": 10, "to_base": 2}
        ).json()
        assert body["fraction_truncated"] is True
        assert "截断" in body["note"]
