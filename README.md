# 前后端分离计算器系统 · 后端服务

软件工程实践第一次作业 —— 计算器系统的**后端仓库**（FastAPI）。

前端（`832401320_calculator_frontend`）只负责交互与展示：它把用户输入的表达式字符串发给本服务，
本服务完成**校验 → 词法分析 → 语法分析 → 求值 → 落库 → 返回结果**的完整链路。
**所有计算都在后端完成**，前端不参与任何数学运算。

> **安全声明（重要）**：本项目**完全没有** `eval` / `exec` / `compile` / `pickle` / `subprocess` 调用。
> 表达式由手写的词法分析器 + 递归下降语法分析器处理成一棵 AST，再按**白名单函数表**求值。
> 即使输入 `__import__('os').system('rm -rf /')`，也只会得到一条“非法字符”的语法错误（详见第 16 节）。

---

## 1. 项目介绍

| 环节 | 由谁完成 | 实现位置 |
| --- | --- | --- |
| 接收表达式 | 后端 | `POST /api/calculate` |
| 参数校验（长度/类型） | 后端 | `app/schemas/calculator.py`（Pydantic v2） |
| 词法分析（字符串 → Token） | 后端 | `app/services/expression_lexer.py` |
| 语法分析（Token → AST） | 后端 | `app/services/expression_parser.py` |
| 求值与数值规范化 | 后端 | `app/services/calculator_service.py` |
| 历史记录落库 | 后端 | `app/services/history_service.py` + `app/db/models.py` |
| 返回统一 JSON | 后端 | `app/controllers/*.py` + `app/main.py` 的异常处理器 |

核心接口的请求体**只有表达式**（`{"expression": "(1+2)*3"}`），响应体里带回计算结果、
规范化后的表达式、语法树节点数/深度与后端耗时，用于证明结果确实由服务端计算得出。
计算失败不会写入历史记录。

### 已实现的作业功能点

| 编号 | 要求 | 实现 |
| --- | --- | --- |
| 功能 1 | 基本运算（加、减、乘、除） | `app/services/calculator_service.py` 的 `_apply_binary` |
| 功能 2 | 复合表达式与错误处理 | 手写递归下降解析器 + 统一异常体系 `app/utils/errors.py` |
| 功能 3 | 历史记录持久化与查询 | `calculation_history` 表 + `GET /api/history`（分页/搜索/收藏过滤） |
| 功能 4 | 删除指定历史记录 | `DELETE /api/history/{record_id}`（不存在返回 404） |
| 扩展 | 科学计算、进制转换、单位换算、语法分析可视化、统计与收藏 | 见第 10、12 节 |

---

## 2. 技术栈

| 组件 | 版本 / 说明 | 备注 |
| --- | --- | --- |
| Python | **3.10+**，开发与测试验证于 **3.12.14** | 依赖写法用到 `X \| None`、内置泛型 `list[str]` |
| FastAPI | `>=0.115,<1.0`，实测 **0.142.2** | 自动生成 `/docs`、`/redoc`、`/openapi.json` |
| Uvicorn | `uvicorn[standard]>=0.30,<1.0`，实测 **0.54.0** | ASGI 服务器 |
| SQLAlchemy | `>=2.0,<3.0`，实测 **2.1.3** | 2.0 风格：`Mapped` / `mapped_column` / `select()` |
| Pydantic | `>=2.7,<3.0`，实测 **2.13.5** | v2 风格：`ConfigDict`、`Field`、`Annotated` |
| 数据库 | **默认 SQLite**（零配置），可通过 `DATABASE_URL` 切换 **PostgreSQL** | 切换方法见第 8 节 |
| 测试 | pytest（可选依赖），实测 **9.1.1** | 使用内存 SQLite，见第 13 节 |

数据库访问全部通过 SQLAlchemy ORM 与 `select()` 表达式，没有写任何 SQLite 专有 SQL，
因此换库不需要改一行业务代码。

---

## 3. 目录结构

```text
832401320_calculator_backend/
├── app/
│   ├── __init__.py                 包说明与版本号（__version__）
│   ├── main.py                     FastAPI 应用工厂：中间件、全局异常处理、可选静态前端托管
│   ├── controllers/                接口层：只做 HTTP 协议、参数绑定、状态码
│   │   ├── __init__.py
│   │   ├── calculate_controller.py POST /api/calculate、/api/parse、/api/convert/base、/api/convert/unit
│   │   ├── history_controller.py   GET/DELETE /api/history*、PATCH /api/history/{id}/favorite
│   │   └── meta_controller.py      GET /api/health、GET /api/meta/functions
│   ├── services/                   业务层：解析、求值、换算、历史读写
│   │   ├── __init__.py
│   │   ├── expression_lexer.py     词法分析 + 全角符号归一化 + 防御性上限常量
│   │   ├── expression_parser.py    递归下降语法分析 → AST，含节点数/深度统计
│   │   ├── calculator_service.py   AST 求值、浮点规范化、`9^9^9` 溢出预判
│   │   ├── math_functions.py       常量与函数白名单表（含参数个数、说明、示例）
│   │   ├── history_service.py      历史记录 CRUD、LIKE 搜索、分页、统计
│   │   ├── base_converter.py       2~36 进制互转（按位权展开 / 短除法）
│   │   └── converter_service.py    八大类单位换算（温度走仿射变换）
│   ├── db/                         数据层
│   │   ├── __init__.py
│   │   ├── database.py             引擎、会话、`get_db` 依赖、方言归一化、SQLite PRAGMA
│   │   └── models.py               ORM 模型 `CalculationHistory` 与 UTC+8 时间函数
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── calculator.py           Pydantic v2 请求/响应模型（接口自文档化）
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py               全部环境变量读取与默认值
│   └── utils/
│       ├── __init__.py
│       └── errors.py               统一异常体系（http_status + error_code + 中文 message）
├── tests/
│   ├── conftest.py                 pytest 夹具：内存 SQLite + 依赖覆盖
│   ├── test_api.py                 接口集成测试（走完整 HTTP）
│   ├── test_calculator_service.py  计算正确性、数值规范化、异常处理
│   └── test_expression_parser.py   词法与语法分析测试
├── sql/
│   └── init_db.sql                 手工建表脚本（SQLite 版，含 PostgreSQL 差异说明）
├── docs/
│   └── DEPLOY.md                   后端部署手册（本机 / Docker / Render+Neon / cloudflared）
├── Dockerfile                      后端镜像（python:3.12-slim、非 root、HEALTHCHECK）
├── .dockerignore                   镜像构建忽略清单（排除 .venv、*.db、docs、本 README 等）
├── render.yaml                     Render Blueprint（Docker 运行时 + 环境变量声明）
├── requirements.txt                运行依赖（psycopg 与 pytest 以注释形式给出）
├── requirements-postgres.txt       仅 PostgreSQL 驱动：psycopg[binary]
├── pytest.ini                      pytest 配置（pythonpath、testpaths、严格标记）
├── run.py                          本地启动脚本（读取 HOST/PORT/RELOAD/LOG_LEVEL）
├── README.md                       本文档
└── codestyle.md                    代码规范与提交前自检清单
```

