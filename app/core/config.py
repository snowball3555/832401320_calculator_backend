"""应用配置。

所有可配置项都通过环境变量注入，遵循"12-Factor App"原则，
使同一份代码可以在本地、Docker、Render/Neon 等环境中无缝切换。

环境变量一览：
    APP_NAME            应用名（默认 Front-back Separated Calculator API）
    APP_VERSION         版本号
    HOST / PORT         监听地址与端口
    DATABASE_URL        数据库连接串，默认 sqlite:///./calculator.db
    CORS_ORIGINS        允许跨域的前端地址，逗号分隔，默认 *（前后端分离必需）
    FRONTEND_DIR        可选的静态前端目录；设置后后端会顺带托管前端，便于单地址演示
    SQL_ECHO            是否打印 SQL（调试用）
    TIMEZONE_OFFSET     记录时间使用的时区偏移（小时），默认 8（东八区）
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

APP_NAME = os.getenv("APP_NAME", "Front-back Separated Calculator API")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

DEFAULT_SQLITE_URL = f"sqlite:///{(BASE_DIR / 'calculator.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

CORS_ORIGINS = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]

FRONTEND_DIR = os.getenv("FRONTEND_DIR", "")

SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in {"1", "true", "yes"}

TIMEZONE_OFFSET = int(os.getenv("TIMEZONE_OFFSET", "8"))


def cors_allow_all() -> bool:
    """``CORS_ORIGINS`` 为 ``*`` 时返回 True。"""
    return "*" in CORS_ORIGINS
