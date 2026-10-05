"""ORM 模型定义。

对应作业要求的 ``calculation_history`` 表::

    calculation_history
    -------------------
    id               主键，自增
    expression       计算表达式（用户原样输入，规范化后保存）
    result           计算结果（字符串形式，避免浮点精度在展示时丢失）
    result_numeric   计算结果（数值形式，便于统计与排序；无法表示为有限数时为空）
    is_favorite      是否收藏（扩展功能）
    created_at       计算时间（东八区挂钟时间）

关于时间字段的取舍
------------------
作业示例里的时间形如 ``2026-10-01 10:20:00``，没有时区信息。如果直接用
``datetime.utcnow()``，服务器在 UTC 环境（例如 Render）时前端会显示成 UTC 时间，
和助教本机时间差 8 小时。因此这里统一按 **固定 UTC+8** 取"业务时间"再存储为 naive
datetime，保证本地开发、Docker、云主机三种环境下看到的时间完全一致。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import TIMEZONE_OFFSET
from app.db.database import Base

APP_TIMEZONE = timezone(timedelta(hours=TIMEZONE_OFFSET))


def now_local() -> datetime:
    """返回东八区当前挂钟时间（naive）。"""
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


class CalculationHistory(Base):
    """一条计算历史记录。"""

    __tablename__ = "calculation_history"
    __table_args__ = (
        # 历史列表默认按时间倒序 + 主键倒序，联合索引可以直接支撑排序与分页
        Index("ix_calculation_history_created_at_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expression: Mapped[str] = mapped_column(String(512), nullable=False, comment="计算表达式")
    result: Mapped[str] = mapped_column(String(128), nullable=False, comment="计算结果（展示用字符串）")
    result_numeric: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="计算结果（数值形式，便于统计）"
    )
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", comment="是否收藏"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_local, index=True, comment="计算时间（UTC+8）"
    )

    def to_dict(self) -> dict:
        """转成 API 输出结构。"""
        return {
            "id": self.id,
            "expression": self.expression,
            "result": self.result,
            "result_numeric": self.result_numeric,
            "is_favorite": bool(self.is_favorite),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试
        return f"<CalculationHistory id={self.id} {self.expression}={self.result}>"
