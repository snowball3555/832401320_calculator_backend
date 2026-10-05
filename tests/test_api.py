"""接口层集成测试：完整走 HTTP，覆盖作业要求的四项核心功能。

用例覆盖：
* 功能 1 基本计算（加减乘除，结果由后端产出）
* 功能 2 复合表达式（优先级、括号、小数、一元正负、非法表达式、除零）
* 功能 3 历史记录（写入数据库、分页/搜索查询、刷新后仍可读取）
* 功能 4 删除指定历史记录（含删除不存在记录返回 404）
* 扩展功能（收藏、统计、清空、进制转换、单位换算、语法分析、元数据）
"""

from __future__ import annotations

import pytest


class TestHealth:
    def test_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert "X-Process-Time-Ms" in response.headers


class TestFeature1BasicCalculation:
    @pytest.mark.parametrize(
        ("expression", "expected"),
        [("12+8", 20), ("12-8", 4), ("12*8", 96), ("12/8", 1.5), ("7/2", 3.5)],
    )
    def test_four_operations(self, client, expression, expected):
        response = client.post("/api/calculate", json={"expression": expression})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["result"] == expected
        assert body["result_display"] == (f"{expected:g}" if isinstance(expected, float) else str(expected))
        assert body["history_id"] is not None

    def test_backend_returns_result_not_frontend(self, client):
        """后端必须回传完整结果与耗时，证明计算发生在服务端。"""
        body = client.post("/api/calculate", json={"expression": "6*7"}).json()
        assert body["result"] == 42
        assert body["elapsed_ms"] >= 0
        assert body["node_count"] == 3

    def test_history_can_be_skipped(self, client):
        body = client.post("/api/calculate", json={"expression": "1+1", "save_history": False}).json()
        assert body["history_id"] is None
        assert client.get("/api/history").json()["total"] == 0


class TestFeature2CompoundExpression:
    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("1+2*3", 7),
            ("(1+2)*3", 9),
            ("10/2+7", 12),
            ("8-3*2", 2),
            ("-5+8", 3),
            ("3*-2", -6),
            ("2^3^2", 512),
            ("sqrt(16)+3!", 10),
            ("12 × 8 ÷ 2", 48),
        ],
    )
    def test_compound(self, client, expression, expected):
        body = client.post("/api/calculate", json={"expression": expression}).json()
        assert body["result"] == expected

    def test_decimal(self, client):
        body = client.post("/api/calculate", json={"expression": "0.1+0.2"}).json()
        assert body["result"] == 0.3
        assert body["result_display"] == "0.3"

    @pytest.mark.parametrize(
        ("expression", "error_code"),
        [
            ("1+", "INVALID_EXPRESSION"),
            ("((1+2)", "INVALID_EXPRESSION"),
            ("abc", "INVALID_EXPRESSION"),
            ("1/0", "DIVISION_BY_ZERO"),
            ("sqrt(-1)", "MATH_DOMAIN_ERROR"),
        ],
    )
    def test_errors_return_400_with_code(self, client, expression, error_code):
        response = client.post("/api/calculate", json={"expression": expression})
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == error_code
        assert body["message"]

    def test_invalid_expression_not_saved_to_history(self, client):
        client.post("/api/calculate", json={"expression": "1/0"})
        assert client.get("/api/history").json()["total"] == 0

    def test_empty_expression_rejected_by_validation(self, client):
        response = client.post("/api/calculate", json={"expression": ""})
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "VALIDATION_ERROR"


class TestFeature3History:
    def test_history_saved_to_database(self, client):
        client.post("/api/calculate", json={"expression": "1+2"})
        client.post("/api/calculate", json={"expression": "5*8"})
        body = client.get("/api/history").json()
        assert body["total"] == 2
        expressions = [item["expression"] for item in body["items"]]
        assert "1+2" in expressions and "5*8" in expressions
        for item in body["items"]:
            assert item["id"] > 0
            assert item["result"]
            assert len(item["created_at"]) == 19  # yyyy-MM-dd HH:mm:ss

    def test_history_is_ordered_newest_first(self, client):
        client.post("/api/calculate", json={"expression": "1+1"})
        client.post("/api/calculate", json={"expression": "2+2"})
        items = client.get("/api/history").json()["items"]
        assert items[0]["expression"] == "2+2"

    def test_history_survives_new_client(self, client):
        """模拟"刷新前端"：接口重新查询数据库，数据仍在。"""
        client.post("/api/calculate", json={"expression": "9*9"})
        body = client.get("/api/history").json()
        assert body["total"] == 1
        assert body["items"][0]["result"] == "81"

    def test_pagination(self, client):
        for index in range(12):
            client.post("/api/calculate", json={"expression": f"{index}+1"})
        first = client.get("/api/history", params={"page": 1, "page_size": 5}).json()
        second = client.get("/api/history", params={"page": 2, "page_size": 5}).json()
        assert first["total"] == 12
        assert first["pages"] == 3
        assert len(first["items"]) == 5
        assert len(second["items"]) == 5
        assert {item["id"] for item in first["items"]}.isdisjoint({item["id"] for item in second["items"]})

    def test_keyword_search(self, client):
        client.post("/api/calculate", json={"expression": "123+456"})
        client.post("/api/calculate", json={"expression": "1+1"})
        body = client.get("/api/history", params={"keyword": "123"}).json()
        assert body["total"] == 1
        assert body["items"][0]["expression"] == "123+456"

    def test_invalid_pagination_rejected(self, client):
        assert client.get("/api/history", params={"page": 0}).status_code == 422
        assert client.get("/api/history", params={"page_size": 999}).status_code == 422


