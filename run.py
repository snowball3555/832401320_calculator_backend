"""本地启动脚本。

用法::

    python run.py                # 默认 0.0.0.0:8000
    PORT=9000 python run.py      # 换端口
    RELOAD=true python run.py    # 开发模式（代码变更自动重启）

Windows PowerShell::

    $env:PORT=9000; python run.py
"""

from __future__ import annotations

import os

import uvicorn

from app.core import config


def main() -> None:
    reload_enabled = os.getenv("RELOAD", "false").lower() in {"1", "true", "yes"}
    log_level = os.getenv("LOG_LEVEL", "info")

    print("=" * 72)
    print(f"  {config.APP_NAME} v{config.APP_VERSION}")
    print(f"  服务地址   http://127.0.0.1:{config.PORT}")
    print(f"  接口文档   http://127.0.0.1:{config.PORT}/docs")
    print(f"  数据库     {config.DATABASE_URL}")
    print(f"  跨域白名单 {', '.join(config.CORS_ORIGINS)}")
    print("=" * 72)

    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=reload_enabled,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
