"""FastAPI 应用入口：应用工厂、中间件、全局异常处理、可选静态前端托管。

请求处理链路::

    HTTP 请求
      → CORS 中间件（前后端分离必需，允许浏览器跨域调用）
      → 计时中间件（给响应加 X-Process-Time-Ms，便于演示性能）
      → 路由 → Controller（协议层）
                → Service（业务层：解析 / 求值 / 历史记录 / 换算）
                  → SQLAlchemy ORM → SQLite / PostgreSQL
      ← 统一 JSON 响应，或由全局异常处理器转换成 {success:false, error_code, message}
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.controllers import calculate_controller, history_controller, meta_controller
from app.core import config
from app.db.database import init_db
from app.utils.errors import CalculatorError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")

API_DESCRIPTION = """
前后端分离计算器系统的后端服务（软件工程实践第一次作业）。

* **计算全部在后端完成**：前端只发送表达式字符串，后端负责词法分析、语法分析、求值、
  异常处理与历史落库；项目中使用手写递归下降解析器，**没有使用 eval / exec**。
* **历史记录持久化**：每次成功计算写入数据库（默认 SQLite，可通过 `DATABASE_URL` 切换 PostgreSQL）。
* **统一响应格式**：成功返回 `{"success": true, ...}`；
  失败返回 `{"success": false, "error_code": ..., "message": ...}`。
"""


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用启动时建表（幂等），保证首次运行无需手工初始化数据库。"""
    init_db()
    logger.info("数据库已就绪：%s", config.DATABASE_URL)
    yield


def _register_exception_handlers(app: FastAPI) -> None:
    """把所有异常翻译成统一的 JSON 错误响应。"""

    @app.exception_handler(CalculatorError)
    async def calculator_error_handler(_request: Request, exc: CalculatorError) -> JSONResponse:
        """业务异常：表达式非法、除数为 0、记录不存在……"""
        logger.warning("业务异常 %s: %s", exc.error_code, exc.message)
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """参数校验失败：给出"哪个字段、为什么"的具体说明。"""
        details = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            details.append(f"{location or '请求体'}: {error.get('msg', '校验失败')}")
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "message": "请求参数不合法",
                "detail": "；".join(details),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """框架层异常：404 路径不存在、405 方法不允许……"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期的异常也要返回规范结构，同时把堆栈写进日志便于排查。"""
        logger.exception("未处理的服务器异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误，请稍后重试",
            },
        )


def create_app() -> FastAPI:
    """应用工厂：便于测试时创建独立实例。"""
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        description=API_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # --- CORS：前后端分离部署在不同域名时必须显式放行 ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time-Ms"],
    )

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    _register_exception_handlers(app)

    # --- 路由注册 ---
    app.include_router(meta_controller.router)
    app.include_router(calculate_controller.router)
    app.include_router(history_controller.router)

    frontend_dir = Path(config.FRONTEND_DIR) if config.FRONTEND_DIR else None
    frontend_ready = bool(frontend_dir and frontend_dir.is_dir())

    if not frontend_ready:

        @app.get("/", tags=["系统"], summary="服务信息")
        def service_info() -> dict:
            """未托管前端时，根路径返回服务信息与接口导航。"""
            return {
                "success": True,
                "app": config.APP_NAME,
                "version": config.APP_VERSION,
                "message": "计算器后端服务已启动，接口文档见 /docs",
                "endpoints": {
                    "计算": "POST /api/calculate",
                    "语法分析": "POST /api/parse",
                    "历史列表": "GET /api/history",
                    "删除历史": "DELETE /api/history/{id}",
                    "清空历史": "DELETE /api/history",
                    "统计": "GET /api/history/stats",
                    "进制转换": "POST /api/convert/base",
                    "单位换算": "POST /api/convert/unit",
                    "元数据": "GET /api/meta/functions",
                    "健康检查": "GET /api/health",
                },
            }

    @app.get("/api", tags=["系统"], summary="接口导航")
    def api_index() -> dict:
        return {
            "success": True,
            "openapi": "/openapi.json",
            "docs": "/docs",
            "redoc": "/redoc",
        }

    if frontend_ready:
        # 单地址演示用：把前端静态文件挂在根路径。
        # 注意：前端是**独立仓库**，两者只通过 HTTP/JSON 通信；
        # 这里托管静态文件只是为了省掉一个域名，不影响前后端分离架构。
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        logger.info("已挂载静态前端目录：%s", frontend_dir)

    return app


app = create_app()