> 运行后会在项目根目录生成 SQLite 文件 `calculator.db`（连同 `-wal` / `-shm` 旁文件），
> 它们已在 `.gitignore` 中被忽略，属于运行时产物，不入库。

---

## 4. 运行环境要求

- **Python 3.10 或更高**（开发与测试验证于 3.12.14；`requirements.txt` 注释中亦标注该下限）
- `pip`（随 Python 附带）
- 无需预装数据库：默认 SQLite 由 Python 标准库自带
- 可选：Docker（第 14 节）、PostgreSQL 服务与 `psycopg` 驱动（第 8 节）
- 可选：`pytest` 与 `httpx`（运行测试，第 13 节）
- 端口：默认 **8000**，被占用时用环境变量 `PORT` 更换

---

## 5. 安装方法

### 5.1 Windows PowerShell

```powershell
cd C:\path\to\832401320_calculator_backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> 若 PowerShell 拒绝执行激活脚本，可先执行
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`，
> 或直接用 `.\.venv\Scripts\python.exe run.py` 而跳过激活。

> **⚠️ Windows 常见陷阱：`python` 可能是"应用商店占位符"。**
> 如果 `python --version` **没有任何输出**（也没有报错），说明这个 `python` 是 Windows 的
> App Execution Alias，不是真正的解释器。此时请把上面所有命令里的 `python` 换成 **`py -3`**
> （Windows 官方启动器），例如：
>
> ```powershell
> py -3 -m venv .venv
> .\.venv\Scripts\python.exe -m pip install -r requirements.txt
> .\.venv\Scripts\python.exe run.py
> ```
>
> 本项目的三个一键启动脚本（`scripts/start-all.bat` / `.ps1` / `.sh`）都会**真的执行一次**候选
> 解释器来验证它可用，因此遇到这种情况会自动跳到 `py -3`，并在确实缺少依赖时给出可照抄的安装命令。

### 5.2 macOS / Linux

```bash
cd se-assignment1/832401320_calculator_backend

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5.3 可选依赖

```bash
pip install -r requirements-postgres.txt   # 使用 PostgreSQL 时必须
pip install pytest httpx                   # 运行测试时必须
```

---

## 6. 启动方法

三种方式等价，任选其一（都必须在**仓库根目录**执行，因为 `app` 是包）。

### 方式一：推荐 —— `python run.py`

```powershell
python run.py
```

启动脚本会打印服务地址、接口文档地址、数据库连接串与跨域白名单：

```text
========================================================================
  Front-back Separated Calculator API v1.0.0
  服务地址   http://127.0.0.1:8000
  接口文档   http://127.0.0.1:8000/docs
  数据库     sqlite:///C:/.../832401320_calculator_backend/calculator.db
  跨域白名单 *
========================================================================
```

### 方式二：直接用 uvicorn

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 方式三：开发模式（代码变更自动重启）

```powershell
# Windows PowerShell
$env:RELOAD = "true"; python run.py

# macOS / Linux
RELOAD=true python run.py
```

`RELOAD` 与 `LOG_LEVEL` 由 `run.py` 读取（不属于 `config.py` 的配置项）：

| 环境变量 | 默认值 | 含义 |
| --- | --- | --- |
| `RELOAD` | `false` | `1/true/yes` 时开启 uvicorn 热重载（开发用） |
| `LOG_LEVEL` | `info` | uvicorn 日志级别 |

启动后可访问：

- 接口文档（Swagger UI）：<http://127.0.0.1:8000/docs>
- 备选文档（ReDoc）：<http://127.0.0.1:8000/redoc>
- OpenAPI 描述：<http://127.0.0.1:8000/openapi.json>
- 健康检查：<http://127.0.0.1:8000/api/health>
- 接口导航：<http://127.0.0.1:8000/api>

> **根路径 `/` 的行为**：未设置 `FRONTEND_DIR` 时返回服务信息与接口导航 JSON；
> 设置且目录存在时改为托管前端静态文件（见第 9.3 节）。

---

## 7. 配置说明

所有配置项均通过**环境变量**注入（12-Factor 风格），代码位置：`app/core/config.py`。

| 环境变量 | 默认值 | 含义 |
| --- | --- | --- |
| `APP_NAME` | `Front-back Separated Calculator API` | 应用名，写入 OpenAPI 标题与 `/api/health` 响应 |
| `APP_VERSION` | `1.0.0` | 版本号，写入 OpenAPI 版本与 `/api/health` 响应 |
| `HOST` | `0.0.0.0` | 监听地址（`0.0.0.0` 允许局域网/容器外访问） |
| `PORT` | `8000` | 监听端口，必须是整数 |
| `DATABASE_URL` | `sqlite:///<仓库根>/calculator.db` | 数据库连接串；平台给出的 `postgres://` / `postgresql://` 会自动改写为 `postgresql+psycopg://` |
| `CORS_ORIGINS` | `*` | 允许跨域的前端地址，**逗号分隔**；`*` 表示放行全部（前后端分离必需） |
| `FRONTEND_DIR` | 空字符串 | 可选的静态前端目录；设置且存在时后端顺带托管前端，便于单地址演示 |
| `SQL_ECHO` | `false` | `1/true/yes` 时打印所有 SQL（调试用） |
| `TIMEZONE_OFFSET` | `8` | 历史记录时间使用的时区偏移（小时），默认东八区 |
| `RELOAD` | `false` | 仅 `run.py` 读取，开启热重载（开发用） |
| `LOG_LEVEL` | `info` | 仅 `run.py` 读取，uvicorn 日志级别 |

