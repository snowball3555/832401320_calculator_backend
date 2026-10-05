-- ============================================================================
-- 计算历史表初始化脚本（SQLite 版）
--
-- 说明：应用启动时会通过 SQLAlchemy 自动建表（幂等），本脚本用于「手工初始化」
--       或「审阅表结构」，两种方式等价。
--
-- 字段说明：
--   id              主键，自增
--   expression      计算表达式
--   result          计算结果（展示用字符串，避免浮点精度丢失）
--   result_numeric  计算结果（数值形式，便于统计与排序）
--   is_favorite     是否收藏（扩展功能）
--   created_at      计算时间（UTC+8）
--
-- PostgreSQL 版本差异（如需迁移）：
--   1) INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
--   2) FLOAT → DOUBLE PRECISION
--   3) DATETIME → TIMESTAMP
--   4) CREATE INDEX IF NOT EXISTS 同样支持
--   5) 可额外使用 COMMENT ON COLUMN ... IS '...' 添加字段注释
-- ============================================================================

CREATE TABLE IF NOT EXISTS calculation_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    expression      VARCHAR(512) NOT NULL,
    result          VARCHAR(128) NOT NULL,
    result_numeric  FLOAT,
    is_favorite     BOOLEAN      NOT NULL DEFAULT 0,
    created_at      DATETIME     NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_calculation_history_created_at
    ON calculation_history (created_at);

CREATE INDEX IF NOT EXISTS ix_calculation_history_created_at_id
    ON calculation_history (created_at, id);

-- 示例数据（可选，便于演示时立刻看到历史列表）
-- INSERT INTO calculation_history (expression, result, result_numeric, created_at)
-- VALUES ('1+2', '3', 3, '2026-10-01 10:20:00'),
--        ('5*8', '40', 40, '2026-10-01 10:21:00'),
--        ('(2+3)*4', '20', 20, '2026-10-01 10:22:00');
