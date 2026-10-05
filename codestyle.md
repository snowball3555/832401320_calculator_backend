# 代码规范（codestyle.md）

本文说明**本后端仓库实际遵守**的编码规范，每条规则都配本仓库的真实代码片段作为正例。
所有片段均取自当前仓库源码（省略号 `...` 表示省略的无关行），可对照文件自行核对。

---

## 1. 规范来源与取舍

### 1.1 主要来源

| 来源 | 采纳的部分 |
| --- | --- |
| **PEP 8 —— Style Guide for Python Code** | 4 空格缩进、`snake_case` 函数与变量、`PascalCase` 类名、`UPPER_SNAKE_CASE` 常量、导入分组与绝对导入、运算符两侧留空格、模块/类/函数之间空行 |
| **Google Python Style Guide** | 模块级 docstring、公开函数必须写 docstring 并说明参数与返回、`if __name__ == "__main__"` 保护、优先使用显式导入而非通配导入、坚持“为读者写代码”的注释原则 |
| **PEP 484 / PEP 585 / PEP 604** | 全量类型注解、内置泛型 `list[str]` / `dict[str, int]`、联合类型 `int \| float` |
| **PEP 257** | docstring 使用三引号、首行为一句话摘要、与代码同缩进 |
| **PEP 20（The Zen of Python）** | 显式优于隐式、扁平优于嵌套、可读性很重要——体现在“错误码显式声明”“魔法数字集中定义”等取舍上 |
| **PEP 8 的 79 列 / Google 的 80 列** | **不采纳**，理由见 1.2 |

### 1.2 本项目在两者基础上的取舍

| 规范点 | PEP 8 / Google | 本项目实际做法 | 取舍理由 |
| --- | --- | --- | --- |
| 行宽上限 | 79 / 80 字符 | **110**，由 ruff 强制（见 4.1） | 中文 docstring 与带 `description` 的 `Field(...)` 在 80 列下会被切得极碎；110 列在 1080p 双栏编辑器下仍可完整阅读。`app/` 下实测最长 108 列 |
| 注释语言 | 英文 | **中文** | 交付对象是中文助教与评阅人；错误提示、docstring、注释全部中文，便于直接阅读与演示 |
| 行内注释对齐 | PEP 8 建议至少两个空格 | 遵循 | 统一 `代码  # 注释`，特殊情况用 `# noqa` / `# pragma: no cover` 说明原因 |
| 例外处理 | 宽泛 `except` 通常被禁止 | 允许但**必须**给出理由注释 | 仅出现在健康检查与兜底异常处理器，且均带 `# noqa: BLE001` 或 docstring 说明 |
| 文档字符串风格 | Google 的 `Args:` / `Returns:` 分节 | **散文式中文说明** + 设计理由 | 本项目函数签名简单（多为 1~2 个参数），分节反而啰嗦；把篇幅留给“为什么这样设计” |
| 单文件规模 | 建议拆分 | `expression_parser.py` 425 行、`calculator_service.py` 272 行 | 解析器与求值器各自内聚（AST 定义 + 文法产生式必须放在一起），拆开反而增加跳转成本 |
| 工具强制 | 建议接 ruff / black | **已接入 ruff**：`pyproject.toml` 声明规则集 `E,W,F,I,UP,B` 与行宽 110，`ruff check .` 输出 `All checks passed!` | 规范应当**可被机器校验**，而不是只靠文字约定；`ruff format` 未强制重排（原因见下） |

---

## 2. 命名规范

| 对象 | 规则 | 正例 |
| --- | --- | --- |
| 模块 / 包 | 全小写 `snake_case`，有意义的名词 | `expression_lexer.py`、`history_service.py` |
| 类 | `PascalCase` | `ExpressionParser`、`CalculationHistory` |
| 常量 | `UPPER_SNAKE_CASE`，集中在模块顶部 | `MAX_EXPRESSION_LENGTH`、`DEFAULT_SQLITE_URL` |
| 函数 / 方法 | `snake_case`，动词或动词短语 | `parse_expression`、`normalize_number`、`convert_base` |
| 私有实现 | 单下划线前缀，表示“不对外承诺” | `_power`、`_escape_like`、`_register_exception_handlers` |
| 数据类字段 | `snake_case`，单位或语义后缀 | `result_numeric`、`elapsed_ms`、`node_count` |
| 布尔量 | 用 `is_` / `has_` / `only` 等前缀，读起来像判断句 | `is_favorite`、`favorite_only`、`frontend_ready` |

