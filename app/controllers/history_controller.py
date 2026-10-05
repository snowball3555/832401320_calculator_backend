"""历史记录接口。

接口清单
--------
``GET    /api/history``                     分页查询历史（支持关键字搜索、只看收藏）
``GET    /api/history/stats``               统计信息（扩展）
``DELETE /api/history``                     清空历史（扩展）
``DELETE /api/history/{record_id}``         删除指定历史（**作业要求的功能 4**）
``PATCH  /api/history/{record_id}/favorite`` 收藏/取消收藏（扩展）
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.calculator import (
    DeleteResponse,
    ErrorResponse,
    FavoriteRequest,
    HistoryItem,
    HistoryListResponse,
    StatsResponse,
)
from app.services import history_service
from app.utils.errors import ResourceNotFoundError

router = APIRouter(prefix="/api/history", tags=["历史记录"])


@router.get(
    "",
    response_model=HistoryListResponse,
    summary="分页查询历史记录",
    description="历史记录来自后端数据库，刷新/重启前端不会丢失；支持表达式与结果的关键字模糊搜索。",
)
def list_history(
    db: Annotated[Session, Depends(get_db)],
    keyword: Annotated[str | None, Query(max_length=100, description="搜索关键字")] = None,
    favorite_only: Annotated[bool, Query(description="只看收藏")] = False,
    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 10,
) -> HistoryListResponse:
    """查询历史记录列表。"""
    records, total, pages = history_service.list_records(
        db, keyword=keyword, favorite_only=favorite_only, page=page, page_size=page_size
    )
    return HistoryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[HistoryItem(**record.to_dict()) for record in records],
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="计算统计（扩展功能）",
    description="返回总记录数、今日计算次数、收藏数、运算符使用频次等统计信息。",
)
def history_stats(db: Annotated[Session, Depends(get_db)]) -> StatsResponse:
    """统计信息。"""
    return StatsResponse(**history_service.statistics(db))


@router.delete(
    "",
    response_model=DeleteResponse,
    summary="清空历史记录（扩展功能）",
    description="清空全部历史；带 ``favorite_only=true`` 时只清空收藏的记录。",
)
def clear_history(
    db: Annotated[Session, Depends(get_db)],
    favorite_only: Annotated[bool, Query(description="只清空收藏记录")] = False,
) -> DeleteResponse:
    """清空历史。"""
    deleted = history_service.clear_records(db, favorite_only=favorite_only)
    scope = "收藏的" if favorite_only else "全部"
    return DeleteResponse(
        message=f"已清空{scope}历史记录，共删除 {deleted} 条", deleted=deleted
    )


@router.delete(
    "/{record_id}",
    response_model=DeleteResponse,
    summary="删除指定历史记录",
    description="按主键删除数据库中的一条历史记录；记录不存在时返回 404。",
    responses={404: {"model": ErrorResponse, "description": "记录不存在"}},
)
def delete_history(
    db: Annotated[Session, Depends(get_db)],
    record_id: Annotated[int, Path(ge=1, description="历史记录 ID")],
) -> DeleteResponse:
    """删除指定历史记录。"""
    deleted = history_service.delete_record(db, record_id)
    if not deleted:
        raise ResourceNotFoundError(f"历史记录 {record_id} 不存在或已被删除")
    return DeleteResponse(message=f"已删除历史记录 {record_id}", deleted=1)


@router.patch(
    "/{record_id}/favorite",
    response_model=HistoryItem,
    summary="收藏 / 取消收藏（扩展功能）",
    description="``is_favorite`` 留空表示取反切换。",
    responses={404: {"model": ErrorResponse, "description": "记录不存在"}},
)
def toggle_favorite(
    payload: FavoriteRequest,
    db: Annotated[Session, Depends(get_db)],
    record_id: Annotated[int, Path(ge=1, description="历史记录 ID")],
) -> HistoryItem:
    """切换收藏状态。"""
    record = history_service.set_favorite(db, record_id, payload.is_favorite)
    return HistoryItem(**record.to_dict())
