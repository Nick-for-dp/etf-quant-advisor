# ETF Quant Advisor 开发计划

> 目标：两周内完成MVP版本，实现基础数据采集、技术指标计算、右侧交易信号生成。

---

## 第一周：数据基础设施

### Day 1 (周一)：项目初始化与环境搭建
- [x] 创建项目基础结构（已完成）
- [x] 配置Python 3.13.12虚拟环境（已完成）
- [x] 安装依赖：psycopg, sqlalchemy, akshare, pandas, numpy, baostock（已完成）
- [x] 配置PostgreSQL数据库（Docker或本地）（已完成）
- [x] 运行初始迁移脚本，创建表结构（已完成）
- [x] 验证数据库连接（已完成）

**交付物**：可运行的开发环境，数据库表已创建

### Day 2 (周二)：数据模型实现
- [x] 实现 `src/data/models/etf.py` - ETF基础信息模型（etfs表）（已完成）
- [x] 实现 `src/data/models/quote.py` - ETF价格数据模型（etf_quotes表，注意_px后缀字段）（已完成）
- [x] 实现 `src/data/models/indicator.py` - 技术指标模型（etf_indicators表，含ADX/ATR/布林带）（已完成）
- [x] 实现 `src/data/models/strategy.py` - 策略配置模型（strategies表）（已完成）
- [x] 实现 `src/data/models/signal.py` - 交易信号模型（signals表，含建议参数和状态）（已完成）
- [x] 实现 `src/data/models/performance.py` - 信号性能追踪模型（signal_performance表）（已完成）
- [x] 配置SQLAlchemy连接和会话管理（已完成，修复text()和utcnow）
- [x] 编写模型基础CRUD测试（已完成，全部测试通过）

**交付物**：完整的SQLAlchemy模型层，覆盖6张核心表

### Day 3 (周三)：AKShare数据源接入
- [x] 调研AKShare ETF接口：fund_etf_spot_em, fund_etf_hist_em（已完成）
- [x] 实现 `src/data/source/akshare_client.py` - AKShare客户端（已完成）
- [x] 实现日K线数据获取（含OHLCV、换手率、nav、溢价率）（已完成）
- [x] 实现ETF列表获取（已完成）
- [x] 添加数据清洗：处理停牌、异常值（已完成）
- [x] 添加请求限速（避免触发AKShare限制）（已完成）

**交付物**：可从AKShare获取ETF历史数据

### Day 4 (周四)：数据持久化实现
- [x] 实现 `src/data/repository/` - 数据仓库模式（已完成）
- [x] 实现批量写入价格数据（避免单条插入慢）（已完成）
- [x] 实现数据去重和更新逻辑（已完成）
- [x] 实现ETF基础信息同步（`src/data/service/etf_service.py`）（已完成）
- [x] 编写数据获取和存储的集成测试（已完成）

**交付物**：数据可自动获取并存储到PostgreSQL

### Day 5 (周五)：历史数据初始化
- [x] 编写 `scripts/init_history.py` - 历史数据初始化脚本（已完成）
- [x] 下载核心ETF的2年历史数据（510300, 512000, 513100等）（已完成）
- [x] 处理数据缺失情况（标记空缺、补全策略）（已完成）
- [x] 实现停牌日/周末填充逻辑，确保数据连续（已完成）
- [x] 验证数据完整性（已完成）
- [x] 编写数据质量检查脚本（已完成）

**交付物**：本地数据库包含完整历史数据，日期连续

### Day 6-7 (周末)：缓冲与优化
- [ ] 解决第一周遗留问题
- [ ] 代码Review和重构
- [ ] 补充单元测试
- [ ] 文档更新

---

## 第二周：分析与策略

### Day 8 (周一)：技术指标计算
- [ ] 实现 `src/analysis/indicators.py`
- [ ] 均线计算：MA5, MA10, MA20, MA60
- [ ] MACD计算：DIF, DEA, BAR
- [ ] RSI计算：RSI6, RSI12, RSI24
- [ ] 布林带计算：boll_upper, boll_mid, boll_lower
- [ ] ATR计算：atr_14（用于止损距离）
- [ ] ADX计算：adx, adx_plus_di, adx_minus_di（趋势强度核心）
- [ ] 成交量指标：volume_ma5, volume_ma20, volume_ratio
- [ ] 实现指标批量计算（pandas向量化）
- [ ] 实现指标结果存储到 `etf_indicators` 表

