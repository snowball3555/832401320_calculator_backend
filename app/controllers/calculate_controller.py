"""计算相关接口。

接口清单
--------
``POST /api/calculate``       计算表达式（**核心接口**：前端只传表达式，结果由后端算出）
``POST /api/parse``           只做语法分析，返回词法 Token 与语法树（扩展，用于演示）
``POST /api/convert/base``    进制转换（扩展）
``POST /api/convert/unit``    单位换算（扩展）
"""

from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.calculator import (
    BaseConvertRequest,
    BaseConvertResponse,
    CalculateRequest,
    CalculateResponse,
    ErrorResponse,
    ParseRequest,
    ParseResponse,
    UnitConvertRequest,
    UnitConvertResponse,
)
from app.services import base_converter, calculator_service, converter_service, history_service

router = APIRouter(prefix="/api", tags=["计算"])


@router.post(
    "/calculate",
    response_model=CalculateResponse,
    summary="计算表达式并保存历史",
    description=(
        "接收数学表达式，由**后端**完成解析、校验、求值，成功后写入数据库历史表并返回结果。\n\n"
        "前端只负责展示，不参与任何计算。"
    ),
    responses={400: {"model": ErrorResponse, "description": "表达式非法 / 除数为 0 / 数学定义域错误"}},
)
def calculate(
    payload: CalculateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> CalculateResponse:
    """核心计算接口。"""
    result = calculator_service.calculate(payload.expression)

    history_id: int | None = None
    if payload.save_history:
        numeric = float(result.result)
        record = history_service.create_record(
            db,
            expression=result.expression,
            result_display=result.result_display,
            result_numeric=numeric if math.isfinite(numeric) else None,
        )
        history_id = record.id

    return CalculateResponse(**result.to_dict(), history_id=history_id)


@router.post(
    "/parse",
    response_model=ParseResponse,
    summary="解析表达式（返回词法与语法树）",
    description="只做语法分析不做计算，用于展示运算符优先级与括号是如何被解析成语法树的。",
    responses={400: {"model": ErrorResponse, "description": "表达式非法"}},
)
def parse(payload: ParseRequest) -> ParseResponse:
    """语法分析接口（扩展功能）。"""
    return ParseResponse(**calculator_service.inspect(payload.expression))


@router.post(
    "/convert/base",
    response_model=BaseConvertResponse,
    summary="进制转换（扩展功能）",
    description="支持 2~36 进制互转，小数部分最多保留 16 位并给出截断提示。",
    responses={400: {"model": ErrorResponse, "description": "进制或数值非法"}},
)
def convert_base(payload: BaseConvertRequest) -> BaseConvertResponse:
    """进制转换接口。"""
    data = base_converter.convert_base(payload.value, payload.from_base, payload.to_base)
    return BaseConvertResponse(**data)


@router.post(
    "/convert/unit",
    response_model=UnitConvertResponse,
    summary="单位换算（扩展功能）",
    description="支持长度、质量、面积、体积、时间、速度、数据存储、温度八大类单位换算。",
    responses={400: {"model": ErrorResponse, "description": "单位类别或单位代码非法"}},
)
def convert_unit(payload: UnitConvertRequest) -> UnitConvertResponse:
    """单位换算接口。"""
    data = converter_service.convert_unit(
        payload.value, payload.category, payload.from_unit, payload.to_unit
    )
    return UnitConvertResponse(**data)
