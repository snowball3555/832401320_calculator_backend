"""系统与元数据接口：健康检查、函数/常量/单位清单。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import config
from app.db.database import get_db
from app.db.models import now_local
from app.schemas.calculator import HealthResponse, MetaResponse
from app.services import base_converter, converter_service
from app.services.math_functions import describe_constants, describe_functions

router = APIRouter(prefix="/api", tags=["系统"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="前端启动时轮询此接口，用于显示「后端在线 / 后端离线」状态徽标。",
)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    """健康检查：顺带验证一次数据库连通性。"""
    try:
        db.execute(text("SELECT 1"))
        database = "connected"
    except Exception:  # noqa: BLE001 - 健康检查不应因数据库异常而抛错
        database = "error"

    return HealthResponse(
        app=config.APP_NAME,
        version=config.APP_VERSION,
        database=database,
        server_time=now_local().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get(
    "/meta/functions",
    response_model=MetaResponse,
    summary="获取支持的函数、常量与单位",
    description=(
        "前端据此动态渲染科学计算面板、进制选择器与单位下拉框，"
        "新增后端函数时前端无需改代码，避免两边各维护一份清单。"
    ),
)
def meta_functions() -> MetaResponse:
    """元数据接口。"""
    return MetaResponse(
        app=config.APP_NAME,
        version=config.APP_VERSION,
        constants=describe_constants(),
        functions=describe_functions(),
        unit_categories=converter_service.describe_categories(),
        supported_bases=base_converter.SUPPORTED_BASES,
    )
