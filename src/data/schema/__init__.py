"""数据库 Schema 模块.

提供 SQLAlchemy ORM 模型，对应数据库表结构。

所有模型均继承自 src.data.schema.base.Base。

Example:
    >>> from src.data.schema import ETF, Signal
    >>> from src.data.database import db_session
    >>>
    >>> with db_session() as db:
    ...     etf = db.get(ETF, "510300")
    ...     signals = db.query(Signal).filter_by(etf_code="510300").all()

Tables:
    - etfs: ETF基础信息
    - etf_quotes: ETF价格数据
    - etf_indicators: 技术指标
    - strategies: 策略配置
    - signals: 交易信号
    - signal_performance: 信号性能追踪
"""

from src.data.schema.base import Base
from src.data.schema.etf import ETF
from src.data.schema.quote import ETFQuote
from src.data.schema.indicator import ETFIndicator
from src.data.schema.strategy import Strategy
from src.data.schema.signal import Signal
from src.data.schema.performance import SignalPerformance

__all__ = [
    "Base",
    "ETF",
    "ETFQuote",
    "ETFIndicator",
    "Strategy",
    "Signal",
    "SignalPerformance",
]