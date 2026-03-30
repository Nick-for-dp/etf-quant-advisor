-- PostgreSQL Database Schema for ETF Quant Advisor
-- 面向右侧交易的ETF助手数据模型

-- 创建数据库（手动执行）
-- CREATE DATABASE etf_quant WITH ENCODING = 'UTF8';

-- -----------------------------------------------------------------------------
-- ETF基础信息表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etfs (
    etf_code VARCHAR(8) PRIMARY KEY,         -- ETF代码，如"510300"，8字符足够
    etf_name VARCHAR(50) NOT NULL,          -- ETF名称，中文通常20-30字符
    market VARCHAR(2) DEFAULT 'CN',         -- 市场：CN、US、HK等
    category VARCHAR(20),                   -- 类别：宽基、行业、商品等
    tracking_index VARCHAR(60),             -- 跟踪指数名称
    fund_company VARCHAR(30),               -- 基金公司简称
    aum DECIMAL(15, 2),                     -- 资产规模（亿元）
    expense_ratio DECIMAL(5, 4),            -- 费率（小数）
    inception_date DATE,                    -- 成立日期
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')
);

-- -----------------------------------------------------------------------------
-- ETF每日价格数据表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etf_quotes (
    etf_code VARCHAR(8) NOT NULL,
    trade_date DATE NOT NULL,

    -- 价格数据（OHLC）- 使用 _px 后缀避免与SQL/Python保留字冲突
    open_px DECIMAL(12, 4),
    high_px DECIMAL(12, 4),
    low_px DECIMAL(12, 4),
    close_px DECIMAL(12, 4),

    -- 成交量能
    volume BIGINT,
    amount DECIMAL(16, 2),                  -- 成交金额
    turnover DECIMAL(10, 4),                -- 换手率

    -- ETF特有指标
    nav DECIMAL(12, 4),                        -- 基金净值（单位净值）
    premium_rate DECIMAL(8, 6),             -- 溢价率（小数表示）

    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),

    PRIMARY KEY (etf_code, trade_date),
    FOREIGN KEY (etf_code) REFERENCES etfs(etf_code) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- 技术指标表（面向右侧交易优化）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etf_indicators (
    etf_code VARCHAR(8) NOT NULL,
    trade_date DATE NOT NULL,

    -- 均线指标（趋势判断）
    ma5 DECIMAL(12, 4),
    ma10 DECIMAL(12, 4),
    ma20 DECIMAL(12, 4),
    ma60 DECIMAL(12, 4),

    -- MACD指标（趋势动量）
    macd_dif DECIMAL(12, 4),
    macd_dea DECIMAL(12, 4),
    macd_bar DECIMAL(12, 4),

    -- RSI指标（超买超卖）
    rsi_6 DECIMAL(6, 2),
    rsi_12 DECIMAL(6, 2),
    rsi_24 DECIMAL(6, 2),

    -- 布林带（波动区间）
    boll_upper DECIMAL(12, 4),
    boll_mid DECIMAL(12, 4),
    boll_lower DECIMAL(12, 4),

    -- ATR指标（波动率，用于设置止损/目标价）
    atr_14 DECIMAL(12, 4),

    -- ADX指标（趋势强度，右侧交易核心）
    adx DECIMAL(6, 2),
    adx_plus_di DECIMAL(6, 2),
    adx_minus_di DECIMAL(6, 2),

    -- 成交量指标（趋势确认）
    volume_ma5 BIGINT,
    volume_ma20 BIGINT,
    volume_ratio DECIMAL(6, 2),             -- 量比

    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),

    PRIMARY KEY (etf_code, trade_date),
    FOREIGN KEY (etf_code) REFERENCES etfs(etf_code) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- 策略配置表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(30) NOT NULL,     -- 策略名称
    strategy_desc VARCHAR(200),             -- 策略描述（控制长度）
    strategy_type VARCHAR(12) NOT NULL,     -- RIGHT_TREND / BREAKOUT / PULLBACK

    -- 策略参数（JSON格式，灵活配置）
    params JSONB DEFAULT '{}',

    -- 风控参数
    default_position_pct DECIMAL(4, 3) DEFAULT 0.3,     -- 默认仓位 30%
    default_stop_loss_pct DECIMAL(5, 4) DEFAULT 0.05,   -- 默认止损 5%
    default_target_pct DECIMAL(5, 4) DEFAULT 0.15,      -- 默认目标 15%

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')
);

-- -----------------------------------------------------------------------------
-- 交易信号表（核心：记录助手生成的建议）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    etf_code VARCHAR(8) NOT NULL,
    strategy_id INTEGER,                    -- 关联策略

    -- 信号基本信息
    signal_type VARCHAR(6) NOT NULL,        -- BUY / SELL / HOLD
    time_frame VARCHAR(4) DEFAULT '1D',     -- 1D / 60M / 15M

    -- 触发条件（生成信号时的市场状态）
    trigger_price DECIMAL(12, 4) NOT NULL,  -- 信号触发时的价格
    trigger_condition VARCHAR(200),         -- 触发条件描述

    -- 建议参数（助手输出的核心建议）
    suggested_entry DECIMAL(12, 4),         -- 建议入场价
    stop_loss DECIMAL(12, 4),               -- 建议止损价
    target_price DECIMAL(12, 4),            -- 建议目标价
    position_pct DECIMAL(4, 3),             -- 建议仓位比例

    -- 信号质量
    confidence DECIMAL(3, 2),               -- 置信度 0-1
    invalidation_price DECIMAL(12, 4),      -- 信号失效价

    -- 有效期
    valid_until DATE,                       -- 信号有效期至

    -- 信号状态 - 使用 signal_status 避免与SQL保留字冲突
    signal_status VARCHAR(12) DEFAULT 'PENDING',   -- PENDING / ACTIVE / EXPIRED / TRIGGERED / INVALIDATED

    -- 元信息
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),
    notes VARCHAR(500),                     -- 备注（控制长度）

    FOREIGN KEY (etf_code) REFERENCES etfs(etf_code) ON DELETE CASCADE,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE SET NULL
);