**正例 1** —— 私有函数前缀 + 常量上划线命名（`app/services/calculator_service.py:40` 与 `:138`，两处节选）：

```python
# 双精度浮点的十进制指数上限（约 1e308）
_MAX_DECIMAL_EXPONENT = 308.0
```

```python
def _apply_binary(operator: str, left: float, right: float) -> float:
    """执行一个二元运算。"""
    if operator == "+":
        result = left + right
    elif operator == "-":
        result = left - right
    elif operator == "*":
        result = left * right
    elif operator == "/":
        if right == 0:
            raise DivisionByZeroError("除数不能为 0")
        result = left / right
```

**正例 2** —— `PascalCase` 类名 + `UPPER_SNAKE_CASE` 常量集中定义（`app/services/math_functions.py:37`）：

```python
_TAN_GUARD_EPSILON = 1e-12
_FACTORIAL_MAX = 170  # 170! 已接近双精度浮点上限（约 7.26e306）


def _tan(x: float) -> float:
    """正切函数；cos(x)≈0 时按"该点无定义"处理，而不是返回 1.6e16 这种误导性数值。"""
    if abs(math.cos(x)) < _TAN_GUARD_EPSILON:
        raise ValueError("tan 在该角度处无定义（cos 为 0）")
    return math.tan(x)
```

---

## 3. 导入规范

规则：

1. 每个模块首行是 `from __future__ import annotations`（见第 5 节）。
2. 之后按 **标准库 → 第三方 → 本项目** 三组排列，组间空一行；**不使用相对导入**（统一 `from app.xxx import yyy`）。
3. 每行只导入一个模块（`from x import a, b` 形式仅用于同一模块内的多个名字，按字母序排列；
   名字较多或过长时改写为带括号的多行形式）。
4. 函数内部导入仅用于**打破循环依赖**，并必须写明原因注释。

**正例** —— 标准库 / 第三方 / 本项目三段式（`app/services/calculator_service.py:13`；下面**只摘录分组骨架**，
首个本项目导入实际写作多行 `from app.services.expression_parser import (` + 按字母序排列的名字 + `)`）：

```python
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from app.services.math_functions import FUNCTIONS
from app.utils.errors import (
    CalculatorError,
    DivisionByZeroError,
    ExpressionSyntaxError,
    MathDomainError,
    NumericOverflowError,
)
```

> 实际代码中第三组按模块名字母序排列：`expression_parser` → `math_functions` → `utils.errors`；
> 同一模块导入多个名字时若超出 110 列，改用带括号的多行形式（上面即为 `calculator_service.py` 的真实写法）。

**正例** —— 打破循环依赖的局部导入（`app/services/calculator_service.py:241`）：

```python
    from app.services.expression_lexer import normalize_expression  # 局部导入避免循环依赖
```

> `history_service.py`、`converter_service.py` 等模块均遵循同样的三段式。整个仓库**只有一处**局部导入
> （就是上面这个，原因是 `calculator_service` 与 `expression_lexer` 互相需要对方的公开函数）；
> 其余导入一律放在模块顶部。

---

## 4. 行宽、缩进与格式

### 4.1 行宽上限 110 列

- 缩进：**4 个空格**，不使用 Tab（全仓库无 Tab）；续行使用与开括号对齐或 4 空格悬挂缩进。
- 行宽：**上限 110 列**，由 `pyproject.toml` 的 `[tool.ruff] line-length = 110` **强制校验**，
  不是口头约定。`app/` 下实测最长行 108 列，全部代码通过检查。

**校验命令**（两条命令都应通过，这是可复核的证据）：

```bash
pip install ruff
ruff check .          # → All checks passed!
python -m pytest -q   # → 279 passed
```

> **有意声明的例外**：`pyproject.toml` 里对 `tests/*` 关闭了 `E501`（`per-file-ignores`）。
> 原因是 `@pytest.mark.parametrize` 的参数列表一旦按行拆开，反而更难一眼核对输入与期望的对应关系；
> 这是**写在配置里的显式取舍**，而不是悄悄放过超长行。
>
> 另外，`ruff format` 没有被用于强制重排。原因是本文档（codestyle.md）逐字引用了源码片段，
> 自动重排会让文档与源码脱节；**静态检查（`ruff check`）才是本项目的强制门禁**。

