# ============================================================================
# 后端镜像：python:3.12-slim + FastAPI + Uvicorn
#
# 构建：docker build -t calculator-backend .
# 运行：docker run -p 8000:8000 -v calculator-data:/data calculator-backend
#
# 说明：
#   * 默认使用容器内 /data 下的 SQLite 文件，配合 -v 卷即可持久化；
#   * 同时预装 psycopg，设置 DATABASE_URL 为 PostgreSQL（如 Neon）连接串即可无缝切换；
#   * 以非 root 用户运行，符合最小权限原则。
# ============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# curl 用于 HEALTHCHECK；git 用于构建时拉取前端仓库（见下方 FRONTEND_DIR）
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "psycopg[binary]>=3.1,<4.0"

COPY . .

# 构建时把前端仓库克隆进来，交给后端**同源托管**（环境变量 FRONTEND_DIR）。
# 这样一次部署就同时提供「计算器页面 + /api/* + /docs」，只需要一个固定地址，
# 也天然没有跨域问题。前端仍是独立仓库、只通过 HTTP/JSON 通信，架构约束不变。
# 前端仓库必须是公开的（本项目两个仓库都是 public）。
ARG FRONTEND_REPO=https://github.com/snowball3555/832401320_calculator_frontend.git
RUN git clone --depth 1 "${FRONTEND_REPO}" /app/frontend \
    && rm -rf /app/frontend/.git
ENV FRONTEND_DIR=/app/frontend

# 数据目录与运行账号
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

USER appuser

# 容器内默认数据库路径（挂载 /data 卷即可持久化；改用 PostgreSQL 时覆盖此变量）
ENV DATABASE_URL=sqlite:////data/calculator.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
