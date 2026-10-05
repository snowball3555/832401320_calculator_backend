"""pytest 公共夹具。

这里把 ``DATABASE_URL`` 换成内存 SQLite 后再导入应用，保证：

* 测试不会污染开发用的 ``calculator.db``；
* 每个测试用例拿到一个独立的会话，用例之间互不影响。
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SQL_ECHO"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session():
    """每个用例一个内存数据库会话。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """把应用的数据库依赖替换成测试会话。"""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