**交付物**：可自动计算并存储完整技术指标（含右侧交易核心指标ADX/ATR）

### Day 9 (周二)：右侧交易策略实现
- [ ] 实现 `src/strategy/right_side.py` - 右侧趋势跟随策略
- [ ] 买入信号逻辑（右侧交易核心）：
  - 趋势确认：ADX > 25（趋势强度足够）
  - 方向确认：+DI > -DI（上升趋势）
  - 价格确认：close > MA20（站上中期均线）
  - 成交量确认：volume_ratio > 1.2（放量）
  - 溢价率风控：premium < 3%
- [ ] 实现 `src/strategy/breakout.py` - 突破策略
  - 突破20日高点 + 放量
- [ ] 实现 `src/strategy/pullback.py` - 均线回踩策略
  - MA60向上 + 价格回踩MA20
- [ ] 信号生成：写入signals表（含suggested_entry, stop_loss, target_price）
- [ ] 信号强度评分：基于ADX、成交量、形态质量
- [ ] 实现信号性能自动追踪：写入signal_performance表

**交付物**：可生成带建议参数的BUY/SELL/HOLD信号

### Day 10 (周三)：溢价率风控集成
- [ ] 实现 `src/strategy/risk_control.py`
- [ ] 溢价率实时监控（>5%警告，>10%禁止买入）
- [ ] 折价机会识别（<-2%标记为机会）
- [ ] IOPV缺失时的估算逻辑
- [ ] 将风控规则整合到信号生成流程
- [ ] 编写风控测试用例

**交付物**：完整的风控体系，信号包含风险提示

### Day 11 (周四)：定时任务与自动化
- [ ] 实现 `src/scheduler/daily_job.py`
- [ ] 配置APScheduler每日15:30执行：
  1. 获取当日收盘数据
  2. 计算技术指标
  3. 生成交易信号
  4. 输出报告
- [ ] 实现 `src/output/reporter.py` - 控制台报告输出
- [ ] 实现 `src/output/logger.py` - 日志记录
- [ ] 测试定时任务流程

**交付物**：系统可自动每日运行并输出报告

### Day 12 (周五)：MVP整合与测试
- [ ] 编写 `main.py` - 主入口
- [ ] 整合所有模块：数据→分析→策略→输出
- [ ] 端到端测试：模拟完整交易日流程
- [ ] 处理边界情况（停牌、数据缺失、首次运行）
- [ ] 性能测试：确保处理50只ETF在1分钟内完成
- [ ] 编写用户使用文档

**交付物**：可独立运行的MVP版本

### Day 13-14 (周末)：文档与交付
- [ ] 完善README.md
- [ ] 编写部署文档
- [ ] 补充架构说明
- [ ] 预留扩展接口文档（多市场、LLM）
- [ ] 最终代码Review
- [ ] 创建Git仓库并提交

**交付物**：完整的MVP，可直接使用

---

## 风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| AKShare数据不稳定 | 高 | ✅ 已实现混合数据源（BaoStock + AkShare），降低单一数据源风险 |
| 单一数据源被封 | 高 | ✅ 已实现限速装饰器（@rate_limit）+ 重试机制（@retry_on_error） |
| 停牌日数据缺失 | 中 | ✅ 已实现停牌日/周末填充逻辑，确保日期连续 |
| IOPV历史数据缺失 | 中 | 用跟踪指数涨跌幅估算；标记数据来源 |
| 计算性能不足 | 低 | pandas向量化计算；必要时用numpy加速 |
| 数据量大慢 | 低 | 分批处理；数据库索引优化 |

---

## MVP成功标准

- [ ] 数据库包含完整的6张表结构（etfs, etf_quotes, etf_indicators, strategies, signals, signal_performance）
- [ ] 包含至少10只ETF的2年历史数据
- [ ] 每日自动获取收盘数据（OHLCV、IOPV、溢价率、换手率、成交金额）
- [ ] 自动计算完整技术指标（MA、MACD、RSI、布林带、ADX、ATR、成交量指标）
- [ ] 生成右侧交易信号（含建议入场价、止损、目标、仓位、置信度）
- [ ] 自动追踪信号表现（收益、目标达成、最大回撤）
- [ ] 溢价率风控正常工作
- [ ] 输出可读的交易建议报告
- [ ] 完整记录运行日志

---

## 后续迭代方向（非MVP）

- Week 3-4: 回测系统、多市场支持（美股、港股）
- Week 5-6: LLM增强分析报告
- Week 7-8: Web界面、通知推送
