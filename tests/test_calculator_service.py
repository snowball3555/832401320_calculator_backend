"""计算服务测试：正确性、数值规范化与异常处理。"""

from __future__ import annotations

import pytest

from app.services.calculator_service import calculate, normalize_number
from app.utils.errors import (
    CalculatorError,
    DivisionByZeroError,
    ExpressionSyntaxError,
    MathDomainError,
    NumericOverflowError,
)


def value_of(expression: str):
    return calculate(expression).result


class TestBasicArithmetic:
    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("12+8", 20),
            ("12-8", 4),
            ("12*8", 96),
            ("12/8", 1.5),
            ("0+0", 0),
            ("-0", 0),
            ("100-100", 0),
        ],
    )
    def test_basic_operations(self, expression, expected):
        assert value_of(expression) == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("1 + 2 * 3", 7),
            ("(1 + 2) * 3", 9),
            ("10 / 2 + 7", 12),
            ("8 - 3 * 2", 2),
            ("2 + 3 * 4 - 6 / 2", 11),
            ("((1+2)*(3+4))", 21),
        ],
    )
    def test_compound_expressions(self, expression, expected):
        assert value_of(expression) == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [("-5 + 8", 3), ("3 * -2", -6), ("-5 - -3", -2), ("--5", 5), ("+7", 7)],
    )
    def test_unary_signs(self, expression, expected):
        assert value_of(expression) == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [("0.1 + 0.2", 0.3), ("1.5 * 2", 3), (".5 + .5", 1), ("1.5e-3", 0.0015)],
    )
    def test_decimals(self, expression, expected):
        assert value_of(expression) == expected

    def test_float_error_is_normalized(self):
        """0.1+0.2 在 IEEE-754 下是 0.30000000000000004，必须被规范化。"""
        result = calculate("0.1+0.2")
        assert result.result == 0.3
        assert result.result_display == "0.3"

    def test_integer_result_has_no_trailing_zero(self):
        result = calculate("10/2")
        assert result.result == 5
        assert result.result_display == "5"
        assert isinstance(result.result, int)


class TestAdvancedArithmetic:
    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("2^10", 1024),
            ("2^3^2", 512),
            ("2^-1", 0.5),
            ("(-2)^2", 4),
            ("-2^2", -4),
            ("9^0.5", 3),
            ("5%3", 2),
            ("3!", 6),
            ("3!!", 720),
            ("sqrt(16)", 4),
            ("cbrt(-8)", -2),
            ("abs(-3)", 3),
            ("floor(2.9)", 2),
            ("ceil(2.1)", 3),
            ("round(3.14159,2)", 3.14),
            ("max(1,9,4)", 9),
            ("min(1,9,4)", 1),
            ("log(8,2)", 3),
            ("log10(1000)", 3),
            ("log2(8)", 3),
            ("sign(-5)", -1),
        ],
    )
    def test_scientific_functions(self, expression, expected):
        assert value_of(expression) == expected

    def test_trigonometric_identity(self):
        assert value_of("sin(pi/2)") == 1
        assert round(float(value_of("cos(0)")), 10) == 1

    @pytest.mark.parametrize(("expression", "expected"), [("2pi", None), ("3(4+5)", 27), ("(1+2)(3+4)", 21)])
    def test_implicit_multiplication(self, expression, expected):
        result = value_of(expression)
        if expected is None:
            assert result == pytest.approx(6.283185307179586)
        else:
            assert result == expected

    def test_full_width_expression_supported(self):
        assert value_of("12 × 8 ÷ 2") == 48


class TestErrorHandling:
    @pytest.mark.parametrize("expression", ["1/0", "1/(2-2)", "5%0", "0^-1"])
    def test_division_by_zero(self, expression):
        with pytest.raises(DivisionByZeroError) as excinfo:
            calculate(expression)
        assert excinfo.value.error_code == "DIVISION_BY_ZERO"
        assert excinfo.value.http_status == 400

    @pytest.mark.parametrize(
        "expression", ["sqrt(-1)", "ln(0)", "ln(-1)", "asin(2)", "tan(pi/2)", "(-8)^0.5"]
    )
    def test_domain_errors(self, expression):
        with pytest.raises(MathDomainError) as excinfo:
            calculate(expression)
        assert excinfo.value.error_code == "MATH_DOMAIN_ERROR"

    @pytest.mark.parametrize("expression", ["1e308*10", "9^9^9", "factorial(171)"])
    def test_overflow_or_limit(self, expression):
        with pytest.raises(CalculatorError):
            calculate(expression)

    @pytest.mark.parametrize(
        "expression",
        ["", "   ", "1+", "+", "abc", "1..2", "((1+2)", "__import__('os').system('echo hi')"],
    )
    def test_invalid_expressions(self, expression):
        with pytest.raises(ExpressionSyntaxError):
            calculate(expression)

    def test_large_power_is_rejected_quickly(self):
        """``9^9^9`` 必须被预判拦下，而不是真的去算 —— 否则会长时间占满 CPU。"""
        import time

        started = time.perf_counter()
        with pytest.raises(NumericOverflowError):
            calculate("9^9^9")
        assert time.perf_counter() - started < 0.5

    def test_error_messages_are_chinese(self):
        with pytest.raises(CalculatorError) as excinfo:
            calculate("1/0")
        assert "除数" in excinfo.value.message


class TestNormalizeNumber:
    @pytest.mark.parametrize(
        ("value", "expected_display"),
        [(3.0, "3"), (0.3, "0.3"), (1 / 3, "0.333333333333"), (0.0, "0")],
    )
    def test_display(self, value, expected_display):
        _, display = normalize_number(value)
        assert display == expected_display

    def test_non_finite_rejected(self):
        with pytest.raises(NumericOverflowError):
            normalize_number(float("inf"))


class TestExpressionInspection:
    def test_inspect_returns_tree_and_tokens(self):
        from app.services.calculator_service import inspect

        payload = inspect("(1+2)*3")
        assert payload["infix"] == "(1 + 2) * 3"
        assert payload["node_count"] == 5
        assert payload["max_depth"] == 3
        assert len(payload["tokens"]) == 7

    def test_inspect_rejects_invalid_expression(self):
        from app.services.calculator_service import inspect

        with pytest.raises(ExpressionSyntaxError):
            inspect("1+")