**正例** —— 长调用按参数拆行，保持每行远低于上限（`app/db/database.py:65`）：

```python
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
```

```python
    records, total, pages = history_service.list_records(
        db, keyword=keyword, favorite_only=favorite_only, page=page, page_size=page_size
    )
```

### 4.2 空行

- 顶层类 / 函数之间空 **2 行**，方法之间空 **1 行**。
- 逻辑段落之间空 1 行；用 `# ---` 分隔线划分“结果规范化 / 求值 / 对外 API”这类大段落。

**正例** —— 段落分隔线（`app/services/calculator_service.py:105`）：

```python
# ---------------------------------------------------------------------------
# 求值
# ---------------------------------------------------------------------------
def _power(base: float, exponent: float) -> float:
```

---

## 5. 类型注解

规则：

1. 所有模块首行 `from __future__ import annotations`，使 `int | None` 这类写法在 3.10 下无需 `typing.Optional`。
2. 使用**内置泛型**（`list[str]`、`dict[str, int]`、`tuple[...]`），不写 `typing.List` / `typing.Dict`。
3. 使用 `X | None` 而不是 `Optional[X]`；返回“无返回”标注 `-> None`。
4. 函数必须标注**全部**参数与返回值；`self` / `cls` 除外。
5. 只作为容器元素或外部契约的复杂类型才允许 `Any`，且尽量收窄。

**正例 1** —— `from __future__ import annotations` + 具体类型（`app/db/database.py:15`）：

```python
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core import config
```

**正例 2** —— 内置泛型与联合类型（`app/db/database.py:76`）：

```python
def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

**正例 3** —— 元组返回 + 可空字段（`app/services/history_service.py:59`）：

```python
def list_records(
    db: Session,
    *,
    keyword: str | None = None,
    favorite_only: bool = False,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[CalculationHistory], int, int]:
    """分页查询历史记录，返回 (当前页数据, 总条数, 总页数)。"""
```

---

## 6. 文档字符串（docstring）

规则：

1. **每个模块**都有模块级 docstring：一句话说明模块职责，必要时补充设计理由。
2. **每个公开类与函数**都有 docstring；私有函数在逻辑不直观时也要写。
3. 使用三引号、首行为一句话摘要，与代码同缩进。
4. 中文书写，重点解释**设计理由与取舍**，而不是复述函数名。
5. 文件内的模块 docstring 可用 reStructuredText 的 `::` 代码块与 `----` 分节，让 `help()` 与 IDE 悬停可读。

**正例 1** —— 模块级 docstring 交代设计理由（`app/db/database.py:1`，节选）：

```python
"""数据库引擎与会话管理。

设计要点
--------
1. **数据库无关**：连接串由环境变量 ``DATABASE_URL`` 决定。默认 SQLite（零配置、便于助教
   一键运行），生产环境换成 PostgreSQL 只需改一个环境变量，业务代码一行都不用动。
"""
```

**正例 2** —— 类 docstring 说明“本类不做什么”（`app/services/expression_parser.py:159`）：

```python
class ExpressionParser:
    """把 Token 序列解析成 AST。

    解析器自身不计算任何结果，只负责"结构是否正确"；
    求值交给 :mod:`app.services.calculator_service`，职责分离，便于分别测试。
    """