Windows PowerShell 设置示例：

```powershell
$env:PORT = "9000"
$env:SQL_ECHO = "true"
$env:CORS_ORIGINS = "http://127.0.0.1:5500,http://localhost:3000"
python run.py
```

macOS / Linux 设置示例：

```bash
PORT=9000 SQL_ECHO=true CORS_ORIGINS="http://127.0.0.1:5500" python run.py
```

> 提示：环境变量的值都是字符串，`PORT` 与 `TIMEZONE_OFFSET` 必须能被解析成整数，否则启动即报错。

---

## 8. 数据库初始化方法

### 8.1 自动建表（推荐，零操作）

应用启动时在 lifespan 中调用 `init_db()`，执行 `Base.metadata.create_all()`——**幂等**，
只建不改，重复启动不会报错也不会清空数据。首次运行即自动生成 `calculator.db`。

### 8.2 手工初始化（审阅表结构 / 复现用）

`sql/init_db.sql` 与自动建表等价。SQLite 下执行：

```powershell
# Windows（需要 sqlite3 命令行工具；没有也可直接用 Python）
sqlite3 calculator.db ".read sql/init_db.sql"

# macOS / Linux
sqlite3 calculator.db < sql/init_db.sql
```

脚本文件末尾附带了示例数据的 `INSERT` 语句（默认注释掉），演示时可取消注释。

### 8.3 表结构

```text
calculation_history
-------------------
id                INTEGER  主键，自增
expression        VARCHAR(512) NOT NULL   计算表达式（规范化后保存）
result            VARCHAR(128) NOT NULL   计算结果（展示用字符串，避免浮点精度丢失）
result_numeric    FLOAT    NULL           计算结果（数值形式，便于统计与排序）
is_favorite       BOOLEAN  NOT NULL 默认 0 是否收藏（扩展功能）
created_at        DATETIME NOT NULL       计算时间（UTC+8 挂钟时间）
```

索引：`created_at` 单列索引，以及 `(created_at, id)` 联合索引——历史列表默认按
“时间倒序 + 主键倒序”排序，联合索引可直接支撑排序与分页。

> 时间字段刻意存成 **UTC+8 的 naive datetime**：作业示例时间是 `2026-10-01 10:20:00` 这种无时区格式，
> 若用 `datetime.utcnow()`，部署在 UTC 环境（如 Render）时前端会看到差 8 小时的时间。

### 8.4 切换到 PostgreSQL

1. 安装驱动（或直接 `pip install -r requirements-postgres.txt`）：

   ```bash
   pip install "psycopg[binary]>=3.1,<4.0"
   ```

   `requirements.txt` 里也以注释形式给出了这一行，取消注释即可。

2. 设置连接串（`postgres://` 与 `postgresql://` 都会被自动改写为 `postgresql+psycopg://`，无需手工改）：

   ```powershell
   # Windows PowerShell
   $env:DATABASE_URL = "postgresql://user:password@host:5432/dbname?sslmode=require"
   python run.py
   ```

   ```bash
   # macOS / Linux
   export DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require"
   python run.py
   ```

3. 首次启动会自动在 PostgreSQL 中建表。若想手工执行，`sql/init_db.sql` 的文件头列出了
   需要替换的语法差异：`INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`、
   `FLOAT` → `DOUBLE PRECISION`、`DATETIME` → `TIMESTAMP`。

> 业务代码无需任何改动：数据层只用了 SQLAlchemy ORM 与 `select()` 表达式。
> 注意 SQLite 特有的调优（WAL、`check_same_thread=False`）由代码按连接串前缀自动跳过。

---

## 9. 前后端连接方法

前端是**独立仓库**（`se-assignment1/832401320_calculator_frontend`），两者只通过 HTTP/JSON 通信。

### 9.1 CORS 配置（后端侧）

前后端不同源时，浏览器会先发预检请求。后端在 `app/main.py` 中配置：

- `allow_origins` = `CORS_ORIGINS`（默认 `*`）
- `allow_credentials` = `False`
- `allow_methods` = `GET, POST, PATCH, DELETE, OPTIONS`
- `allow_headers` = `*`，`expose_headers` = `X-Process-Time-Ms`（前端可读取后端耗时）

本地开发若前端跑在别的端口（例如 VS Code Live Server 的 5500），推荐显式白名单：

```powershell
$env:CORS_ORIGINS = "http://127.0.0.1:5500,http://localhost:5500"
python run.py
```

### 9.2 前端侧填写 API 地址

前端**唯一需要按环境修改**的文件是 `js/config.js`：

```javascript
window.CALC_CONFIG = {
  API_BASE_URL: '',                       // 留空 = 与页面同源；分开部署时填后端地址
  API_CANDIDATES: [
    '',                                   // 同源
    'http://127.0.0.1:8000',              // 本机后端
    'http://localhost:8000'
  ],
  ...
};
```

- **分开部署**：把 `API_BASE_URL` 填成后端公网地址，例如 `https://xxx-calculator-api.onrender.com`
  （不要漏掉 `https://`，也不要带结尾 `/`），同时把该前端地址加入后端 `CORS_ORIGINS`。
- **同源部署 / 单地址演示**：`API_BASE_URL` 留空 `''`，前端按 `API_CANDIDATES` 顺序做健康探测，
  自动选中第一个能连通的地址（因此 `file://` 直接打开本地调试也能找到本机后端）。

