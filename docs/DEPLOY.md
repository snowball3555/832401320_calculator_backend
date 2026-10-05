# 后端部署手册

本文覆盖四种部署方式，从"本机 30 秒跑起来"到"公网长期可访问"。
**助教评阅只需看第 1 节或第 2 节即可复现**；第 3、4 节是真正的公网部署方案。

| 方式 | 适用场景 | 是否需要账号 | 历史记录是否持久 |
| --- | --- | --- | --- |
| 1. 本机直接运行 | 本地开发、助教复现 | 否 | 是（本地 `calculator.db`） |
| 2. Docker 运行 | 环境隔离、演示 | 否 | 是（挂载 `/data` 卷） |
| 3. Render + Neon | 公网长期地址 | 需要（免费） | 是（PostgreSQL） |
| 4. cloudflared 快速隧道 | 免账号临时公网演示 | 否 | 是（本机 SQLite，但要保持开机） |

---

## 1. 本机直接运行

```bash
# 1) 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2) 安装依赖
pip install -r requirements.txt

# 3) 启动（默认 0.0.0.0:8000）
python run.py
```

启动后：

- 接口文档 <http://127.0.0.1:8000/docs>
- 健康检查 <http://127.0.0.1:8000/api/health>
- 数据库文件 `calculator.db` 会自动创建在项目根目录（首次启动时建表，幂等）

Windows PowerShell 里换端口与开发模式：

```powershell
$env:PORT=9000
$env:RELOAD="true"
python run.py
```

---

## 2. Docker 运行

```bash
docker build -t calculator-backend .

# SQLite（挂载卷保证历史记录不丢）
docker run -d --name calculator-api -p 8000:8000 \
  -v calculator-data:/data \
  calculator-backend

# 或者直接用 PostgreSQL
docker run -d --name calculator-api -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require" \
  calculator-backend
```

容器内已预装 `psycopg`，因此 SQLite 与 PostgreSQL 可以随时切换，无需改代码、无需重新构建。
`HEALTHCHECK` 会周期性请求 `/api/health`，`docker ps` 里可直接看到健康状态。

---

## 3. Render + Neon（推荐长期方案）

> 为什么不能只用 Render 免费实例的 SQLite？
> Render 免费实例的磁盘是**临时的**：重新部署或实例重启后文件系统会重置，
> `calculator.db` 连同历史记录一起消失，会直接影响"历史记录持久化"这一评分点。
> 因此把数据库放到外部的 Neon 免费 Postgres 上。

### 3.1 创建 Neon 数据库

1. 打开 <https://neon.tech> 注册（可用邮箱或 GitHub 账号，免费额度足够本项目）。
2. 新建 Project，区域选择离你最近的（如 `Asia Pacific (Singapore)`）。
3. 在 Dashboard 复制 **Connection string**，形如：

   ```text
   postgresql://neondb_owner:********@ep-cool-frog-a1b2c3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```

   注意：Neon 可能给出 `postgres://` 前缀，本项目会自动转换，不必手工改。

### 3.2 部署到 Render

1. 把后端仓库推到 GitHub。
2. Render 控制台 → **New +** → **Web Service**（或 **Blueprint**，本仓库已带 `render.yaml`）。
3. 选择该仓库，Runtime 选 **Docker**，Plan 选 **Free**。
4. 环境变量：

   | Key | Value |
   | --- | --- |
   | `DATABASE_URL` | 上一步复制的 Neon 连接串 |
   | `CORS_ORIGINS` | 前端地址；若前端由本服务托管则填 `*` |
   | `TIMEZONE_OFFSET` | `8` |

5. Health Check Path 填 `/api/health`，部署完成后访问
   `https://<你的服务名>.onrender.com/docs` 确认接口可用。

### 3.3 让后端顺带托管前端（可选，用于单地址演示）

把前端仓库的内容复制到后端镜像里，并设置：

```text
FRONTEND_DIR=/app/frontend
```

此时访问后端根地址 `/` 就是前端页面，前后端同源，不需要 CORS。
**注意**：这只是"部署便利"，两个仓库依然是独立的代码库，前端也完全可以独立部署
（见前端仓库的 `docs/DEPLOY.md`），两者只通过 HTTP/JSON 通信。

---

## 4. cloudflared 快速隧道（免账号公网演示）

适合"临时给助教一个能直接打开的公网地址"。

```powershell
# 1) 下载 cloudflared（Windows）
curl.exe -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# 2) 先启动后端（建议同时托管前端，这样一个地址就够了）
$env:FRONTEND_DIR="..\832401320_calculator_frontend"
$env:PORT="8000"
python run.py

# 3) 另开一个终端，起隧道
.\cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate
```

命令输出里会打印形如 `https://xxxx-xxxx-xxxx.trycloudflare.com` 的公网地址。

**必须知道的限制**：

- 快速隧道的地址是**临时的**，cloudflared 进程退出或电脑关机后立即失效，重启会得到**新地址**；
- 没有可用性承诺，Cloudflare 可能限流；
- 因此它只适合"演示期临时可达"，正式提交建议用第 3 节的 Render + Neon。

---

## 5. 数据库初始化与迁移

- **自动**：应用启动时执行 `Base.metadata.create_all()`，只建不改，幂等安全。
- **手工**：`sql/init_db.sql`（SQLite 版，文内含 PostgreSQL 差异说明）。
- **切换 PostgreSQL**：

  ```bash
  pip install -r requirements-postgres.txt
  export DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require"
  python run.py
  ```

  代码只依赖 SQLAlchemy ORM 与 `select()` 表达式，没有写任何 SQLite 方言 SQL，
  因此换库不需要改一行业务代码。

---

## 6. 排查清单

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `Address already in use` | 端口被占用 | 换 `PORT`，或结束占用进程：`netstat -ano \| findstr :8000` |
| 浏览器报 CORS 错误 | `CORS_ORIGINS` 没包含前端地址 | 加进白名单或设为 `*` |
| `sqlite3.OperationalError: attempt to write a readonly database` | 数据库文件所在目录无写权限（Docker 常见） | 确认 `/data` 卷已挂载且属主为容器用户 |
| 历史记录突然空了 | 免费实例磁盘被重置 | 改用 Neon PostgreSQL |
| 前端一直显示"后端离线" | 后端未启动 / 地址填错 | 打开 `/api/health` 确认，检查前端 `js/config.js` |
| 计算返回 400 | 表达式非法或除数为 0 | 属预期行为，响应体里有 `error_code` 与中文提示 |