```

**正例 3** —— 函数 docstring 解释“为什么这样取值”（`app/db/models.py:35`）：

```python
def now_local() -> datetime:
    """返回东八区当前挂钟时间（naive）。"""
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)
```

---

## 7. 分层与依赖方向

架构：`controllers`（协议层）→ `services`（业务层）→ `db` / `schemas` / `utils`（基础设施）。
**依赖方向单向，禁止反向依赖，也禁止跨层回跳**。

| 层次 | 目录 | 允许导入 | 禁止导入 |
| --- | --- | --- | --- |
| 接口层 | `app/controllers/` | `services`、`schemas`、`db.database`、`utils.errors` | 不得写业务算法；不得直接写 SQL |
| 业务层 | `app/services/` | 同层模块、`db`、`utils.errors`、`core.config` | **不得导入 `controllers` / `fastapi`** |
| 数据层 | `app/db/` | `sqlalchemy`、`core.config`、`utils.errors` | 不得导入 `services` / `controllers` |
| 契约层 | `app/schemas/` | `pydantic` | 不得导入其它 app 子包（保持零依赖） |
| 通用 | `app/utils/errors.py` | 仅标准库 | 不得导入任何 app 子包（避免循环） |

**正例** —— 控制器只做绑定与封装，不出现算法与 SQL（`app/controllers/calculate_controller.py:46`）：

```python
def calculate(
    payload: CalculateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> CalculateResponse:
    """核心计算接口。"""
    result = calculator_service.calculate(payload.expression)

    history_id: int | None = None
    if payload.save_history:
        numeric = float(result.result)
```

> 依赖注入统一用 `Annotated[Session, Depends(get_db)]` 而不是把 `Depends(...)` 写进参数默认值：
> 后者会被 `flake8-bugbear` 报 `B008`（在默认参数里执行函数调用），而且 `Annotated` 形式
> 能让静态检查器正确推断 `db` 的类型。

**正例** —— 业务层不感知 HTTP（`app/services/history_service.py:46`，只抛业务异常，由接口层统一翻译）：

```python
def get_record(db: Session, record_id: int) -> CalculationHistory:
    """按主键取一条记录，不存在则抛 404 业务异常。"""
    record = db.get(CalculationHistory, record_id)
    if record is None:
        raise ResourceNotFoundError(f"历史记录 {record_id} 不存在")
    return record
```

---

## 8. 异常处理规范

规则：

1. 业务异常**必须**继承 `CalculatorError`，并声明 `http_status`、`error_code`、`default_message`
   三要素；`error_code` 是给前端做差异化提示用的稳定标识。
2. **不向上抛裸 `ValueError`**：把标准库异常在业务边界处翻译成本项目异常，并保留原始异常链（`from exc`）。
3. **不吞异常**：捕获后必须重新抛出、记录日志或给出可展示的中文提示；确需宽泛捕获时必须写明原因注释。
4. 异常处理器集中在 `app/main.py`，控制器里**不写重复的 `try/except`**。

**正例 1** —— 异常基类携带 `http_status` 与 `error_code`（`app/utils/errors.py:17`）：

```python
class CalculatorError(Exception):
    """所有计算相关异常的基类。"""

    http_status = 400
    error_code = "CALCULATOR_ERROR"
    default_message = "计算失败"

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)
```

**正例 2** —— 子类只改三要素，不重复实现（`app/utils/errors.py:36`）：

```python
class ExpressionSyntaxError(CalculatorError):
    """表达式语法错误：非法字符、括号不匹配、运算符缺失操作数等。"""

    error_code = "INVALID_EXPRESSION"
    default_message = "表达式非法，请检查后重试"
```

**正例 3** —— 把标准库异常翻译成业务异常并保留异常链（`app/services/calculator_service.py:130`）：

```python
    try:
        return math.pow(base, exponent)
    except OverflowError as exc:
        raise NumericOverflowError("幂运算结果超出可表示范围") from exc
    except ValueError as exc:
        raise MathDomainError("幂运算在实数范围内无意义") from exc
```

**正例 4** —— 宽泛捕获必须写理由（`app/controllers/meta_controller.py:29`）：

```python
    try:
        db.execute(text("SELECT 1"))
        database = "connected"
    except Exception:  # noqa: BLE001 - 健康检查不应因数据库异常而抛错
        database = "error"
