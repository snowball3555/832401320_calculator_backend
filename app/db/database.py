"""数据库引擎与会话管理。

设计要点
--------
1. **数据库无关**：连接串由环境变量 ``DATABASE_URL`` 决定。默认 SQLite（零配置、便于助教
   一键运行），生产环境换成 PostgreSQL 只需改一个环境变量，业务代码一行都不用动。
2. **方言归一化**：Render / Neon 之类平台常给出 ``postgres://`` 前缀，SQLAlchemy 不认，
   这里统一改写成 ``postgresql+psycopg://``。
3. **SQLite 调优**：开启 WAL 日志与外键约束。WAL 允许"读写并发"，避免前端轮询历史记录时
   与写入操作互相阻塞（部署演示时前端会定时刷新）。
4. **会话即依赖**：``get_db`` 作为 FastAPI 的 ``Depends`` 注入，每个请求一个会话，
   请求结束自动关闭；测试里可以用 ``app.dependency_overrides`` 换成内存数据库。
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core import config


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def normalize_database_url(url: str) -> str:
    """把平台提供的连接串改写成 SQLAlchemy 认识的方言前缀。"""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_db_engine(url: str | None = None) -> Engine:
    """按连接串创建引擎。"""
    database_url = normalize_database_url(url or config.DATABASE_URL)

    options: dict = {"echo": config.SQL_ECHO, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        # check_same_thread=False：FastAPI 的同步视图会在线程池里执行，连接需要跨线程使用
        options["connect_args"] = {"check_same_thread": False}

    engine = create_engine(database_url, **options)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


engine: Engine = create_db_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(target_engine: Engine | None = None) -> None:
    """建表（幂等）。应用启动时调用。"""
    # 导入模型以完成 ORM 映射注册，否则 create_all 看不到任何表
    from app.db import models  # noqa: F401  pylint: disable=unused-import

    Base.metadata.create_all(bind=target_engine or engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
