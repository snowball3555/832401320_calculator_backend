"""词法与语法分析测试（不涉及数据库）。"""

from __future__ import annotations

import pytest

from app.services.expression_lexer import normalize_expression, tokenize
from app.services.expression_parser import (
    BinaryNode,
    FunctionNode,
    NumberNode,
    UnaryNode,
    parse_expression,
)
from app.utils.errors import ExpressionSyntaxError, ExpressionTooComplexError


class TestTokenizer:
    def test_basic_tokens(self):
        tokens = [token for token in tokenize("1+2*3") if token.kind != "eof"]
        assert [(token.kind, token.value) for token in tokens] == [
            ("number", "1"),
            ("op", "+"),
            ("number", "2"),
            ("op", "*"),
            ("number", "3"),
        ]

    def test_token_positions_are_zero_based_start_indexes(self):
        tokens = [token for token in tokenize("(1+2)*3") if token.kind != "eof"]
        assert [token.pos for token in tokens] == [0, 1, 2, 3, 4, 5, 6]

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("3.14", "3.14"),
            (".5", ".5"),
            ("1.5e-3", "1.5e-3"),
            ("2E10", "2E10"),
        ],
    )
    def test_number_literals(self, expression, expected):
        tokens = [token for token in tokenize(expression) if token.kind == "number"]
        assert [token.value for token in tokens] == [expected]

    def test_scientific_notation_only_when_digits_follow(self):
        """``2e`` 应被切成 2 与常量 e，而不是半个科学计数法。"""
        tokens = [token for token in tokenize("2e") if token.kind != "eof"]
        assert [(token.kind, token.value) for token in tokens] == [("number", "2"), ("name", "e")]

    def test_full_width_and_display_symbols_are_normalized(self):
        assert normalize_expression("12 × 8 ÷ 2 − 1") == "12 * 8 / 2 - 1"
        assert normalize_expression("sin（pi/2）") == "sin(pi/2)"

    def test_empty_expression_rejected(self):
        with pytest.raises(ExpressionSyntaxError):
            tokenize("   ")

    def test_illegal_character_rejected(self):
        with pytest.raises(ExpressionSyntaxError) as excinfo:
            tokenize("1 + $2")
        assert "非法字符" in excinfo.value.message

    def test_too_long_expression_rejected(self):
        with pytest.raises(ExpressionTooComplexError):
            tokenize("1+" * 400 + "1")


class TestParser:
    def test_precedence_multiplication_binds_tighter(self):
        tree = parse_expression("1+2*3")
        assert isinstance(tree, BinaryNode)
        assert tree.op == "+"
        assert isinstance(tree.right, BinaryNode)
        assert tree.right.op == "*"

    def test_parentheses_override_precedence(self):
        tree = parse_expression("(1+2)*3")
        assert tree.op == "*"
        assert isinstance(tree.left, BinaryNode)
        assert tree.left.op == "+"

    def test_power_is_right_associative(self):
        tree = parse_expression("2^3^2")
        assert tree.op == "^"
        assert isinstance(tree.right, BinaryNode)
        assert tree.right.op == "^"

    def test_unary_minus_node(self):
        tree = parse_expression("-5")
        assert isinstance(tree, UnaryNode)
        assert tree.op == "-"
        assert isinstance(tree.operand, NumberNode)
        assert tree.operand.value == 5

    def test_double_unary_minus(self):
        tree = parse_expression("--5")
        assert isinstance(tree, UnaryNode)
        assert isinstance(tree.operand, UnaryNode)

    def test_implicit_multiplication_with_constant(self):
        tree = parse_expression("2pi")
        assert tree.op == "*"
        assert isinstance(tree.right, NumberNode)

    def test_implicit_multiplication_with_parentheses(self):
        tree = parse_expression("3(4+5)")
        assert tree.op == "*"
        assert isinstance(tree.right, BinaryNode)

    def test_two_bare_numbers_are_rejected(self):
        """``2 3`` 不允许被静默解释成 6，应作为非法表达式处理。"""
        with pytest.raises(ExpressionSyntaxError):
            parse_expression("2 3")

    def test_function_call_node(self):
        tree = parse_expression("log(8,2)")
        assert isinstance(tree, FunctionNode)
        assert tree.name == "log"
        assert len(tree.args) == 2

    def test_unknown_function_rejected(self):
        with pytest.raises(ExpressionSyntaxError) as excinfo:
            parse_expression("system(1)")
        assert "未知的名称" in excinfo.value.message

    def test_code_like_input_is_only_a_syntax_error(self):
        """带引号/下划线的"代码式"输入只会被当成非法字符，不可能被执行。"""
        with pytest.raises(ExpressionSyntaxError) as excinfo:
            parse_expression("__import__('os').system('rm -rf /')")
        assert "非法字符" in excinfo.value.message

    def test_function_without_parentheses_rejected(self):
        with pytest.raises(ExpressionSyntaxError) as excinfo:
            parse_expression("sin 1")
        assert "必须带括号调用" in excinfo.value.message

    def test_wrong_argument_count_rejected(self):
        with pytest.raises(ExpressionSyntaxError) as excinfo:
            parse_expression("sin(1,2)")
        assert "需要" in excinfo.value.message

    @pytest.mark.parametrize(
        "expression",
        ["1+", "*2", "1+2)", "((1+2)", "()", "1++", "2^", "1,2", "round(1,2,3)"],
    )
    def test_invalid_expressions_rejected(self, expression):
        with pytest.raises(ExpressionSyntaxError):
            parse_expression(expression)

    def test_deep_nesting_rejected(self):
        with pytest.raises(ExpressionTooComplexError):
            parse_expression("(" * 40 + "1" + ")" * 40)

    def test_too_many_nodes_rejected(self):
        with pytest.raises(ExpressionTooComplexError):
            parse_expression("+".join(["1"] * 260))
