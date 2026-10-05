"""软件工程实践第一次作业 —— 前后端分离计算器系统（后端）。

分层结构::

    app/
    ├── controllers/   接口层：只负责 HTTP 协议、参数绑定、状态码
    ├── services/      业务层：表达式解析求值、历史记录、单位/进制换算
    ├── db/            数据层：SQLAlchemy 引擎、会话、ORM 模型
    ├── schemas/       数据契约层：Pydantic 请求/响应模型
    ├── core/          配置
    └── utils/         通用工具与异常体系
"""

__version__ = "1.0.0"