### 9.3 同源部署：`FRONTEND_DIR` 的用法

设置 `FRONTEND_DIR` 指向前端仓库目录后，后端会把静态文件挂载在根路径，
此时前端页面与 API 同源，**不需要任何 CORS 配置**：

```powershell
# Windows PowerShell：先启动后端，一个地址即可演示前后端
$env:FRONTEND_DIR = "..\832401320_calculator_frontend"
python run.py
```

```bash
# macOS / Linux
FRONTEND_DIR=../832401320_calculator_frontend python run.py
```

效果：访问 <http://127.0.0.1:8000/> 直接打开前端页面，`/api/*` 仍是接口，
`/` 不再返回服务信息 JSON。

> 这只是“部署便利”，两个仓库依然是独立代码库，前端也完全可以独立部署。
> 若 `FRONTEND_DIR` 指向的目录不存在，后端会忽略它并回到“根路径返回服务信息”的行为。

---

## 10. API 接口清单

所有接口都以 `/api` 为前缀。成功响应统一带 `"success": true`。

| 方法 | 路径 | 说明 | 主要参数 | 成功 | 失败 |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/health` | 健康检查（顺带验证数据库连通性），前端据此显示在线状态 | — | 200 | — |
| GET | `/api/meta/functions` | 返回支持的常量、函数、单位类别与可用进制，供前端动态渲染 | — | 200 | — |
| POST | `/api/calculate` | **核心接口**：计算表达式，成功后写入历史记录 | Body：`expression`（1~500 字符）、`save_history`（默认 `true`） | 200 | 400 / 422 |
| POST | `/api/parse` | 只做语法分析，返回 Token 列表与 AST（扩展） | Body：`expression`（1~500 字符） | 200 | 400 / 422 |
| POST | `/api/convert/base` | 2~36 进制互转，小数最多保留 16 位并给出截断提示（扩展） | Body：`value`（1~64 字符）、`from_base`（2~36，默认 10）、`to_base`（2~36，默认 2） | 200 | 400 / 422 |
| POST | `/api/convert/unit` | 八大类单位换算（扩展） | Body：`value`、`category`、`from_unit`、`to_unit` | 200 | 400 / 422 |
| GET | `/api/history` | 分页查询历史（时间倒序），支持关键字模糊搜索与收藏过滤 | Query：`keyword`（≤100）、`favorite_only`、`page`（≥1）、`page_size`（1~100，默认 10） | 200 | 422 |
| GET | `/api/history/stats` | 统计：总量、今日、收藏、去重表达式数、运算符频次（扩展） | — | 200 | — |
| DELETE | `/api/history` | 清空历史；`favorite_only=true` 时只清收藏（扩展） | Query：`favorite_only` | 200 | — |
| DELETE | `/api/history/{record_id}` | **删除指定历史记录**；记录不存在返回 404 | Path：`record_id`（≥1） | 200 | 404 / 422 |
| PATCH | `/api/history/{record_id}/favorite` | 收藏 / 取消收藏；`is_favorite` 留空表示取反（扩展） | Path：`record_id`；Body：`is_favorite`（可空） | 200 | 404 / 422 |
| GET | `/` | 未托管前端时返回服务信息与接口导航；托管时返回前端页面 | — | 200 | — |
| GET | `/api` | 接口导航（`/docs`、`/redoc`、`/openapi.json`） | — | 200 | — |

状态码约定：`200` 成功；`400` 业务异常（表达式非法、除数为 0、数学定义域错误、换算参数错误）；
`404` 资源不存在；`422` 请求参数校验失败（框架层）；`500` 未预期异常。
响应头附带 `X-Process-Time-Ms`（后端处理耗时，毫秒）。

### 10.1 curl 示例（Windows PowerShell 可直接粘贴）

PowerShell 5.1 的 `Invoke-WebRequest` 在 4xx 时会抛异常且难以读取响应体，因此示例统一用
`curl.exe`（Windows 10/11 自带）。注意：PowerShell 中 JSON 用**单引号包裹**、内部双引号用 `\"` 转义。

**示例 1：基本计算（`12+8` → 20）**

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/calculate -H "Content-Type: application/json" -d '{\"expression\":\"12+8\"}'
```

```json
{"success":true,"expression":"12+8","raw_expression":"12+8","result":20,"result_display":"20",
 "history_id":1,"node_count":3,"max_depth":2,"elapsed_ms":0.031}
```

**示例 2：复合表达式 + 查看历史**

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/calculate -H "Content-Type: application/json" -d '{\"expression\":\"(1+2)*3\"}'

curl.exe -s "http://127.0.0.1:8000/api/history?page=1&page_size=5"
```

**示例 3：错误场景与删除记录（含非 2xx 响应）**

```powershell
# 除数为 0 → 400 DIVISION_BY_ZERO
curl.exe -s -w "`nHTTP %{http_code}`n" -X POST http://127.0.0.1:8000/api/calculate -H "Content-Type: application/json" -d '{\"expression\":\"1/0\"}'

# 删除不存在的记录 → 404 NOT_FOUND
curl.exe -s -w "`nHTTP %{http_code}`n" -X DELETE http://127.0.0.1:8000/api/history/999999
```

> macOS / Linux 下把 `\"` 换成 `"`、去掉反引号换行即可：
> `curl -s -X POST http://127.0.0.1:8000/api/calculate -H "Content-Type: application/json" -d '{"expression":"12+8"}'`

---

## 11. 统一响应格式与错误码

### 11.1 成功响应

```json
{
  "success": true,
  "expression": "(1+2)*3",
  "raw_expression": "(1+2)*3",
  "result": 9,
  "result_display": "9",
  "history_id": 13,
  "node_count": 5,
  "max_depth": 3,
  "elapsed_ms": 0.045
}
```

### 11.2 失败响应

所有异常都由 `app/main.py` 的全局处理器翻译成同一结构，前端只需写一套处理逻辑：