```

**正例 5** —— 全局处理器集中翻译，日志留痕（`app/main.py:60`）：

```python
    @app.exception_handler(CalculatorError)
    async def calculator_error_handler(_request: Request, exc: CalculatorError) -> JSONResponse:
        """业务异常：表达式非法、除数为 0、记录不存在……"""
        logger.warning("业务异常 %s: %s", exc.error_code, exc.message)
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())
```

---

## 9. 数据库与 ORM（SQLAlchemy 2.0 风格）

规则：

1. 模型继承 `Base(DeclarativeBase)`，字段用 `Mapped[...]` + `mapped_column(...)`，让类型注解与列定义一致。
2. 查询使用 `select()` 表达式 + `db.execute(...).scalars()`，**不使用** 1.x 的 `Query.query()`。
3. 删除用 `delete()` 表达式；按主键取用 `db.get(Model, pk)`。
4. 会话通过 `Depends(get_db)` 注入，一处创建一处关闭（`try/finally`）。
5. 建表统一走 `Base.metadata.create_all()`，幂等；模型必须在建表前导入以完成映射注册。
6. 索引与列注释写在模型里，说明“为什么加这个索引”。

**正例 1** —— 2.0 风格模型定义与索引（`app/db/models.py:40`）：

```python
class CalculationHistory(Base):
    """一条计算历史记录。"""

    __tablename__ = "calculation_history"
    __table_args__ = (
        # 历史列表默认按时间倒序 + 主键倒序，联合索引可以直接支撑排序与分页
        Index("ix_calculation_history_created_at_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
```

**正例 2** —— `select()` 而非 `query()`（`app/services/history_service.py:88`）：

```python
    data_query = select(CalculationHistory)
    if conditions:
        data_query = data_query.where(*conditions)
    data_query = (
        data_query.order_by(CalculationHistory.created_at.desc(), CalculationHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = list(db.execute(data_query).scalars().all())
```

**正例 3** —— 建表前显式导入模型，并说明原因（`app/db/database.py:68`）：

```python
def init_db(target_engine: Engine | None = None) -> None:
    """建表（幂等）。应用启动时调用。"""
    # 导入模型以完成 ORM 映射注册，否则 create_all 看不到任何表
    from app.db import models  # noqa: F401  pylint: disable=unused-import

    Base.metadata.create_all(bind=target_engine or engine)
```

---

## 10. 数据契约（Pydantic v2 风格）

规则：

1. 请求 / 响应模型集中在 `app/schemas/`，控制器不直接收发裸 `dict`。
2. 用 `Annotated[T, Field(...)]` 承载约束与描述，让约束出现在 `/docs` 的 Swagger UI 中。
3. 示例数据用 `model_config = ConfigDict(json_schema_extra={...})`，不用 v1 的 `class Config`。
4. 成功响应用 `Literal[True] = True` 固定 `success` 字段，保证响应结构稳定。

**正例 1** —— v2 的 `ConfigDict` + `Annotated` 约束（`app/schemas/calculator.py:49`）：

```python
class CalculateRequest(BaseModel):
    """计算请求：**只传表达式，不传结果**。"""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"expression": "(1+2)*3", "save_history": True}]}
    )

    expression: Annotated[str, Field(min_length=1, max_length=500, description="数学表达式")]
    save_history: Annotated[bool, Field(description="是否把本次计算写入历史记录")] = True
```

**正例 2** —— 错误响应契约固定为 `success: Literal[False]`（`app/schemas/calculator.py:24`）：

```python
class ErrorResponse(BaseModel):
    """统一的错误响应体（由全局异常处理器产出）。"""

    success: Literal[False] = False
    error_code: str = Field(description="机器可读的错误码，如 INVALID_EXPRESSION", examples=["DIVISION_BY_ZERO"])
    message: str = Field(description="可直接展示给用户的中文提示", examples=["除数不能为 0"])
    detail: str | None = Field(default=None, description="可选的补充说明")
```

---

## 11. 常量与魔法数字

规则：

1. 所有具有阈值含义的数字必须是**具名常量**，集中定义在模块顶部，并注释来源或依据。
2. 常量命名说明“限制什么”，例如 `MAX_EXPRESSION_LENGTH` 而不是 `LIMIT1`。
3. 视图层要用到的常量通过接口暴露，而不是让前端复制一份（如 `/api/meta/functions`）。

**正例 1** —— 防御性上限集中定义并统一注释（`app/services/expression_lexer.py:25`）：

```python
# ---------------------------------------------------------------------------
# 防御性限制：把"恶意/异常输入"挡在解析之前，避免 CPU 与内存被拖垮
# ---------------------------------------------------------------------------
MAX_EXPRESSION_LENGTH = 500
MAX_TOKEN_COUNT = 300
MAX_NESTING_DEPTH = 32
MAX_NODE_COUNT = 200
```

**正例 2** —— 常量直接拼进中文错误消息，避免消息与阈值不一致（`app/services/expression_lexer.py:108`）：

```python
    if len(src) > MAX_EXPRESSION_LENGTH:
        raise ExpressionTooComplexError(
            f"表达式长度不能超过 {MAX_EXPRESSION_LENGTH} 个字符（当前 {len(src)}）"
        )
```

**正例 3** —— 环境变量默认值也走常量，避免“魔法字符串”散落（`app/core/config.py:22`）：

```python
BASE_DIR = Path(__file__).resolve().parents[2]