-- -----------------------------------------------------------------------------
-- 信号性能追踪表（自动生成复盘数据）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_performance (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER NOT NULL,
    etf_code VARCHAR(8) NOT NULL,                 -- ETF代码，冗余存储便于查询

    -- 追踪状态
    hold_start_date DATE,                         -- 持仓开始日期（reference_price对应的日期）
    performance_status VARCHAR(16) DEFAULT 'pending_init',  -- 追踪状态：pending_init/active/completed/expired

    -- 基准价格（信号生成时的价格）
    reference_price DECIMAL(12, 4),

    -- 后续表现（相对于 reference_price 的涨跌幅）
    return_1d DECIMAL(6, 4),                -- 1日收益
    return_3d DECIMAL(6, 4),                -- 3日收益
    return_5d DECIMAL(6, 4),                -- 5日收益
    return_10d DECIMAL(6, 4),               -- 10日收益
    return_20d DECIMAL(6, 4),               -- 20日收益

    -- 极值追踪（持仓后N日内的极值）
    max_price_1d DECIMAL(12, 4),            -- 1日内最高价
    min_price_1d DECIMAL(12, 4),            -- 1日内最低价
    max_price_3d DECIMAL(12, 4),            -- 3日内最高价
    min_price_3d DECIMAL(12, 4),            -- 3日内最低价
    max_price_5d DECIMAL(12, 4),            -- 5日内最高价
    min_price_5d DECIMAL(12, 4),            -- 5日内最低价
    max_price_10d DECIMAL(12, 4),           -- 10日内最高价
    min_price_10d DECIMAL(12, 4),           -- 10日内最低价
    max_price_20d DECIMAL(12, 4),           -- 20日内最高价
    min_price_20d DECIMAL(12, 4),           -- 20日内最低价

    -- 目标达成情况
    hit_target BOOLEAN DEFAULT FALSE,       -- 是否触及目标价
    hit_target_days INTEGER,                -- 触及目标所需天数
    hit_stop_loss BOOLEAN DEFAULT FALSE,    -- 是否触及止损
    hit_stop_loss_days INTEGER,             -- 触及止损所需天数

    -- 最大回撤
    max_drawdown_5d DECIMAL(6, 4),          -- 5日最大回撤
    max_drawdown_20d DECIMAL(6, 4),         -- 20日最大回撤

    -- 实际执行（用户可选录入）
    executed_price DECIMAL(12, 4),          -- 实际执行价
    executed_at TIMESTAMP,                  -- 实际执行时间
    executed_return DECIMAL(6, 4),          -- 实际收益

    -- 评分（系统根据表现自动评分）
    score INTEGER CHECK (score BETWEEN 1 AND 10),

    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'),

    FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- 索引优化
-- -----------------------------------------------------------------------------
-- ETF查询索引
CREATE INDEX IF NOT EXISTS idx_etfs_category ON etfs(category);

-- 价格数据索引
CREATE INDEX IF NOT EXISTS idx_quotes_date ON etf_quotes(trade_date);
CREATE INDEX IF NOT EXISTS idx_quotes_etf_date ON etf_quotes(etf_code, trade_date);

-- 技术指标索引
CREATE INDEX IF NOT EXISTS idx_indicators_date ON etf_indicators(trade_date);
CREATE INDEX IF NOT EXISTS idx_indicators_adx ON etf_indicators(adx);

-- 信号查询索引（更新字段名）
CREATE INDEX IF NOT EXISTS idx_signals_etf ON signals(etf_code);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(signal_status);      -- 更新为 signal_status
CREATE INDEX IF NOT EXISTS idx_signals_generated ON signals(generated_at);
CREATE INDEX IF NOT EXISTS idx_signals_etf_status ON signals(etf_code, signal_status); -- 更新为 signal_status

-- 信号性能追踪索引
CREATE INDEX IF NOT EXISTS idx_performance_status ON signal_performance(performance_status);
CREATE INDEX IF NOT EXISTS idx_performance_etf_status ON signal_performance(etf_code, performance_status);

-- -----------------------------------------------------------------------------
-- 更新时间戳触发器
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_etfs_updated_at BEFORE UPDATE ON etfs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_signal_performance_updated_at BEFORE UPDATE ON signal_performance
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 插入默认策略数据
-- -----------------------------------------------------------------------------
INSERT INTO strategies (strategy_name, strategy_desc, strategy_type, params) VALUES
('右侧趋势跟随', '趋势确认后入场，ADX>25且价格站上MA20', 'RIGHT_TREND', '{"ma_period": 20, "adx_threshold": 25, "volume_confirm": true}'),
('突破策略', '价格突破20日高点且放量1.5倍以上', 'BREAKOUT', '{"lookback_days": 20, "breakout_threshold": 0.02, "volume_surge": 1.5}'),
('均线回踩', '趋势向上时回踩MA20支撑买入', 'PULLBACK', '{"trend_ma": 60, "entry_ma": 20, "max_pullback": 0.05}')
ON CONFLICT DO NOTHING;