```json
{
  "success": false,
  "error_code": "DIVISION_BY_ZERO",
  "message": "除数不能为 0"
}
```

参数校验失败时额外带 `detail`，指出是哪个字段有问题：

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数不合法",
  "detail": "expression: String should have at least 1 character"
}
```

### 11.3 错误码表

错误码来源：`app/utils/errors.py`（业务异常）与 `app/main.py`（框架层与兜底异常）。
`error_code` 是稳定的机器可读标识，`message` 是可直接展示的中文提示。

| error_code | HTTP 状态码 | 触发场景 | 对应异常类 / 处理器 |
| --- | --- | --- | --- |
| `INVALID_EXPRESSION` | 400 | 非法字符、括号不匹配、末尾缺少操作数、未知函数名、参数个数不对、空表达式 | `ExpressionSyntaxError` |
| `EXPRESSION_TOO_COMPLEX` | 400 | 表达式超过 500 字符、Token 超过 300 个、嵌套超过 32 层、AST 节点超过 200 个 | `ExpressionTooComplexError` |
| `DIVISION_BY_ZERO` | 400 | 除数为 0、取模除数为 0、`0^-1` | `DivisionByZeroError` |
| `MATH_DOMAIN_ERROR` | 400 | `sqrt(-1)`、`ln(0)`、`asin(2)`、`tan(pi/2)`、`(-8)^0.5` | `MathDomainError` |
| `NUMERIC_OVERFLOW` | 400 | 结果超出双精度可表示范围，如 `1e308*10`、`9^9^9`、`factorial(171)` | `NumericOverflowError` |
| `NOT_FOUND` | 404 | 删除/操作不存在的历史记录 | `ResourceNotFoundError` |
| `CONVERSION_ERROR` | 400 | 进制不在 2~36、数字不属于该进制、未知单位类别或单位代码、开尔文为负 | `ConversionError` |
| `VALIDATION_ERROR` | 422 | 请求体/查询参数不符合 Pydantic 校验（缺字段、超长、越界） | `RequestValidationError` 处理器 |
| `INTERNAL_SERVER_ERROR` | 500 | 未预期异常（堆栈写入服务端日志，不返回给客户端） | 兜底 `Exception` 处理器 |
| `HTTP_<状态码>` | 同响应 | 框架层错误，如路径不存在返回 `HTTP_404`、方法不允许返回 `HTTP_405` | `StarletteHTTPException` 处理器 |
| `CALCULATOR_ERROR` | 400 | 基类兜底错误码（正常流程不会出现） | `CalculatorError` |

---

## 12. 支持的运算符、常量与函数

### 12.1 运算符

运算符与优先级定义在 `app/services/expression_parser.py` 的文法注释中。

| 运算符 | 含义 | 优先级 | 结合性 | 示例 |
| --- | --- | --- | --- | --- |
| `+` `-` | 二元加、减 | 1 | 左结合 | `12+8` → 20 |
| `*` `/` `%` | 乘、除、取模（C 语义，`math.fmod`） | 2 | 左结合 | `5%3` → 2 |
| 隐式乘法 | `2pi`、`3(4+5)`、`(1+2)(3+4)` | 2 | 左结合（与 `*` 同级） | `3(4+5)` → 27 |
| `+` `-` | 一元正负号（前缀，可叠加 `--5`） | 3 | 右结合 | `-5+8` → 3 |
| `^` | 幂运算（右结合，允许 `2^-1`） | 4 | 右结合 | `2^3^2` = `2^9` = 512 |
| `!` | 后缀阶乘（可叠加，`3!!` = `(3!)!`） | 5 | 后缀 | `3!` → 6、`3!!` → 720 |

补充规则：

- 幂运算比一元负号结合更紧，因此 `-2^2` = `-(2^2)` = **-4**，`(-2)^2` = **4**。
- **不允许两个裸数字相邻**：`2 3` 会被判为非法表达式，而不是静默算成 6（避免 `12 8` 之类的误输入被算错）。
- 函数名与常量名**不区分大小写**（解析时统一转小写）。
- 全角/显示符号会被自动归一化：`×` `✕` `⋅` `·` `＊` → `*`，`÷` `／` → `/`，`−` `–` `—` `－` → `-`，
  `＋` → `+`，`＾` → `^`，`！` → `!`，`％` → `%`，`（` `）` → `()`，`，` → `,`，`。` → `.`，`π` → `pi`。
- 数值字面量支持小数与科学计数法：`3.14`、`.5`、`1.5e-3`、`2E10`（`2e` 会被切成数字 `2` 与常量 `e`）。

### 12.2 常量

| 名称 | 值 | 说明 |
| --- | --- | --- |
| `pi` | 3.141592653589793 | 圆周率 π（`π` 字符亦可） |
| `e` | 2.718281828459045 | 自然常数 e |
| `tau` | 6.283185307179586 | 2π |
| `phi` | 1.618033988749895 | 黄金分割比 |

### 12.3 函数（共 29 个，白名单见 `app/services/math_functions.py`）

| 分类 | 函数 | 参数个数 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| 三角 | `sin` | 1 | 正弦（弧度） | `sin(pi/2)` = 1 |
| 三角 | `cos` | 1 | 余弦（弧度） | `cos(0)` = 1 |
| 三角 | `tan` | 1 | 正切（弧度）；`cos(x)≈0` 时报定义域错误 | `tan(pi/4)` = 1 |
| 三角 | `asin` | 1 | 反正弦，参数需在 `[-1,1]` | `asin(1)` = π/2 |
| 三角 | `acos` | 1 | 反余弦，参数需在 `[-1,1]` | `acos(1)` = 0 |
| 三角 | `atan` | 1 | 反正切 | `atan(1)` = π/4 |
| 三角 | `sinh` | 1 | 双曲正弦 | `sinh(1)` ≈ 1.1752 |
| 三角 | `cosh` | 1 | 双曲余弦 | `cosh(1)` ≈ 1.5431 |
| 三角 | `tanh` | 1 | 双曲正切 | `tanh(1)` ≈ 0.7616 |
| 三角 | `deg` | 1 | 弧度转角度 | `deg(pi)` = 180 |
| 三角 | `rad` | 1 | 角度转弧度 | `rad(180)` = π |
| 幂与根 | `sqrt` | 1 | 平方根，参数需 ≥ 0 | `sqrt(16)` = 4 |
| 幂与根 | `cbrt` | 1 | 立方根，支持负数 | `cbrt(-8)` = -2 |
| 幂与根 | `exp` | 1 | 自然指数 e^x | `exp(1)` = e |
| 幂与根 | `pow` | 2 | 幂运算，等价 `^`（复用除零与溢出保护） | `pow(2,10)` = 1024 |
| 幂与根 | `hypot` | ≥2 | 欧几里得范数 | `hypot(3,4)` = 5 |
| 对数 | `ln` | 1 | 自然对数，真数需 > 0 | `ln(e)` = 1 |
| 对数 | `log` | 1~2 | 单参数为常用对数（底 10）；双参数可指定底数 | `log(100)` = 2、`log(8,2)` = 3 |
| 对数 | `log10` | 1 | 以 10 为底的对数 | `log10(1000)` = 3 |
| 对数 | `log2` | 1 | 以 2 为底的对数 | `log2(8)` = 3 |
| 取整与符号 | `abs` | 1 | 绝对值 | `abs(-3)` = 3 |
| 取整与符号 | `floor` | 1 | 向下取整 | `floor(2.9)` = 2 |
| 取整与符号 | `ceil` | 1 | 向上取整 | `ceil(2.1)` = 3 |
| 取整与符号 | `round` | 1~2 | 四舍五入，可指定小数位（位数必须是整数） | `round(3.14159,2)` = 3.14 |
| 取整与符号 | `sign` | 1 | 符号函数 | `sign(-5)` = -1 |
| 取整与符号 | `factorial` | 1 | 阶乘，参数为 0~170 的整数 | `factorial(5)` = 120 |
| 统计 | `max` | ≥1 | 最大值 | `max(1,9,4)` = 9 |
| 统计 | `min` | ≥1 | 最小值 | `min(1,9,4)` = 1 |
| 统计 | `mod` | 2 | 取模，等价 `%`（复用除零保护） | `mod(10,3)` = 1 |

调用约定：

- 函数**必须带括号**，`sin 1` 会被拒绝并提示正确写法。
- 参数个数在**解析阶段**就会校验，`sin(1,2)`、`round(1,2,3)` 直接报 `INVALID_EXPRESSION`。
- 参数用逗号分隔，可用嵌套表达式：`max(sqrt(16), 2^3)`。
- 常量与函数清单也可通过 `GET /api/meta/functions` 获取（前端据此动态渲染，避免两边各维护一份）。

---

## 13. 测试方法

### 13.1 安装与运行

```powershell
pip install pytest httpx

