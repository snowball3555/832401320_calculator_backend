"""API 数据契约（Pydantic 模型）。

为什么要把请求/响应单独抽成一层？
--------------------------------
1. **参数校验前置**：``expression`` 的长度、``page`` 的下界、``from_base`` 的取值范围
   都在进入业务代码之前就被框架拦住，业务层可以放心假设数据是"干净"的；
2. **接口自文档化**：模型里的 ``description`` / ``examples`` 会直接出现在 ``/docs`` 的
   Swagger UI 中，助教不用看代码就能试接口；
3. **响应结构稳定**：所有成功响应都带 ``success: true``，失败响应统一为
   ``{success: false, error_code, message}``，前端只需要写一套处理逻辑。
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """统一的错误响应体（由全局异常处理器产出）。"""

    success: Literal[False] = False
    error_code: str = Field(
        description="机器可读的错误码，如 INVALID_EXPRESSION", examples=["DIVISION_BY_ZERO"]
    )
    message: str = Field(description="可直接展示给用户的中文提示", examples=["除数不能为 0"])
    detail: str | None = Field(default=None, description="可选的补充说明")


class HealthResponse(BaseModel):
    """健康检查响应；前端用它判断"后端是否在线"。"""

    success: Literal[True] = True
    status: Literal["ok"] = "ok"
    app: str
    version: str
    database: str = Field(description="数据库连接是否正常")
    server_time: str = Field(description="服务器时间（UTC+8）")


# ---------------------------------------------------------------------------
# 计算
# ---------------------------------------------------------------------------


class CalculateRequest(BaseModel):
    """计算请求：**只传表达式，不传结果**。"""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"expression": "(1+2)*3", "save_history": True}]}
    )

    expression: Annotated[str, Field(min_length=1, max_length=500, description="数学表达式")]
    save_history: Annotated[bool, Field(description="是否把本次计算写入历史记录")] = True


class CalculateResponse(BaseModel):
    """计算响应。"""

    success: Literal[True] = True
    expression: str = Field(description="规范化后的表达式", examples=["(1+2)*3"])
    raw_expression: str = Field(description="用户原样输入", examples=["(1+2)*3"])
    result: int | float = Field(description="数值结果", examples=[9])
    result_display: str = Field(description="展示用字符串", examples=["9"])
    history_id: int | None = Field(default=None, description="本次计算写入的历史记录 ID")
    node_count: int = Field(description="表达式语法树节点数")
    max_depth: int = Field(description="表达式语法树深度")
    elapsed_ms: float = Field(description="后端计算耗时（毫秒）")


class ParseRequest(BaseModel):
    """语法分析请求（扩展功能：展示分词与语法树）。"""

    expression: Annotated[str, Field(min_length=1, max_length=500, description="数学表达式")]


class ParseResponse(BaseModel):
    """语法分析响应。"""

    success: Literal[True] = True
    raw_expression: str
    expression: str
    infix: str = Field(description="由语法树还原的表达式，括号体现优先级")
    node_count: int
    max_depth: int
    tokens: list[dict[str, Any]]
    tree: dict[str, Any]


# ---------------------------------------------------------------------------
# 历史记录
# ---------------------------------------------------------------------------


class HistoryItem(BaseModel):
    """一条历史记录。"""

    id: int
    expression: str
    result: str
    result_numeric: float | None = None
    is_favorite: bool = False
    created_at: str = Field(description="计算时间（UTC+8，yyyy-MM-dd HH:mm:ss）")


class HistoryListResponse(BaseModel):
    """分页后的历史记录列表。"""

    success: Literal[True] = True
    total: int = Field(description="满足条件的记录总数")
    page: int
    page_size: int
    pages: int = Field(description="总页数")
    items: list[HistoryItem]


class DeleteResponse(BaseModel):
    """删除结果。"""

    success: Literal[True] = True
    message: str
    deleted: int = Field(description="实际删除的记录条数")


class FavoriteRequest(BaseModel):
    """收藏切换请求。"""

    is_favorite: bool | None = Field(
        default=None, description="留空表示取反（在收藏与未收藏之间切换）"
    )


class StatsResponse(BaseModel):
    """计算统计（扩展功能）。"""

    success: Literal[True] = True
    total: int
    today: int
    favorites: int
    unique_expressions: int
    most_used_operator: str | None
    operator_usage: dict[str, int]
    last_calculated_at: str | None


# ---------------------------------------------------------------------------
# 进制 / 单位换算（扩展功能）
# ---------------------------------------------------------------------------


class BaseConvertRequest(BaseModel):
    """进制转换请求。"""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": "FF", "from_base": 16, "to_base": 2}]}
    )

    value: Annotated[str, Field(min_length=1, max_length=64, description="待转换的数值文本")]
    from_base: Annotated[int, Field(ge=2, le=36, description="源进制 2~36")] = 10
    to_base: Annotated[int, Field(ge=2, le=36, description="目标进制 2~36")] = 2


class BaseConvertResponse(BaseModel):
    """进制转换结果。"""

    success: Literal[True] = True
    value: str
    from_base: int
    to_base: int
    result: str = Field(description="目标进制下的表示")
    decimal_value: str = Field(description="十进制的等值表示，便于核对")
    fraction_truncated: bool = Field(default=False, description="小数部分是否因精度被截断")
    note: str = Field(default="转换结果精确", description="精度说明")


class UnitConvertRequest(BaseModel):
    """单位换算请求。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"value": 1, "category": "length", "from_unit": "km", "to_unit": "m"}]
        }
    )

    value: float = Field(description="待换算的数值")
    category: Annotated[str, Field(description="单位类别，如 length/mass/temperature")] = "length"
    from_unit: Annotated[str, Field(description="源单位代码")] = "m"
    to_unit: Annotated[str, Field(description="目标单位代码")] = "km"


class UnitConvertResponse(BaseModel):
    """单位换算结果。"""

    success: Literal[True] = True
    value: float
    category: str
    from_unit: str
    to_unit: str
    from_name: str
    to_name: str
    result: int | float
    result_display: str
    formula: str = Field(description="换算过程说明")


class MetaResponse(BaseModel):
    """元数据：函数、常量、单位清单，供前端动态渲染。"""

    success: Literal[True] = True
    app: str
    version: str
    constants: list[dict[str, Any]]
    functions: list[dict[str, Any]]
    unit_categories: list[dict[str, Any]]
    supported_bases: list[int]
