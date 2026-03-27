# ETF Quant Advisor

> 面向A股的ETF右侧量化交易助手，每日开盘前基于 T-1 日收盘数据生成 T 日交易建议。

## 技术栈

- **Python**: 3.13.12
- **数据库**: PostgreSQL 16
- **数据源**: BaoStock (行情) + AKShare (净值)

## 项目结构

```
etf_quant_advisor/
├── src/
│   ├── core/                # 核心流程编排
│   ├── data/                # 数据层（模型、仓库、服务、数据源）
│   ├── analysis/            # 技术指标计算
│   ├── strategy/            # 交易策略
│   └── output/              # 报告输出
├── config/                  # 配置文件
├── migrations/              # 数据库迁移
├── scripts/                 # 脚本工具
└── main.py                  # 主入口
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/your-repo/etf-quant-advisor.git
cd etf-quant-advisor

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库连接信息
```

### 2. 数据库初始化

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE etf_quant;"

# 运行迁移脚本
psql -U postgres -d etf_quant -f migrations/001_initial_schema.sql
psql -U postgres -d etf_quant -f migrations/002_add_trade_status.sql
```

### 3. 数据初始化

```bash
# 完整初始化（ETF信息 + 历史数据 + 指标）
python scripts/init_data.py

# 指定日期范围
python scripts/init_data.py --start 2024-01-01 --end 2026-03-27
```

### 4. 每日运行

```bash
# 立即执行（生成 T-1 日信号）
python main.py --run-now

# 强制执行（忽略时间检查）
python main.py --run-now --force

# 指定日期
python main.py --run-now --date 2026-03-26
```

## 外部调度

使用 Windows Task Scheduler 或 cron 定时调用：

```
# Windows Task Scheduler
程序: python
参数: D:\projects\etf_quant_advisor\main.py --run-now
触发器: 每日 08:00

# Cron (Linux)
0 8 * * * cd /path/to/etf_quant_advisor && python main.py --run-now
```

## 右侧交易策略

### 核心思想

右侧交易（Trend Following）放弃抄底逃顶，等待趋势确认后跟进。

### 买入条件

| 条件 | 说明 |
|------|------|
| ADX > 25 | 趋势强度足够 |
| +DI > -DI | 上升趋势 |
| MA5 > MA10 > MA20 | 均线多头排列 |
| MACD 金叉 | DIF 上穿 DEA |
| 量比 > 1.2 | 放量确认 |
| RSI < 70 | 非超买 |
| 溢价率 < 3% | ETF 风控 |

### 卖出条件

- 跌破 MA20 且 MA20 走平/向下
- MACD 死叉
- 止损：亏损 > 8%
- 移动止盈：从最高点回撤 > 5%

### 溢价率风控

| 溢价率 | 操作 |
|--------|------|
| > 10% | 禁止买入 |
| 5% - 10% | 警示 |
| -2% - 2% | 最佳区间 |
| < -2% | 可能有机会 |

## 报告输出

报告保存至 `reports/daily_report_YYYY-MM-DD.md`

```
# ETF 量化交易信号日报

**信号日期**: 2026-03-26

## 买入信号 (0)
无

## 持有信号 (5)
| ETF代码 | 收盘价 | 备注 |
|---------|--------|------|
| 510300 | 3.912 | MA趋势向上 |
```

## 配置说明

编辑 `config/settings.yaml` 添加监控的 ETF：

```yaml
watchlist:
  - code: "510300"
  - code: "512000"
  - code: "513100"
```

## 免责声明

本项目仅供**技术研究和个人学习**使用，不构成投资建议。

- 量化交易存在风险，历史表现不代表未来收益
- 使用前请充分回测，并根据个人风险承受能力调整参数

**投资有风险，入市需谨慎。**