APP_NAME = os.getenv("APP_NAME", "Front-back Separated Calculator API")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
```

---

## 12. 注释原则

规则：注释解释 **为什么**（设计理由、被否决的方案、边界条件的来源），不复述代码“做了什么”；
对非直觉的实现（浮点误差、隐式乘法限制、SQLite PRAGMA）必须留注释。

**正例 1** —— 解释“为什么这样排序”而不是“这里在排序”（`app/db/models.py:45`）：

```python
        # 历史列表默认按时间倒序 + 主键倒序，联合索引可以直接支撑排序与分页
        Index("ix_calculation_history_created_at_id", "created_at", "id"),
```

**正例 2** —— 解释“为什么刻意禁止某种写法”（`app/services/expression_parser.py:254`）：

```python
            # 隐式乘法：2pi、3(4+5)、(1+2)(3+4)、2sin(1)
            # 刻意**不允许** "2 3" 这种两个裸数字相邻的写法，保持与主流计算器一致，
            # 避免用户输入 "12 8" 时被静默算成 96。
            following = self._peek()
```

**正例 3** —— 解释浮点误差的处理动机（`app/services/calculator_service.py:80`）：

```python
    """把浮点结果整理成"人看起来舒服"的形式。

    浮点误差是绕不开的：``0.1 + 0.2`` 在 IEEE-754 下等于 ``0.30000000000000004``。
    计算器不能把这个值直接丢给用户，所以这里统一按 **12 位有效数字**收敛后再输出，
    同时如果结果在误差范围内是整数，就返回 ``int``，让前端显示 ``20`` 而不是 ``20.0``。
    """
```

**正例 4** —— 解释“为什么在应用层统计”（`app/services/history_service.py:154`）：

```python
    # 运算符频次：表达式规模有限，取最近 2000 条在应用层统计即可，
    # 避免为了一个展示性指标引入数据库方言相关的字符串函数。
```

---

## 13. 日志规范

规则：

1. 使用标准库 `logging`，**不使用 `print`**（`run.py` 的启动横幅是唯一的例外——那是面向人的交互输出，不是日志）。
2. `main.py` 统一 `logging.basicConfig` 一次，格式为 `时间 | 级别 | logger 名 | 消息`；模块内用
   `logging.getLogger("app")` 取得 logger。
3. 日志级别语义：`info` 启动/就绪事件，`warning` 业务异常（用户可控的错误，非系统故障），
   `exception` 未预期异常（自动带堆栈）。
4. 日志消息用**惰性 % 格式化**（`logger.warning("...%s", value)`），不做 f-string 预拼接。

**正例 1** —— 日志初始化与惰性格式化（`app/main.py:33`）：

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")
```

**正例 2** —— 业务异常用 `warning`、未预期异常用 `exception`（`app/main.py:95`）：

```python
    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期的异常也要返回规范结构，同时把堆栈写进日志便于排查。"""
        logger.exception("未处理的服务器异常: %s", exc)
```

---

## 14. 测试规范

规则：

1. 测试文件命名 `test_*.py`，测试函数命名 `test_*`，测试类 `Test*`（与 `pytest.ini` 一致）。
2. 用**类**按功能/主题组织用例（`TestFeature1BasicCalculation`、`TestErrorHandling`），而不是一长串平铺函数。
3. 多组输入的用例一律 `@pytest.mark.parametrize`，参数名写成元组 `("expression", "expected")` 便于失败时定位。
4. 公共夹具放 `conftest.py`，**先改环境变量再导入应用**（保证测试连内存库）；需要替换依赖时用 `app.dependency_overrides`。
5. 断言要具体：不仅断言状态码，还要断言 `error_code`、`success` 与消息非空。
6. 测试不依赖执行顺序，不污染开发数据库。

**正例 1** —— 参数化 + 断言错误码与状态码（`tests/test_api.py:78`）：

```python
    @pytest.mark.parametrize(
        ("expression", "error_code"),
        [
            ("1+", "INVALID_EXPRESSION"),
            ("((1+2)", "INVALID_EXPRESSION"),
            ("abc", "INVALID_EXPRESSION"),
            ("1/0", "DIVISION_BY_ZERO"),
            ("sqrt(-1)", "MATH_DOMAIN_ERROR"),
        ],
    )
    def test_errors_return_400_with_code(self, client, expression, error_code):
```