python -m pytest            # 全部 279 个用例
python -m pytest -v         # 显示每个用例名
python -m pytest tests/test_api.py                       # 只跑接口测试
python -m pytest -k "division or overflow"               # 按关键字筛选
```

### 13.2 当前测试规模与覆盖点

实测 `pytest --collect-only` 结果：**279 个用例**（4 个测试文件、20 个测试类），语句覆盖率 **96%**。

| 文件 | 用例数 | 覆盖点 |
| --- | --- | --- |
| `tests/test_api.py` | 54 | 走完整 HTTP：健康检查、四项基本运算、复合表达式与优先级、非法表达式/除零/定义域错误的状态码与错误码、空表达式 422、历史落库与倒序、分页、关键字搜索、非法分页参数、删除指定记录、删除不存在记录 404、清空历史、收藏切换与过滤、统计、`/api/parse`、进制转换、单位换算、元数据、OpenAPI 与 `/docs`、未知路由结构化 404、CORS 预检 |
| `tests/test_calculator_service.py` | 80 | 基本运算、复合表达式、一元正负、小数与浮点误差规范化、整数结果不带 `.0`、幂/取模/阶乘/科学函数、隐式乘法、全角表达式、除零与定义域异常、溢出与 `9^9^9` 预判在 0.5 秒内返回、中文错误提示、`normalize_number` 展示格式、`inspect` 返回 AST 与 Token |
| `tests/test_expression_parser.py` | 35 | Token 切分与位置、数值字面量（含科学计数法）、`2e` 不被误切、全角符号归一化、空表达式与非法字符、超长表达式、优先级与括号、幂右结合、一元负号、隐式乘法、裸数字相邻被拒、函数节点与未知函数、代码式输入只报语法错、必须带括号调用、参数个数校验、超深嵌套与超多节点 |
| `tests/test_converters.py` | 110 | 进制：正负号、大小写、空格/下划线分隔、前导零、精确小数与无限循环小数的截断提示、尾随 0 裁剪、进制越界、多位小数点、非法字符、越界数字；单位：7 类比例换算 + 温度三温标互转 + 绝对零度边界、未知类别/未知单位、同单位恒等、公式文本、类别元数据结构；函数白名单：注册表规模与排序、参数个数描述的三条分支、`cbrt/sign/factorial/mod/tan/log/round` 各自的异常路径；以及以上错误经接口层翻译为 400/422 的验证 |

覆盖率实测（`python -m pytest --cov=app --cov-report=term-missing`，1094 条语句 / 未覆盖 46 条）：

| 模块 | 覆盖率 |
| --- | ---: |
| `services/converter_service.py`、`services/math_functions.py`、`schemas/calculator.py` | 100% |
| `services/base_converter.py` | 96%（补测前仅 61%） |
| `services/expression_parser.py` / `expression_lexer.py` | 94% / 99% |
| `services/calculator_service.py` | 92% |
| `main.py` / `db/database.py` | 91% / 84% |
| **合计** | **96%** |

未覆盖的 4% 集中在防御性分支（PostgreSQL 连接参数、未捕获异常兜底处理器等），属于"保留但不为凑数而构造测试"的部分。
这一轮补测直接抓出一个真实数值 bug：`convert_base("0.75", 10, 16)` 曾返回 `0.c0000000000008`（应为 `0.c`），
根因是小数按位累加导致的浮点误差累积，已改为"整数分子 ÷ 基的幂"并在渲染侧把收敛阈值从 `1e-15` 调整到 `1e-12`。

### 13.3 测试环境：内存 SQLite

`tests/conftest.py` 在**导入应用之前**把环境变量改成内存数据库，因此：

- 测试不会污染开发用的 `calculator.db`；
- 每个用例拿到独立的会话与引擎（`StaticPool` 保证同一内存库连接复用），用例之间互不影响；
- 通过 `app.dependency_overrides[get_db]` 把应用的数据库依赖替换成测试会话。

`pytest.ini` 的约定：`pythonpath = .`（保证能 `import app`）、`testpaths = tests`、
`python_classes = Test*`、`addopts = -q --strict-markers`，
并把 `app.*` 的 `DeprecationWarning` 提升为错误（防止使用过时 API）。

### 13.4 代码规范校验（ruff）

代码规范不只是文字约定，仓库根目录的 `pyproject.toml` 声明了可执行的检查规则
（规则集 `E,W,F,I,UP,B`，行宽 110，目标 `py310`），可直接复核：

```bash
pip install ruff
ruff check .            # → All checks passed!
```

说明两点取舍（详见 `codestyle.md` 第 4.1 与第 15 节）：

- `tests/*` 通过 `per-file-ignores` 关闭了 `E501`：`@pytest.mark.parametrize` 的参数列表
  拆行后反而更难核对；
- 只用 `ruff check` 作为门禁，**不用 `ruff format` 强制重排**，因为 `codestyle.md` 逐字引用了源码片段。

---

## 14. 部署方法

完整步骤见 **[docs/DEPLOY.md](docs/DEPLOY.md)**，覆盖四种方式：
本机直接运行、Docker、Render + Neon、cloudflared 临时隧道。这里只做简要说明。

| 文件 | 用途 |
| --- | --- |
| `Dockerfile` | 后端镜像：`python:3.12-slim`，预装运行依赖与 `psycopg`，以非 root 用户 `appuser` 运行，内置 `HEALTHCHECK` 轮询 `/api/health`；默认数据库为 `/data/calculator.db`（配合 `-v` 卷持久化），覆盖 `DATABASE_URL` 即可切换 PostgreSQL |
| `.dockerignore` | 构建上下文排除清单：`.venv`、`__pycache__`、`*.db`、`.env`、`docs/`、本 README 等，缩小镜像并避免把本地数据库与文档打进镜像 |
| `render.yaml` | Render Blueprint（方案 B）：`runtime: docker`、`plan: free`、`healthCheckPath: /api/health`，声明 `APP_NAME`/`HOST`/`PORT`/`CORS_ORIGINS`/`TIMEZONE_OFFSET`，`DATABASE_URL` 标记 `sync: false`（在控制台手工填写，不进仓库） |
| `requirements-postgres.txt` | PostgreSQL 驱动 `psycopg[binary]>=3.1,<4.0`，本地/容器安装用 |

快速上手：

```bash
# 本机
pip install -r requirements.txt && python run.py

# Docker（SQLite + 卷持久化）
docker build -t calculator-backend .
docker run -d --name calculator-api -p 8000:8000 -v calculator-data:/data calculator-backend
```

> **务必注意**：Render 等免费实例的文件系统是**临时的**，重新部署或实例重启后 SQLite 文件会丢失，
> 历史记录随之消失。要保证“历史记录持久化”可靠，请使用外部 PostgreSQL（如 Neon 免费实例）。

---

## 15. 常见问题（FAQ）

**Q1：启动报 `Address already in use` / 端口 8000 被占用怎么办？**

换端口即可（`run.py` 的打印会随之变化）：

```powershell
$env:PORT = "9000"; python run.py
```

或先查出占用进程再决定：

```powershell
netstat -ano | findstr :8000     # 记下最后一列 PID
tasklist | findstr <PID>
```

**Q2：浏览器控制台报 CORS 错误（`No 'Access-Control-Allow-Origin' header`）怎么办？**

后端默认 `CORS_ORIGINS=*` 已放行全部来源；若你手工改成了白名单，必须把**前端的完整源**
（协议 + 主机 + 端口，如 `http://127.0.0.1:5500`）加进去，`localhost` 与 `127.0.0.1` 视为不同源。
修改后需**重启后端**。另外注意：`file://` 直接打开的页面发送的预检请求也可能被浏览器拦截，
此时建议改用本地静态服务器或设置 `FRONTEND_DIR` 走同源。

**Q3：报 `sqlite3.OperationalError: attempt to write a readonly database`？**

说明数据库文件或所在目录当前用户没有写权限，常见于 Docker 挂载卷与只读文件系统：

- Docker：确认 `/data` 卷已挂载，且属主为容器内用户（本仓库镜像已 `chown` 给 `appuser`）；
- 本机：确认仓库目录未被设为只读、未被杀软锁定；
- 也可临时指定一个可写路径：`$env:DATABASE_URL = "sqlite:///C:/temp/calc.db"`。

**Q4：历史记录突然不见了？**

按概率从高到低排查：

1. **免费实例磁盘被重置**（Render 等）：SQLite 文件随实例重建消失，改用 PostgreSQL（第 8.4 节）。
2. **连到了另一个数据库**：`DATABASE_URL` 未设置时用的是仓库根目录的 `calculator.db`；
   在别的目录启动、或设置了不同 `DATABASE_URL`，就会看到“空历史”。启动日志会打印实际连接串。
3. **请求带了 `save_history: false`**：该次计算刻意不入库。
4. **计算失败**：只有成功计算才写历史，失败（如除零）不会产生记录。
5. **被清空了**：`DELETE /api/history` 会清空（带 `favorite_only=true` 时只清收藏），
   前端界面上也有“清空”按钮。

**Q5：前端一直显示“后端离线”？**

先直接访问 <http://127.0.0.1:8000/api/health> 确认后端在跑、返回 `"database": "connected"`；
再检查 `js/config.js` 里的 `API_BASE_URL` / `API_CANDIDATES` 是否指向了正确地址（第 9.2 节）。

**Q6：为什么长表达式被判非法？**

这是**故意的防御性限制**：表达式 ≤ 500 字符、Token ≤ 300、嵌套 ≤ 32 层、AST 节点 ≤ 200。
超过会返回 `EXPRESSION_TOO_COMPLEX`，用于防止超长输入拖垮服务（详见第 16 节）。

**Q7：`0.1+0.2` 为什么能返回 `0.3`？**

IEEE-754 下它是 `0.30000000000000004`。后端在 `normalize_number` 中按 **12 位有效数字**收敛后再输出，
误差范围内是整数时还返回 `int`，所以看到的是 `0.3` 而不是一长串小数、也不是 `20.0` 这种多余的小数点。

---

## 16. 安全说明

### 16.1 为什么不用 `eval` / `exec`

`eval("__import__('os').system('rm -rf /')")` 会真的执行系统命令，是最典型的远程代码执行（RCE）漏洞。
本项目的输入来自浏览器，绝不能当代码执行。因此：

- **全仓库没有** `eval` / `exec` / `compile` / `pickle` / `subprocess` / `os.system` 调用；
- 表达式只能被解释成“数学表达式”：先逐字符扫描成 Token，再由手写递归下降解析器构造 AST；
- 求值阶段只遍历 AST 并按**显式白名单函数表** `FUNCTIONS` 调用函数，其余名字一律在解析阶段报
  “未知的名称”；
- 解析器与求值器只抛出本项目的 `CalculatorError` 子类，**从不向上抛裸 `ValueError`**，
  避免把 Python 内部错误细节泄漏给客户端（标准库的 `math domain error` 会被替换成中文提示）。

效果：输入 `__import__('os').system('echo hi')` 只会得到
`{"success": false, "error_code": "INVALID_EXPRESSION", "message": "表达式中存在非法字符 ..."}`。

### 16.2 防御性限制（拒绝服务防护）

| 限制 | 数值 | 位置 | 触发时的错误码 |
| --- | --- | --- | --- |
| 表达式长度 | 500 字符 | `expression_lexer.MAX_EXPRESSION_LENGTH` | `EXPRESSION_TOO_COMPLEX` |
| Token 数量 | 300 个 | `expression_lexer.MAX_TOKEN_COUNT` | `EXPRESSION_TOO_COMPLEX` |
| 嵌套深度（括号/函数） | 32 层 | `expression_lexer.MAX_NESTING_DEPTH` | `EXPRESSION_TOO_COMPLEX` |
| AST 节点数 | 200 个 | `expression_lexer.MAX_NODE_COUNT` | `EXPRESSION_TOO_COMPLEX` |
| 请求体表达式长度 | 1~500 字符 | `schemas.calculator.CalculateRequest` | `VALIDATION_ERROR`（422） |
| 阶乘参数 | 0~170 的整数 | `math_functions._FACTORIAL_MAX` | `MATH_DOMAIN_ERROR` |
| 分页每页条数 | 1~100 | `history_service.MAX_PAGE_SIZE` | `VALIDATION_ERROR`（422） |
| 搜索关键字长度 | ≤ 100 字符 | `history_controller` 的 Query 约束 | `VALIDATION_ERROR`（422） |

**幂运算溢出预判**：`9^9^9` 这类输入如果在算完之后才检查，会长时间占满 CPU。
`calculator_service._power` 先用对数估算结果量级
（`|指数| × log10(|底数|) > 308` 即判定超出双精度上限），**在计算之前**就抛出 `NUMERIC_OVERFLOW`；
`0^-1`、`(-8)^0.5` 同样被提前拦下。单元测试专门断言该判断在 0.5 秒内返回。

其他数值防护：非有限结果（`inf` / `nan`）统一抛 `NumericOverflowError`；
温度换算会拒绝低于绝对零度的开尔文值。

### 16.3 数据层防护

- **LIKE 通配符转义**：历史搜索的关键字先经过 `history_service._escape_like`，
  把 `\` `%` `_` 转义后再拼成 `%keyword%`，并给 `ilike(..., escape="\\")`，
  避免用户输入的 `%` 变成“匹配任意内容”而拖慢查询或返回意外结果。
- **全参数化查询**：所有数据库访问都通过 SQLAlchemy ORM / `select()` 表达式构造，
  没有字符串拼接 SQL，天然免疫 SQL 注入。
- **ORM 字段约束**：`expression` 最长 512、`result` 最长 128，与接口层限制一致。
- **不返回堆栈**：未预期异常统一返回 `INTERNAL_SERVER_ERROR` 与固定中文提示，堆栈只写服务端日志。

### 16.4 前端 XSS 转义

历史记录中的表达式与结果**来自用户输入**，前端把它们渲染进 `innerHTML` 之前必须转义。
前端仓库 `js/ui.js` 提供了 `escapeHtml`，把 `& < > " '` 替换为 HTML 实体，
`js/history.js` 与 `js/tools.js` 在拼接 HTML 时对所有用户可控文本调用它
（其余纯文本输出统一用 `textContent`）。
结合第 16.2 节的限制，表达式本身不含引号、尖括号等字符（词法阶段即报非法字符），
形成前后端双层防护。

### 16.5 部署相关

- `.gitignore` 排除 `.env` / `.env.*`（可能含数据库密码）与 `*.db` 运行时产物，避免误提交；
- `render.yaml` 中 `DATABASE_URL` 使用 `sync: false`，连接串只在平台控制台填写；
- Docker 镜像以非 root 用户 `appuser` 运行，符合最小权限原则；
- `allow_credentials=False`，因此 CORS 即使设为 `*` 也不会携带凭证，不存在凭证跨域泄漏问题。
