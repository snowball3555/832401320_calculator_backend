"""历史记录服务：对 ``calculation_history`` 表的全部读写操作。

这一层是"业务规则"的落点，接口层只做参数绑定和响应封装：

* 计算成功才写库（失败的计算不产生历史）；
* 删除按主键进行，删除不存在的记录返回 ``False``，由接口层翻译成 404；
* 列表查询支持关键字（同时匹配表达式与结果）、收藏过滤、分页，并按时间倒序返回。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import CalculationHistory, now_local
from app.utils.errors import ResourceNotFoundError

MAX_PAGE_SIZE = 100
OPERATORS = ("+", "-", "*", "/", "%", "^", "!")


def create_record(
    db: Session,
    *,
    expression: str,
    result_display: str,
    result_numeric: float | None = None,
    is_favorite: bool = False,
) -> CalculationHistory:
    """写入一条计算历史并返回（含自增主键）。"""
    record = CalculationHistory(
        expression=expression,
        result=result_display,
        result_numeric=result_numeric,
        is_favorite=is_favorite,
        created_at=now_local(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_record(db: Session, record_id: int) -> CalculationHistory:
    """按主键取一条记录，不存在则抛 404 业务异常。"""
    record = db.get(CalculationHistory, record_id)
    if record is None:
        raise ResourceNotFoundError(f"历史记录 {record_id} 不存在")
    return record


def _escape_like(keyword: str) -> str:
    """转义 LIKE 通配符，避免用户输入的 % 和 _ 被当成通配符。"""
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_records(
    db: Session,
    *,
    keyword: str | None = None,
    favorite_only: bool = False,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[CalculationHistory], int, int]:
    """分页查询历史记录，返回 (当前页数据, 总条数, 总页数)。"""
    page = max(1, int(page))
    page_size = min(MAX_PAGE_SIZE, max(1, int(page_size)))

    conditions = []
    if keyword and keyword.strip():
        pattern = f"%{_escape_like(keyword.strip())}%"
        conditions.append(
            or_(
                CalculationHistory.expression.ilike(pattern, escape="\\"),
                CalculationHistory.result.ilike(pattern, escape="\\"),
            )
        )
    if favorite_only:
        conditions.append(CalculationHistory.is_favorite.is_(True))

    total_query = select(func.count()).select_from(CalculationHistory)
    if conditions:
        total_query = total_query.where(*conditions)
    total = int(db.execute(total_query).scalar_one())

    data_query = select(CalculationHistory)
    if conditions:
        data_query = data_query.where(*conditions)
    data_query = (
        data_query.order_by(CalculationHistory.created_at.desc(), CalculationHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = list(db.execute(data_query).scalars().all())

    pages = max(1, (total + page_size - 1) // page_size)
    return records, total, pages


def delete_record(db: Session, record_id: int) -> bool:
    """删除指定记录，返回是否真的删掉了数据。"""
    record = db.get(CalculationHistory, record_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def clear_records(db: Session, *, favorite_only: bool = False) -> int:
    """清空历史记录，返回删除条数。"""
    statement = delete(CalculationHistory)
    if favorite_only:
        statement = statement.where(CalculationHistory.is_favorite.is_(True))
    result = db.execute(statement)
    db.commit()
    return int(result.rowcount or 0)


def set_favorite(db: Session, record_id: int, is_favorite: bool | None) -> CalculationHistory:
    """设置或切换收藏状态。"""
    record = get_record(db, record_id)
    record.is_favorite = (not record.is_favorite) if is_favorite is None else bool(is_favorite)
    db.commit()
    db.refresh(record)
    return record


def statistics(db: Session) -> dict:
    """统计信息：总量、今日量、收藏量、运算符使用频次等。"""
    total = int(db.execute(select(func.count()).select_from(CalculationHistory)).scalar_one())

    today_start = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    today = int(
        db.execute(
            select(func.count())
            .select_from(CalculationHistory)
            .where(CalculationHistory.created_at >= today_start)
        ).scalar_one()
    )
    favorites = int(
        db.execute(
            select(func.count())
            .select_from(CalculationHistory)
            .where(CalculationHistory.is_favorite.is_(True))
        ).scalar_one()
    )
    unique_expressions = int(
        db.execute(select(func.count(func.distinct(CalculationHistory.expression)))).scalar_one()
    )

    # 运算符频次：表达式规模有限，取最近 2000 条在应用层统计即可，
    # 避免为了一个展示性指标引入数据库方言相关的字符串函数。
    expressions = db.execute(
        select(CalculationHistory.expression)
        .order_by(CalculationHistory.id.desc())
        .limit(2000)
    ).scalars()
    usage: dict[str, int] = {operator: 0 for operator in OPERATORS}
    for expression in expressions:
        for operator in OPERATORS:
            usage[operator] += expression.count(operator)
    usage = {key: value for key, value in usage.items() if value > 0}

    most_used = max(usage.items(), key=lambda item: item[1])[0] if usage else None
    last_record = db.execute(
        select(CalculationHistory.created_at).order_by(CalculationHistory.id.desc()).limit(1)
    ).scalar_one_or_none()

    return {
        "total": total,
        "today": today,
        "favorites": favorites,
        "unique_expressions": unique_expressions,
        "most_used_operator": most_used,
        "operator_usage": usage,
        "last_calculated_at": last_record.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(last_record, datetime)
        else None,
    }
