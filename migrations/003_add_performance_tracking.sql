-- PostgreSQL Migration: 003_add_performance_tracking
-- 信号性能追踪功能增强
-- 新增字段：etf_code, hold_start_date, performance_status
-- 新增极值字段：max_price_1d/3d/10d, min_price_1d/3d/10d

-- -----------------------------------------------------------------------------
-- 新增字段
-- -----------------------------------------------------------------------------
-- ETF代码（冗余存储，便于查询）
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS etf_code VARCHAR(8);

-- 持仓开始日期（reference_price对应的日期）
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS hold_start_date DATE;

-- 追踪状态
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS performance_status VARCHAR(16) DEFAULT 'pending_init';

-- 极值追踪扩展字段
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS max_price_1d DECIMAL(12, 4);
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS min_price_1d DECIMAL(12, 4);
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS max_price_3d DECIMAL(12, 4);
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS min_price_3d DECIMAL(12, 4);
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS max_price_10d DECIMAL(12, 4);
ALTER TABLE signal_performance ADD COLUMN IF NOT EXISTS min_price_10d DECIMAL(12, 4);

-- -----------------------------------------------------------------------------
-- 从已有信号数据回填 etf_code
-- -----------------------------------------------------------------------------
UPDATE signal_performance sp
SET etf_code = s.etf_code
FROM signals s
WHERE sp.signal_id = s.id AND sp.etf_code IS NULL;

-- -----------------------------------------------------------------------------
-- 新增索引
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_performance_status ON signal_performance(performance_status);
CREATE INDEX IF NOT EXISTS idx_performance_etf_status ON signal_performance(etf_code, performance_status);

-- -----------------------------------------------------------------------------
-- 添加注释
-- -----------------------------------------------------------------------------
COMMENT ON COLUMN signal_performance.etf_code IS 'ETF代码，冗余存储便于查询';
COMMENT ON COLUMN signal_performance.hold_start_date IS '持仓开始日期（reference_price对应的日期）';
COMMENT ON COLUMN signal_performance.performance_status IS '追踪状态：pending_init/active/completed/expired';
COMMENT ON COLUMN signal_performance.max_price_1d IS '持仓后1日内最高价';
COMMENT ON COLUMN signal_performance.min_price_1d IS '持仓后1日内最低价';
COMMENT ON COLUMN signal_performance.max_price_3d IS '持仓后3日内最高价';
COMMENT ON COLUMN signal_performance.min_price_3d IS '持仓后3日内最低价';
COMMENT ON COLUMN signal_performance.max_price_10d IS '持仓后10日内最高价';
COMMENT ON COLUMN signal_performance.min_price_10d IS '持仓后10日内最低价';