**正例 2** —— 夹具：先设环境变量，再导入应用并用 `StaticPool` 共享内存库（`tests/conftest.py:13`）：

```python
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SQL_ECHO"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
```

> 这里的 `# noqa: E402`（模块级导入不在文件顶部）是**刻意**的：必须在设置 `DATABASE_URL`
> 之后再导入 `app.main`，否则应用会绑定到开发用的 `calculator.db`。

**正例 3** —— 依赖覆盖夹具，用例结束自动还原（`tests/conftest.py:44`）：

```python
@pytest.fixture()
def client(db_session):
    """把应用的数据库依赖替换成测试会话。"""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
```

**正例 4** —— 用 `pytest.raises` 断言异常类型与业务字段（`tests/test_calculator_service.py:125`）：

```python
    @pytest.mark.parametrize("expression", ["1/0", "1/(2-2)", "5%0", "0^-1"])
    def test_division_by_zero(self, expression):
        with pytest.raises(DivisionByZeroError) as excinfo:
            calculate(expression)
        assert excinfo.value.error_code == "DIVISION_BY_ZERO"
        assert excinfo.value.http_status == 400
```

---

## 15. 已知偏离与改进项

以下是为保持文档诚实而列出的**现存偏离**，不影响功能，但新增代码不应继续扩大：

| 偏离 | 位置 | 说明 |
| --- | --- | --- |
| 测试文件关闭 `E501` | `pyproject.toml` 的 `per-file-ignores` | `tests/*` 不检查行宽，属显式声明的取舍（见 4.1） |
| 未强制 `ruff format` 重排 | 整个仓库 | 只把 `ruff check` 作为门禁；因为本文档逐字引用源码片段，自动重排会使文档与源码不一致 |
| docstring 未使用 Google 的 `Args:` 分节 | 全部模块 | 见 1.2 的取舍说明；参数含义靠签名与 `Field(description=...)` 表达 |

---

## 16. 提交前自检清单

- [ ] 命名：模块 `snake_case`、类 `PascalCase`、常量 `UPPER_SNAKE_CASE`、私有成员以 `_` 开头
- [ ] 每个模块首行都有 `from __future__ import annotations`
- [ ] 导入按“标准库 → 第三方 → 本项目”分组，组间空行，未使用相对导入
- [ ] 缩进 4 空格、无 Tab；新增行宽不超过 **110** 列
- [ ] 全部函数参数与返回值都有类型注解；泛型用 `list[str]`、可空用 `X | None`
- [ ] 新模块有模块级 docstring；新类/公开函数有中文 docstring，说明了设计理由
- [ ] 依赖方向正确：`controllers → services → db`，`services` 中未导入 `fastapi` 或 `controllers`
- [ ] 新业务异常继承 `CalculatorError` 并声明 `http_status` / `error_code` / `default_message`
- [ ] 未裸抛 `ValueError`；翻译标准库异常时使用 `raise ... from exc` 保留异常链
- [ ] 未吞异常；若必须宽泛捕获，已写明 `# noqa` 与原因
- [ ] 数据库查询用 `select()` 表达式，未使用 `Query.query()`；模型用 `Mapped` / `mapped_column`
- [ ] 请求/响应模型放在 `app/schemas/`，用 `ConfigDict` 与 `Field`/`Annotated` 声明约束与描述
- [ ] 阈值类数字已提取为具名常量并写注释，未散落魔法数字
- [ ] 注释解释“为什么”，而非复述代码
- [ ] 使用 `logging` 而非 `print`；日志用惰性 `%s` 格式化；异常用 `logger.exception` 带堆栈
- [ ] 新增测试按功能分类组织、多组输入用 `parametrize`、断言包含 `error_code` 等具体字段
- [ ] 测试通过：`python -m pytest`（当前基线 **279 passed**）
- [ ] 静态检查通过：`ruff check .`（当前输出 `All checks passed!`）
- [ ] 启动自检：`python run.py` 后 `/api/health` 返回 `"database": "connected"`，`/docs` 可打开
- [ ] 未提交 `.env`、`*.db` 及 `-wal` / `-shm` 等运行时产物（已在 `.gitignore` 中）
- [ ] 若改了环境变量或接口，已同步更新 `README.md`（配置表 / 接口清单 / 错误码表）
