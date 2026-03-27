-- 为 etf_quotes 表添加 trade_status 字段
-- 存储交易状态：0=停牌，1=正常交易
-- 与 baostock 返回的 tradestatus 字段保持一致

ALTER TABLE etf_quotes
ADD COLUMN IF NOT EXISTS trade_status INTEGER DEFAULT 1;

COMMENT ON COLUMN etf_quotes.trade_status IS '交易状态：0=停牌，1=正常交易';