class TestFeature4DeleteHistory:
    def test_delete_specified_record(self, client):
        first = client.post("/api/calculate", json={"expression": "1+1"}).json()
        second = client.post("/api/calculate", json={"expression": "2+2"}).json()

        response = client.delete(f"/api/history/{first['history_id']}")
        assert response.status_code == 200
        assert response.json()["deleted"] == 1

        remaining = client.get("/api/history").json()
        assert remaining["total"] == 1
        assert remaining["items"][0]["id"] == second["history_id"]

    def test_delete_missing_record_returns_404(self, client):
        response = client.delete("/api/history/999999")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"

    def test_clear_all_history(self, client):
        for index in range(3):
            client.post("/api/calculate", json={"expression": f"{index}+{index}"})
        response = client.delete("/api/history")
        assert response.status_code == 200
        assert response.json()["deleted"] == 3
        assert client.get("/api/history").json()["total"] == 0


class TestExtendedFeatures:
    def test_favorite_toggle(self, client):
        record_id = client.post("/api/calculate", json={"expression": "1+1"}).json()["history_id"]

        body = client.patch(f"/api/history/{record_id}/favorite", json={}).json()
        assert body["is_favorite"] is True

        body = client.patch(f"/api/history/{record_id}/favorite", json={"is_favorite": False}).json()
        assert body["is_favorite"] is False

    def test_favorite_only_filter(self, client):
        first = client.post("/api/calculate", json={"expression": "1+1"}).json()["history_id"]
        client.post("/api/calculate", json={"expression": "2+2"})
        client.patch(f"/api/history/{first}/favorite", json={"is_favorite": True})

        body = client.get("/api/history", params={"favorite_only": True}).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == first

    def test_statistics(self, client):
        client.post("/api/calculate", json={"expression": "1+2"})
        client.post("/api/calculate", json={"expression": "3*4"})
        body = client.get("/api/history/stats").json()
        assert body["total"] == 2
        assert body["today"] == 2
        assert body["unique_expressions"] == 2
        assert body["most_used_operator"] in {"+", "*"}
        assert body["last_calculated_at"]

    def test_parse_endpoint_returns_ast(self, client):
        body = client.post("/api/parse", json={"expression": "(1+2)*3"}).json()
        assert body["infix"] == "(1 + 2) * 3"
        assert body["tree"]["type"] == "binary"
        assert body["node_count"] == 5

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ({"value": "FF", "from_base": 16, "to_base": 2}, "11111111"),
            ({"value": "1010", "from_base": 2, "to_base": 10}, "10"),
            ({"value": "255", "from_base": 10, "to_base": 16}, "ff"),
            ({"value": "777", "from_base": 8, "to_base": 10}, "511"),
            ({"value": "-1010", "from_base": 2, "to_base": 10}, "-10"),
        ],
    )
    def test_base_conversion(self, client, payload, expected):
        body = client.post("/api/convert/base", json=payload).json()
        assert body["result"] == expected

    def test_base_conversion_rejects_illegal_digit(self, client):
        response = client.post("/api/convert/base", json={"value": "2", "from_base": 2, "to_base": 10})
        assert response.status_code == 400
        assert response.json()["error_code"] == "CONVERSION_ERROR"

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ({"value": 1, "category": "length", "from_unit": "km", "to_unit": "m"}, 1000),
            ({"value": 1, "category": "mass", "from_unit": "kg", "to_unit": "g"}, 1000),
            ({"value": 100, "category": "temperature", "from_unit": "degC", "to_unit": "degF"}, 212),
            ({"value": 1, "category": "data", "from_unit": "KB", "to_unit": "B"}, 1024),
            ({"value": 1, "category": "time", "from_unit": "h", "to_unit": "s"}, 3600),
        ],
    )
    def test_unit_conversion(self, client, payload, expected):
        body = client.post("/api/convert/unit", json=payload).json()
        assert body["result"] == expected
        assert body["formula"]

    def test_unit_conversion_rejects_unknown_unit(self, client):
        response = client.post(
            "/api/convert/unit",
            json={"value": 1, "category": "length", "from_unit": "lightyear", "to_unit": "m"},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "CONVERSION_ERROR"

    def test_meta_endpoint(self, client):
        body = client.get("/api/meta/functions").json()
        names = {item["name"] for item in body["functions"]}
        assert {"sin", "cos", "sqrt", "log", "factorial"} <= names
        assert {item["name"] for item in body["constants"]} >= {"pi", "e"}
        assert len(body["unit_categories"]) >= 6
        assert body["supported_bases"][0] == 2

    def test_openapi_and_docs_available(self, client):
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200

    def test_unknown_route_returns_structured_error(self, client):
        response = client.get("/api/not-exist")
        assert response.status_code == 404
        assert response.json()["success"] is False

    def test_cors_header_for_cross_origin_request(self, client):
        """前后端分离部署在不同源时，浏览器会先发预检请求。"""
        response = client.options(
            "/api/calculate",
            headers={
                "Origin": "http://127.0.0.1:5500",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code in (200, 204)
        assert response.headers.get("access-control-allow-origin") in {"*", "http://127.0.0.1:5500"}
